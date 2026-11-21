"""實際連到 Azure AI Speech 的文字轉語音（AGENTS.md 7.6 external）。

只在本機用 `uv run pytest -m external` 執行；設定只從 .env 讀，缺少時直接失敗並說明缺哪個設定。
"""

import io
import wave

import pytest

from app.core.config import Settings
from app.integrations.tts import TTSConfig, get_tts_provider

pytestmark = pytest.mark.external


def test_real_synthesis(tts_external_settings: Settings) -> None:
    provider = get_tts_provider(
        TTSConfig(
            provider="azure",
            region=tts_external_settings.tts_region,
            api_key=tts_external_settings.tts_api_key,
            voice=tts_external_settings.tts_voice,
        )
    )
    clip = provider.synthesize("步驟三：把打出的牌蓋著洗在一起，然後同時翻開。")
    with wave.open(io.BytesIO(clip.data)) as wav:
        actual = wav.getnframes() / wav.getframerate()
        assert wav.getframerate() == 48000
    assert actual > 1.0
    assert abs(clip.seconds - actual) < 0.05
