"""「查桌遊」工具：工具定義、參數檢查、排序、回傳給 LLM 的內容（spec §11.1–§11.7、§11.8 service）。

假的 repository、FakeEmbeddingProvider，不連資料庫。
"""

import logging
from typing import TYPE_CHECKING, Any

import pytest

from app.integrations.embedding import EmbeddingUnavailable, FakeEmbeddingProvider
from tests.games_advisor.fakes import FakeSearchRepository
from tests.games_advisor.support import make_tag

if TYPE_CHECKING:
    from app.domains.games_advisor.search import GameSearch, SearchOutcome

DIM = 4
MODEL = "m1"
TAGS = [make_tag(code) for code in ("laughter", "luck", "scheming", "tense")]
ARGUMENT_NAMES = [
    "players",
    "max_minutes",
    "min_minutes",
    "youngest_age",
    "prefer_tags",
    "avoid_tags",
    "prefer_categories",
    "avoid_categories",
    "prefer_mechanics",
    "avoid_mechanics",
    "weight_min",
    "weight_max",
    "preference_text",
    "exclude_game_ids",
]


def game(game_id: int, name: str, **overrides: Any) -> dict[str, Any]:
    """一款假桌遊：預設 2–4 人、20–30 分鐘、8 歲、難度 2。"""
    values: dict[str, Any] = {
        "id": game_id,
        "bgg_id": 800000 + game_id,
        "name": name,
        "english_name": f"Game {game_id}",
        "min_players": 2,
        "max_players": 4,
        "min_playtime": 20,
        "max_playtime": 30,
        "min_age": 8,
        "weight": 2.0,
        "categories": [],
        "mechanics": [],
    }
    values.update(overrides)
    return values


def args(**overrides: Any) -> dict[str, Any]:
    """工具參數：strict 模式下 LLM 每個參數都會帶，沒用到的是 null。預設 4 人。"""
    values: dict[str, Any] = dict.fromkeys(ARGUMENT_NAMES)
    values["players"] = 4
    values.update(overrides)
    return values


def make_search(
    repo: FakeSearchRepository, embedding: FakeEmbeddingProvider | None = None
) -> "GameSearch":
    from app.domains.games_advisor.search import GameSearch

    return GameSearch(
        games=repo,
        tags=repo,
        reviews=repo,
        embedding=embedding or FakeEmbeddingProvider(DIM),
        embedding_model=MODEL,
    )


def run(
    repo: FakeSearchRepository,
    embedding: FakeEmbeddingProvider | None = None,
    **arguments: Any,
) -> "SearchOutcome":
    search = make_search(repo, embedding)
    return search.run(args(**arguments), search.load_vocabulary())


def names(outcome: "SearchOutcome") -> list[str]:
    return [found["name"] for found in outcome.output["games"]]


# --- 排序 ---


def test_higher_tag_confidence_ranks_first() -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=3.0), game(2, "乙", weight=1.0)],
        tags=TAGS,
        game_tags={1: {"laughter": 0.9}, 2: {"laughter": 0.6}},
    )

    assert names(run(repo, prefer_tags=["laughter"])) == ["甲", "乙"]


def test_tag_below_threshold_counts_as_absent() -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.0), game(2, "乙", weight=3.0)],
        tags=TAGS,
        game_tags={1: {"laughter": 0.4}, 2: {"laughter": 0.5}},
    )

    outcome = run(repo, prefer_tags=["laughter"])

    # 0.4 不算有這個標籤；剛好 0.5 算
    assert names(outcome) == ["乙", "甲"]
    first, second = outcome.output["games"]
    assert [tag["name"] for tag in first["matched_preferences"]["tags"]] == ["歡樂爆笑"]
    assert second["matched_preferences"]["tags"] == []


def test_any_avoid_hit_ranks_after_more_positive_hits() -> None:
    repo = FakeSearchRepository(
        [
            game(1, "甲", weight=1.0, categories=["Card Game"], mechanics=["Voting"]),
            game(2, "乙", weight=3.0),
        ],
        tags=TAGS,
        game_tags={1: {"laughter": 0.9, "luck": 0.9}, 2: {"laughter": 0.9}},
    )

    outcome = run(
        repo,
        prefer_tags=["laughter"],
        prefer_categories=["Card Game"],
        prefer_mechanics=["Voting"],
        avoid_tags=["luck"],
    )

    assert names(outcome) == ["乙", "甲"]


def test_lower_avoid_score_ranks_first() -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=3.0), game(2, "乙", weight=1.0)],
        tags=TAGS,
        game_tags={1: {"luck": 0.6}, 2: {"luck": 0.9}},
    )

    assert names(run(repo, avoid_tags=["luck"])) == ["甲", "乙"]


