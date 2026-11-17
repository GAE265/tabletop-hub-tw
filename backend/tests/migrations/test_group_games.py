"""揪團與遊戲的對應表 group_games 的 migration。

情境對應 openspec/changes/update-groups-shop-game-pickers/specs/groups/spec.md
「揪團與遊戲的資料表」。
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_groups_tables import migrate

BEFORE = "0005"
START = datetime.now(UTC) + timedelta(days=3)


@pytest.fixture
def url() -> str:
    """每個測試一個新的資料庫，先升級到 group_games 之前的版本。"""
    db_url = recreate_database(Settings().database_url, "group_games")
    migrate(db_url, "upgrade", BEFORE)
    return db_url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    yield engine
    engine.dispose()


def insert_game(conn: Connection, bgg_id: int, name: str) -> int:
    return conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (:bgg, :name, :name, 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
        ),
        {"bgg": bgg_id, "name": name},
    )


def insert_group(conn: Connection, **extra: object) -> uuid.UUID:
    shop = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
    user = conn.scalar(
        text("INSERT INTO auth_users (display_name, role) VALUES ('玩家', 'player') RETURNING id")
    )
    columns = ["shop_id", "organizer_id", "title", "start_at", "end_at", "capacity", *extra]
    values = {
        "shop_id": shop,
        "organizer_id": user,
        "title": "週末揪團",
        "start_at": START,
        "end_at": START + timedelta(hours=2),
        "capacity": 4,
        **extra,
    }
    return conn.scalar(
        text(
            f"INSERT INTO groups ({', '.join(columns)}) "
            f"VALUES ({', '.join(':' + c for c in columns)}) RETURNING id"
        ),
        values,
    )


def group_columns(engine: Engine) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns("groups")}


def test_upgrade_moves_existing_game_and_drops_column(url: str, engine: Engine) -> None:
    with engine.begin() as conn:
        game = insert_game(conn, 1, "阿瓦隆")
        with_game = insert_group(conn, game_id=game)
        without_game = insert_group(conn)
    migrate(url)
    assert "game_id" not in group_columns(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT group_id, game_id, position FROM group_games")).all()
    assert [tuple(row) for row in rows] == [(with_game, game, 1)]
    assert without_game not in {row[0] for row in rows}


def test_table_and_columns_have_chinese_comments(url: str, engine: Engine) -> None:
    migrate(url)
    inspector = inspect(engine)
    assert inspector.get_table_comment("group_games")["text"]
    for column in inspector.get_columns("group_games"):
        assert column["comment"], column["name"]


def test_deleting_game_removes_link_but_keeps_group(url: str, engine: Engine) -> None:
    migrate(url)
    with engine.begin() as conn:
        game = insert_game(conn, 1, "阿瓦隆")
        group = insert_group(conn)
        conn.execute(
            text("INSERT INTO group_games (group_id, game_id, position) VALUES (:g, :x, 1)"),
            {"g": group, "x": game},
        )
        conn.execute(text("DELETE FROM games WHERE id = :id"), {"id": game})
        links = conn.scalar(text("SELECT count(*) FROM group_games"))
        groups = conn.scalar(text("SELECT count(*) FROM groups"))
    assert (links, groups) == (0, 1)


def test_deleting_group_removes_links(url: str, engine: Engine) -> None:
    migrate(url)
    with engine.begin() as conn:
        game = insert_game(conn, 1, "阿瓦隆")
        group = insert_group(conn)
        conn.execute(
            text("INSERT INTO group_games (group_id, game_id, position) VALUES (:g, :x, 1)"),
            {"g": group, "x": game},
        )
        conn.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group})
        assert conn.scalar(text("SELECT count(*) FROM group_games")) == 0


def test_same_game_twice_is_rejected(url: str, engine: Engine) -> None:
    migrate(url)
    with engine.begin() as conn:
        game = insert_game(conn, 1, "阿瓦隆")
        group = insert_group(conn)
    sql = text("INSERT INTO group_games (group_id, game_id, position) VALUES (:g, :x, :p)")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(sql, {"g": group, "x": game, "p": 1})
        conn.execute(sql, {"g": group, "x": game, "p": 2})


def test_downgrade_restores_first_game(url: str, engine: Engine) -> None:
    migrate(url)
    with engine.begin() as conn:
        first = insert_game(conn, 1, "阿瓦隆")
        second = insert_game(conn, 2, "馬可波羅")
        group = insert_group(conn)
        sql = text("INSERT INTO group_games (group_id, game_id, position) VALUES (:g, :x, :p)")
        conn.execute(sql, {"g": group, "x": second, "p": 2})
        conn.execute(sql, {"g": group, "x": first, "p": 1})
    migrate(url, "downgrade", BEFORE)
    assert "group_games" not in inspect(engine).get_table_names()
    with engine.connect() as conn:
        restored = conn.scalar(text("SELECT game_id FROM groups WHERE id = :id"), {"id": group})
    assert restored == first
