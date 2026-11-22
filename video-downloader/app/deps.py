from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DepSpec:
    id: str
    name: str
    command: str
    version_args: list[str]
    install_mac: str
    install_note: str
    required: bool = True


DEPS: tuple[DepSpec, ...] = (
    DepSpec(
        id="yt-dlp",
        name="yt-dlp",
        command="yt-dlp",
        version_args=["--version"],
        install_mac="brew install yt-dlp",
        install_note="或用 pip：pip install -U yt-dlp",
    ),
    DepSpec(
        id="ffmpeg",
        name="ffmpeg",
        command="ffmpeg",
        version_args=["-version"],
        install_mac="brew install ffmpeg",
        install_note="用于合并 B 站分离的音视频轨",
    ),
)


def _first_line(text: str) -> str:
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line[:120]


def check_one(spec: DepSpec) -> dict[str, Any]:
    path = shutil.which(spec.command)
    if not path:
        return {
            "id": spec.id,
            "name": spec.name,
            "installed": False,
            "path": None,
            "version": None,
            "install_mac": spec.install_mac,
            "install_note": spec.install_note,
            "required": spec.required,
        }

    version = None
    try:
        proc = subprocess.run(
            [path, *spec.version_args],
            capture_output=True,
            text=True,
            timeout=8,
        )
        out = proc.stdout or proc.stderr or ""
        version = _first_line(out)
    except (OSError, subprocess.TimeoutExpired):
        version = "已安装"

    return {
        "id": spec.id,
        "name": spec.name,
        "installed": True,
        "path": path,
        "version": version,
        "install_mac": spec.install_mac,
        "install_note": spec.install_note,
        "required": spec.required,
    }


def check_requirements() -> dict[str, Any]:
    items = [check_one(spec) for spec in DEPS]
    missing = [i for i in items if i["required"] and not i["installed"]]
    return {
        "ready": len(missing) == 0,
        "missing_count": len(missing),
        "items": items,
        "hints": {
            "browser_login": (
                "支持 B 站、YouTube、抖音、X (Twitter)。"
                "抖音/X 等通常需在所选浏览器中登录对应网站；"
                "首次下载若弹出「访问浏览器数据」，需点允许。"
            ),
            "start_server": (
                "在项目目录执行：cd ~/Projects/pocket-tools/video-downloader && ./run.sh"
            ),
            "homebrew": "若未安装 Homebrew，可先安装：https://brew.sh",
        },
    }


def format_missing_message() -> str:
    data = check_requirements()
    if data["ready"]:
        return ""
    lines = ["本机缺少以下依赖，请先安装："]
    for item in data["items"]:
        if item["required"] and not item["installed"]:
            lines.append(f"• {item['name']}：{item['install_mac']}（{item['install_note']}）")
    return "\n".join(lines)