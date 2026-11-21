"""程式合成的背景音樂（spec rules-video-maker「完整影片輸出」的背景音樂長度，MR 3）。"""

import numpy as np
import pytest

from app.integrations.video.bgm import PEAK, SAMPLE_RATE, synthesize_bgm


@pytest.mark.parametrize("seconds", [6.0, 31.25])
def test_length_rate_and_channels(seconds: float) -> None:
    audio = synthesize_bgm(seconds, chapter_starts=(0.0,))
    assert SAMPLE_RATE == 48000
    assert audio.shape == (round(seconds * SAMPLE_RATE), 2)
    assert audio.dtype == np.float32


def test_reproducible() -> None:
    first = synthesize_bgm(8.0, chapter_starts=(0.0,))
    second = synthesize_bgm(8.0, chapter_starts=(0.0,))
    assert np.array_equal(first, second)


def test_no_clipping() -> None:
    audio = synthesize_bgm(12.0, chapter_starts=(0.0, 6.0))
    assert float(np.max(np.abs(audio))) <= PEAK + 1e-6
    assert float(np.max(np.abs(audio))) > 0.1  # 不是一片靜音


def test_fade_in_and_out() -> None:
    audio = synthesize_bgm(12.0, chapter_starts=(0.0,))
    edge = SAMPLE_RATE // 100  # 10 毫秒
    assert float(np.max(np.abs(audio[:edge]))) < 0.01
    assert float(np.max(np.abs(audio[-edge:]))) < 0.01
