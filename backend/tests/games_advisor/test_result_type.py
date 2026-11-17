"""games.result_type 在匯入、匯出、同步與推薦 API 的行為（spec games-result-type）。

指令經過 main()，連測試用的 PostgreSQL。
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine

from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    exported,
    make_game,
    read_games,
    seed_game,
    snapshot,
    write_export_file,
    write_games_file,
)

FIRST_FOUR = "900001,900002,900003,900004"


def result_types(db: Engine) -> list[str | None]:
    return [game["result_type"] for game in read_games(db)]


def without_result_type(game: dict[str, Any]) -> dict[str, Any]:
    """舊格式：沒有 result_type 這個欄位。"""
    return {key: value for key, value in game.items() if key != "result_type"}


def import_args(path: Path) -> tuple[str, ...]:
    return ("import-games", str(path), "--first-four", FIRST_FOUR)


# --- 匯出 ---


def test_export_includes_result_type_for_each_game(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_game(games_db, make_game(1, result_type="score"))
    seed_game(games_db, make_game(2))
    out_path = tmp_path / "export.json"

    result = run_command("export-games", "--out", str(out_path))

    assert result.code == 0, result.err
    games = json.loads(out_path.read_text(encoding="utf-8"))["games"]
    assert [game["result_type"] for game in games] == ["score", None]


# --- 匯入 ---


def test_import_stores_result_type(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = [
        make_game(1, result_type="faction"),
        make_game(2, result_type="score"),
        make_game(3, result_type="cooperative"),
        make_game(4),
    ]

    result = run_command(*import_args(write_games_file(tmp_path, games)))

    assert result.code == 0, result.err
    assert result_types(games_db) == ["faction", "score", "cooperative", None]


def test_import_old_format_without_result_type_is_accepted(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = [without_result_type(make_game(number)) for number in (1, 2, 3, 4)]

    result = run_command(*import_args(write_games_file(tmp_path, games)))

    assert result.code == 0, result.err
    assert result_types(games_db) == [None, None, None, None]


@pytest.mark.parametrize("bad_value", ["ranking", "", "Faction", 1])
def test_import_refuses_invalid_result_type_and_changes_nothing(
    games_db: Engine, run_command: RunCommand, tmp_path: Path, bad_value: object
) -> None:
    games = [make_game(number) for number in (1, 2, 3, 4)]
    games[2] = make_game(3, result_type=bad_value)
    before = snapshot(games_db)

    result = run_command(*import_args(write_games_file(tmp_path, games)))

    assert result.code == 1
    assert "900003" in result.err  # 指出是哪一款（bgg_id）
    assert "result_type" in result.err
    assert snapshot(games_db) == before


# --- 同步 ---


def test_sync_stores_result_type(games_db: Engine, run_command: RunCommand, tmp_path: Path) -> None:
    games = [exported(1, 1, result_type="cooperative"), exported(2, 2)]

    result = run_command("sync-games", str(write_export_file(tmp_path, games, next_id=3)))

    assert result.code == 0, result.err
    assert result_types(games_db) == ["cooperative", None]


def test_sync_old_format_file_is_accepted(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    games = [without_result_type(exported(number, number)) for number in (1, 2)]

    result = run_command("sync-games", str(write_export_file(tmp_path, games, next_id=3)))

    assert result.code == 0, result.err
    assert result_types(games_db) == [None, None]


def test_sync_refuses_invalid_result_type_and_changes_nothing(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_game(games_db, make_game(1, result_type="score"))
    before = snapshot(games_db)
    games = [exported(1, 1, result_type="ranking")]

    result = run_command("sync-games", str(write_export_file(tmp_path, games, next_id=2)))

    assert result.code == 1
    assert "result_type" in result.err
    assert snapshot(games_db) == before


def test_sync_overwrites_database_value_with_the_file(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_game(games_db, make_game(1, result_type="score"))
    games = [exported(1, 1)]  # 匯出檔裡這一款是空的

    result = run_command("sync-games", str(write_export_file(tmp_path, games, next_id=2)))

    assert result.code == 0, result.err
    assert result_types(games_db) == [None]


# --- 推薦 API 的回應格式不變 ---


def test_advisor_game_card_does_not_expose_result_type() -> None:
    from app.domains.games_advisor.schemas import AdvisorGame
    from app.domains.games_advisor.search import GAME_FIELDS

    assert "result_type" not in GAME_FIELDS
    assert "result_type" not in AdvisorGame.model_fields
