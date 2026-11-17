"""OCR 整合層的例外。

不帶 HTTP 狀態碼、不繼承 core.errors.AppError，由呼叫端的 service 自己轉換（同 llm/errors.py）。
"""


class OCRError(Exception):
    """基底類別。也用在設定或程式錯誤，例如金鑰錯誤、圖片格式不認得。"""


class OCRNotConfigured(OCRError):
    """OCR_PROVIDER=cloud 但缺少必要設定。missing 是缺少的設定名稱，之後轉成 503 寫進 details。"""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(f"OCR_PROVIDER=cloud 缺少設定：{'、'.join(missing)}")
        self.missing = missing


class OCRUnavailable(OCRError):
    """逾時、連線失敗、429、5xx，SDK 重試後仍然失敗；或 fake 沒有放入腳本。"""


class OCROutputRejected(OCRError):
    """被內容過濾擋下、模型拒答、輸出因 token 上限被截斷，或輸出不是合法 JSON。"""
