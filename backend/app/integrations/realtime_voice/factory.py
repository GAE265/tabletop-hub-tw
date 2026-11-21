from app.core.config import Settings
from app.integrations.realtime_voice.base import RealtimeVoiceProvider
from app.integrations.realtime_voice.fake import FakeRealtimeVoiceProvider


def get_realtime_voice_provider(settings: Settings) -> RealtimeVoiceProvider:
    """依 HOST_REALTIME_PROVIDER 選擇實作。cloud 缺欄位在 Settings 建立時就已經擋掉。"""
    name = settings.host_realtime_provider
    if name == "fake":
        return FakeRealtimeVoiceProvider()
    if name == "cloud":
        # 🚧 阿里雲的實作在 host 實作 ticket 08
        raise NotImplementedError("HOST_REALTIME_PROVIDER=cloud 尚未實作，目前只支援 fake")
    raise ValueError(f"未知的 HOST_REALTIME_PROVIDER：{name}")