def test_avoid_tag_below_threshold_is_not_a_hit() -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.0), game(2, "乙", weight=3.0)],
        tags=TAGS,
        game_tags={1: {"luck": 0.4}},
    )

    outcome = run(repo, avoid_tags=["luck"])

    assert names(outcome) == ["甲", "乙"]
    assert outcome.output["games"][0]["matched_avoids"]["tags"] == []


def test_rrf_merges_structured_and_similarity_ranks() -> None:
    # 結構化：甲 2 分（第 1）、乙 1 分（第 2）、丙 0 分（第 3）
    # 相似度：乙（第 1）、丙（第 2）、甲（第 3）
    # 甲 1/61＋1/63 < 乙 1/62＋1/61；丙 1/63＋1/62 最低
    repo = FakeSearchRepository(
        [
            game(1, "甲", weight=1.0, categories=["Card Game", "Party Game"]),
            game(2, "乙", weight=3.0, categories=["Card Game"]),
            game(3, "丙", weight=2.0),
        ],
        tags=TAGS,
        summary_models={1: MODEL, 2: MODEL, 3: MODEL},
        similarities={1: 0.1, 2: 0.9, 3: 0.5},
    )

    outcome = run(repo, prefer_categories=["Card Game", "Party Game"], preference_text="熱鬧")

    assert names(outcome) == ["乙", "甲", "丙"]


def test_without_preference_text_uses_structured_rank_only() -> None:
    embedding = FakeEmbeddingProvider(DIM)
    repo = FakeSearchRepository(
        [game(1, "甲", weight=3.0, categories=["Card Game"]), game(2, "乙", weight=1.0)],
        tags=TAGS,
        summary_models={1: MODEL, 2: MODEL},
        similarities={1: 0.1, 2: 0.9},
    )

    outcome = run(repo, embedding, prefer_categories=["Card Game"])

    assert names(outcome) == ["甲", "乙"]
    assert embedding.calls == []


def test_only_preference_text_uses_similarity_rank_only() -> None:
    embedding = FakeEmbeddingProvider(DIM)
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.0), game(2, "乙", weight=3.0)],
        tags=TAGS,
        summary_models={1: MODEL, 2: MODEL},
        similarities={1: 0.1, 2: 0.9},
    )

    outcome = run(repo, embedding, preference_text="想要輕鬆聊天")

    assert names(outcome) == ["乙", "甲"]
    assert embedding.calls == [["想要輕鬆聊天"]]


def test_no_preferences_sorts_by_weight_then_name_codepoint() -> None:
    # 「甲」U+7532 在「乙」U+4E59 之後，所以同難度時乙在前
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.5), game(2, "丙", weight=2.5), game(3, "乙", weight=1.5)],
        tags=TAGS,
    )

    assert names(run(repo)) == ["乙", "甲", "丙"]


def test_tied_scores_share_a_rank_and_skip_the_next() -> None:
    # 結構化：甲、乙都 2 分並列第 1，丙 1 分是第 3（不是第 2）
    # 相似度：丙第 1、甲第 2、乙第 3
    # 甲 1/61＋1/62 > 丙 1/63＋1/61 = 乙 1/61＋1/63，丙比乙輕所以在乙前面
    # 若丙算第 2，丙會和甲同分，又比甲輕，就會排到甲前面
    categories = ["Card Game", "Party Game"]
    repo = FakeSearchRepository(
        [
            game(1, "甲", weight=3.0, categories=categories),
            game(2, "乙", weight=3.0, categories=categories),
            game(3, "丙", weight=1.0, categories=["Card Game"]),
        ],
        tags=TAGS,
        summary_models={1: MODEL, 2: MODEL, 3: MODEL},
        similarities={1: 0.8, 2: 0.1, 3: 0.9},
    )

    outcome = run(repo, prefer_categories=categories, preference_text="熱鬧")

    assert names(outcome) == ["甲", "丙", "乙"]


def test_game_without_vector_ranks_last_by_similarity() -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.0), game(2, "乙", weight=3.0)],
        tags=TAGS,
        summary_models={2: MODEL},
        similarities={2: 0.1},
    )

    assert names(run(repo, preference_text="熱鬧")) == ["乙", "甲"]


def test_weight_equal_to_weight_max_is_in_range() -> None:
    repo = FakeSearchRepository([game(1, "甲", weight=2.5)], tags=TAGS)

    outcome = run(repo, weight_max=2.5)

    assert outcome.output["games"][0]["matched_preferences"]["weight_in_range"] is True


