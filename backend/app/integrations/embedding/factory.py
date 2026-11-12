from dataclasses import dataclass

from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.embedding.cloud import CloudEmbeddingProvider
from app.integrations.embedding.fake import FakeEmbeddingProvider


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
    """依 config.provider 選擇實作。cloud 缺 endpoint、api_key 或 model 時拋 ValueError。"""
    if config.provider == "fake":
        return FakeEmbeddingProvider(dim=config.dim)
    if config.provider == "cloud":
        required = {"endpoint": config.endpoint, "api_key": config.api_key, "model": config.model}
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"embedding provider=cloud 缺少設定：{'、'.join(missing)}")
        return CloudEmbeddingProvider(
            endpoint=config.endpoint,  # type: ignore[arg-type]
            api_key=config.api_key,  # type: ignore[arg-type]
            model=config.model,  # type: ignore[arg-type]
            dim=config.dim,
        )
    raise ValueError(f"未知的 embedding provider：{config.provider}")
