from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from app import deps, thumbnails, ytdlp

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="多平台视频本地下载器", version="1.2.0")


class AnalyzeRequest(BaseModel):
    url: str
    browser: str = "chrome"
    quality: str = Field(default="720", pattern="^(480|720|1080|best)$")


class DownloadRequest(BaseModel):
    urls: list[str] | None = None
    url: str | None = None
    quality: str = Field(default="720", pattern="^(480|720|1080|best)$")
    browser: str = "chrome"
    folder_name: str | None = None

    @model_validator(mode="after")
    def normalize_urls(self) -> "DownloadRequest":
        collected: list[str] = []
        if self.urls:
            collected.extend(self.urls)
        if self.url:
            collected.append(self.url)
        self.urls = collected
        return self


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/requirements")
def requirements() -> dict:
    return deps.check_requirements()


def _ensure_ready() -> None:
    if not deps.check_requirements()["ready"]:
        raise HTTPException(status_code=503, detail=deps.format_missing_message())


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    _ensure_ready()
    try:
        return ytdlp.analyze(req.url, req.browser, req.quality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


def _run_job(job_id: str) -> None:
    job = ytdlp.JOBS.get(job_id)
    if not job:
        return
    ytdlp.execute_download(job)


@app.post("/api/download")
async def download(req: DownloadRequest, background: BackgroundTasks) -> dict:
    if not req.urls:
        raise HTTPException(status_code=400, detail="请至少选择一个视频")
    _ensure_ready()
    try:
        job = ytdlp.start_download(
            req.urls,
            req.quality,
            req.browser,
            req.folder_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    background.add_task(_run_job, job.job_id)
    await asyncio.sleep(0)
    return {
        "job_id": job.job_id,
        "total": job.total,
        "folder_name": job.folder_name,
        "output_dir": str(job.output_dir) if job.output_dir else None,
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = ytdlp.JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ytdlp.job_to_dict(job)


@app.get("/api/thumbnail")
def proxy_thumbnail(url: str):
    try:
        body, media_type = thumbnails.fetch_thumbnail(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return Response(content=body, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/jobs/{job_id}/file")
def get_file(job_id: str, index: int = 0):
    job = ytdlp.JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not job.output_files:
        raise HTTPException(status_code=409, detail="文件尚未就绪")
    if index < 0 or index >= len(job.output_files):
        raise HTTPException(status_code=404, detail="文件索引无效")
    target = job.output_files[index]
    if job.status != "done" and not target.exists():
        raise HTTPException(status_code=409, detail="文件尚未就绪")
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        target,
        media_type="video/mp4",
        filename=target.name,
    )


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")