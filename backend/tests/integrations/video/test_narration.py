"""旁白合成與快取（spec rules-video-maker「先音後畫的時間軸」的旁白快取，MR 3）。

一律用 FakeTTSProvider 與手寫的 fake，不連 Azure。
"""

from pathlib import Path

import pytest

from app.integrations.tts import AudioClip, FakeTTSProvider, TTSProvider, TTSUnavailable
from app.integrations.video import load_video
from app.integrations.video.narration import prepare_narration
from tests.integrations.video.support import base_data, segment, write_game


class FailingOnSecondCall(TTSProvider):
    """手寫的 fake：第一句成功，第二句起拋 TTSUnavailable。"""

    def __init__(self) -> None:
        self.fake = FakeTTSProvider()
        self.calls = 0

    def synthesize(self, text: str, voice: str | None = None) -> AudioClip:
        self.calls += 1
        if self.calls >= 2:
            raise TTSUnavailable("文字轉語音服務暫時無法使用（測試）")
        return self.fake.synthesize(text, voice)


def _video(tmp_path: Path, data: dict | None = None):
    return load_video(write_game(tmp_path / "game", data or base_data()))


def test_first_synthesis_caches_each_beat(tmp_path: Path) -> None:
    tts = FakeTTSProvider()
    clips = prepare_narration(_video(tmp_path), tts, tmp_path / "cache")
    assert [text for text, _ in tts.calls] == ["a" * 12, "b" * 12, "c" * 12]
    assert set(clips) == {"b1", "b2", "b3"}
    for clip in clips.values():
        assert clip.path.is_file()
        assert clip.seconds == pytest.approx(3.0)


def test_unchanged_text_uses_cache(tmp_path: Path) -> None:
    video = _video(tmp_path)
    prepare_narration(video, FakeTTSProvider(), tmp_path / "cache")
    tts = FakeTTSProvider()
    clips = prepare_narration(video, tts, tmp_path / "cache")
    assert tts.calls == []
    assert clips["b1"].seconds == pytest.approx(3.0)


def test_changed_beat_only_resynthesized(tmp_path: Path) -> None:
    prepare_narration(_video(tmp_path), FakeTTSProvider(), tmp_path / "cache")
    data = base_data()
    segment(data, "s1")["beats"][1]["narration"] = "x" * 20
    tts = FakeTTSProvider()
    clips = prepare_narration(_video(tmp_path, data), tts, tmp_path / "cache")
    assert [text for text, _ in tts.calls] == ["x" * 20]
    assert clips["b2"].seconds == pytest.approx(5.0)


def test_changed_voice_resynthesizes_all(tmp_path: Path) -> None:
    prepare_narration(_video(tmp_path), FakeTTSProvider(), tmp_path / "cache")
    data = base_data()
    data["voice"] = "zh-TW-HsiaoChenNeural"
    tts = FakeTTSProvider()
    prepare_narration(_video(tmp_path, data), tts, tmp_path / "cache")
    assert len(tts.calls) == 3
    assert {voice for _, voice in tts.calls} == {"zh-TW-HsiaoChenNeural"}


def test_failure_keeps_finished_beats(tmp_path: Path) -> None:
    video = _video(tmp_path)
    with pytest.raises(TTSUnavailable):
        prepare_narration(video, FailingOnSecondCall(), tmp_path / "cache")
    # 第一句已經存進快取，下次只補缺的兩句
    tts = FakeTTSProvider()
    prepare_narration(video, tts, tmp_path / "cache")
    assert [text for text, _ in tts.calls] == ["b" * 12, "c" * 12]


class LoudTTS(TTSProvider):
    """手寫的 fake：代表另一種 TTS（例如 Azure），回傳有聲音的音檔並記下呼叫。"""

    def __init__(self) -> None:
        self.fake = FakeTTSProvider()
        self.calls: list[str] = []

    def synthesize(self, text: str, voice: str | None = None) -> AudioClip:
        self.calls.append(text)
        clip = self.fake.synthesize(text, voice)
        return AudioClip(
            data=clip.data[:44] + b"\x10\x00" * ((len(clip.data) - 44) // 2), seconds=clip.seconds
        )


def test_switching_tts_provider_resynthesizes(tmp_path: Path) -> None:
    # #75 審核：先在 TTS 未設定（fake）時輸出，再換成 Azure，不能沿用快取裡的靜音檔
    video = _video(tmp_path)
    prepare_narration(video, FakeTTSProvider(), tmp_path / "cache")
    loud = LoudTTS()
    clips = prepare_narration(video, loud, tmp_path / "cache")
    assert len(loud.calls) == 3
    assert set(clips["b1"].path.read_bytes()[44:]) != {0}
