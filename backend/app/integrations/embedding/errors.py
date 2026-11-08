"""embedding 整合層的例外（整合層提案 §5）。不帶 HTTP 狀態碼。"""


class EmbeddingError(Exception):
    """基底類別。也用在回傳零向量、維度或筆數不符。"""


class EmbeddingUnavailable(EmbeddingError):
    """逾時、連線失敗、429、5xx，重試後仍然失敗。"""
