"""檔案儲存的雲端實作：Azure Blob Storage。

azure-storage-blob 只在這個檔案裡 import（AGENTS.md §4.2）。
"""

from collections.abc import Iterator
from contextlib import contextmanager

from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
    ServiceResponseError,
)
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.integrations.storage.base import FileStorage, check_key
from app.integrations.storage.errors import FileNotFound, StorageError, StorageUnavailable

# 單一請求的逾時秒數；影片檔較大，上傳給寬一點
TIMEOUT_SECONDS = 120


class AzureBlobFileStorage(FileStorage):
    """一個 provider 只綁一個容器。回傳的網址是 blob 的網址；能不能匿名讀取由容器設定決定。"""

    def __init__(self, *, connection_string: str, container: str) -> None:
        service = BlobServiceClient.from_connection_string(
            connection_string, connection_timeout=TIMEOUT_SECONDS, read_timeout=TIMEOUT_SECONDS
        )
        self._container = service.get_container_client(container)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        check_key(key)
        blob = self._container.get_blob_client(key)
        with _translate_errors():
            blob.upload_blob(
                data, overwrite=True, content_settings=ContentSettings(content_type=content_type)
            )
        return blob.url

    def get(self, key: str) -> bytes:
        check_key(key)
        with _translate_errors():
            return self._container.get_blob_client(key).download_blob().readall()

    def delete(self, key: str) -> None:
        check_key(key)
        try:
            with _translate_errors():
                self._container.get_blob_client(key).delete_blob()
        except FileNotFound:
            return


@contextmanager
def _translate_errors() -> Iterator[None]:
    """把 Azure SDK 的例外轉成本整合層的例外；訊息不含連線字串。"""
    try:
        yield
    except ResourceNotFoundError as exc:
        raise FileNotFound("找不到檔案") from exc
    except (ServiceRequestError, ServiceResponseError) as exc:
        raise StorageUnavailable(f"連不上 Azure Blob Storage：{type(exc).__name__}") from exc
    except HttpResponseError as exc:
        status = exc.status_code or 0
        if status == 429 or status >= 500:
            raise StorageUnavailable(f"Azure Blob Storage 暫時無法使用（HTTP {status}）") from exc
        raise StorageError(f"Azure Blob Storage 回應錯誤（HTTP {status}）") from exc
    except AzureError as exc:
        raise StorageError(f"Azure Blob Storage 發生錯誤：{type(exc).__name__}") from exc
