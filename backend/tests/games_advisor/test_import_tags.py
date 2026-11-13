"""import-tags：匯入標籤草稿（spec §8.8）。

service 的測試：假的 repository，不連資料庫。草稿與原始檔寫在 tmp_path。
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from app.domains.games_advisor import service
from tests.games_advisor.fakes import FakeGameRepository, FakeTagRepository
from tests.games_advisor.support import exported, make_game, make_review, make_tag, write_json

Entries = list[dict[str, Any]]


def tag(code: str, confidence: float) -> dict[str, Any]:
    return {"code": code, "confidence": confidence, "source_urls": [make_review(1)["source_url"]]}


def entry(number: int, *tags: dict[str, Any]) -> dict[str, Any]:
    game = make_game(number)
    return {"bgg_id": game["bgg_id"], "name": game["name"], "tags": list(tags)}


def full_draft() -> Entries:
    """上標籤產生的草稿：第 1 款 2 個標籤（其中一個只有 0.3 分），第 2 款 1 個。"""
    return [entry(1, tag("laughter", 0.8), tag("luck", 0.3)), entry(2, tag("scheming", 0.5))]


def store_with_vocabulary(*codes: str) -> FakeTagRepository:
    store = FakeTagRepository()
    for code in codes or ("laughter", "luck", "scheming", "tense"):
        definition = make_tag(code)
        store.tags[code] = {"name": definition["name"], "definition": definition["definition"]}
    return store


def give_tags(store: FakeTagRepository, game_id: int, **tags: float) -> None:
    """資料庫裡這款桌遊原本的標籤。"""
    with store.transaction():
        store.replace_game_tags(
            game_id, [{"code": code, "confidence": confidence} for code, confidence in tags.items()]
        )


def write_files(tmp_path: Path, draft: Entries, original: Entries | None = None) -> Path:
    """寫出草稿與原始檔，回傳草稿的路徑。original 沒給就和草稿一樣（立倫沒有修改）。"""
    write_json(tmp_path / "tags-draft.original.json", {"games": original or draft})
    return write_json(tmp_path / "tags-draft.json", {"games": draft})


def import_tags(store: FakeTagRepository, draft_path: Path) -> Any:
    games = FakeGameRepository([exported(number, game_id=number) for number in (1, 2)])
    return service.import_tags(games, store, draft_path)


def test_unmodified_draft_is_imported_including_low_confidence_tags(tmp_path: Path) -> None:
    store = store_with_vocabulary()

    import_tags(store, write_files(tmp_path, full_draft()))

    assert store.tags_of(1) == {"laughter": 0.8, "luck": 0.3}
    assert store.tags_of(2) == {"scheming": 0.5}


def test_deleted_tag_is_not_imported(tmp_path: Path) -> None:
    store = store_with_vocabulary()
    draft = [entry(1, tag("laughter", 0.8)), entry(2, tag("scheming", 0.5))]

    import_tags(store, write_files(tmp_path, draft, original=full_draft()))

    assert store.tags_of(1) == {"laughter": 0.8}
    assert store.tags_of(2) == {"scheming": 0.5}


def test_game_removed_from_the_draft_keeps_its_tags(tmp_path: Path) -> None:
    store = store_with_vocabulary()
    give_tags(store, 2, tense=0.9)
    draft = full_draft()[:1]

    import_tags(store, write_files(tmp_path, draft, original=full_draft()))

    assert store.tags_of(1) == {"laughter": 0.8, "luck": 0.3}
    assert store.tags_of(2) == {"tense": 0.9}


def test_draft_with_one_game_leaves_other_games_alone(tmp_path: Path) -> None:
    # 用 --bgg-id 產生的草稿：草稿和原始檔都只有第 1 款
    store = store_with_vocabulary()
    give_tags(store, 2, tense=0.9)

    import_tags(store, write_files(tmp_path, full_draft()[:1]))

    assert store.tags_of(1) == {"laughter": 0.8, "luck": 0.3}
    assert store.tags_of(2) == {"tense": 0.9}


def test_existing_tags_are_replaced_by_the_draft(tmp_path: Path) -> None:
    store = store_with_vocabulary()
    give_tags(store, 1, tense=0.9, laughter=0.4)

    import_tags(store, write_files(tmp_path, full_draft()))

    assert store.tags_of(1) == {"laughter": 0.8, "luck": 0.3}


# --- 整份拒絕，資料庫不變 ---


def assert_refused(store: FakeTagRepository, draft_path: Path, mentions: str = "") -> None:
    give_tags(store, 1, tense=0.9)
    before = copy.deepcopy(store.game_tags)

    with pytest.raises(service.Refused) as refused:
        import_tags(store, draft_path)

    assert mentions in str(refused.value)
    assert store.game_tags == before


def test_refuses_draft_with_an_added_tag(tmp_path: Path) -> None:
    draft = full_draft()
    draft[1]["tags"].append(tag("laughter", 0.6))

    assert_refused(store_with_vocabulary(), write_files(tmp_path, draft, original=full_draft()))


def test_refuses_draft_with_a_changed_confidence(tmp_path: Path) -> None:
    draft = full_draft()
    draft[0]["tags"][0]["confidence"] = 0.9

    assert_refused(store_with_vocabulary(), write_files(tmp_path, draft, original=full_draft()))


def test_refuses_when_a_code_was_removed_from_the_vocabulary(tmp_path: Path) -> None:
    # 產生草稿之後又同步過詞彙表，luck 被刪掉了
    store = store_with_vocabulary("laughter", "scheming", "tense")

    # 提示重跑上標籤
    assert_refused(store, write_files(tmp_path, full_draft()), mentions="draft-tags")


def test_refuses_when_the_original_is_missing(tmp_path: Path) -> None:
    draft_path = write_files(tmp_path, full_draft())
    (tmp_path / "tags-draft.original.json").unlink()

    assert_refused(store_with_vocabulary(), draft_path, mentions="tags-draft.original.json")


def test_refuses_draft_with_a_game_that_is_not_in_the_database(tmp_path: Path) -> None:
    draft = [*full_draft(), {"bgg_id": 900009, "name": "不存在的桌遊", "tags": []}]

    assert_refused(store_with_vocabulary(), write_files(tmp_path, draft), mentions="900009")


def test_refuses_when_the_draft_file_does_not_exist(tmp_path: Path) -> None:
    assert_refused(store_with_vocabulary(), tmp_path / "no-such-draft.json", "no-such-draft.json")


def test_refuses_when_the_draft_is_not_valid_json(tmp_path: Path) -> None:
    draft_path = write_files(tmp_path, full_draft())
    draft_path.write_text('{"games": [', encoding="utf-8")

    assert_refused(store_with_vocabulary(), draft_path, mentions="JSON")
