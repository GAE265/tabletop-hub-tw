"""YouTube 網址解析（spec rules-qa「設定教學影片」）。"""

import pytest

from app.domains.rules_qa.youtube import parse_youtube_id

# 組內《血與刃的白薔薇》教學影片的 ID 含有 - 與 _
VIDEO_ID = "XE-Sw_FtFFs"


@pytest.mark.parametrize(
    "url",
    [
        f"https://youtu.be/{VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}?si=abc123",
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://youtube.com/watch?v={VIDEO_ID}&t=42s",
        f"https://m.youtube.com/watch?feature=share&v={VIDEO_ID}",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"  https://youtu.be/{VIDEO_ID}  ",
    ],
)
def test_supported_formats(url: str) -> None:
    assert parse_youtube_id(url) == VIDEO_ID


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://www.youtube.com/",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=",
        "https://vimeo.com/123456",
        "https://example.com/watch?v=XE-Sw_FtFFs",
        "https://youtu.be/",
        "https://youtu.be/有中文",
        "ftp://youtu.be/XE-Sw_FtFFs",
        "不是網址",
    ],
)
def test_unsupported_urls(url: str) -> None:
    assert parse_youtube_id(url) is None
