"""0015：rules_qa_video_projects（add-rules-video-mobile MR 1，design.md D1）。"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate

TABLE = "rules_qa_video_projects"


@pytest.fixture(scope="module")
def url() -> str:
    url = recreate_database(Settings().database_url, "rules_qa_video_projects")
    migrate(url, "upgrade", "0015")
    return url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE games, auth_users, booking_shops RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def seed(conn: Connection) -> tuple[int, uuid.UUID, uuid.UUID]:
    game = conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (1, '假遊戲', 'Fake', 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
        )
    )
    shop = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
    user = conn.scalar(
        text(
            "INSERT INTO auth_users (display_name, role, shop_id) "
            "VALUES ('店員', 'shop_staff', :s) RETURNING id"
        ),
        {"s": shop},
    )
    return game, shop, user


def insert_project(
    conn: Connection, game: int, shop: uuid.UUID, user: uuid.UUID, number: int = 11
) -> uuid.UUID:
    return conn.scalar(
        text(
            f"INSERT INTO {TABLE} (game_id, shop_id, created_by, chapter_number, chapter_title) "
            "VALUES (:g, :s, :u, :n, '步驟三') RETURNING id"
        ),
        {"g": game, "s": shop, "u": user, "n": number},
    )


def test_table_and_columns_have_chinese_comments(engine: Engine):
    inspector = inspect(engine)
    assert inspector.get_table_comment(TABLE)["text"]
    columns = {c["name"]: c for c in inspector.get_columns(TABLE)}
    # 本章頁、參考頁、段資料等欄位由「頁面文字」「草稿工作」才加（design.md D1、D11）
    assert set(columns) == {
        "id",
        "game_id",
        "shop_id",
        "created_by",
        "chapter_number",
        "chapter_title",
        "created_at",
        "updated_at",
    }
    for column in columns.values():
        assert column["comment"], column["name"]
        assert not column["nullable"], column["name"]


def test_insert_defaults(engine: Engine):
    with engine.begin() as conn:
        project = insert_project(conn, *seed(conn))
        row = conn.execute(
            text(f"SELECT id, created_at, updated_at FROM {TABLE} WHERE id = :i"), {"i": project}
        ).one()
    assert isinstance(row.id, uuid.UUID)
    assert row.created_at is not None and row.updated_at is not None


def test_same_chapter_twice_is_allowed(engine: Engine):
    # 同店同一章可以有多個專案（2026-11-21 永傑決定），不加唯一限制
    with engine.begin() as conn:
        game, shop, user = seed(conn)
        insert_project(conn, game, shop, user)
        insert_project(conn, game, shop, user)
        assert conn.scalar(text(f"SELECT count(*) FROM {TABLE}")) == 2


def test_chapter_number_must_be_positive(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_project(conn, *seed(conn), number=0)


def test_game_with_projects_cannot_be_deleted(engine: Engine):
    # ADR 0003：刪掉遊戲不會連帶刪掉專案
    with engine.begin() as conn:
        game, shop, user = seed(conn)
        insert_project(conn, game, shop, user)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE id = :g"), {"g": game})


def test_unknown_shop_is_rejected(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        game, _, user = seed(conn)
        insert_project(conn, game, uuid.uuid4(), user)


def test_downgrade_removes_table(url: str):
    try:
        migrate(url, "downgrade", "0014")
        engine = create_engine(url)
        try:
            assert TABLE not in inspect(engine).get_table_names()
        finally:
            engine.dispose()
    finally:
        migrate(url, "upgrade", "0015")
