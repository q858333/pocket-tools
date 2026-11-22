from __future__ import annotations

import re
from typing import Literal

Platform = Literal["bilibili", "youtube", "douyin", "twitter", "unknown"]

PLATFORM_RULES: tuple[tuple[Platform, re.Pattern[str], str], ...] = (
    (
        "bilibili",
        re.compile(r"(https?://)?(www\.)?(bilibili\.com|b23\.tv|m\.bilibili\.com)/", re.I),
        "B 站",
    ),
    (
        "youtube",
        re.compile(
            r"(https?://)?((www|m)\.)?(youtube\.com|youtu\.be)/",
            re.I,
        ),
        "YouTube",
    ),
    (
        "douyin",
        re.compile(
            r"(https?://)?(www\.)?(douyin\.com|v\.douyin\.com|iesdouyin\.com)/",
            re.I,
        ),
        "抖音",
    ),
    (
        "twitter",
        re.compile(
            r"(https?://)?(www\.)?(twitter\.com|x\.com|mobile\.twitter\.com)/",
            re.I,
        ),
        "X (Twitter)",
    ),
)

PLATFORM_HINTS: dict[Platform, str] = {
    "bilibili": "B 站建议登录账号；会员/高清内容需对应权限。",
    "youtube": "多数公开视频可直接下载；年龄限制或会员内容可能需浏览器登录。",
    "douyin": "多数链接需用所选浏览器登录 douyin.com 后再下载。",
    "twitter": "X 多为登录后可见，请在浏览器登录 x.com 后再试。",
    "unknown": "请确认链接有效；部分站点需登录后才能下载。",
}


def detect_platform(url: str) -> Platform:
    text = url.strip()
    for platform, pattern, _label in PLATFORM_RULES:
        if pattern.search(text):
            return platform
    return "unknown"


def platform_label(platform: Platform) -> str:
    for pid, _pattern, label in PLATFORM_RULES:
        if pid == platform:
            return label
    return "其它站点"


def is_supported_url(url: str) -> bool:
    return detect_platform(url) != "unknown"


def supported_sites_text() -> str:
    return "、".join(label for _p, _r, label in PLATFORM_RULES)