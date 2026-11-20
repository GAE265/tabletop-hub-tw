"""Azure AI Speech 的文字轉語音（REST API）。

只有 factory 在 TTS_PROVIDER=azure 時才建立；其他地方一律透過 TTSProvider 介面。
免費層每分鐘約 20 次請求，遇到 429 依 Retry-After 等待後重試。
"""

import time
from collections.abc import Callable
from xml.sax.saxutils import escape, quoteattr

import httpx

from app.integrations.tts.base import AudioClip, TTSProvider, check_text, wav_seconds
from app.integrations.tts.errors import TTSError, TTSUnavailable

OUTPUT_FORMAT = "riff-48khz-16bit-mono-pcm"
LANGUAGE = "zh-TW"


class AzureTTSProvider(TTSProvider):
    def __init__(
        self,
        region: str,
        api_key: str,
        voice: str,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 30,
        max_retries: int = 3,
        retry_wait_seconds: float = 3.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self._api_key = api_key
        self._voice = voice
        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._max_retries = max_retries
        self._retry_wait = retry_wait_seconds
        self._sleep = sleep

    def synthesize(self, text: str, voice: str | None = None) -> AudioClip:
        check_text(text)
        body = _ssml(text, voice or self._voice)
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/ssml+xml; charset=utf-8",
            "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
            "User-Agent": "rules-video-tts",
        }
        last_problem = ""
        last_retry_after: float | None = None
        for attempt in range(self._max_retries + 1):
            if attempt:
                self._sleep(self._wait_seconds(attempt, last_retry_after))
                last_retry_after = None
            try:
                response = self._client.post(self._url, content=body, headers=headers)
            except httpx.TimeoutException:
                last_problem = "逾時"
                continue
            except httpx.TransportError:
                last_problem = "連線失敗"
                continue
            status = response.status_code
            if status == 200:
                data = response.content
                return AudioClip(data=data, seconds=wav_seconds(data))
            if status in (401, 403):
                raise TTSError(
                    f"文字轉語音的金鑰或區域錯誤（HTTP {status}），請檢查 TTS_API_KEY 與 TTS_REGION"
                )
            if status == 429 or status >= 500:
                last_problem = f"HTTP {status}"
                last_retry_after = _retry_after(response)
                continue
            raise TTSError(f"文字轉語音的請求被拒絕（HTTP {status}）")
        raise TTSUnavailable(
            f"文字轉語音服務暫時無法使用（{last_problem}，已重試 {self._max_retries} 次）"
        )

    def _wait_seconds(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return retry_after
        return self._retry_wait * attempt


def _ssml(text: str, voice: str) -> bytes:
    return (
        f"<speak version='1.0' xml:lang='{LANGUAGE}'>"
        f"<voice name={quoteattr(voice)}>{escape(text)}</voice>"
        "</speak>"
    ).encode()


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
