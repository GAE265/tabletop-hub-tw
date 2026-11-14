"""評估題組的比對規則（spec §15.2，§15.5 的「比對」）：一輪的預期和實際結果怎麼比。

只測比對函式本身：不呼叫模型，也不連資料庫。一輪的實際結果有三樣：每次查詢的工具參數
（照先後）、卡片上的桌遊 id、放寬的條件。
"""

from typing import Any

import pytest

from tests.games_advisor.eval_support import bgg

# BGG ID → 桌遊 id：題組檔用 BGG ID 寫桌遊，比對前換成 id（spec §15.2）
GAME_IDS = {bgg(game_id): game_id for game_id in (1, 2, 3, 4)}

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


def tool_args(**overrides: Any) -> dict[str, Any]:
    """模型送出的工具參數：strict 模式每個參數都會帶，沒用到的是 null。預設 4 人。"""
    values: dict[str, Any] = dict.fromkeys(ARGUMENT_NAMES)
    values["players"] = 4
    values.update(overrides)
    return values


def checks(
    expect: dict[str, Any],
    *,
    searches: list[dict[str, Any]] | None = None,
    cards: list[int] | None = None,
    relaxed: str | None = None,
) -> dict[str, bool]:
    """比對一輪，回傳每個項目過了沒：項目名稱 → 過或不過。"""
    from app.domains.games_advisor.evaluation import TurnOutcome, check_turn
    from app.domains.games_advisor.schemas import EvalExpect

    outcome = TurnOutcome(
        searches=searches or [],
        card_game_ids=cards or [],
        relaxed_constraint=relaxed,
    )
    results = check_turn(EvalExpect.model_validate(expect), outcome, GAME_IDS)
    return {result.name: result.passed for result in results}


def test_players_must_be_equal() -> None:
    expect = {"tool_args": {"players": 4}}

    assert checks(expect, searches=[tool_args(players=4)]) == {"tool_args.players": True}
    assert checks(expect, searches=[tool_args(players=5)]) == {"tool_args.players": False}


def test_preferences_only_need_to_include_expected() -> None:
    expect = {"tool_args": {"prefer_tags": ["laughter"]}}
    more = [tool_args(prefer_tags=["laughter", "luck"])]

    assert checks(expect, searches=more) == {"tool_args.prefer_tags": True}

    # 預期 2 個代碼還是 1 個項目，兩個都要有才算過（MR 說明的解讀 3）
    both = {"tool_args": {"prefer_tags": ["laughter", "luck"]}}
    only_one = [tool_args(prefer_tags=["laughter"])]
    assert checks(both, searches=only_one) == {"tool_args.prefer_tags": False}


def test_null_means_not_given() -> None:
    expect = {"tool_args": {"max_minutes": None}}

    assert checks(expect, searches=[tool_args(max_minutes=60)]) == {"tool_args.max_minutes": False}
    assert checks(expect, searches=[tool_args()]) == {"tool_args.max_minutes": True}


def test_tool_args_compare_first_search() -> None:
    expect = {"tool_args": {"max_minutes": 15}}
    first_15 = [tool_args(max_minutes=15), tool_args(max_minutes=30)]
    first_30 = [tool_args(max_minutes=30), tool_args(max_minutes=15)]

    # 第 1 次查詢是玩家原本說的條件，第 2 次是模型放寬後的
    assert checks(expect, searches=first_15) == {"tool_args.max_minutes": True}
    assert checks(expect, searches=first_30) == {"tool_args.max_minutes": False}


def test_exclude_bgg_ids_compare_as_game_ids() -> None:
    expect = {"tool_args": {"exclude_bgg_ids": [bgg(3)]}}

    excluded = [tool_args(exclude_game_ids=[3, 4])]
    assert checks(expect, searches=excluded) == {"tool_args.exclude_bgg_ids": True}
    not_excluded = [tool_args(exclude_game_ids=[4])]
    assert checks(expect, searches=not_excluded) == {"tool_args.exclude_bgg_ids": False}


def test_recommend_without_cards_fails() -> None:
    expect = {"action": "recommend"}

    assert checks(expect, cards=[]) == {"action": False}
    assert checks(expect, cards=[1]) == {"action": True}


def test_expect_any_and_forbid() -> None:
    expect = {"expect_any": [bgg(1), bgg(3)], "forbid": [bgg(2)]}

    assert checks(expect, cards=[1, 2]) == {"expect_any": True, "forbid": False}
    assert checks(expect, cards=[4]) == {"expect_any": False, "forbid": True}


@pytest.mark.parametrize("action", ["follow_up", "off_topic"])
def test_follow_up_and_off_topic_need_no_cards(action: str) -> None:
    expect = {"action": action}

    assert checks(expect, cards=[]) == {"action": True}
    assert checks(expect, cards=[1]) == {"action": False}


def test_tool_args_without_search_fail() -> None:
    # 寫 null（必須沒帶）的項目也一樣：沒有呼叫工具就沒有參數可以比
    expect = {"tool_args": {"players": 4, "prefer_tags": ["laughter"], "max_minutes": None}}

    assert checks(expect, searches=[]) == {
        "tool_args.players": False,
        "tool_args.prefer_tags": False,
        "tool_args.max_minutes": False,
    }


def test_relaxed_constraint_must_be_equal() -> None:
    expect = {"relaxed_constraint": "playtime"}

    assert checks(expect, relaxed=None) == {"relaxed_constraint": False}
    assert checks(expect, relaxed="playtime") == {"relaxed_constraint": True}
