"""integrations 測試共用的 fixture。

external_settings 只給 @pytest.mark.external 的測試用（AGENTS.md 7.6）：設定只從 .env 讀，
不從 shell 讀；缺少設定時直接失敗並說明缺哪個欄位，不自動跳過。
"""

import os

import pytest

from app.core.config import REPO_ROOT, Settings

EXTERNAL_REQUIRED = (
    "LLM_ENDPOINT",
    "LLM_API_KEY",
    "LLM_MODEL",
    "GAMES_ADVISOR_EMBEDDING_ENDPOINT",
    "GAMES_ADVISOR_EMBEDDING_API_KEY",
    "GAMES_ADVISOR_EMBEDDING_MODEL",
)
# OCR 的外部服務測試（直連 Azure Document Intelligence 與 Azure OpenAI 視覺模型）
OCR_EXTERNAL_REQUIRED = (
    "OCR_DI_ENDPOINT",
    "LLM_ENDPOINT",
    "LLM_API_KEY",
    "LLM_MODEL",
)
# 文字轉語音的外部服務測試（直連 Azure AI Speech）
TTS_EXTERNAL_REQUIRED = ("TTS_REGION", "TTS_API_KEY")
# 即時語音的外部服務測試（直連阿里雲的即時語音模型，AI 語音主持用）
REALTIME_EXTERNAL_REQUIRED = ("HOST_REALTIME_API_KEY", "HOST_REALTIME_API_HOST")
# 外部服務測試不連資料庫，給一個用不到的值，.env 沒有 DATABASE_URL 也能跑
UNUSED_DB = "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"


def _load_external_settings(monkeypatch: pytest.MonkeyPatch, required: tuple[str, ...]) -> Settings:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        pytest.fail(f"外部服務測試要讀 {env_file}，但檔案不存在；請照 .env.example 建立並填好金鑰")

    # Settings 也讀 shell 的環境變數；先清掉，確保值只來自 .env
    fields = set(Settings.model_fields)
    for key in list(os.environ):
        if key.lower() in fields:
            monkeypatch.delenv(key)

    settings = Settings(_env_file=env_file, database_url=UNUSED_DB)
    missing = [name for name in required if not getattr(settings, name.lower())]
    if missing:
        pytest.fail(f"外部服務測試缺少設定：{'、'.join(missing)}（請在 {env_file} 填好）")
    return settings


@pytest.fixture
def external_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return _load_external_settings(monkeypatch, EXTERNAL_REQUIRED)


@pytest.fixture
def ocr_external_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return _load_external_settings(monkeypatch, OCR_EXTERNAL_REQUIRED)


@pytest.fixture
def tts_external_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return _load_external_settings(monkeypatch, TTS_EXTERNAL_REQUIRED)


@pytest.fixture
def realtime_external_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return _load_external_settings(monkeypatch, REALTIME_EXTERNAL_REQUIRED)
