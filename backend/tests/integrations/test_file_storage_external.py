"""檔案儲存的雲端實作：實際連到 Azure Blob Storage（AGENTS.md 7.6，預設不執行）。

執行：在 backend/ 跑 `uv run pytest -m external tests/integrations/test_file_storage_external.py`。
設定只從 .env 讀；缺少設定時直接失敗並說明缺哪個欄位，不自動跳過。
"""

import os
import uuid

import pytest

from app.core.config import REPO_ROOT, Settings
from app.integrations.storage import FileNotFound, StorageConfig, get_file_storage

pytestmark = pytest.mark.external

REQUIRED = ("STORAGE_CONNECTION_STRING", "STORAGE_CONTAINER")
UNUSED_DB = "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"


@pytest.fixture
def storage_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        pytest.fail(f"外部服務測試要讀 {env_file}，但檔案不存在；請照 .env.example 建立並填好")
    fields = set(Settings.model_fields)
    for key in list(os.environ):
        if key.lower() in fields:
            monkeypatch.delenv(key)
    settings = Settings(_env_file=env_file, database_url=UNUSED_DB)
    missing = [name for name in REQUIRED if not getattr(settings, name.lower())]
    if missing:
        pytest.fail(f"外部服務測試缺少設定：{'、'.join(missing)}（請在 {env_file} 填好）")
    return settings


def test_blob_put_get_delete_roundtrip(storage_settings: Settings) -> None:
    storage = get_file_storage(
        StorageConfig(
            provider="cloud",
            connection_string=storage_settings.storage_connection_string,
            container=storage_settings.storage_container,
        )
    )
    key = f"external-test/{uuid.uuid4()}.txt"
    url = storage.put(key, "測試內容".encode(), "text/plain; charset=utf-8")
    try:
        assert url.endswith(key)
        assert storage.get(key) == "測試內容".encode()
    finally:
        storage.delete(key)
    with pytest.raises(FileNotFound):
        storage.get(key)
    # 再刪一次也不拋錯
    storage.delete(key)
