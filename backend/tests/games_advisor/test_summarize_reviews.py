"""summarize-reviews：產生心得摘要（spec §8.3、§7.2）。

service 的測試：假的 repository、FakeLLMProvider、FakeEmbeddingProvider，不連資料庫。
LLM 出錯時的重試與跳過在上標籤測（spec §8.7），這裡不重測。
"""

from typing import Any

import pytest

from app.domains.games_advisor import service
from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.embedding.errors import EmbeddingError
from app.integrations.embedding.factory import EmbeddingConfig
from app.integrations.embedding.fake import FakeEmbeddingProvider
from app.integrations.llm.fake import FakeLLMProvider
from tests.games_advisor.fakes import (
    FakeEmbeddingProviderFailingOnCall,
    FakeGameRepository,
    FakeReviewRepository,
)
from tests.games_advisor.support import exported, make_review, reviews_data

DIM = 8
SUMMARY = "大家都說這款桌遊氣氛熱鬧，規則簡單，很適合聚會。"
FAKE_CONFIG = EmbeddingConfig(provider="fake", dim=DIM)
OLD_SUMMARY = {"summary": "舊的心得摘要", "embedding": [1.0] * DIM, "embedding_model": "old"}


def two_games() -> FakeGameRepository:
    return FakeGameRepository([exported(1, game_id=1), exported(2, game_id=2)])


def two_reviews_each() -> dict[str, Any]:
    """第 1、2 款各有 2 篇心得。"""
    return reviews_data(
        [make_review(1, 1), make_review(1, 2), make_review(2, 1), make_review(2, 2)]
    )


def new_summary(embedding_model: str = "fake") -> dict[str, Any]:
    """service 這次應該寫入的那一列。"""
    return {
        "summary": SUMMARY,
        "embedding": FakeEmbeddingProvider(DIM).embed([SUMMARY])[0],
        "embedding_model": embedding_model,
    }


def summarize(
    store: FakeReviewRepository,
    data: dict[str, Any],
    *,
    llm: FakeLLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
    embedding_config: EmbeddingConfig = FAKE_CONFIG,
    only_bgg_ids: list[int] | None = None,
) -> Any:
    return service.summarize_reviews(
        two_games(),
        store,
        data,
        llm=llm or FakeLLMProvider(reply=SUMMARY),
        embedding=embedding or FakeEmbeddingProvider(DIM),
        embedding_config=embedding_config,
        only_bgg_ids=only_bgg_ids,
    )


def test_each_game_gets_one_llm_call_with_all_its_reviews() -> None:
    store = FakeReviewRepository()
    llm = FakeLLMProvider(reply=SUMMARY)

    result = summarize(store, two_reviews_each(), llm=llm)

    assert [call.method for call in llm.calls] == ["generate", "generate"]
    for call, number, other in zip(llm.calls, (1, 2), (2, 1), strict=True):
        prompt = call.kwargs["prompt"]
        for index in (1, 2):
            assert make_review(number, index)["text"] in prompt
            assert make_review(other, index)["text"] not in prompt
    assert store.summaries == {1: new_summary(), 2: new_summary()}
    assert result.skipped == []
    assert result.exit_code == 0


def test_fake_embedding_is_recorded_as_fake() -> None:
    store = FakeReviewRepository()

    summarize(store, two_reviews_each(), embedding_config=EmbeddingConfig(provider="fake", dim=DIM))

    assert {row["embedding_model"] for row in store.summaries.values()} == {"fake"}


def test_embedding_model_name_is_recorded() -> None:
    store = FakeReviewRepository()
    config = EmbeddingConfig(
        provider="cloud", dim=DIM, endpoint="https://example.invalid", api_key="k", model="m1"
    )

    summarize(store, two_reviews_each(), embedding_config=config)

    assert {row["embedding_model"] for row in store.summaries.values()} == {"m1"}


def test_rerun_replaces_the_old_summary() -> None:
    store = FakeReviewRepository()
    store.summaries[1] = dict(OLD_SUMMARY)

    summarize(store, two_reviews_each())

    assert store.summaries[1] == new_summary()


def test_bgg_id_option_limits_the_run_to_that_game() -> None:
    store = FakeReviewRepository()
    store.summaries[1] = dict(OLD_SUMMARY)
    llm = FakeLLMProvider(reply=SUMMARY)

    summarize(store, two_reviews_each(), llm=llm, only_bgg_ids=[900002])

    assert len(llm.calls) == 1
    assert make_review(2, 1)["text"] in llm.calls[0].kwargs["prompt"]
    assert store.summaries == {1: OLD_SUMMARY, 2: new_summary()}


def test_embedding_failure_skips_that_game_and_keeps_its_old_summary() -> None:
    store = FakeReviewRepository()
    store.summaries[1] = dict(OLD_SUMMARY)
    # 第 1 次呼叫 embed（第 1 款）失敗，第 2 次（第 2 款）照常
    embedding = FakeEmbeddingProviderFailingOnCall(
        DIM, fail_on=1, error=EmbeddingError("模型回傳零向量")
    )

    result = summarize(store, two_reviews_each(), embedding=embedding)

    assert store.summaries == {1: OLD_SUMMARY, 2: new_summary()}
    assert [skipped.bgg_id for skipped in result.skipped] == [900001]
    assert "模型回傳零向量" in result.skipped[0].reason
    assert result.exit_code == 2


def test_game_without_reviews_loses_its_old_summary() -> None:
    store = FakeReviewRepository()
    store.summaries[2] = dict(OLD_SUMMARY)
    llm = FakeLLMProvider(reply=SUMMARY)
    # 只有第 1 款有心得
    data = reviews_data([make_review(1, 1), make_review(1, 2)])

    result = summarize(store, data, llm=llm)

    assert len(llm.calls) == 1
    assert store.summaries == {1: new_summary()}
    assert result.exit_code == 0


# --- 拒絕執行：什麼都不寫，也不呼叫模型（spec §7.2 規則 1） ---


def test_refuses_when_reviews_mention_a_game_that_is_not_in_the_database() -> None:
    store = FakeReviewRepository()
    store.summaries[1] = dict(OLD_SUMMARY)
    llm = FakeLLMProvider(reply=SUMMARY)
    embedding = FakeEmbeddingProvider(DIM)
    data = reviews_data([make_review(1, 1), make_review(1, 2, bgg_id=900009)])

    with pytest.raises(service.Refused) as refused:
        summarize(store, data, llm=llm, embedding=embedding)

    assert "900009" in str(refused.value)
    assert llm.calls == []
    assert embedding.calls == []
    assert store.summaries == {1: OLD_SUMMARY}


def test_refuses_bgg_id_option_that_is_not_in_the_database() -> None:
    store = FakeReviewRepository()
    llm = FakeLLMProvider(reply=SUMMARY)
    embedding = FakeEmbeddingProvider(DIM)

    with pytest.raises(service.Refused) as refused:
        summarize(
            store, two_reviews_each(), llm=llm, embedding=embedding, only_bgg_ids=[900002, 900009]
        )

    assert "900009" in str(refused.value)
    assert llm.calls == []
    assert embedding.calls == []
    assert store.summaries == {}
