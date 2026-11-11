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
# 外部服務測試不連資料庫，給一個用不到的值，.env 沒有 DATABASE_URL 也能跑
UNUSED_DB = "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"


@pytest.fixture
def external_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        pytest.fail(f"外部服務測試要讀 {env_file}，但檔案不存在；請照 .env.example 建立並填好金鑰")

    # Settings 也讀 shell 的環境變數；先清掉，確保值只來自 .env
    fields = set(Settings.model_fields)
    for key in list(os.environ):
        if key.lower() in fields:
            monkeypatch.delenv(key)

    settings = Settings(_env_file=env_file, database_url=UNUSED_DB)
    missing = [name for name in EXTERNAL_REQUIRED if not getattr(settings, name.lower())]
    if missing:
        pytest.fail(f"外部服務測試缺少設定：{'、'.join(missing)}（請在 {env_file} 填好）")
    return settings
