"""LLM 整合層的例外（整合層提案 §5）。

不帶 HTTP 狀態碼、不繼承 core.errors.AppError，由呼叫端的 service 自己轉換。
"""


class LLMError(Exception):
    """基底類別。也用在設定或程式錯誤，例如金鑰錯誤、schema 不符合 strict 規定。"""


class LLMUnavailable(LLMError):
    """逾時、連線失敗、429、5xx，SDK 重試後仍然失敗；或根本沒有設定模型。"""


class LLMConversationNotFound(LLMError):
    """找不到 previous_response_id：過期、亂填，或別的 Foundry 資源產生的。"""


class LLMOutputRejected(LLMError):
    """被內容過濾擋下、模型拒答、輸出因 token 上限被截斷，或輸出不是合法 JSON。"""
