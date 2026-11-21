"""文字轉語音的 fake。

spec：openspec/changes/add-rules-video-maker/specs/media-integrations「文字轉語音」。
"""

import io
import wave

import pytest

from app.integrations.tts import AudioClip, FakeTTSProvider


def _wav_info(data: bytes) -> tuple[int, int, int, float]:
    with wave.open(io.BytesIO(data)) as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        return rate, wav.getsampwidth(), wav.getnchannels(), frames / rate


def test_fake_returns_silent_wav_with_predictable_length() -> None:
    clip = FakeTTSProvider().synthesize("一二三四五六七八九十一二")
    assert isinstance(clip, AudioClip)
    assert clip.seconds == pytest.approx(3.0)
    rate, width, channels, seconds = _wav_info(clip.data)
    assert (rate, width, channels) == (48000, 2, 1)
    assert seconds == pytest.approx(3.0, abs=0.001)
    # 靜音：每個樣本都是 0
    assert set(clip.data[44:]) == {0}


def test_fake_minimum_one_second() -> None:
    clip = FakeTTSProvider().synthesize("短句")
    assert clip.seconds == pytest.approx(1.0)


def test_fake_records_calls() -> None:
    fake = FakeTTSProvider()
    fake.synthesize("第一句", voice="zh-TW-HsiaoChenNeural")
    fake.synthesize("第二句")
    assert fake.calls == [("第一句", "zh-TW-HsiaoChenNeural"), ("第二句", None)]


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_blank_text_rejected(text: str) -> None:
    fake = FakeTTSProvider()
    with pytest.raises(ValueError):
        fake.synthesize(text)
    assert fake.calls == []