def test_returns_at_most_three_games() -> None:
    repo = FakeSearchRepository([game(i, f"桌遊{i}") for i in range(1, 6)], tags=TAGS)

    assert len(run(repo).output["games"]) == 3


# --- 心得片段 ---


def test_excerpts_use_preference_text_vector() -> None:
    vector = [1.0, 0.0, 0.0, 0.0]
    embedding = FakeEmbeddingProvider(DIM, vectors={"熱鬧": vector})
    repo = FakeSearchRepository([game(1, "甲"), game(2, "乙")], tags=TAGS)

    run(repo, embedding, preference_text="熱鬧")

    assert [call["query_vector"] for call in repo.excerpt_calls] == [vector, vector]
    assert {call["limit"] for call in repo.excerpt_calls} == {2}
    # 排序與心得片段共用同一個向量，不重算
    assert embedding.calls == [["熱鬧"]]


def test_excerpts_use_summary_vector_without_preference_text() -> None:
    repo = FakeSearchRepository([game(1, "甲"), game(2, "乙")], tags=TAGS)

    run(repo)

    assert [call["query_vector"] for call in repo.excerpt_calls] == [None, None]


def test_summary_vector_from_other_model_counts_as_missing_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.0), game(2, "乙", weight=3.0)],
        tags=TAGS,
        summary_models={1: "old-model", 2: MODEL},
        similarities={1: 0.99, 2: 0.1},
    )

    with caplog.at_level(logging.WARNING):
        outcome = run(repo, preference_text="熱鬧")

    assert names(outcome) == ["乙", "甲"]
    warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert any("甲" in message and "心得摘要" in message for message in warnings)


def test_excerpts_from_other_model_warn(caplog: pytest.LogCaptureFixture) -> None:
    repo = FakeSearchRepository(
        [game(1, "甲", weight=1.0), game(2, "乙", weight=3.0)],
        tags=TAGS,
        excerpt_models={1: ["old-model"], 2: [MODEL]},
    )

    with caplog.at_level(logging.WARNING):
        run(repo)

    warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert any("甲" in message and "心得片段" in message for message in warnings)
    assert not any("乙" in message for message in warnings)


# --- 參數檢查 ---


@pytest.mark.parametrize("players", [0, 31, None, "4", True])
def test_invalid_players_returns_error_without_query(players: Any) -> None:
    repo = FakeSearchRepository([game(1, "甲")], tags=TAGS)

    outcome = run(repo, players=players)

    assert outcome.is_error
    assert set(outcome.output) == {"error"}
    assert "人數" in outcome.output["error"]
    assert repo.filter_calls == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"weight_min": 3.0, "weight_max": 2.0},
        {"weight_max": 5.5},
        {"max_minutes": 0},
        {"min_minutes": 90, "max_minutes": 60},
        {"youngest_age": -1},
        {"prefer_tags": ["not_a_tag"]},
        {"avoid_categories": ["Not A Category"]},
        {"prefer_mechanics": ["Not A Mechanic"]},
        {"exclude_game_ids": [999]},
    ],
)
def test_other_invalid_arguments_return_error_without_query(arguments: dict[str, Any]) -> None:
    repo = FakeSearchRepository([game(1, "甲", categories=["Card Game"])], tags=TAGS)

    outcome = run(repo, **arguments)

    assert outcome.is_error
    assert set(outcome.output) == {"error"}
    assert repo.filter_calls == []


def test_blank_preference_text_counts_as_absent() -> None:
    embedding = FakeEmbeddingProvider(DIM)
    repo = FakeSearchRepository([game(1, "甲")], tags=TAGS)

    outcome = run(repo, embedding, preference_text="   ")

    assert not outcome.is_error
    assert embedding.calls == []


def test_embedding_unavailable_propagates() -> None:
    embedding = FakeEmbeddingProvider(DIM, error=EmbeddingUnavailable("連不上"))
    repo = FakeSearchRepository([game(1, "甲")], tags=TAGS)

    with pytest.raises(EmbeddingUnavailable):
        run(repo, embedding, preference_text="熱鬧")


def test_filters_are_passed_to_repository() -> None:
    repo = FakeSearchRepository([game(1, "甲"), game(2, "乙")], tags=TAGS)

    run(repo, players=3, max_minutes=60, min_minutes=10, youngest_age=9, exclude_game_ids=[2])

    assert repo.filter_calls == [
        {
            "players": 3,
            "max_minutes": 60,
            "min_minutes": 10,
            "youngest_age": 9,
            "exclude_ids": [2],
        }
    ]


# --- 回傳給 LLM 的內容 ---


