"""export-games：匯出共用桌遊資料（spec §8.10）。指令經過 main()，連測試用的 PostgreSQL。"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    GAME_FIELDS,
    delete_game,
    make_game,
    read_games,
    seed_game,
    snapshot,
)


def seed_three_games(db: Engine) -> None:
    for number in (1, 2, 3):
        seed_game(db, make_game(number))


def read_export(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def with_sorted_types(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**game, "types": sorted(game["types"])} for game in games]


def test_exports_all_games_with_ids_and_next_id(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_three_games(games_db)
    before = snapshot(games_db)
    out_path = tmp_path / "export.json"

    result = run_command("export-games", "--out", str(out_path))

    assert result.code == 0, result.err
    data = read_export(out_path)
    assert set(data) == {"next_id", "games"}
    assert data["next_id"] == 4
    assert [game["id"] for game in data["games"]] == [1, 2, 3]
    for game in data["games"]:
        assert set(game) == {"id", *GAME_FIELDS}
    assert with_sorted_types(data["games"]) == read_games(games_db)
    # 只讀資料庫，不改任何資料
    assert snapshot(games_db) == before
    assert "3 款" in result.out
    assert "next_id" in result.out and "4" in result.out
    assert "GAE265G5" in result.out


def test_next_id_does_not_shrink_after_deleting_the_last_game(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_three_games(games_db)
    delete_game(games_db, 3)
    out_path = tmp_path / "export.json"

    result = run_command("export-games", "--out", str(out_path))

    assert result.code == 0, result.err
    data = read_export(out_path)
    assert [game["id"] for game in data["games"]] == [1, 2]
    assert data["next_id"] == 4


def test_refuses_when_there_are_no_games(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    out_path = tmp_path / "export.json"

    result = run_command("export-games", "--out", str(out_path))

    assert result.code == 1
    assert not out_path.exists()


def test_overwrites_existing_out_file(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_three_games(games_db)
    out_path = tmp_path / "export.json"
    out_path.write_text('{"next_id": 2, "games": []}', encoding="utf-8")

    result = run_command("export-games", "--out", str(out_path))

    assert result.code == 0, result.err
    assert [game["id"] for game in read_export(out_path)["games"]] == [1, 2, 3]
