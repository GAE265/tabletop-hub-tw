from app.integrations.storage.base import FileStorage, check_key, check_prefix
from app.integrations.storage.errors import FileNotFound


class FakeFileStorage(FileStorage):
    """存在記憶體的假實作，給 domain 的測試使用。網址是 `fake://<key>`。"""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    def put(self, key: str, data: bytes, content_type: str) -> str:
        check_key(key)
        self.files[key] = data
        self.content_types[key] = content_type
        return f"fake://{key}"

    def get(self, key: str) -> bytes:
        check_key(key)
        if key not in self.files:
            raise FileNotFound(f"找不到檔案：{key}")
        return self.files[key]

    def delete(self, key: str) -> None:
        check_key(key)
        self.files.pop(key, None)
        self.content_types.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        folder = check_prefix(prefix) + "/"
        keys = [key for key in self.files if key.startswith(folder)]
        for key in keys:
            self.delete(key)
        return len(keys)
