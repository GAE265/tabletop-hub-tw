"""檔案儲存整合層的例外。不帶 HTTP 狀態碼，由 domain 的 service 轉成 API 錯誤。"""


class StorageError(Exception):
    """基底類別：設定錯誤、權限不足等不會因重試而成功的錯誤。"""


class StorageUnavailable(StorageError):
    """連線失敗、逾時、429、5xx：稍後重試可能會成功。"""


class FileNotFound(StorageError):
    """要讀取的檔案不存在。"""
