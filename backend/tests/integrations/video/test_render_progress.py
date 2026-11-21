"""產生影片的進度回呼與 ffmpeg 逾時（add-rules-video-mobile MR 9，design.md D15）。

用手寫的假 ffmpeg 指令稿（python）與 FakeTTSProvider，不需要安裝 ffmpeg、不需要金鑰。
"""

import sys
import time
from pathlib import Path

import pytest

from app.integrations.tts import FakeTTSProvider
from app.integrations.video import DEFAULT_STYLE, FontSet, VideoRenderError, load_video
from app.integrations.video.encode import pipe_frames
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.pipeline import render_video
from tests.integrations.video.support import base_data, fake_ffmpeg, write_game

SLOW_FFMPEG = """
import time
time.sleep(30)
"""


def slow_ffmpeg(folder: Path) -> list[str]:
    """不讀輸入、睡 30 秒的假 ffmpeg（模擬卡住）。"""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "slow_ffmpeg.py"
    script.write_text(SLOW_FFMPEG, encoding="utf-8")
    return [sys.executable, str(script)]


def _render(tmp_path: Path, command: list[str], progress=None, cache: str = "cache"):
    video = load_video(write_game(tmp_path / "game", base_data()))
    result = render_video(
        video,
        tmp_path / "game" / "out",
        FontSet(None, None),
        DEFAULT_STYLE,
        FakeTTSProvider(),
        Ffmpeg(command),
        cache_dir=tmp_path / "game" / cache,
        on_progress=progress,
    )
    return video, result


class Recorder:
    def __init__(self) -> None:
        self.reports: list[tuple[float, str]] = []

    def __call__(self, progress: float, message: str) -> None:
        self.reports.append((progress, message))

    @property
    def messages(self) -> list[str]:
        return [m for _, m in self.reports]


def test_progress_order_and_counts(tmp_path: Path) -> None:
    recorder = Recorder()
    video, _ = _render(tmp_path, fake_ffmpeg(tmp_path / "bin"), recorder)
    beats = sum(len(s.beats) for s in video.segments)
    segments = len(video.segments)
    messages = recorder.messages
    assert messages[0] == "排版"
    narration = [m for m in messages if m.startswith("旁白")]
    assert narration == [f"旁白 {i}／{beats}" for i in range(1, beats + 1)]
    encoded = [m for m in messages if m.startswith("段影片")]
    assert encoded == [f"段影片 {i}／{segments}" for i in range(1, segments + 1)]
    assert messages[-3:] == ["串接段影片", "疊上進度條", "混音"]
    # 依序：排版 → 旁白 → 段影片 → 串接 → 進度條 → 混音
    assert messages.index(narration[-1]) < messages.index(encoded[0])
    progress = [p for p, _ in recorder.reports]
    assert progress == sorted(progress)
    assert 0 <= progress[0] and progress[-1] <= 1


def test_progress_marks_reused_segments(tmp_path: Path) -> None:
    command = fake_ffmpeg(tmp_path / "bin")
    _render(tmp_path, command)
    recorder = Recorder()
    video, _ = _render(tmp_path, command, recorder)
    segments = len(video.segments)
    encoded = [m for m in recorder.messages if m.startswith("段影片")]
    assert encoded == [f"段影片 {i}／{segments}（沿用）" for i in range(1, segments + 1)]


def test_without_progress_callback_still_works(tmp_path: Path) -> None:
    _, result = _render(tmp_path, fake_ffmpeg(tmp_path / "bin"))
    assert result.video.is_file()


# --- ffmpeg 逾時 ---


def test_run_timeout(tmp_path: Path) -> None:
    ffmpeg = Ffmpeg(slow_ffmpeg(tmp_path / "bin"), timeout_seconds=0.5)
    started = time.monotonic()
    with pytest.raises(VideoRenderError) as exc:
        ffmpeg.run(["-version"], what="測試")
    assert time.monotonic() - started < 10
    assert "超過 0.5 秒" in str(exc.value)


def test_pipe_frames_timeout_leaves_no_file(tmp_path: Path) -> None:
    ffmpeg = Ffmpeg(slow_ffmpeg(tmp_path / "bin"), timeout_seconds=0.5)
    target = tmp_path / "out" / "s1.mp4"
    target.parent.mkdir()
    # 假 ffmpeg 不讀輸入：送很多格會塞住管線，逾時要能結束子程序
    frames = (b"\0" * (1 << 20) for _ in range(200))
    started = time.monotonic()
    with pytest.raises(VideoRenderError) as exc:
        pipe_frames(ffmpeg, [], frames, target, what="編碼段 s1 ")
    assert time.monotonic() - started < 10
    assert "超過 0.5 秒" in str(exc.value)
    assert list(target.parent.iterdir()) == []


def test_no_timeout_by_default(tmp_path: Path) -> None:
    assert Ffmpeg(fake_ffmpeg(tmp_path / "bin")).timeout_seconds is None