def test_output_contains_basic_fields_matches_and_excerpts_only() -> None:
    excerpt = {
        "id": "11111111-1111-4111-8111-111111111111",
        "text": "大家笑成一團",
        "language": "zh-TW",
        "source_url": "https://example.com/should-not-leak",
    }
    repo = FakeSearchRepository(
        [
            game(
                1,
                "甲",
                weight=1.85,
                categories=["Card Game", "Bluffing"],
                mechanics=["Voting"],
            )
        ],
        tags=TAGS,
        game_tags={1: {"laughter": 0.9, "luck": 0.7, "tense": 0.3}},
        summary_models={1: MODEL},
        similarities={1: 0.5},
        excerpts={1: [excerpt]},
    )

    outcome = run(
        repo,
        prefer_tags=["laughter", "tense"],
        avoid_tags=["luck"],
        prefer_categories=["Card Game"],
        avoid_mechanics=["Voting"],
    )

    assert outcome.output == {
        "games": [
            {
                "id": 1,
                "name": "甲",
                "min_players": 2,
                "max_players": 4,
                "min_playtime": 20,
                "max_playtime": 30,
                "min_age": 8,
                "weight": 1.85,
                "matched_preferences": {
                    "tags": [{"name": "歡樂爆笑", "definition": "玩的過程常有大笑、吵鬧的場面"}],
                    "categories": ["Card Game"],
                    "mechanics": [],
                    "weight_in_range": None,
                },
                "matched_avoids": {
                    "tags": [
                        {"name": "運氣影響大", "definition": "勝負常常取決於抽牌或擲骰的運氣"}
                    ],
                    "categories": [],
                    "mechanics": ["Voting"],
                },
                "excerpts": [
                    {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "text": "大家笑成一團",
                        "language": "zh-TW",
                    }
                ],
            }
        ]
    }


def test_no_match_returns_empty_games() -> None:
    repo = FakeSearchRepository([game(1, "甲")], tags=TAGS)

    outcome = run(repo, players=10)

    assert not outcome.is_error
    assert outcome.output == {"games": []}


# --- 工具定義 ---


def tool_for(repo: FakeSearchRepository) -> Any:
    from app.domains.games_advisor.search import build_search_tool

    return build_search_tool(make_search(repo).load_vocabulary())


def test_tool_enums_come_from_repository() -> None:
    repo = FakeSearchRepository(
        [
            game(1, "甲", categories=["Card Game", "Party Game", "Bluffing"], mechanics=["Voting"]),
            game(2, "乙", categories=["Deduction", "Humor"], mechanics=["Drafting"]),
        ],
        tags=TAGS,
    )

    tool = tool_for(repo)
    properties = tool.parameters["properties"]

    assert tool.name == "search_games"
    assert set(properties) == set(ARGUMENT_NAMES)
    tag_codes = ["laughter", "luck", "scheming", "tense"]
    categories = ["Bluffing", "Card Game", "Deduction", "Humor", "Party Game"]
    assert properties["prefer_tags"]["items"]["enum"] == tag_codes
    assert properties["avoid_tags"]["items"]["enum"] == tag_codes
    assert properties["prefer_categories"]["items"]["enum"] == categories
    assert properties["avoid_mechanics"]["items"]["enum"] == ["Drafting", "Voting"]
    assert properties["exclude_game_ids"]["items"]["enum"] == [1, 2]
    assert (
        "laughter：歡樂爆笑——玩的過程常有大笑、吵鬧的場面"
        in properties["prefer_tags"]["description"]
    )


def test_tool_is_strict() -> None:
    tool = tool_for(FakeSearchRepository([game(1, "甲")], tags=TAGS))

    assert tool.parameters["additionalProperties"] is False
    assert set(tool.parameters["required"]) == set(tool.parameters["properties"])


def test_empty_vocabulary_drops_tag_parameters() -> None:
    tool = tool_for(FakeSearchRepository([game(1, "甲")], tags=[]))

    assert "prefer_tags" not in tool.parameters["properties"]
    assert "avoid_tags" not in tool.parameters["properties"]
    assert "prefer_tags" not in tool.parameters["required"]


def test_vocabulary_is_read_again_for_each_message() -> None:
    repo = FakeSearchRepository([game(1, "甲")], tags=TAGS)
    search = make_search(repo)
    search.load_vocabulary()

    repo.tags = [make_tag("cozy")]
    tool = build_tool(search)

    assert tool.parameters["properties"]["prefer_tags"]["items"]["enum"] == ["cozy"]


def build_tool(search: "GameSearch") -> Any:
    from app.domains.games_advisor.search import build_search_tool

    return build_search_tool(search.load_vocabulary())
