"""整合層提案 §11.1 中需要雲端實作的列：cloud 的 factory 與啟動。"""

from collections.abc import Callable

import pytest

from app.core.config import Settings
from app.integrations.embedding import EmbeddingConfig, get_embedding_provider
from app.integrations.embedding.cloud import CloudEmbeddingProvider
from app.integrations.llm import get_llm_provider
from app.integrations.llm.cloud import CloudLLMProvider
from app.main import create_app

CLOUD_LLM = {
    "llm_provider": "cloud",
    "llm_endpoint": "https://example.openai.azure.com/openai/v1/",
    "llm_api_key": "test-key",
    "llm_model": "test-deployment",
}


def test_factory_returns_cloud_llm_provider_when_settings_are_complete(
    make_settings: Callable[..., Settings],
) -> None:
    provider = get_llm_provider("cloud", make_settings(**CLOUD_LLM))

    assert isinstance(provider, CloudLLMProvider)


@pytest.mark.parametrize(
    ("field", "env_name"),
    [
        ("llm_endpoint", "LLM_ENDPOINT"),
        ("llm_api_key", "LLM_API_KEY"),
        ("llm_model", "LLM_MODEL"),
    ],
)
def test_app_startup_fails_naming_the_missing_llm_setting(
    make_settings: Callable[..., Settings], field: str, env_name: str
) -> None:
    settings = make_settings(**{key: value for key, value in CLOUD_LLM.items() if key != field})

    with pytest.raises(ValueError, match=env_name):
        create_app(settings)


def test_embedding_factory_returns_cloud_provider_when_config_is_complete() -> None:
    provider = get_embedding_provider(
        EmbeddingConfig(
            provider="cloud",
            dim=1536,
            endpoint="https://example.openai.azure.com/openai/v1/",
            api_key="test-key",
            model="test-embedding",
        )
    )

    assert isinstance(provider, CloudEmbeddingProvider)


def test_app_startup_fails_naming_the_missing_embedding_model(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(
        games_advisor_embedding_provider="cloud",
        games_advisor_embedding_endpoint="https://example.openai.azure.com/openai/v1/",
        games_advisor_embedding_api_key="test-key",
    )

    # 整合層不知道 games_advisor，錯誤訊息只能指出 EmbeddingConfig 缺 model
    with pytest.raises(ValueError, match="model"):
        create_app(settings)
