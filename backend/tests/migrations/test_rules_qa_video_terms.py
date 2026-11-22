"""0018：rules_qa_video_terms（add-rules-video-mobile MR 3，design.md D4）。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate

TABLE = "rules_qa_video_terms"


@pytest.fixture(scope="module")
def url() -> str:
    url = recreate_database(Settings().database_url, "rules_qa_video_terms")
    migrate(url, "upgrade", "0018")
    return url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE games, auth_users RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def seed(conn: Connection) -> tuple[int, object]:
    game = conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (1, '假遊戲', 'Fake', 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
        )
    )
    user = conn.scalar(
        text("INSERT INTO auth_users (display_name, role) VALUES ('管理員', 'admin') RETURNING id")
    )
    return game, user


def insert_terms(conn: Connection, game: int, user: object) -> None:
    conn.execute(
        text(
            f"INSERT INTO {TABLE} (game_id, terms, updated_by) VALUES (:g, CAST(:t AS jsonb), :u)"
        ),
        {"g": game, "t": '[{"en": "Red card", "zh": "紅牌"}]', "u": user},
    )


def test_table_and_columns_have_chinese_comments(engine: Engine):
    inspector = inspect(engine)
    assert inspector.get_table_comment(TABLE)["text"]
    columns = {c["name"]: c for c in inspector.get_columns(TABLE)}
    assert set(columns) == {"game_id", "terms", "updated_by", "updated_at"}
    for column in columns.values():
        assert column["comment"], column["name"]
        assert not column["nullable"], column["name"]


def test_insert_defaults(engine: Engine):
    with engine.begin() as conn:
        game, user = seed(conn)
        insert_terms(conn, game, user)
        row = conn.execute(text(f"SELECT * FROM {TABLE} WHERE game_id = :g"), {"g": game}).one()
    assert row.terms == [{"en": "Red card", "zh": "紅牌"}]
    assert row.updated_at is not None


def test_one_table_per_game(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        game, user = seed(conn)
        insert_terms(conn, game, user)
        insert_terms(conn, game, user)


def test_game_with_terms_cannot_be_deleted(engine: Engine):
    with engine.begin() as conn:
        game, user = seed(conn)
        insert_terms(conn, game, user)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE id = :g"), {"g": game})


def test_downgrade_removes_table(url: str):
    try:
        migrate(url, "downgrade", "0017")
        engine = create_engine(url)
        try:
            assert TABLE not in inspect(engine).get_table_names()
        finally:
            engine.dispose()
    finally:
        migrate(url, "upgrade", "0018")
