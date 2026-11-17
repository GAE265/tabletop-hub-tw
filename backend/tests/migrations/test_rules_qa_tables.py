"""rules_qa 的 migration：rules_qa_videos、rules_qa_chunks（design.md D2）。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_groups_tables import migrate

NEW_TABLES = {"rules_qa_videos", "rules_qa_chunks"}


@pytest.fixture(scope="module")
def migrated_url() -> str:
    url = recreate_database(Settings().database_url, "rules_qa_tables")
    migrate(url)
    return url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def insert_game(conn: Connection, bgg_id: int = 1) -> int:
    return conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (:bgg, '血與刃的白薔薇', 'Rose', 2, 4, 30, 60, 10, 2.0, '{}', '{}') "
            "RETURNING id"
        ),
        {"bgg": bgg_id},
    )


def vector_literal(conn: Connection) -> str:
    """依資料庫欄位的實際維度產生一個向量字串。"""
    dim = conn.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'rules_qa_chunks'::regclass AND attname = 'embedding'"
        )
    )
    return "[" + ",".join(["0.1"] * dim) + "]"


def insert_chunk(conn: Connection, game_id: int, page: int = 1) -> None:
    conn.execute(
        text(
            "INSERT INTO rules_qa_chunks (game_id, page, content, embedding, embedding_model) "
            "VALUES (:g, :p, '段落', CAST(:v AS vector), 'fake')"
        ),
        {"g": game_id, "p": page, "v": vector_literal(conn)},
    )


def insert_video(conn: Connection, game_id: int, **overrides: object) -> None:
    values = {
        "g": game_id,
        "source": "youtube",
        "url": "https://youtu.be/XE-Sw_FtFFs",
        "yt": "XE-Sw_FtFFs",
        "title": "規則影片",
        **overrides,
    }
    conn.execute(
        text(
            "INSERT INTO rules_qa_videos (game_id, source, video_url, youtube_id, title) "
            "VALUES (:g, :source, :url, :yt, :title)"
        ),
        values,
    )


def test_tables_exist_with_chinese_comments(engine: Engine) -> None:
    inspector = inspect(engine)
    assert NEW_TABLES <= set(inspector.get_table_names())
    for table in NEW_TABLES:
        assert inspector.get_table_comment(table)["text"], table
        for column in inspector.get_columns(table):
            assert column["comment"], f"{table}.{column['name']}"


def test_chunk_and_video_can_be_stored(engine: Engine) -> None:
    with engine.begin() as conn:
        game = insert_game(conn)
        insert_chunk(conn, game, page=3)
        insert_video(conn, game)
        assert conn.scalar(text("SELECT count(*) FROM rules_qa_chunks")) == 1
        assert conn.scalar(text("SELECT youtube_id FROM rules_qa_videos")) == "XE-Sw_FtFFs"


def test_one_video_per_game(engine: Engine) -> None:
    with engine.begin() as conn:
        game = insert_game(conn)
        insert_video(conn, game)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_video(conn, game)


@pytest.mark.parametrize(
    "overrides",
    [
        {"source": "vimeo"},
        {"source": "youtube", "yt": None},
        {"source": "file", "yt": "XE-Sw_FtFFs"},
    ],
    ids=["unknown-source", "youtube-without-id", "file-with-youtube-id"],
)
def test_video_checks(engine: Engine, overrides: dict[str, object]) -> None:
    with engine.begin() as conn:
        game = insert_game(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_video(conn, game, **overrides)


def test_page_must_be_positive(engine: Engine) -> None:
    with engine.begin() as conn:
        game = insert_game(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_chunk(conn, game, page=0)


@pytest.mark.parametrize("table", ["rules_qa_chunks", "rules_qa_videos"])
def test_game_cannot_be_deleted_while_referenced(engine: Engine, table: str) -> None:
    """依 ADR 0003：參照 games.id 的資料不跟著桌遊刪除，資料庫擋下刪除。"""
    with engine.begin() as conn:
        game = insert_game(conn)
        if table == "rules_qa_chunks":
            insert_chunk(conn, game)
        else:
            insert_video(conn, game)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE id = :id"), {"id": game})


def test_downgrade_removes_tables() -> None:
    url = recreate_database(Settings().database_url, "rules_qa_downgrade")
    migrate(url)
    migrate(url, "downgrade", "0007")
    engine = create_engine(url)
    try:
        assert not (NEW_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()
