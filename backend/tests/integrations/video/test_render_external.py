"""實際用 ffmpeg 輸出整章影片（spec rules-video-maker「完整影片輸出」，AGENTS.md 7.6 external）。

需要本機安裝 ffmpeg 與 ffprobe（從 PATH 找），
只在本機用 `uv run pytest -m external` 執行；找不到時直接失敗並說明，不自動跳過。
旁白用 FakeTTSProvider（靜音），不需要金鑰。
"""

import csv
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from app.integrations.tts import FakeTTSProvider
from app.integrations.video import DEFAULT_STYLE, FontSet, load_video
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.pipeline import render_video
from tests.integrations.video.support import base_data, write_game

pytestmark = pytest.mark.external


@pytest.fixture
def ffmpeg_tools() -> tuple[str, str]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.fail(
            "找不到 ffmpeg 或 ffprobe：請安裝 ffmpeg 並加入 PATH（Windows：winget install ffmpeg）"
        )
    return ffmpeg, ffprobe


def test_render_whole_chapter(tmp_path: Path, ffmpeg_tools: tuple[str, str]) -> None:
    ffmpeg, ffprobe = ffmpeg_tools
    data = base_data()
    # 片尾加標題字卡（沒有旁白），確認音軌仍然和畫面一樣長（#75 審核）
    data["segments"].append({"segment_key": "end", "chapter_key": "c1", "template": "title_card"})
    video = load_video(write_game(tmp_path / "game", data))
    result = render_video(
        video,
        tmp_path / "game" / "out",
        FontSet(None, None),
        DEFAULT_STYLE,
        FakeTTSProvider(),
        Ffmpeg([ffmpeg]),
        cache_dir=tmp_path / "game" / "cache",
    )
    probe = json.loads(
        subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(result.video),
            ],
            capture_output=True,
            check=True,
        ).stdout
    )
    video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert (video_stream["width"], video_stream["height"]) == (1920, 1080)
    assert video_stream["r_frame_rate"] == "30/1"
    assert audio_stream["codec_name"] == "aac"

    with result.timing_csv.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert abs(float(probe["format"]["duration"]) - result.total_seconds) < 0.1
    # 音軌與畫面一樣長（旁白結束後，背景音樂要一直播到片尾）
    assert abs(float(audio_stream["duration"]) - float(video_stream["duration"])) < 0.05


# --- 第 2 階段 MR 1：進度條最後才疊上去 ---


def _frame_rgb(ffmpeg: str, path: Path, t: float) -> np.ndarray:
    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(raw, np.uint8).reshape(DEFAULT_STYLE.height, DEFAULT_STYLE.width, 3)


def test_progress_bar_fill_and_quality(tmp_path: Path, ffmpeg_tools: tuple[str, str]) -> None:
    from app.integrations.video.render import progress_box

    ffmpeg, _ = ffmpeg_tools
    video = load_video(write_game(tmp_path / "game", base_data()))
    result = render_video(
        video,
        tmp_path / "game" / "out",
        FontSet(None, None),
        DEFAULT_STYLE,
        FakeTTSProvider(),
        Ffmpeg([ffmpeg]),
        cache_dir=tmp_path / "game" / "cache",
    )
    x, y, w, h = progress_box(DEFAULT_STYLE)
    gold = np.array(DEFAULT_STYLE.gold)
    for fraction in (0.25, 0.5, 0.75):
        t = result.total_seconds * fraction
        row = _frame_rgb(ffmpeg, result.video, t)[y + h // 2, x : x + w].astype(int)
        filled = float((np.abs(row - gold) <= 40).all(axis=-1).mean())
        # 第 t 秒的填滿比例約為 t ÷ 總長（誤差 2% 以內）
        assert abs(filled - fraction) < 0.02, (fraction, filled)

    # 二次編碼的畫質：疊加前（串接好的段影片）與成品比 SSIM，不含進度條那一條
    crop = f"crop={DEFAULT_STYLE.width}:{y - 12}:0:0"
    measured = subprocess.run(
        [ffmpeg, "-v", "info", "-i", str(result.joined), "-i", str(result.video),
         "-lavfi", f"[0:v]{crop}[a];[1:v]{crop}[b];[a][b]ssim", "-f", "null", "-"],
        capture_output=True,
        check=True,
    ).stderr.decode("utf-8", errors="replace")  # fmt: skip
    ssim = float(re.findall(r"All:([0-9.]+)", measured)[-1])
    print(f"SSIM（疊加前 vs 成品，不含進度條）：{ssim:.5f}")
    assert ssim >= 0.98
