"""games_advisor 測試共用的假桌遊與資料庫輔助函式。

測試只用自編的假資料（AGENTS.md §2.2、spec §8.1）。這裡的函式直接用 SQL 讀寫資料庫，
不經過要測的程式，才能當作檢查的依據。
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, text

GAME_COLUMNS = [
    "bgg_id",
    "name",
    "english_name",
    "min_players",
    "max_players",
    "min_playtime",
    "max_playtime",
    "min_age",
    "weight",
    "categories",
    "mechanics",
]
# games.json 的一款：11 個資料表欄位加上 types
GAME_FIELDS = [*GAME_COLUMNS, "types"]

_TYPES = {1: ["family"], 2: ["party", "family"], 3: [], 4: ["strategy"], 5: ["thematic", "war"]}


@dataclass(frozen=True)
class CommandResult:
    """指令執行一次的結果：結束碼、印到 stdout 與 stderr 的文字。"""

    code: int
    out: str
    err: str


def make_game(number: int, **overrides: Any) -> dict[str, Any]:
    """第 number 款假桌遊（1–5），格式是 games.json 的一款。每款的欄位值都不同。"""
    game: dict[str, Any] = {
        "bgg_id": 900000 + number,
        "name": f"範例桌遊{'甲乙丙丁戊'[number - 1]}",
        "english_name": f"Example Game {'ABCDE'[number - 1]}",
        "min_players": number,
        "max_players": number + 2,
        "min_playtime": 10 * number,
        "max_playtime": 10 * number + 15,
        "min_age": 6 + number,
        "weight": 1 + number * 0.5,
        "categories": [f"Category {number}", "Card Game"],
        "mechanics": [f"Mechanic {number}"],
        "types": list(_TYPES[number]),
    }
    game.update(overrides)
    return game


def exported(number: int, game_id: int, **overrides: Any) -> dict[str, Any]:
    """匯出檔的一款：games.json 的 12 個欄位加上 id。"""
    return {"id": game_id, **make_game(number, **overrides)}


def game_columns(game: dict[str, Any]) -> dict[str, Any]:
    """只留 games 資料表的 11 個欄位（不含 id、types）。"""
    return {column: game[column] for column in GAME_COLUMNS}


def stored(game: dict[str, Any]) -> dict[str, Any]:
    """這一款寫進資料庫後，read_games 應該讀到的樣子（types 照代碼排序）。"""
    return {**game, "types": sorted(game["types"])}


def write_json(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_games_file(tmp_path: Path, games: list[dict[str, Any]]) -> Path:
    """寫出 games.json（spec §8.1）。"""
    return write_json(tmp_path / "games.json", {"games": games})


def write_export_file(
    tmp_path: Path, games: list[dict[str, Any]], next_id: int, name: str = "export.json"
) -> Path:
    """寫出匯出檔（spec §8.10）。"""
    return write_json(tmp_path / name, {"next_id": next_id, "games": games})


@contextmanager
def _connect(db: Engine | Connection) -> Iterator[Connection]:
    """給 Engine 就開一個交易並提交；給 Connection 就沿用它目前的交易。"""
    if isinstance(db, Connection):
        yield db
    else:
        with db.begin() as conn:
            yield conn


def read_games(db: Engine | Connection) -> list[dict[str, Any]]:
    """資料庫裡的全部桌遊，照 id 排；每款是 id、11 個欄位與 types（照代碼排序）。"""
    sql = text(
        f"SELECT g.id, {', '.join('g.' + column for column in GAME_COLUMNS)}, "
        "COALESCE(array_agg(t.code ORDER BY t.code) FILTER (WHERE t.code IS NOT NULL), '{}') "
        "AS types "
        "FROM games g "
        "LEFT JOIN game_game_types ggt ON ggt.game_id = g.id "
        "LEFT JOIN game_types t ON t.id = ggt.game_type_id "
        "GROUP BY g.id ORDER BY g.id"
    )
    with _connect(db) as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]


def peek_next_id(db: Engine | Connection) -> int:
    """games.id 計數器的下一個號碼；只看，不會用掉號碼。"""
    with _connect(db) as conn:
        sequence = conn.scalar(text("SELECT pg_get_serial_sequence('games', 'id')"))
        next_or_last = "CASE WHEN is_called THEN last_value + 1 ELSE last_value END"
        return conn.scalar(text(f"SELECT {next_or_last} FROM {sequence}"))


def snapshot(db: Engine | Connection) -> dict[str, Any]:
    """共用桌遊資料的完整狀態，用來確認「資料庫沒有任何變動」。"""
    return {"games": read_games(db), "next_id": peek_next_id(db)}


def seed_game(db: Engine | Connection, game: dict[str, Any], game_id: int | None = None) -> int:
    """直接用 SQL 寫入一款桌遊與它的類型，回傳 id。game_id 沒給就由資料庫自動給號。"""
    columns = list(GAME_COLUMNS)
    params = game_columns(game)
    if game_id is not None:
        columns.insert(0, "id")
        params["id"] = game_id
    sql = text(
        f"INSERT INTO games ({', '.join(columns)}) "
        f"VALUES ({', '.join(':' + column for column in columns)}) RETURNING id"
    )
    with _connect(db) as conn:
        new_id = conn.scalar(sql, params)
        for code in game["types"]:
            conn.execute(
                text(
                    "INSERT INTO game_game_types (game_id, game_type_id) "
                    "SELECT :g, id FROM game_types WHERE code = :c"
                ),
                {"g": new_id, "c": code},
            )
        return new_id


def delete_game(db: Engine | Connection, game_id: int) -> None:
    with _connect(db) as conn:
        conn.execute(text("DELETE FROM games WHERE id = :id"), {"id": game_id})


def seed_summary(db: Engine | Connection, game_id: int) -> None:
    """直接用 SQL 替一款桌遊寫入心得摘要；向量長度照資料表欄位的維度。"""
    with _connect(db) as conn:
        column_type = conn.scalar(
            text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = CAST('games_advisor_review_summaries' AS regclass) "
                "AND attname = 'embedding'"
            )
        )
        dim = int(column_type[len("vector(") : -1])
        conn.execute(
            text(
                "INSERT INTO games_advisor_review_summaries "
                "(game_id, summary, embedding, embedding_model) "
                "VALUES (:g, '心得摘要', CAST(:v AS vector), 'fake')"
            ),
            {"g": game_id, "v": "[" + ",".join(["0.5"] * dim) + "]"},
        )


def summary_game_ids(db: Engine | Connection) -> list[int]:
    """有心得摘要的桌遊 id，照 id 排。"""
    with _connect(db) as conn:
        return list(
            conn.scalars(
                text("SELECT game_id FROM games_advisor_review_summaries ORDER BY game_id")
            )
        )
