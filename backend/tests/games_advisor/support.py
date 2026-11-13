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


def embedding_dim(db: Engine | Connection) -> int:
    """資料表向量欄位的維度（建表時讀 GAMES_ADVISOR_EMBEDDING_DIM 決定）。"""
    with _connect(db) as conn:
        column_type = conn.scalar(
            text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = CAST('games_advisor_review_summaries' AS regclass) "
                "AND attname = 'embedding'"
            )
        )
    return int(column_type[len("vector(") : -1])


def _vector_text(dim: int) -> str:
    return "[" + ",".join(["0.5"] * dim) + "]"


def seed_summary(db: Engine | Connection, game_id: int, summary: str = "心得摘要") -> None:
    """直接用 SQL 替一款桌遊寫入心得摘要；向量長度照資料表欄位的維度。"""
    with _connect(db) as conn:
        conn.execute(
            text(
                "INSERT INTO games_advisor_review_summaries "
                "(game_id, summary, embedding, embedding_model) "
                "VALUES (:g, :s, CAST(:v AS vector), 'fake')"
            ),
            {"g": game_id, "s": summary, "v": _vector_text(embedding_dim(conn))},
        )


def summary_game_ids(db: Engine | Connection) -> list[int]:
    """有心得摘要的桌遊 id，照 id 排。"""
    with _connect(db) as conn:
        return list(
            conn.scalars(
                text("SELECT game_id FROM games_advisor_review_summaries ORDER BY game_id")
            )
        )


def read_summaries(db: Engine | Connection) -> list[dict[str, Any]]:
    """全部心得摘要，照桌遊 id 排；dims 是向量的長度。"""
    sql = text(
        "SELECT game_id, summary, embedding_model, vector_dims(embedding) AS dims "
        "FROM games_advisor_review_summaries ORDER BY game_id"
    )
    with _connect(db) as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]


def seed_excerpt(db: Engine | Connection, game_id: int, excerpt_text: str = "舊的心得片段") -> None:
    """直接用 SQL 替一款桌遊寫入一段心得片段。"""
    with _connect(db) as conn:
        conn.execute(
            text(
                "INSERT INTO games_advisor_review_excerpts "
                "(game_id, text, embedding, embedding_model, source_url, site_name, language) "
                "VALUES (:g, :t, CAST(:v AS vector), 'fake', "
                "'https://example.com/old', '舊網站', 'zh-TW')"
            ),
            {"g": game_id, "t": excerpt_text, "v": _vector_text(embedding_dim(conn))},
        )


def read_excerpts(db: Engine | Connection) -> list[dict[str, Any]]:
    """全部心得片段，照桌遊 id、文字排；dims 是向量的長度。"""
    sql = text(
        "SELECT game_id, text, embedding_model, source_url, site_name, language, "
        "vector_dims(embedding) AS dims "
        "FROM games_advisor_review_excerpts ORDER BY game_id, text"
    )
    with _connect(db) as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]


# --- 假心得（reviews.json，spec §8.2） ---


def review_paragraphs(number: int, index: int = 1) -> list[str]:
    """第 number 款第 index 篇假心得的兩個段落。每段約 60 字，不會被合併也不會被切開。"""
    tag = f"【第 {number} 款第 {index} 篇】"
    return [
        tag + "大家圍著桌子一邊出牌一邊笑，氣氛很熱鬧。" * 3,
        tag + "規則不難，新手玩過一輪就能跟上，很適合聚會。" * 3,
    ]


def english_paragraphs(number: int, index: int = 1) -> list[str]:
    """英文假心得的兩個段落，各 30 個單字：用單字數算也不會被合併或切開。"""
    tag = f"game{number}review{index}"
    return [
        f"{tag} " + " ".join(["laughing"] * 29),
        f"{tag} " + " ".join(["bluffing"] * 29),
    ]


