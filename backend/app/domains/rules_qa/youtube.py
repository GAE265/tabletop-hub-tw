"""從 YouTube 網址取出影片 ID（spec rules-qa「設定教學影片」）。不新增套件，用標準函式庫解析。"""

import re
from urllib.parse import parse_qs, urlsplit

# YouTube 影片 ID：英數、-、_（例如 XE-Sw_FtFFs）
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}


def parse_youtube_id(url: str) -> str | None:
    """支援 youtube.com/watch?v=、youtu.be/、youtube.com/embed/、youtube.com/shorts/；
    其他網址或取不到 ID 時回傳 None。"""
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        return None
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]

    candidate: str | None = None
    if host == "youtu.be":
        candidate = segments[0] if segments else None
    elif host in _YOUTUBE_HOSTS:
        if segments == ["watch"]:
            candidate = parse_qs(parts.query).get("v", [None])[0]
        elif len(segments) >= 2 and segments[0] in {"embed", "shorts"}:
            candidate = segments[1]
    if candidate and _VIDEO_ID.match(candidate):
        return candidate
    return None
