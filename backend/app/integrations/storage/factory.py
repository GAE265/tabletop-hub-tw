from dataclasses import dataclass
from pathlib import Path

from app.integrations.storage.base import FileStorage
from app.integrations.storage.fake import FakeFileStorage
from app.integrations.storage.local import LocalFileStorage


@dataclass(frozen=True)
class StorageConfig:
    """建立檔案儲存需要的設定值。

    整合層不讀 Settings，由呼叫方從自己的設定欄位組出來，整合層因此不知道是哪個 domain 在用。
    """

    provider: str  # fake | local | cloud
    local_dir: str | None = None
    public_base_url: str | None = None
    connection_string: str | None = None
    container: str | None = None


def get_file_storage(config: StorageConfig) -> FileStorage:
    """依 config.provider 選擇實作；缺少必要設定時拋 ValueError 並說明缺哪個。"""
    if config.provider == "fake":
        return FakeFileStorage()
    if config.provider == "local":
        _require(config, "local_dir", "public_base_url")
        return LocalFileStorage(
            root=Path(config.local_dir),  # type: ignore[arg-type]
            public_base_url=config.public_base_url,  # type: ignore[arg-type]
        )
    if config.provider == "cloud":
        _require(config, "connection_string", "container")
        # 只有用到雲端時才載入 Azure SDK
        from app.integrations.storage.cloud import AzureBlobFileStorage

        return AzureBlobFileStorage(
            connection_string=config.connection_string,  # type: ignore[arg-type]
            container=config.container,  # type: ignore[arg-type]
        )
    raise ValueError(f"未知的檔案儲存 provider：{config.provider}")


def _require(config: StorageConfig, *names: str) -> None:
    missing = [name for name in names if not getattr(config, name)]
    if missing:
        raise ValueError(f"檔案儲存 provider={config.provider} 缺少設定：{'、'.join(missing)}")
