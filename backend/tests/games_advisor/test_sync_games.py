"""sync-games：同步共用桌遊資料（spec §8.11）。指令經過 main()，連測試用的 PostgreSQL。"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    CommandResult,
    exported,
    make_game,
    peek_next_id,
    read_games,
    seed_game,
    seed_summary,
    snapshot,
    stored,
    summary_game_ids,
    write_export_file,
    write_games_file,
    write_json,
)

REFERENCING_TABLE = "test_other_domain_refs"

Games = list[dict[str, Any]]


def three_exported() -> Games:
    return [exported(number, game_id=number) for number in (1, 2, 3)]


def in_database(games: Games) -> Games:
    """匯出檔的這幾款同步後，read_games 應該讀到的樣子。"""
    return [stored(game) for game in games]


def sync(run_command: RunCommand, path: Path, database_url: str | None = None) -> CommandResult:
    return run_command("sync-games", str(path), database_url=database_url)


def seed_three_games(db: Engine) -> None:
    """資料庫已經有第 1–3 款（1–3 號），計數器是 4；和同步過 three_exported() 一樣。"""
    for number in (1, 2, 3):
        seed_game(db, make_game(number))


@pytest.fixture
def referencing_table(games_db: Engine) -> Iterator[str]:
    """模擬其他 domain 的表：參照 games.id，桌遊刪掉時不跟著刪（ADR 0003）。"""
    with games_db.begin() as conn:
        conn.execute(
            text(
                f"CREATE TABLE {REFERENCING_TABLE} (game_id bigint NOT NULL REFERENCES games (id))"
            )
        )
    yield REFERENCING_TABLE
    with games_db.begin() as conn:
        conn.execute(text(f"DROP TABLE {REFERENCING_TABLE}"))


# --- 正常情況 ---


def test_sync_into_empty_database_writes_games_with_file_ids(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = three_exported()

    result = sync(run_command, write_export_file(tmp_path, games, next_id=4))

    assert result.code == 0, result.err
    assert read_games(games_db) == in_database(games)
    assert "新增 3" in result.out
    assert "更新 0" in result.out
    assert "刪除 0" in result.out
    assert "next_id" in result.out


def test_next_game_after_sync_gets_next_id(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    assert sync(run_command, write_export_file(tmp_path, three_exported(), next_id=4)).code == 0

    assert seed_game(games_db, make_game(5)) == 4


def test_next_game_follows_next_id_not_the_largest_id(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    # 匯出前刪過第 3 款：只有 1、2 號，但 3 號已經給出去過，不能重用
    games = three_exported()[:2]

    assert sync(run_command, write_export_file(tmp_path, games, next_id=4)).code == 0

    assert seed_game(games_db, make_game(5)) == 4


def test_syncing_the_same_file_again_updates_in_place(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = three_exported()
    path = write_export_file(tmp_path, games, next_id=4)
    assert sync(run_command, path).code == 0

    result = sync(run_command, path)

    assert result.code == 0, result.err
    assert read_games(games_db) == in_database(games)
    assert "新增 0" in result.out
    assert "更新 3" in result.out
    assert "刪除 0" in result.out


def test_deletes_games_that_are_not_in_the_file(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = three_exported()
    path = write_export_file(tmp_path, games, next_id=4)
    assert sync(run_command, path).code == 0
    # 組員自己在本機加的桌遊
    assert seed_game(games_db, make_game(5)) == 4

    result = sync(run_command, path)

    assert result.code == 0, result.err
    assert read_games(games_db) == in_database(games)
    assert "新增 0" in result.out
    assert "更新 3" in result.out
    assert "刪除 1" in result.out
    assert peek_next_id(games_db) == 4


def test_same_id_with_another_bgg_id_is_replaced_as_a_different_game(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    # 資料庫的 2 號是另一款（第 5 款）
    for game_id, number in ((1, 1), (2, 5), (3, 3)):
        seed_game(games_db, make_game(number), game_id=game_id)
    seed_summary(games_db, 1)
    seed_summary(games_db, 2)
    games = three_exported()

    result = sync(run_command, write_export_file(tmp_path, games, next_id=4))

    assert result.code == 0, result.err
    assert read_games(games_db) == in_database(games)
    # 2 號算刪掉舊的、新增新的；1、3 號是更新
    assert "新增 1" in result.out
    assert "更新 2" in result.out
    assert "刪除 1" in result.out
    # 同一款只更新欄位，心得摘要保留；被換掉的那一款，心得摘要跟著刪
    assert summary_game_ids(games_db) == [1]


def test_types_are_replaced_as_a_whole(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = three_exported()
    assert games[1]["types"] == ["party", "family"]
    assert sync(run_command, write_export_file(tmp_path, games, next_id=4)).code == 0
    games[1]["types"] = ["party"]

    result = sync(run_command, write_export_file(tmp_path, games, next_id=4))

    assert result.code == 0, result.err
    assert read_games(games_db) == in_database(games)
    assert read_games(games_db)[1]["types"] == ["party"]


def test_export_then_sync_makes_another_database_identical(
    games_db: Engine, other_db: Engine, other_db_url: str, run_command: RunCommand, tmp_path: Path
) -> None:
    # 立倫的資料庫：匯入 5 款，再匯出
    games_file = write_games_file(tmp_path, [make_game(number) for number in range(1, 6)])
    first_four = "900005,900003,900001,900004"
    assert run_command("import-games", str(games_file), "--first-four", first_four).code == 0
    export_path = tmp_path / "export.json"
    assert run_command("export-games", "--out", str(export_path)).code == 0

    # 組員的資料庫：同步
    result = sync(run_command, export_path, database_url=other_db_url)

    assert result.code == 0, result.err
    assert len(read_games(other_db)) == 5
    assert read_games(other_db) == read_games(games_db)
    # 之後各自新增的下一款是同一個號碼
    extra = make_game(1, bgg_id=900099)
    assert seed_game(games_db, extra) == seed_game(other_db, extra) == 6


def test_swapped_ids_are_fixed_to_match_the_file(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    # 組員自己跑過 import-games，順序不同：1、2 號和匯出檔對調
    for game_id, number in ((1, 2), (2, 1), (3, 3)):
        seed_game(games_db, make_game(number), game_id=game_id)
    games = three_exported()

    result = sync(run_command, write_export_file(tmp_path, games, next_id=4))

    assert result.code == 0, result.err
    assert read_games(games_db) == in_database(games)
    assert peek_next_id(games_db) == 4


# --- 狀態衝突：其他 domain 還參照要刪的桌遊 ---


def test_refuses_when_another_table_still_references_a_game_to_delete(
    games_db: Engine, run_command: RunCommand, tmp_path: Path, referencing_table: str
) -> None:
    seed_three_games(games_db)
    with games_db.begin() as conn:
        conn.execute(text(f"INSERT INTO {referencing_table} (game_id) VALUES (3)"))
    before = snapshot(games_db)
    # 匯出檔沒有第 3 款
    path = write_export_file(tmp_path, three_exported()[:2], next_id=4)

    result = sync(run_command, path)

    assert result.code == 1
    assert make_game(3)["name"] in result.err
    assert referencing_table in result.err
    assert snapshot(games_db) == before


# --- 匯出檔內容不對：整份拒絕 ---


def _without_next_id(data: dict[str, Any]) -> None:
    del data["next_id"]


def _next_id_not_above_largest_id(data: dict[str, Any]) -> None:
    data["next_id"] = 3


def _duplicate_id(data: dict[str, Any]) -> None:
    data["games"][2]["id"] = 2


def _zero_id(data: dict[str, Any]) -> None:
    data["games"][2]["id"] = 0


def _text_id(data: dict[str, Any]) -> None:
    data["games"][2]["id"] = "a"


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        pytest.param(_without_next_id, "next_id", id="缺 next_id"),
        pytest.param(_next_id_not_above_largest_id, "next_id", id="next_id 不大於最大的 id"),
        pytest.param(_duplicate_id, "id", id="兩款的 id 相同"),
        pytest.param(_zero_id, "id", id="id 是 0"),
        pytest.param(_text_id, "id", id="id 是文字"),
    ],
)
def test_refuses_file_with_invalid_next_id_or_id(
    games_db: Engine,
    run_command: RunCommand,
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    field: str,
) -> None:
    seed_three_games(games_db)
    before = snapshot(games_db)
    data = {"next_id": 4, "games": three_exported()}
    mutate(data)

    result = sync(run_command, write_json(tmp_path / "export.json", data))

    assert result.code == 1
    assert field in result.err
    assert snapshot(games_db) == before


def test_refuses_file_when_a_game_fails_the_field_checks(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_three_games(games_db)
    before = snapshot(games_db)
    games = [exported(1, game_id=1), exported(2, game_id=2), exported(3, game_id=42, weight=5.5)]

    result = sync(run_command, write_export_file(tmp_path, games, next_id=43))

    assert result.code == 1
    # 印出是哪一款（id）的哪個欄位
    assert "42" in result.err
    assert "weight" in result.err
    assert snapshot(games_db) == before


def test_refuses_when_file_does_not_exist(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_three_games(games_db)
    before = snapshot(games_db)

    result = sync(run_command, tmp_path / "no-such-file.json")

    assert result.code == 1
    assert snapshot(games_db) == before


def test_refuses_when_file_is_not_valid_json(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_three_games(games_db)
    before = snapshot(games_db)
    path = tmp_path / "export.json"
    path.write_text('{"next_id": 4, "games": [', encoding="utf-8")

    result = sync(run_command, path)

    assert result.code == 1
    assert snapshot(games_db) == before
