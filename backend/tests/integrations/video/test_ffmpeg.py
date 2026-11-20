"""ffmpeg 呼叫（spec media-integrations「ffmpeg 呼叫」，MR 3）。

用手寫的假 ffmpeg 指令稿（python），不需要安裝 ffmpeg。
"""

from pathlib import Path

import pytest

from app.integrations.video import (
    DEFAULT_STYLE,
    FontSet,
    Renderer,
    VideoRenderError,
    build_timeline,
    layout_video,
    load_video,
)
from app.integrations.video.encode import FfmpegSegmentEncoder
from app.integrations.video.ffmpeg import Ffmpeg
from tests.integrations.video.support import base_data, fake_ffmpeg, write_game


def test_missing_ffmpeg(tmp_path: Path) -> None:
    ffmpeg = Ffmpeg([str(tmp_path / "no-such-ffmpeg.exe")])
    with pytest.raises(VideoRenderError) as exc:
        ffmpeg.check()
    message = str(exc.value)
    assert "ffmpeg" in message and "FFMPEG_PATH" in message


def test_encoder_failure_leaves_no_files(tmp_path: Path) -> None:
    video = load_video(write_game(tmp_path / "game", base_data()))
    fonts = FontSet(None, None)
    timeline = build_timeline(video, lambda beat: 3.0, DEFAULT_STYLE)
    renderer = Renderer(
        video, timeline, layout_video(video, fonts, DEFAULT_STYLE), fonts, DEFAULT_STYLE
    )
    encoder = FfmpegSegmentEncoder(Ffmpeg(fake_ffmpeg(tmp_path / "bin", fail=True)), DEFAULT_STYLE)
    target = tmp_path / "out" / "s1.mp4"
    target.parent.mkdir()
    with pytest.raises(VideoRenderError) as exc:
        encoder.encode(timeline.segments[0], renderer, target)
    # 訊息含 ffmpeg 輸出的最後幾行
    assert "fake encoder exploded" in str(exc.value)
    assert list(target.parent.iterdir()) == []
