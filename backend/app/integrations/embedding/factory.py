from dataclasses import dataclass

from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.embedding.fake import FakeEmbeddingProvider

# 🚧 cloud 尚未實作，之後另開 MR 補上雲端實作
UNIMPLEMENTED = ("cloud",)


@dataclass(frozen=True)
class EmbeddingConfig:
    """建立 embedding provider 需要的設定值。

    整合層不讀 Settings，由呼叫方從自己的設定欄位組出來，整合層因此不知道是哪個 domain 在用。
    """

    provider: str  # fake | cloud
    dim: int
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None


def get_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    """依 config.provider 選擇實作。尚未實作的值明確報錯，不靜默退回 fake。"""
    if config.provider == "fake":
        return FakeEmbeddingProvider(dim=config.dim)
    if config.provider in UNIMPLEMENTED:
        raise NotImplementedError(f"embedding provider={config.provider} 尚未實作，目前只支援 fake")
    raise ValueError(f"未知的 embedding provider：{config.provider}")
