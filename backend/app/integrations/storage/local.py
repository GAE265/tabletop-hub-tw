import shutil
from pathlib import Path

from app.integrations.storage.base import FileStorage, check_key, check_prefix
from app.integrations.storage.errors import FileNotFound


class LocalFileStorage(FileStorage):
    """存在本機資料夾，開發用。

    回傳的網址是 `<public_base_url>/<key>`；讓瀏覽器能讀到檔案的下載路由，
    由使用這個儲存的 domain 在開發環境掛上（本整合層不知道 FastAPI）。
    """

    def __init__(self, *, root: Path, public_base_url: str) -> None:
        self._root = root
        self._base_url = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        check_key(key)
        return self._root / key

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"{self._base_url}/{key}"

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFound(f"找不到檔案：{key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> int:
        folder = self._root / check_prefix(prefix)
        if not folder.is_dir():
            return 0
        count = sum(1 for path in folder.rglob("*") if path.is_file())
        shutil.rmtree(folder)
        return count
