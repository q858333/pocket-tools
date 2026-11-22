from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.platforms import (
    PLATFORM_HINTS,
    detect_platform,
    is_supported_url,
    platform_label,
)

DEFAULT_OUTPUT = Path.home() / "Downloads" / "video-web"
JOBS: dict[str, "DownloadJob"] = {}


def _clean_env() -> dict[str, str]:
    import os

    env = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "SOCKS_PROXY",
        "SOCKS5_PROXY",
    ):
        env.pop(key, None)
    return env


def quality_format(quality: str) -> str:
    q = quality.lower()
    if q == "1080":
        return "bv[height<=1080]+ba/bv*[height<=1080]+ba/b"
    if q == "720":
        return "bv[height<=720][vcodec^=av01]+ba[acodec^=mp4a]/bv[height<=720]+ba/b"
    if q == "480":
        return "bv[height<=480]+ba/b"
    return "bv*+ba/b"


def _run_ytdlp(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=_clean_env(),
    )


def run_ytdlp_json(url: str, browser: str) -> dict[str, Any]:
    args = [
        "yt-dlp",
        "--no-update",
        "--cookies-from-browser",
        browser,
        "--dump-single-json",
        "--no-download",
        url,
    ]
    proc = _run_ytdlp(args)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "yt-dlp 失败").strip()
        raise RuntimeError(err[-800:])
    return json.loads(proc.stdout)


def run_ytdlp_json_lines(url: str, browser: str, flat: bool) -> list[dict[str, Any]]:
    args = [
        "yt-dlp",
        "--no-update",
        "--cookies-from-browser",
        browser,
        "--dump-json",
        "--no-download",
    ]
    if flat:
        args.append("--flat-playlist")
    args.append(url)
    proc = _run_ytdlp(args)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "yt-dlp 失败").strip()
        raise RuntimeError(err[-800:])
    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _entry_url(entry: dict[str, Any]) -> str | None:
    for key in ("webpage_url", "url", "original_url"):
        v = entry.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    eid = entry.get("id")
    if eid is not None:
        eid_s = str(eid)
        if entry.get("season_id") or entry.get("series_id"):
            return f"https://www.bilibili.com/bangumi/play/ep{eid_s}"
        if eid_s.startswith("BV") or eid_s.startswith("bv"):
            return f"https://www.bilibili.com/video/{eid_s}"
    return None


