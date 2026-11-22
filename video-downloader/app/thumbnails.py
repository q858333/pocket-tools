from __future__ import annotations

import re
import urllib.error
import urllib.request

THUMB_URL = re.compile(
    r"^https://"
    r"([a-z0-9.-]+\.)?"
    r"(hdslb\.com|hdslb\.net|ytimg\.com|ggpht\.com|"
    r"douyinpic\.com|byteimg\.com|twimg\.com|pbs\.twimg\.com)/",
    re.I,
)


def fetch_thumbnail(url: str) -> tuple[bytes, str]:
    target = url.strip()
    if not THUMB_URL.match(target):
        raise ValueError("不支持的封面地址")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    if "hdslb.com" in target or "hdslb.net" in target:
        headers["Referer"] = "https://www.bilibili.com/"

    req = urllib.request.Request(target, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return body, ctype
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"封面返回 HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError("封面网络请求失败") from e