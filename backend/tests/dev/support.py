"""tests/dev 共用的輔助函式：測試用的小型資料檔、資料表筆數與內容雜湊。"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

GAMES_FILE = "games-export.json"
ADVISOR_FILE = "games_advisor_data.sql"

# seed 的桌遊步驟會寫入的 6 張表（genres 由 migration 寫入，seed 不動它）
GAMES_STEP_TABLES = (
    "games",
    "game_genres",
    "games_advisor_tags",
    "games_advisor_game_tags",
    "games_advisor_review_summaries",
    "games_advisor_review_excerpts",
)


def fake_game(game_id: int, bgg_id: int, name: str) -> dict[str, Any]:
    """匯出檔格式的一款假桌遊，只有名稱與編號不同。"""
    return {
        "id": game_id,
        "bgg_id": bgg_id,
        "name": name,
        "english_name": f"Fake Game {bgg_id}",
        "min_players": 2,
        "max_players": 4,
        "min_playtime": 30,
        "max_playtime": 60,
        "min_age": 10,
        "weight": 2.0,
        "categories": ["Card Game"],
        "mechanics": ["Hand Management"],
        "result_type": None,
        "types": ["party"],
    }


def fake_tag_sql(code: str = "fake_tag") -> str:
    """推薦資料檔格式的一行假資料：只寫一個標籤，不含心得原文與向量。"""
    return (
        "INSERT INTO public.games_advisor_tags (id, code, name, definition) VALUES "
        f"('00000000-0000-4000-8000-000000000001', '{code}', '假標籤', '測試用的假標籤');\n"
    )


def write_seed_data(
    folder: Path,
    *,
    games: list[dict[str, Any]] | None = None,
    games_text: str | None = None,
    advisor_sql: str | None = None,
) -> Path:
    """在 folder 寫一份測試用的小型資料檔，回傳 folder。

    games 是匯出檔格式的桌遊（next_id 自動算）；games_text 是直接寫進桌遊檔的文字，用來
    模擬損壞的檔案。games、games_text 都沒給就不寫桌遊檔；advisor_sql 沒給就不寫推薦資料檔。
    """
    folder.mkdir(parents=True, exist_ok=True)
    if games is not None:
        next_id = max((game["id"] for game in games), default=0) + 1
        games_text = json.dumps({"next_id": next_id, "games": games}, ensure_ascii=False)
    if games_text is not None:
        (folder / GAMES_FILE).write_text(games_text, encoding="utf-8")
    if advisor_sql is not None:
        (folder / ADVISOR_FILE).write_text(advisor_sql, encoding="utf-8")
    return folder


def table_counts(engine: Engine, tables: tuple[str, ...]) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            table: conn.scalar(text(f'SELECT count(*) FROM "{table}"')) or 0 for table in tables
        }


def fingerprints(engine: Engine, tables: tuple[str, ...]) -> dict[str, tuple[int, str]]:
    """每張表的（筆數，全部資料列的雜湊），用來確認「內容沒有變」。"""
    result = {}
    with engine.connect() as conn:
        for table in tables:
            row = conn.execute(
                text(
                    "SELECT count(*), "
                    "md5(coalesce(string_agg(md5(t::text), '' ORDER BY md5(t::text)), '')) "
                    f'FROM "{table}" AS t'
                )
            ).one()
            result[table] = (row[0], row[1])
    return result


def next_game_id(engine: Engine) -> int:
    """games.id 計數器的下一個號碼；只看，不會用掉號碼。"""
    with engine.connect() as conn:
        sequence = conn.scalar(text("SELECT pg_get_serial_sequence('games', 'id')"))
        next_or_last = "CASE WHEN is_called THEN last_value + 1 ELSE last_value END"
        return conn.scalar(text(f"SELECT {next_or_last} FROM {sequence}"))


def other_domain_tables(engine: Engine) -> tuple[str, ...]:
    """資料庫裡除了桌遊步驟那 6 張表以外的所有資料表。"""
    with engine.connect() as conn:
        names = conn.scalars(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
            )
        ).all()
    return tuple(name for name in names if name not in GAMES_STEP_TABLES)
