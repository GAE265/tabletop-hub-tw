"""即時語音的設定（host spec §13.4）：預設 fake；cloud 缺欄位就啟動失敗。"""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings()
    assert settings.host_realtime_provider == "fake"
    assert settings.host_realtime_api_key is None
    assert settings.host_realtime_api_host is None
    assert settings.host_realtime_model == "qwen-audio-3.1-realtime-flash"
    assert settings.host_thinking_model is None


def test_cloud_with_all_fields(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(
        host_realtime_provider="cloud",
        host_realtime_api_key="test-key",
        host_realtime_api_host="example.invalid",
    )
    assert settings.host_realtime_provider == "cloud"


@pytest.mark.parametrize(
    "overrides, missing",
    [
        ({"host_realtime_api_host": "example.invalid"}, ["HOST_REALTIME_API_KEY"]),
        ({"host_realtime_api_key": "test-key"}, ["HOST_REALTIME_API_HOST"]),
        ({}, ["HOST_REALTIME_API_KEY", "HOST_REALTIME_API_HOST"]),
    ],
)
def test_cloud_missing_fields_fails_at_startup(
    make_settings: Callable[..., Settings], overrides: dict[str, str], missing: list[str]
) -> None:
    with pytest.raises(ValidationError) as exc:
        make_settings(host_realtime_provider="cloud", **overrides)
    for name in missing:
        assert name in str(exc.value)


def test_unknown_provider_rejected(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(ValidationError):
        make_settings(host_realtime_provider="xyz")


def test_fake_does_not_need_key(make_settings: Callable[..., Settings]) -> None:
    assert make_settings(host_realtime_provider="fake").host_realtime_api_key is None
