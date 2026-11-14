"""import-games：匯入桌遊（spec §8.1）。指令經過 main()，連測試用的 PostgreSQL。"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine

from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    CommandResult,
    delete_game,
    make_game,
    peek_next_id,
    read_games,
    seed_game,
    snapshot,
    stored,
    write_games_file,
)

# 第 5、3、1、4 款，順序刻意和檔案不同
FIRST_FOUR = "900005,900003,900001,900004"
FIRST_FOUR_NUMBERS = [5, 3, 1, 4]

Games = list[dict[str, Any]]


def five_games() -> Games:
    return [make_game(number) for number in range(1, 6)]


def import_games(
    run_command: RunCommand, path: Path, first_four: str = FIRST_FOUR
) -> CommandResult:
    return run_command("import-games", str(path), "--first-four", first_four)


def assert_imported_in_first_four_order(db: Engine) -> None:
    """--first-four 的 4 款依序是 1–4 號，剩下的第 2 款是 5 號；欄位、類型和檔案相同。"""
    expected = [
        {"id": game_id, **stored(make_game(number))}
        for game_id, number in enumerate([*FIRST_FOUR_NUMBERS, 2], start=1)
    ]
    assert read_games(db) == expected


# --- 正常情況 ---


def test_first_four_get_ids_1_to_4_and_the_rest_follow_file_order(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    result = import_games(run_command, write_games_file(tmp_path, five_games()))

    assert result.code == 0, result.err
    assert_imported_in_first_four_order(games_db)
    assert "5 款" in result.out
    # 印出 1–4 號各是哪一款
    lines = result.out.splitlines()
    for game_id, number in enumerate(FIRST_FOUR_NUMBERS, start=1):
        name = make_game(number)["name"]
        assert any(f"{game_id} 號" in line and name in line for line in lines), result.out
    # 提醒接著匯出、放進團隊共用資料夾
    assert "export-games" in result.out
    assert "GAE265G5" in result.out


def test_next_game_after_import_gets_the_next_number(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    assert import_games(run_command, write_games_file(tmp_path, five_games())).code == 0

    extra = make_game(1, bgg_id=900099)
    assert seed_game(games_db, extra) == 6


def test_empty_table_with_used_counter_still_starts_from_1(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    # games 是空的，但計數器已經不是 1：以前寫入過又刪掉
    delete_game(games_db, seed_game(games_db, make_game(1)))
    assert peek_next_id(games_db) == 2

    result = import_games(run_command, write_games_file(tmp_path, five_games()))

    assert result.code == 0, result.err
    assert_imported_in_first_four_order(games_db)


# --- 狀態衝突 ---


def test_refuses_when_games_already_exist(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_game(games_db, make_game(1, bgg_id=900099))
    before = snapshot(games_db)

    result = import_games(run_command, write_games_file(tmp_path, five_games()))

    assert result.code == 1
    assert "sync-games" in result.err
    assert snapshot(games_db) == before


# --- --first-four 不對 ---


@pytest.mark.parametrize(
    "first_four",
    [
        pytest.param("900005,900003,900001", id="只給 3 個"),
        pytest.param("900005,900003,900001,900004,900002", id="給了 5 個"),
        pytest.param("900005,900003,900001,900001", id="有重複"),
    ],
)
def test_refuses_first_four_that_is_not_four_distinct_ids(
    games_db: Engine, run_command: RunCommand, tmp_path: Path, first_four: str
) -> None:
    before = snapshot(games_db)

    result = import_games(run_command, write_games_file(tmp_path, five_games()), first_four)

    assert result.code == 1
    assert "--first-four" in result.err
    assert snapshot(games_db) == before


def test_refuses_first_four_with_bgg_id_missing_from_file(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    before = snapshot(games_db)

    result = import_games(
        run_command, write_games_file(tmp_path, five_games()), "900005,900003,900001,900009"
    )

    assert result.code == 1
    assert "--first-four" in result.err
    assert "900009" in result.err
    assert snapshot(games_db) == before


def test_missing_first_four_exits_with_1_not_argparse_default(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    # 結束碼 2 在 spec §7.2 是「部分完成」，參數打錯不能用它
    before = snapshot(games_db)

    result = run_command("import-games", str(write_games_file(tmp_path, five_games())))

    assert result.code == 1
    assert "--first-four" in result.err
    assert snapshot(games_db) == before


# --- 檔案內容不對：整份拒絕，印出是哪一款（bgg_id）的哪個欄位 ---


def _without_name(games: Games) -> None:
    del games[2]["name"]


def _blank_name(games: Games) -> None:
    games[2]["name"] = "   "


def _min_players_over_max(games: Games) -> None:
    games[2]["min_players"] = games[2]["max_players"] + 1


def _weight_too_high(games: Games) -> None:
    games[2]["weight"] = 5.5


def _duplicate_bgg_id(games: Games) -> None:
    # 改第 2 款，它不在 --first-four 裡，才不會同時觸發 --first-four 的檢查
    games[1]["bgg_id"] = 900003


def _unknown_type(games: Games) -> None:
    games[2]["types"] = ["partyy"]


def _misspelled_field(games: Games) -> None:
    games[2]["min_player"] = games[2].pop("min_players")


def _extra_id_field(games: Games) -> None:
    games[2]["id"] = 3


def _zero_min_playtime(games: Games) -> None:
    games[2]["min_playtime"] = 0


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        pytest.param(_without_name, "name", id="缺必填欄位 name"),
        pytest.param(_blank_name, "name", id="name 是空白"),
        pytest.param(_min_players_over_max, "min_players", id="min_players 大於 max_players"),
        pytest.param(_weight_too_high, "weight", id="weight 是 5.5"),
        pytest.param(_duplicate_bgg_id, "bgg_id", id="兩款的 bgg_id 相同"),
        pytest.param(_unknown_type, "partyy", id="types 有不認得的代碼"),
        pytest.param(_misspelled_field, "min_player", id="欄位拼錯成 min_player"),
        pytest.param(_extra_id_field, "id", id="多帶了 id"),
        pytest.param(_zero_min_playtime, "min_playtime", id="min_playtime 是 0"),
    ],
)
def test_refuses_whole_file_when_one_game_is_invalid(
    games_db: Engine,
    run_command: RunCommand,
    tmp_path: Path,
    mutate: Callable[[Games], None],
    field: str,
) -> None:
    games = five_games()
    mutate(games)
    before = snapshot(games_db)

    result = import_games(run_command, write_games_file(tmp_path, games))

    assert result.code == 1
    assert "900003" in result.err
    assert field in result.err
    assert snapshot(games_db) == before


def test_refuses_when_file_does_not_exist(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    before = snapshot(games_db)

    result = import_games(run_command, tmp_path / "no-such-file.json")

    assert result.code == 1
    assert snapshot(games_db) == before


def test_refuses_when_file_is_not_valid_json(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    path = tmp_path / "games.json"
    path.write_text('{"games": [', encoding="utf-8")
    before = snapshot(games_db)

    result = import_games(run_command, path)

    assert result.code == 1
    assert snapshot(games_db) == before
