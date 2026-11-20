"""文字轉語音的介面。所有 domain 只透過這個介面產生旁白，不直接呼叫廠商 API。"""

import io
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.integrations.tts.errors import TTSError

SAMPLE_RATE = 48000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


@dataclass(frozen=True)
class AudioClip:
    """一段旁白：wav 音檔內容（48 kHz、16-bit、mono）與長度（秒）。"""

    data: bytes
    seconds: float


class TTSProvider(ABC):
    @property
    def cache_name(self) -> str:
        """這種 TTS 的識別名稱，旁白快取用：不同種類（例如靜音的 fake 與 Azure）的音檔不能混用。"""
        return type(self).__name__

    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> AudioClip:
        """把一句旁白轉成語音。voice 沒給時用設定的預設聲音；空白文字拋 ValueError。"""


def check_text(text: str) -> None:
    if not text or not text.strip():
        raise ValueError("旁白文字不能是空白")


def wav_seconds(data: bytes) -> float:
    """從 wav 檔頭算出長度；不是合法的 wav 時拋 TTSError。"""
    try:
        with wave.open(io.BytesIO(data)) as wav:
            return wav.getnframes() / wav.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise TTSError("文字轉語音的回應不是合法的 wav 音檔") from exc


def silent_wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00" * SAMPLE_WIDTH * CHANNELS * round(seconds * SAMPLE_RATE))
    return buffer.getvalue()
