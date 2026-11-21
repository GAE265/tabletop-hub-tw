"""即時語音的工廠（host spec §13.3）：用 HOST_REALTIME_PROVIDER 切換 fake 與 cloud。"""

from collections.abc import Callable

import pytest

from app.core.config import Settings
from app.integrations.realtime_voice import (
    FakeRealtimeVoiceProvider,
    get_realtime_voice_provider,
)


def test_fake(make_settings: Callable[..., Settings]) -> None:
    provider = get_realtime_voice_provider(make_settings())
    assert isinstance(provider, FakeRealtimeVoiceProvider)


def test_cloud_not_implemented_yet(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(
        host_realtime_provider="cloud",
        host_realtime_api_key="test-key",
        host_realtime_api_host="example.invalid",
    )
    with pytest.raises(NotImplementedError) as exc:
        get_realtime_voice_provider(settings)
    assert "cloud" in str(exc.value)
