from abc import ABC, abstractmethod

from app.integrations.embedding.errors import EmbeddingError


class EmbeddingProvider(ABC):
    """所有 domain 取得 embedding 的唯一介面；不得直接 import 模型廠商 SDK。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批次把文字轉成向量，順序與筆數和 texts 相同。

        - 只轉 1 段時傳長度 1 的 list；傳空的 list 就回傳空的 list，不發請求。
        - 文字有空字串或只有空白時拋 ValueError（用 check_texts）。
        - 每個向量的長度都等於建立 provider 時的 dim；結果不對時拋 EmbeddingError
          （用 check_vectors）。
        """


def check_texts(texts: list[str]) -> None:
    """所有實作共用：送出前檢查輸入。"""
    for index, text in enumerate(texts):
        if not text.strip():
            raise ValueError(f"embedding 的第 {index} 段文字是空字串或只有空白")


def check_vectors(vectors: list[list[float]], *, dim: int, count: int) -> None:
    """所有實作共用：檢查模型回傳的向量，fake 也走這裡。"""
    if len(vectors) != count:
        raise EmbeddingError(f"收到 {len(vectors)} 個向量，應為 {count} 個")
    for index, vector in enumerate(vectors):
        if len(vector) != dim:
            raise EmbeddingError(f"第 {index} 個向量長度是 {len(vector)}，應為 {dim}")
        if not any(vector):
            raise EmbeddingError(f"第 {index} 個向量是零向量")
