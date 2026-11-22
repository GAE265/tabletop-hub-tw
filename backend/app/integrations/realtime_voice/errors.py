"""即時語音整合層的例外。

不帶 HTTP 狀態碼、不繼承 core.errors.AppError，由呼叫端自己轉換。
"""


class RealtimeVoiceError(Exception):
    """基底類別。"""


class RealtimeVoiceUnavailable(RealtimeVoiceError):
    """連不上、金鑰錯誤、或連線已經斷了。真正原因只放在例外訊息，由呼叫端寫進紀錄。"""