_SIZE_UNITS = {"KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}


def _size_from_json(data: dict[str, Any]) -> int | None:
    for key in ("filesize", "filesize_approx"):
        val = data.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    req = data.get("requested_formats")
    if isinstance(req, list) and req:
        total = 0
        found = False
        for fmt in req:
            if not fmt:
                continue
            val = fmt.get("filesize") or fmt.get("filesize_approx")
            if isinstance(val, (int, float)) and val > 0:
                total += int(val)
                found = True
        if found:
            return total
    return None


def probe_download_size(url: str, browser: str, quality: str) -> int | None:
    args = [
        "yt-dlp",
        "--no-update",
        "--cookies-from-browser",
        browser,
        "-f",
        quality_format(quality),
        "--dump-single-json",
        "--no-download",
        url,
    ]
    proc = _run_ytdlp(args)
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return _size_from_json(data)


def sanitize_folder_name(name: str) -> str:
    text = (name or "").strip() or "未命名视频"
    text = re.sub(r'[\\/:*?"<>|\r\n]+', "_", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" ._")
    return text[:100] or "未命名视频"


def resolve_folder_name(collection_title: str, items: list[dict[str, Any]]) -> str:
    if len(items) > 1:
        base = collection_title
    else:
        base = items[0].get("title") or collection_title
    return sanitize_folder_name(base)


def _normalize_title(title: str | None, index: int, entry_id: str) -> str:
    if title and title.strip() and title.upper() != "NA":
        return title.strip()
    return f"第 {index} 集 · {entry_id}"


def _item_from_entry(entry: dict[str, Any], index: int) -> dict[str, Any] | None:
    url = _entry_url(entry)
    if not url:
        return None
    eid = str(entry.get("id") or index)
    thumbs = entry.get("thumbnails") or []
    thumb = entry.get("thumbnail") or (thumbs[-1].get("url") if thumbs else None)
    size = _size_from_json(entry)
    return {
        "id": eid,
        "index": entry.get("playlist_index") or index,
        "title": _normalize_title(entry.get("title") or entry.get("fulltitle"), index, eid),
        "duration": entry.get("duration"),
        "url": url,
        "thumbnail": thumb,
        "filesize_bytes": size,
    }


def _collect_items(url: str, browser: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {}
    try:
        data = run_ytdlp_json(url, browser)
        meta = data
        entries = data.get("entries")
        if entries:
            items: list[dict[str, Any]] = []
            for i, entry in enumerate(entries, start=1):
                if not entry:
                    continue
                item = _item_from_entry(entry, i)
                if item:
                    items.append(item)
            if items:
                return items, meta
    except RuntimeError:
        pass

    flat_rows = run_ytdlp_json_lines(url, browser, flat=True)
    if len(flat_rows) > 1:
        items = []
        for i, row in enumerate(flat_rows, start=1):
            item = _item_from_entry(row, i)
            if item:
                items.append(item)
        if not meta:
            try:
                meta = run_ytdlp_json(url, browser)
            except RuntimeError:
                meta = {"title": url}
        return items, meta

    if len(flat_rows) == 1:
        row = flat_rows[0]
        if row.get("_type") in (None, "video", "url"):
            item = _item_from_entry(row, 1)
            if item:
                return [item], row

    data = run_ytdlp_json(url, browser)
    item = _item_from_entry(data, 1)
    if not item:
        item = {
            "id": str(data.get("id") or "1"),
            "index": 1,
            "title": data.get("title") or data.get("fulltitle") or "未知标题",
            "duration": data.get("duration"),
            "url": data.get("webpage_url") or url,
            "thumbnail": data.get("thumbnail"),
            "filesize_bytes": _size_from_json(data),
        }
    return [item], data


def _attach_sizes(items: list[dict[str, Any]], browser: str, quality: str) -> None:
    for item in items:
        if item.get("filesize_bytes"):
            continue
        size = probe_download_size(item["url"], browser, quality)
        item["filesize_bytes"] = size


def analyze(url: str, browser: str = "chrome", quality: str = "720") -> dict[str, Any]:
    if not is_supported_url(url):
        raise ValueError("暂不支持该链接，请使用 B 站 / YouTube / 抖音 / X (Twitter)")

    platform = detect_platform(url)

    items, meta = _collect_items(url, browser)
    if not items:
        raise RuntimeError("未能解析到可下载的视频")

    if len(items) <= 30:
        _attach_sizes(items, browser, quality)

    total_bytes = sum(i.get("filesize_bytes") or 0 for i in items)

    thumbnails = meta.get("thumbnails") or []
    thumb = meta.get("thumbnail") or (thumbnails[-1].get("url") if thumbnails else None)
    if not thumb and items:
        thumb = items[0].get("thumbnail")

    playlist_title = (
        meta.get("title")
        or meta.get("fulltitle")
        or meta.get("playlist_title")
        or items[0]["title"]
    )

    return {
        "title": playlist_title,
        "duration": meta.get("duration"),
        "uploader": meta.get("uploader") or meta.get("channel"),
        "thumbnail": thumb,
        "webpage_url": meta.get("webpage_url") or meta.get("original_url") or url,
        "is_playlist": len(items) > 1,
        "entry_count": len(items),
        "quality": quality,
        "total_filesize_bytes": total_bytes or None,
        "platform": platform,
        "platform_label": platform_label(platform),
        "platform_hint": PLATFORM_HINTS[platform],
        "folder_name": resolve_folder_name(playlist_title, items),
        "items": items,
    }


@dataclass
class DownloadJob:
    job_id: str
    urls: list[str]
    quality: str
    browser: str
    status: str = "pending"
    progress: str = ""
    speed: str = ""
    eta: str = ""
    title: str = ""
    output_file: Path | None = None
    output_files: list[Path] = field(default_factory=list)
    error: str = ""
    log_lines: list[str] = field(default_factory=list)
    current_index: int = 0
    total: int = 0
    current_title: str = ""
    current_total_bytes: int | None = None
    current_total_label: str = ""
    folder_name: str = ""
    output_dir: Path | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def start_download(
    urls: list[str],
    quality: str,
    browser: str = "chrome",
    folder_name: str | None = None,
) -> DownloadJob:
    cleaned = [u.strip() for u in urls if u.strip()]
    if not cleaned:
        raise ValueError("请至少选择一个视频")
    for u in cleaned:
        if not is_supported_url(u):
            raise ValueError(f"不支持的链接: {u}")

    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)

    multi = len(cleaned) > 1
    safe_folder = ""
    output_dir = DEFAULT_OUTPUT

    if multi:
        safe_folder = sanitize_folder_name(folder_name or "")
        if not safe_folder or safe_folder == "未命名视频":
            try:
                info = run_ytdlp_json(cleaned[0], browser)
                safe_folder = sanitize_folder_name(
                    info.get("title") or info.get("fulltitle") or "未命名视频"
                )
            except RuntimeError:
                safe_folder = "未命名视频"
        output_dir = DEFAULT_OUTPUT / safe_folder
        output_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex[:12]
    job = DownloadJob(
        job_id=job_id,
        urls=cleaned,
        quality=quality,
        browser=browser,
        total=len(cleaned),
        folder_name=safe_folder,
        output_dir=output_dir,
        title=safe_folder or (cleaned[0] if cleaned else ""),
    )
    JOBS[job_id] = job
    return job


def _parse_size_token(token: str) -> int | None:
    m = re.match(r"([\d.]+)\s*(KiB|MiB|GiB)", token, re.I)
    if not m:
        return None
    unit = m.group(2)
    unit_key = unit[0].upper() + unit[1:].lower()
    mul = _SIZE_UNITS.get(unit_key, 0)
    return int(float(m.group(1)) * mul) if mul else None


def _parse_progress_line(line: str) -> tuple[str, str, str, int | None] | None:
    m = re.search(
        r"\[download\]\s+(\S+)\s+of\s+(\S+)\s+at\s+(\S+)\s+ETA\s+(\S+)",
        line,
    )
    if m:
        total = _parse_size_token(m.group(2))
        return m.group(1), m.group(3), m.group(4), total
    return None


def _download_one(job: DownloadJob, url: str) -> Path | None:
    out_dir = job.output_dir or DEFAULT_OUTPUT
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(out_dir / "%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-update",
        "--cookies-from-browser",
        job.browser,
        "-f",
        quality_format(job.quality),
        "--merge-output-format",
        "mp4",
        "--concurrent-fragments",
        "8",
        "--newline",
        "-o",
        out_tmpl,
        url,
    ]

    info = run_ytdlp_json(url, job.browser)
    job.current_title = info.get("title") or info.get("fulltitle") or url
    job.title = job.current_title
    size = probe_download_size(url, job.browser, job.quality)
    job.current_total_bytes = size
    job.current_total_label = ""

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=_clean_env(),
        bufsize=1,
    )
    assert proc.stdout is not None
    output_lines: list[str] = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            job.log_lines.append(line)
            if len(job.log_lines) > 300:
                job.log_lines.pop(0)
            output_lines.append(line)
            parsed = _parse_progress_line(line)
            if parsed:
                job.progress, job.speed, job.eta, total = parsed
                if total:
                    job.current_total_bytes = total
            if line.startswith("[Merger]") or "Merging formats into" in line:
                job.status = "merging"

    code = proc.wait()
    if code != 0:
        raise RuntimeError("\n".join(output_lines[-15:]) or f"yt-dlp 退出码 {code}")

    output_file: Path | None = None
    for line in reversed(output_lines):
        m = re.search(r'Merging formats into "(.+)"', line)
        if m:
            output_file = Path(m.group(1))
            break
        if "has already been downloaded" in line:
            m2 = re.search(r'\[download\] (.+?) has already been downloaded', line)
            if m2:
                output_file = Path(m2.group(1))

    if not output_file or not output_file.exists():
        candidates = sorted(
            out_dir.glob("*.mp4"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            output_file = candidates[0]
    return output_file


def execute_download(job: DownloadJob) -> None:
    job.status = "downloading"
    job.output_files = []
    try:
        for i, url in enumerate(job.urls, start=1):
            job.current_index = i
            job.progress = ""
            job.speed = ""
            job.eta = ""
            job.status = "downloading"
            outfile = _download_one(job, url)
            if outfile and outfile.exists():
                job.output_files.append(outfile)
                job.output_file = outfile
            job.progress = "100%"

        if not job.output_files:
            job.status = "error"
            job.error = "未找到已下载的文件"
            return
        job.status = "done"
        job.progress = "100%"
    except Exception as e:  # noqa: BLE001
        job.status = "error"
        job.error = str(e)


def job_to_dict(job: DownloadJob) -> dict[str, Any]:
    outputs = []
    for p in job.output_files:
        if not p.exists():
            continue
        outputs.append(
            {
                "name": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
            }
        )
    return {
        "job_id": job.job_id,
        "status": job.status,
        "title": job.title,
        "current_title": job.current_title,
        "current_index": job.current_index,
        "total": job.total,
        "progress": job.progress,
        "speed": job.speed,
        "eta": job.eta,
        "error": job.error,
        "output_file": str(job.output_file) if job.output_file else None,
        "output_name": job.output_file.name if job.output_file else None,
        "output_files": outputs,
        "folder_name": job.folder_name,
        "output_dir": str(job.output_dir) if job.output_dir else None,
        "current_total_bytes": job.current_total_bytes,
        "log_tail": job.log_lines[-30:],
        "created_at": job.created_at,
    }