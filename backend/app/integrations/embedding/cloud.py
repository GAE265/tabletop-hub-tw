"""embedding 的雲端實作：Azure OpenAI Embeddings API（整合層提案 §4、§5）。

openai SDK 只在這個檔案裡 import（AGENTS.md §4.2）。
"""

import httpx
import openai

from app.integrations.embedding.base import EmbeddingProvider, check_texts, check_vectors
from app.integrations.embedding.errors import EmbeddingError, EmbeddingUnavailable

# ⚠️ 必須與 Azure OpenAI 的限制同步：embeddings 一次請求最多 2048 段
MAX_TEXTS_PER_REQUEST = 2048
# SDK 預設逾時 600 秒；「查桌遊」線上轉 1 段文字，玩家等不了那麼久
TIMEOUT_SECONDS = 30


class CloudEmbeddingProvider(EmbeddingProvider):
    """一個 provider 只綁一個部署（model）。重試沿用 SDK 預設的 2 次。"""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model: str,
        dim: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        # ⚠️ endpoint 是 Azure 的 v1 端點（.../openai/v1/），不帶 api-version
        self._client = openai.OpenAI(
            base_url=endpoint,
            api_key=api_key,
            timeout=TIMEOUT_SECONDS,
            http_client=http_client,
        )
        self._model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        check_texts(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_TEXTS_PER_REQUEST):
            vectors.extend(self._embed_batch(texts[start : start + MAX_TEXTS_PER_REQUEST]))
        check_vectors(vectors, dim=self.dim, count=len(texts))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            # text-embedding-3 系列用 dimensions 縮成設定的維度
            response = self._client.embeddings.create(
                model=self._model, input=texts, dimensions=self.dim
            )
        except openai.APIConnectionError as exc:  # 包含逾時（APITimeoutError）
            raise EmbeddingUnavailable(f"連不上 Azure OpenAI：{exc}") from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise EmbeddingUnavailable(
                    f"Azure OpenAI 暫時無法使用（HTTP {exc.status_code}）：{exc}"
                ) from exc
            raise EmbeddingError(f"Azure OpenAI 回傳錯誤（HTTP {exc.status_code}）：{exc}") from exc
        except openai.OpenAIError as exc:
            raise EmbeddingError(f"Azure OpenAI 呼叫失敗：{exc}") from exc
        # 回應的順序不保證和輸入相同，依 index 排回去
        return [list(item.embedding) for item in sorted(response.data, key=lambda d: d.index)]