def make_review(number: int, index: int = 1, **overrides: Any) -> dict[str, Any]:
    """第 number 款桌遊的第 index 篇假心得，格式是 reviews.json 的一篇。"""
    review: dict[str, Any] = {
        "bgg_id": 900000 + number,
        "source_url": f"https://example.com/game-{number}/review-{index}",
        "site_name": f"範例網站{index}",
        "title": f"第 {number} 款的心得",
        "author": None,
        "language": "zh-TW",
        "published_on": "2025-03-01",
        "retrieved_on": "2026-11-08",
        "text": "\n\n".join(review_paragraphs(number, index)),
    }
    review.update(overrides)
    return review


def reviews_data(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """reviews.json 的內容；shortfalls 後端不讀，照 Codex 的格式放一個空的。"""
    return {"reviews": reviews, "shortfalls": []}


def write_reviews_file(tmp_path: Path, reviews: list[dict[str, Any]]) -> Path:
    return write_json(tmp_path / "reviews.json", reviews_data(reviews))


# --- 假的標籤詞彙表（tag_vocabulary.json，spec §8.6） ---

_TAGS = {
    "laughter": ("歡樂爆笑", "玩的過程常有大笑、吵鬧的場面"),
    "scheming": ("勾心鬥角", "玩家之間互相猜忌、設局"),
    "luck": ("運氣影響大", "勝負常常取決於抽牌或擲骰的運氣"),
    "tense": ("緊張刺激", "玩的過程讓人屏住呼吸"),
}


def make_tag(code: str, /, **overrides: Any) -> dict[str, Any]:
    """詞彙表的一個標籤：代碼、繁中名稱、一句定義。沒列在 _TAGS 的代碼就用代碼產生。

    overrides 可以換掉任何欄位，包括 code：make_tag("laughter", code="laughing")。
    """
    name, definition = _TAGS.get(code, (f"標籤 {code}", f"{code} 的定義"))
    tag = {"code": code, "name": name, "definition": definition}
    tag.update(overrides)
    return tag


def vocabulary_data(*tags: dict[str, Any]) -> dict[str, Any]:
    return {"tags": list(tags)}


def write_vocabulary_file(tmp_path: Path, *tags: dict[str, Any]) -> Path:
    return write_json(tmp_path / "tag_vocabulary.json", vocabulary_data(*tags))


def seed_tag(db: Engine | Connection, tag: dict[str, Any]) -> None:
    """直接用 SQL 寫入一個標籤。"""
    with _connect(db) as conn:
        conn.execute(
            text(
                "INSERT INTO games_advisor_tags (code, name, definition) "
                "VALUES (:code, :name, :definition)"
            ),
            tag,
        )


def seed_game_tag(
    db: Engine | Connection, game_id: int, code: str, confidence: float = 0.8
) -> None:
    """直接用 SQL 替一款桌遊加上一個標籤。"""
    with _connect(db) as conn:
        conn.execute(
            text(
                "INSERT INTO games_advisor_game_tags (game_id, tag_id, confidence) "
                "SELECT :g, id, :c FROM games_advisor_tags WHERE code = :code"
            ),
            {"g": game_id, "c": confidence, "code": code},
        )


def read_tags(db: Engine | Connection) -> list[dict[str, Any]]:
    """資料庫的標籤詞彙表，照代碼排。"""
    sql = text("SELECT code, name, definition FROM games_advisor_tags ORDER BY code")
    with _connect(db) as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]


def read_game_tags(db: Engine | Connection) -> list[tuple[int, str, float]]:
    """每款桌遊的標籤：（桌遊 id，代碼，信心分數），照桌遊 id、代碼排。"""
    sql = text(
        "SELECT gt.game_id, t.code, gt.confidence FROM games_advisor_game_tags gt "
        "JOIN games_advisor_tags t ON t.id = gt.tag_id ORDER BY gt.game_id, t.code"
    )
    with _connect(db) as conn:
        return [tuple(row) for row in conn.execute(sql)]
