"""測試與開發用的文字轉語音：產生靜音 wav，長度依字數計算，結果可以預測。"""

from app.integrations.tts.base import AudioClip, TTSProvider, check_text, silent_wav


def estimate_seconds(text: str) -> float:
    """每 4 個字 1 秒，至少 1 秒（不算空白）。"""
    return max(1.0, len("".join(text.split())) / 4)


class FakeTTSProvider(TTSProvider):
    def __init__(self) -> None:
        # 每次呼叫的（文字, 聲音），方便測試確認呼叫了哪些句子
        self.calls: list[tuple[str, str | None]] = []

    def synthesize(self, text: str, voice: str | None = None) -> AudioClip:
        check_text(text)
        self.calls.append((text, voice))
        seconds = estimate_seconds(text)
        return AudioClip(data=silent_wav(seconds), seconds=seconds)
