"""文字轉語音整合層的例外。

不帶 HTTP 狀態碼、不繼承 core.errors.AppError，由呼叫端自己轉換（同 llm、ocr）。
訊息一律不含金鑰，也不含外部服務的原始回應內容。
"""


class TTSError(Exception):
    """基底類別。也用在重試也不會成功的錯誤，例如金鑰錯誤、回應不是合法的音檔。"""


class TTSNotConfigured(TTSError):
    """TTS_PROVIDER=azure 但缺少必要設定。missing 是缺少的設定名稱。"""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(f"TTS_PROVIDER=azure 缺少設定：{'、'.join(missing)}")
        self.missing = missing


class TTSUnavailable(TTSError):
    """逾時、連線失敗、429、5xx，重試後仍然失敗：稍後再試可能會成功。"""
