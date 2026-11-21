"""文字轉語音的 factory 與設定（spec media-integrations「文字轉語音」）。"""

import pytest

from app.integrations.tts import (
    AzureTTSProvider,
    FakeTTSProvider,
    TTSConfig,
    TTSNotConfigured,
    get_tts_provider,
)


@pytest.mark.parametrize("provider", ["fake", None])
def test_default_is_fake(provider: str | None) -> None:
    config = TTSConfig(provider=provider) if provider else TTSConfig()
    assert isinstance(get_tts_provider(config), FakeTTSProvider)


def test_azure_with_settings() -> None:
    config = TTSConfig(provider="azure", region="eastasia", api_key="test-key")
    assert isinstance(get_tts_provider(config), AzureTTSProvider)


@pytest.mark.parametrize(
    "config, missing",
    [
        (TTSConfig(provider="azure", api_key="test-key"), ["TTS_REGION"]),
        (TTSConfig(provider="azure", region="eastasia"), ["TTS_API_KEY"]),
        (TTSConfig(provider="azure"), ["TTS_REGION", "TTS_API_KEY"]),
    ],
)
def test_missing_settings(config: TTSConfig, missing: list[str]) -> None:
    with pytest.raises(TTSNotConfigured) as exc:
        get_tts_provider(config)
    assert exc.value.missing == missing
    for name in missing:
        assert name in str(exc.value)


def test_unknown_provider() -> None:
    with pytest.raises(ValueError) as exc:
        get_tts_provider(TTSConfig(provider="xyz"))
    message = str(exc.value)
    assert "xyz" in message and "fake" in message and "azure" in message
