"""Azure 文字轉語音（spec media-integrations「文字轉語音」）。

用手寫的 FakeAzureTransport 回傳假的 HTTP 回應，不連網路；等待也換成記錄用的函式，測試不用真的等。
"""

import io
import wave
import xml.etree.ElementTree as ET

import httpx
import pytest

from app.integrations.tts import AzureTTSProvider, TTSError, TTSUnavailable
from tests.integrations.fake_azure import FakeAzureTransport

KEY = "secret-test-key"
REGION = "eastasia"
VOICE = "zh-TW-YunJheNeural"


def _wav(seconds: float, rate: int = 48000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * round(seconds * rate))
    return buffer.getvalue()


def _ok(seconds: float = 2.5) -> httpx.Response:
    return httpx.Response(200, content=_wav(seconds), headers={"content-type": "audio/x-wav"})


class Waits:
    """記錄要求等待的秒數，不真的等。"""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def _provider(
    transport: FakeAzureTransport, waits: Waits | None = None, **kwargs
) -> AzureTTSProvider:
    return AzureTTSProvider(
        region=REGION,
        api_key=KEY,
        voice=VOICE,
        http_client=transport.client(),
        sleep=waits or Waits(),
        **kwargs,
    )


def test_synthesize_returns_wav_and_seconds_from_header() -> None:
    transport = FakeAzureTransport([_ok(2.5)])
    clip = _provider(transport).synthesize("步驟三：同時翻開。")
    assert clip.seconds == pytest.approx(2.5, abs=0.001)
    assert clip.data.startswith(b"RIFF")


def test_request_content() -> None:
    transport = FakeAzureTransport([_ok()])
    _provider(transport).synthesize("步驟三", voice="zh-TW-HsiaoChenNeural")
    request = transport.requests[0]
    assert request.method == "POST"
    assert str(request.url) == f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    assert request.headers["Ocp-Apim-Subscription-Key"] == KEY
    assert request.headers["X-Microsoft-OutputFormat"] == "riff-48khz-16bit-mono-pcm"
    assert request.headers["Content-Type"].startswith("application/ssml+xml")
    root = ET.fromstring(request.content)
    assert root.get("{http://www.w3.org/XML/1998/namespace}lang") == "zh-TW"
    voice = root.find("voice")
    assert voice is not None and voice.get("name") == "zh-TW-HsiaoChenNeural"
    assert "".join(voice.itertext()) == "步驟三"


def test_default_voice_from_config() -> None:
    transport = FakeAzureTransport([_ok()])
    _provider(transport).synthesize("步驟三")
    voice = ET.fromstring(transport.requests[0].content).find("voice")
    assert voice is not None and voice.get("name") == VOICE


def test_special_characters_escaped() -> None:
    transport = FakeAzureTransport([_ok()])
    text = "A & B < C > D"
    _provider(transport).synthesize(text)
    root = ET.fromstring(transport.requests[0].content)  # 不合法的 XML 會在這裡失敗
    voice = root.find("voice")
    assert voice is not None and "".join(voice.itertext()) == text


def test_retry_after_429() -> None:
    waits = Waits()
    transport = FakeAzureTransport([httpx.Response(429, headers={"Retry-After": "2"}), _ok(1.5)])
    clip = _provider(transport, waits).synthesize("步驟三")
    assert clip.seconds == pytest.approx(1.5, abs=0.001)
    assert len(transport.requests) == 2
    assert waits.seconds == [2.0]


def test_429_beyond_retry_limit() -> None:
    transport = FakeAzureTransport([httpx.Response(429)] * 3)
    with pytest.raises(TTSUnavailable) as exc:
        _provider(transport, max_retries=2).synthesize("步驟三")
    assert len(transport.requests) == 3
    assert KEY not in str(exc.value)


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.ReadTimeout("timeout"), httpx.ConnectError("refused")],
    ids=["503", "timeout", "connect"],
)
def test_service_unavailable(failure: httpx.Response | Exception) -> None:
    transport = FakeAzureTransport([failure, failure])
    with pytest.raises(TTSUnavailable) as exc:
        _provider(transport, max_retries=1).synthesize("步驟三")
    assert KEY not in str(exc.value)


@pytest.mark.parametrize("status", [401, 403])
def test_wrong_key_is_error_not_unavailable(status: int) -> None:
    transport = FakeAzureTransport([httpx.Response(status, text=f"bad key {KEY}")])
    with pytest.raises(TTSError) as exc:
        _provider(transport).synthesize("步驟三")
    assert not isinstance(exc.value, TTSUnavailable)
    assert len(transport.requests) == 1  # 不重試
    assert KEY not in str(exc.value)


def test_invalid_audio_is_error() -> None:
    transport = FakeAzureTransport([httpx.Response(200, content=b"not a wav")])
    with pytest.raises(TTSError):
        _provider(transport).synthesize("步驟三")


def test_blank_text_sends_nothing() -> None:
    transport = FakeAzureTransport([])
    with pytest.raises(ValueError):
        _provider(transport).synthesize("  ")
    assert transport.requests == []
