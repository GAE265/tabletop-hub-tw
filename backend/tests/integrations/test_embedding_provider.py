"""整合層提案 §11.1（embedding 的 factory 與啟動）與 §11.3（FakeEmbeddingProvider）。"""

import math
from collections.abc import Callable

import pytest

from app.core.config import Settings
from app.integrations.embedding import (
    EmbeddingConfig,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingUnavailable,
    FakeEmbeddingProvider,
    get_embedding_provider,
)
from app.main import create_app

DIM = 8

# --- §11.1 factory 與啟動 ---


def test_factory_returns_fake_with_configured_dim() -> None:
    provider = get_embedding_provider(EmbeddingConfig(provider="fake", dim=1536))

    assert isinstance(provider, FakeEmbeddingProvider)
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dim == 1536


def test_app_startup_defaults_games_advisor_embedding_to_fake(
    make_settings: Callable[..., Settings],
) -> None:
    # 全域 EMBEDDING_DIM 刻意設成別的值，確認 games_advisor 不讀它
    app = create_app(make_settings(embedding_dim=768))

    embedding = app.state.games_advisor_embedding
    assert isinstance(embedding, FakeEmbeddingProvider)
    assert embedding.dim == 1536


def test_app_startup_ignores_settings_in_shell_environment(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 本機為了跑需要金鑰的測試把真的設定載入 shell 時，一般測試仍然是「都沒填」
    monkeypatch.setenv("GAMES_ADVISOR_EMBEDDING_PROVIDER", "cloud")
    monkeypatch.setenv("GAMES_ADVISOR_EMBEDDING_DIM", "3072")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "not-a-valid-value")

    app = create_app(make_settings())

    embedding = app.state.games_advisor_embedding
    assert isinstance(embedding, FakeEmbeddingProvider)
    assert embedding.dim == 1536


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        get_embedding_provider(EmbeddingConfig(provider="nope", dim=1536))


# --- §11.3 FakeEmbeddingProvider ---


def test_unspecified_text_gets_stable_non_zero_vector() -> None:
    fake = FakeEmbeddingProvider(dim=DIM)

    [first] = fake.embed(["想要歡樂爆笑"])
    [second] = fake.embed(["想要歡樂爆笑"])

    assert first == second
    assert len(first) == DIM
    assert any(value != 0 for value in first)
    assert math.isclose(math.sqrt(sum(v * v for v in first)), 1.0)


def test_specified_text_returns_specified_vector() -> None:
    vector = [1.0] + [0.0] * (DIM - 1)
    fake = FakeEmbeddingProvider(dim=DIM, vectors={"想要歡樂爆笑": vector})

    assert fake.embed(["想要歡樂爆笑"]) == [vector]


def test_specified_vector_with_wrong_length_is_rejected_on_creation() -> None:
    with pytest.raises(ValueError):
        FakeEmbeddingProvider(dim=DIM, vectors={"想要歡樂爆笑": [1.0, 0.0]})


def test_specified_zero_vector_raises_embedding_error() -> None:
    fake = FakeEmbeddingProvider(dim=DIM, vectors={"想要歡樂爆笑": [0.0] * DIM})

    with pytest.raises(EmbeddingError):
        fake.embed(["想要歡樂爆笑"])


def test_configured_error_is_raised() -> None:
    fake = FakeEmbeddingProvider(dim=DIM, error=EmbeddingUnavailable("逾時"))

    with pytest.raises(EmbeddingUnavailable, match="逾時"):
        fake.embed(["想要歡樂爆笑"])


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_text_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        FakeEmbeddingProvider(dim=DIM).embed([text])


def test_empty_list_returns_empty_list() -> None:
    assert FakeEmbeddingProvider(dim=DIM).embed([]) == []


def test_calls_record_each_embed() -> None:
    fake = FakeEmbeddingProvider(dim=DIM)

    fake.embed(["想要歡樂爆笑"])
    fake.embed(["燒腦", "陣營"])

    assert fake.calls == [["想要歡樂爆笑"], ["燒腦", "陣營"]]
