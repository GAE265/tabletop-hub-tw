from app.core.config import Settings
from app.integrations.realtime_voice.base import RealtimeVoiceProvider
from app.integrations.realtime_voice.cloud import CloudRealtimeVoiceProvider
from app.integrations.realtime_voice.fake import FakeRealtimeVoiceProvider


def get_realtime_voice_provider(settings: Settings) -> RealtimeVoiceProvider:
    """依 HOST_REALTIME_PROVIDER 選擇實作。cloud 缺欄位在 Settings 建立時就已經擋掉。"""
    name = settings.host_realtime_provider
    if name == "fake":
        return FakeRealtimeVoiceProvider()
    if name == "cloud":
        return CloudRealtimeVoiceProvider(
            api_key=settings.host_realtime_api_key,  # type: ignore[arg-type]
            api_host=settings.host_realtime_api_host,  # type: ignore[arg-type]
            model=settings.host_realtime_model,
        )
    raise ValueError(f"未知的 HOST_REALTIME_PROVIDER：{name}")
