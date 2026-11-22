from dataclasses import dataclass

from app.integrations.tts.base import TTSProvider
from app.integrations.tts.errors import TTSNotConfigured
from app.integrations.tts.fake import FakeTTSProvider

DEFAULT_VOICE = "zh-TW-YunJheNeural"
PROVIDERS = ("fake", "azure")


@dataclass(frozen=True)
class TTSConfig:
    """建立文字轉語音需要的設定值。

    整合層不讀 Settings，由呼叫方從自己的設定欄位組出來，整合層因此不知道是哪個 domain 在用。
    """

    provider: str = "fake"  # fake | azure
    region: str | None = None
    api_key: str | None = None
    voice: str = DEFAULT_VOICE


def get_tts_provider(config: TTSConfig) -> TTSProvider:
    """依 config.provider 選擇實作；缺少必要設定時拋 TTSNotConfigured 並說明缺哪個。"""
    if config.provider == "fake":
        return FakeTTSProvider()
    if config.provider == "azure":
        missing = [
            name
            for name, value in (("TTS_REGION", config.region), ("TTS_API_KEY", config.api_key))
            if not value
        ]
        if missing:
            raise TTSNotConfigured(missing)
        from app.integrations.tts.azure import AzureTTSProvider

        return AzureTTSProvider(
            region=config.region,  # type: ignore[arg-type]
            api_key=config.api_key,  # type: ignore[arg-type]
            voice=config.voice,
        )
    raise ValueError(
        f"未知的文字轉語音 provider：{config.provider}（可用的值：{'、'.join(PROVIDERS)}）"
    )
