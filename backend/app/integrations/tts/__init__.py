"""文字轉語音整合層（spec：openspec/specs/media-integrations）。"""

from app.integrations.tts.azure import AzureTTSProvider
from app.integrations.tts.base import AudioClip, TTSProvider
from app.integrations.tts.errors import TTSError, TTSNotConfigured, TTSUnavailable
from app.integrations.tts.factory import DEFAULT_VOICE, TTSConfig, get_tts_provider
from app.integrations.tts.fake import FakeTTSProvider

__all__ = [
    "DEFAULT_VOICE",
    "AudioClip",
    "AzureTTSProvider",
    "FakeTTSProvider",
    "TTSConfig",
    "TTSError",
    "TTSNotConfigured",
    "TTSProvider",
    "TTSUnavailable",
    "get_tts_provider",
]
