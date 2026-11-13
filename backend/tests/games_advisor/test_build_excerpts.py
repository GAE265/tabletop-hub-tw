"""build-excerpts：產生心得片段（spec §8.4、§7.2）。

service 的測試：假的 repository、FakeEmbeddingProvider，不連資料庫。切段函式另外在
test_excerpt_splitting 測；這裡的假心得每篇剛好是兩段，不會被合併或切開。
"""

from typing import Any

import pytest

from app.domains.games_advisor import service
from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.embedding.errors import EmbeddingError
from app.integrations.embedding.factory import EmbeddingConfig
from app.integrations.embedding.fake import FakeEmbeddingProvider
from tests.games_advisor.fakes import (
    FakeEmbeddingProviderFailingOnCall,
    FakeGameRepository,
    FakeReviewRepository,
)
from tests.games_advisor.support import (
    english_paragraphs,
    exported,
    make_review,
    review_paragraphs,
    reviews_data,
)

DIM = 8
FAKE_CONFIG = EmbeddingConfig(provider="fake", dim=DIM)
OLD_EXCERPTS = [
    {
        "text": f"舊的心得片段{index}",
        "embedding": [1.0] * DIM,
        "embedding_model": "old",
        "source_url": "https://example.com/old",
        "site_name": "舊網站",
        "language": "zh-TW",
    }
    for index in (1, 2)
]


def two_games() -> FakeGameRepository:
    return FakeGameRepository([exported(1, game_id=1), exported(2, game_id=2)])


def reviews_for_both() -> dict[str, Any]:
    """第 1 款 2 篇心得（中文、英文各一），第 2 款 1 篇。"""
    english = make_review(
        1, 2, language="en", site_name="BGG", text="\n\n".join(english_paragraphs(1, 2))
    )
    return reviews_data([make_review(1, 1), english, make_review(2, 1)])


def new_excerpts(*reviews: dict[str, Any], embedding_model: str = "fake") -> list[dict[str, Any]]:
    """這幾篇心得應該產生的心得片段：每篇兩段，照心得的順序。"""
    fake = FakeEmbeddingProvider(DIM)
    return [
        {
            "text": paragraph,
            "embedding": fake.embed([paragraph])[0],
            "embedding_model": embedding_model,
            "source_url": review["source_url"],
            "site_name": review["site_name"],
            "language": review["language"],
        }
        for review in reviews
        for paragraph in review["text"].split("\n\n")
    ]


def build(
    store: FakeReviewRepository,
    data: dict[str, Any],
    *,
    embedding: EmbeddingProvider | None = None,
    only_bgg_ids: list[int] | None = None,
) -> Any:
    return service.build_excerpts(
        two_games(),
        store,
        data,
        embedding=embedding or FakeEmbeddingProvider(DIM),
        embedding_config=FAKE_CONFIG,
        only_bgg_ids=only_bgg_ids,
    )


def test_each_game_gets_one_embed_call_and_excerpts_carry_review_fields() -> None:
    store = FakeReviewRepository()
    embedding = FakeEmbeddingProvider(DIM)
    data = reviews_for_both()
    first, second, third = data["reviews"]

    result = build(store, data, embedding=embedding)

    # 每款的片段一起送 embed：一款一次
    assert embedding.calls == [
        [*review_paragraphs(1, 1), *english_paragraphs(1, 2)],
        review_paragraphs(2, 1),
    ]
    assert store.excerpts == {1: new_excerpts(first, second), 2: new_excerpts(third)}
    assert {excerpt["language"] for excerpt in store.excerpts[1]} == {"zh-TW", "en"}
    assert result.skipped == []
    assert result.exit_code == 0


def test_rerun_replaces_all_old_excerpts() -> None:
    store = FakeReviewRepository()
    store.excerpts[1] = [dict(excerpt) for excerpt in OLD_EXCERPTS]
    data = reviews_for_both()

    build(store, data)

    assert store.excerpts[1] == new_excerpts(*data["reviews"][:2])


def test_bgg_id_option_limits_the_run_to_that_game() -> None:
    store = FakeReviewRepository()
    store.excerpts[1] = [dict(excerpt) for excerpt in OLD_EXCERPTS]
    embedding = FakeEmbeddingProvider(DIM)
    data = reviews_for_both()

    build(store, data, embedding=embedding, only_bgg_ids=[900002])

    assert len(embedding.calls) == 1
    assert store.excerpts == {1: OLD_EXCERPTS, 2: new_excerpts(data["reviews"][2])}


def test_embedding_failure_skips_that_game_and_keeps_its_old_excerpts() -> None:
    store = FakeReviewRepository()
    store.excerpts[1] = [dict(excerpt) for excerpt in OLD_EXCERPTS]
    # 第 1 次呼叫 embed（第 1 款）失敗，第 2 次（第 2 款）照常
    embedding = FakeEmbeddingProviderFailingOnCall(
        DIM, fail_on=1, error=EmbeddingError("模型回傳零向量")
    )
    data = reviews_for_both()

    result = build(store, data, embedding=embedding)

    assert store.excerpts == {1: OLD_EXCERPTS, 2: new_excerpts(data["reviews"][2])}
    assert [skipped.bgg_id for skipped in result.skipped] == [900001]
    assert "模型回傳零向量" in result.skipped[0].reason
    assert result.exit_code == 2


def test_game_without_reviews_loses_its_old_excerpts() -> None:
    store = FakeReviewRepository()
    store.excerpts[2] = [dict(excerpt) for excerpt in OLD_EXCERPTS]
    embedding = FakeEmbeddingProvider(DIM)
    # 只有第 1 款有心得
    data = reviews_data([make_review(1, 1)])

    result = build(store, data, embedding=embedding)

    assert len(embedding.calls) == 1
    assert store.excerpts == {1: new_excerpts(data["reviews"][0]), 2: []}
    assert result.exit_code == 0


# --- 拒絕執行：什麼都不寫，也不呼叫模型（spec §7.2 規則 1） ---


def test_refuses_when_reviews_mention_a_game_that_is_not_in_the_database() -> None:
    store = FakeReviewRepository()
    store.excerpts[1] = [dict(excerpt) for excerpt in OLD_EXCERPTS]
    embedding = FakeEmbeddingProvider(DIM)
    data = reviews_data([make_review(1, 1), make_review(1, 2, bgg_id=900009)])

    with pytest.raises(service.Refused) as refused:
        build(store, data, embedding=embedding)

    assert "900009" in str(refused.value)
    assert embedding.calls == []
    assert store.excerpts == {1: OLD_EXCERPTS}


def test_refuses_bgg_id_option_that_is_not_in_the_database() -> None:
    store = FakeReviewRepository()
    embedding = FakeEmbeddingProvider(DIM)

    with pytest.raises(service.Refused) as refused:
        build(store, reviews_for_both(), embedding=embedding, only_bgg_ids=[900009])

    assert "900009" in str(refused.value)
    assert embedding.calls == []
    assert store.excerpts == {}
