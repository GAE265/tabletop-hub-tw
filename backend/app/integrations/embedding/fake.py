import hashlib
import math

from app.integrations.embedding.base import EmbeddingProvider, check_texts, check_vectors


class FakeEmbeddingProvider(EmbeddingProvider):
    """測試用：不發出任何網路請求。

    - vectors 有指定的文字，回傳指定的向量。
    - 沒指定的文字，用 sha256 產生固定的單位向量；同一段文字每次都得到相同的向量。
    - 設定了 error 時，每次 embed 都拋出它。
    - 每次呼叫的 texts 都記在 calls。
    """

    def __init__(
        self,
        dim: int,
        vectors: dict[str, list[float]] | None = None,
        error: Exception | None = None,
    ) -> None:
        if dim <= 0:
            raise ValueError(f"dim 必須是正整數，收到 {dim}")
        for text, vector in (vectors or {}).items():
            if len(vector) != dim:
                raise ValueError(f"「{text}」指定的向量長度是 {len(vector)}，應為 {dim}")
        self.dim = dim
        self.calls: list[list[str]] = []
        self._vectors = dict(vectors or {})
        self._error = error

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._error is not None:
            raise self._error
        check_texts(texts)
        if not texts:
            return []
        result = [
            list(self._vectors[text]) if text in self._vectors else self._hash_vector(text)
            for text in texts
        ]
        check_vectors(result, dim=self.dim, count=len(texts))
        return result

    def _hash_vector(self, text: str) -> list[float]:
        # 每 4 bytes 換成一個 [-1, 1) 的值，sha256 不夠長就加上區塊編號再算
        raw = b""
        block = 0
        while len(raw) < self.dim * 4:
            raw += hashlib.sha256(f"{block}:{text}".encode()).digest()
            block += 1
        values = [
            int.from_bytes(raw[i * 4 : i * 4 + 4], "big") / 2**31 - 1 for i in range(self.dim)
        ]
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values]
