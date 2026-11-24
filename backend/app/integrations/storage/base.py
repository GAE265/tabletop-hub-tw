import re
from abc import ABC, abstractmethod

# 相對路徑，每一段只能是英數、-、_、.，不能有空段（//）、.、..
_SEGMENT = re.compile(r"^[A-Za-z0-9_\-][A-Za-z0-9_.\-]*$")


class FileStorage(ABC):
    """所有 domain 存放檔案（素材照片、旁白、影片）的唯一介面；不得直接 import 廠商 SDK。

    key 是儲存位置內的相對路徑，例如 `rules_videos/<project_id>/final.mp4`。
    """

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """存入檔案（同一個 key 會取代舊檔），回傳可以讀取這個檔案的網址。"""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """讀取檔案；不存在時拋 FileNotFound。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """刪除檔案；不存在時不拋錯（可以重複執行）。"""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """刪除這個資料夾（`<prefix>/`）底下的所有檔案，回傳刪了幾個；沒有檔案時回 0。

        前綴一律當成資料夾：`rules_videos/abc` 不會刪到 `rules_videos/abcd/...`。
        前綴和 key 一樣要是安全的相對路徑：空字串、`..` 等直接拒絕（ValueError），
        避免誤刪整個儲存位置。
        """


def check_prefix(prefix: str) -> str:
    """回傳去掉結尾 `/` 的前綴；不安全時拋 ValueError（規則同 check_key）。"""
    trimmed = prefix[:-1] if prefix.endswith("/") else prefix
    check_key(trimmed)
    return trimmed


def check_key(key: str) -> None:
    """所有實作共用：key 必須是安全的相對路徑，不能跳出儲存位置。"""
    if not key or key.startswith("/") or "\\" in key:
        raise ValueError(f"不合法的檔案 key：{key!r}")
    for segment in key.split("/"):
        if segment in ("", ".", "..") or not _SEGMENT.match(segment):
            raise ValueError(f"不合法的檔案 key：{key!r}")
