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


# --- #75 審核延後的項目 ---


def test_fake_ffmpeg_counts_all_frame_bytes(tmp_path: Path) -> None:
    # tasks 4.16：假 ffmpeg 改成分塊讀取，收到的位元組數仍要等於全部畫面
    from app.integrations.video.encode import frame_times

    video = load_video(write_game(tmp_path / "game", base_data()))
    fonts = FontSet(None, None)
    timeline = build_timeline(video, lambda beat: 3.0, DEFAULT_STYLE)
    renderer = Renderer(
        video, timeline, layout_video(video, fonts, DEFAULT_STYLE), fonts, DEFAULT_STYLE
    )
    encoder = FfmpegSegmentEncoder(Ffmpeg(fake_ffmpeg(tmp_path / "bin")), DEFAULT_STYLE)
    target = tmp_path / "s1.mp4"
    encoder.encode(timeline.segments[0], renderer, target)
    frames = len(frame_times(timeline.segments[0], DEFAULT_STYLE.fps))
    expected = frames * DEFAULT_STYLE.width * DEFAULT_STYLE.height * 3
    assert target.read_bytes() == f"fake-media {expected}".encode()


@pytest.mark.parametrize(
    "fail_on, leftovers",
    [
        ("concat", ["silent.tmp.mp4", "silent.mp4"]),
        ("-filter_complex", ["fake_game.tmp.mp4", "fake_game.mp4"]),
    ],
    ids=["concat", "mix"],
)
def test_concat_or_mix_failure_leaves_no_temp(
    tmp_path: Path, fail_on: str, leftovers: list[str]
) -> None:
    # tasks 4.17：串接或混音失敗時，不留暫存檔，也不產生成品
    from app.integrations.tts import FakeTTSProvider
    from app.integrations.video.pipeline import render_video

    video = load_video(write_game(tmp_path / "game", base_data()))
    out = tmp_path / "game" / "out"
    with pytest.raises(VideoRenderError):
        render_video(
            video,
            out,
            FontSet(None, None),
            DEFAULT_STYLE,
            FakeTTSProvider(),
            Ffmpeg(fake_ffmpeg(tmp_path / "bin", fail_on=fail_on)),
            cache_dir=tmp_path / "game" / "cache",
        )
    for name in leftovers:
        assert not (out / name).exists(), name
