"""sync-vocabulary：同步詞彙表（spec §8.6）。

service 的測試：假的 repository，不連資料庫。刪標籤時連帶刪除、同步到一半失敗整份回滾，
另外用 PostgreSQL 測（test_tag_repository、test_vocabulary_commands）。
"""

import copy
from typing import Any

import pytest

from app.domains.games_advisor import service
from tests.games_advisor.fakes import FakeTagRepository
from tests.games_advisor.support import exported, make_game, make_tag, vocabulary_data


def store_with(*codes: str) -> FakeTagRepository:
    """資料表已經有這幾個標籤。"""
    store = FakeTagRepository()
    for code in codes:
        tag = make_tag(code)
        store.tags[code] = {"name": tag["name"], "definition": tag["definition"]}
    return store


def give_tag(store: FakeTagRepository, code: str, *numbers: int, confidence: float = 0.8) -> None:
    """讓第 numbers 款桌遊有這個標籤。"""
    store.game_tags[code] = [
        {"game": exported(number, game_id=number), "confidence": confidence} for number in numbers
    ]


def sync(store: FakeTagRepository, *tags: dict[str, Any]) -> Any:
    return service.sync_vocabulary(store, vocabulary_data(*tags))


def printed(result: Any) -> str:
    """同步結束時印給立倫看的文字。"""
    return "\n".join(result.lines)


def test_empty_table_gets_all_tags_from_the_file() -> None:
    store = FakeTagRepository()
    tags = [make_tag("laughter"), make_tag("scheming"), make_tag("luck")]

    sync(store, *tags)

    assert store.list_tags() == sorted(tags, key=lambda tag: tag["code"])


def test_removed_code_deletes_the_tag_from_every_game() -> None:
    store = store_with("laughter", "scheming")
    give_tag(store, "laughter", 1, 2)

    result = sync(store, make_tag("scheming"))

    assert store.list_tag_codes() == ["scheming"]
    assert "laughter" not in store.game_tags
    # 印出哪幾款少了哪個標籤
    assert "laughter" in printed(result)
    assert make_game(1)["name"] in printed(result)
    assert make_game(2)["name"] in printed(result)


def test_new_code_is_added_with_a_reminder_to_tag_again() -> None:
    store = store_with("laughter")
    give_tag(store, "laughter", 1)

    result = sync(store, make_tag("laughter"), make_tag("scheming"))

    assert store.list_tag_codes() == ["laughter", "scheming"]
    # 還沒有任何桌遊有新的標籤
    assert "scheming" not in store.game_tags
    assert "重跑上標籤" in printed(result)


def test_changed_code_counts_as_remove_and_add() -> None:
    store = store_with("laughter")
    give_tag(store, "laughter", 1, 2)

    # 名稱、定義都沒變，只把代碼從 laughter 改成 laughing
    result = sync(store, make_tag("laughter", code="laughing"))

    assert store.list_tag_codes() == ["laughing"]
    assert "laughter" not in store.game_tags
    assert "laughing" not in store.game_tags
    assert make_game(1)["name"] in printed(result)
    assert make_game(2)["name"] in printed(result)
    assert "重跑上標籤" in printed(result)


def test_changed_definition_updates_in_place_and_keeps_game_tags() -> None:
    store = store_with("laughter", "scheming")
    give_tag(store, "laughter", 1, confidence=0.3)
    game_tags_before = copy.deepcopy(store.game_tags)

    result = sync(store, make_tag("laughter", definition="新的定義"), make_tag("scheming"))

    assert store.tags["laughter"] == {
        "name": make_tag("laughter")["name"],
        "definition": "新的定義",
    }
    assert store.game_tags == game_tags_before
    assert "laughter" in printed(result)
    assert "可以考慮重標" in printed(result)
    assert "重跑上標籤" not in printed(result)


def test_identical_file_changes_nothing_and_prints_no_reminder() -> None:
    store = store_with("laughter", "scheming")
    give_tag(store, "laughter", 1)
    before = copy.deepcopy((store.tags, store.game_tags))

    result = sync(store, make_tag("laughter"), make_tag("scheming"))

    assert (store.tags, store.game_tags) == before
    assert "重跑" not in printed(result)
    assert "重標" not in printed(result)


def test_exactly_30_tags_is_accepted() -> None:
    store = FakeTagRepository()

    sync(store, *[make_tag(f"tag_{number}") for number in range(30)])

    assert len(store.tags) == 30


# --- 格式不對：整份拒絕，資料表不變 ---


def assert_refused(*tags: dict[str, Any], mentions: str = "") -> None:
    store = store_with("laughter")
    give_tag(store, "laughter", 1)
    before = copy.deepcopy((store.tags, store.game_tags))

    with pytest.raises(service.Refused) as refused:
        sync(store, *tags)

    assert mentions in str(refused.value)
    assert (store.tags, store.game_tags) == before


@pytest.mark.parametrize(
    "code",
    [pytest.param("Laughter", id="有大寫字母"), pytest.param("2fast", id="以數字開頭")],
)
def test_refuses_code_in_wrong_format(code: str) -> None:
    # 印出是哪個代碼
    assert_refused(make_tag("laughter"), make_tag("scheming", code=code), mentions=code)


def test_refuses_duplicate_code() -> None:
    assert_refused(make_tag("laughter"), make_tag("scheming", code="laughter"), mentions="laughter")


def test_refuses_duplicate_name() -> None:
    name = make_tag("laughter")["name"]

    assert_refused(make_tag("laughter"), make_tag("scheming", name=name), mentions=name)


@pytest.mark.parametrize("field", ["name", "definition"])
def test_refuses_blank_name_or_definition(field: str) -> None:
    assert_refused(make_tag("laughter"), make_tag("scheming", **{field: "  "}), mentions=field)


def test_refuses_31_tags() -> None:
    assert_refused(*[make_tag(f"tag_{number}") for number in range(31)], mentions="30")


def test_refuses_file_without_tags() -> None:
    store = store_with("laughter")
    before = copy.deepcopy(store.tags)

    with pytest.raises(service.Refused) as refused:
        service.sync_vocabulary(store, {"vocabulary": []})

    assert "tags" in str(refused.value)
    assert store.tags == before
