"""games.result_type 的 migration（spec games-result-type）：欄位、CHECK、空值、說明、降版。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations

CHECK_COUNT_SQL = text("SELECT count(*) FROM pg_constraint WHERE conname = 'ck_games_result_type'")


def migrate(url: str, action: str = "upgrade", revision: str = "head") -> None:
    """不讀本機的 `.env` 檔執行 migration，結果才不受個人設定影響。"""
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(Settings.model_config, "env_file", None)
        mp.setenv("DATABASE_URL", url)
        mp.delenv("GAMES_ADVISOR_EMBEDDING_DIM", raising=False)
        config.get_settings.cache_clear()
        try:
            run_migrations(url, action, revision)
        finally:
            config.get_settings.cache_clear()


def insert_game(conn: Connection, bgg_id: int, **extra: object) -> None:
    columns = {
        "bgg_id": bgg_id,
        "name": f"範例{bgg_id}",
        "english_name": f"Example {bgg_id}",
        "min_players": 2,
        "max_players": 4,
        "min_playtime": 10,
        "max_playtime": 30,
        "min_age": 8,
        "weight": 2.0,
        "categories": ["Card Game"],
        "mechanics": ["Dice"],
        **extra,
    }
    names = ", ".join(columns)
    values = ", ".join(f":{name}" for name in columns)
    conn.execute(text(f"INSERT INTO games ({names}) VALUES ({values})"), columns)


def result_type_of(conn: Connection, bgg_id: int) -> str | None:
    return conn.scalar(text("SELECT result_type FROM games WHERE bgg_id = :b"), {"b": bgg_id})


def has_result_type_column(engine: Engine) -> bool:
    sql = text(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'games' AND column_name = 'result_type'"
    )
    with engine.connect() as conn:
        return conn.scalar(sql) == 1


@pytest.fixture(scope="module")
def migrated_url() -> str:
    url = recreate_database(Settings().database_url, "games_result_type")
    migrate(url)
    return url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


@pytest.mark.parametrize("value", ["faction", "score", "cooperative"])
def test_accepts_each_valid_value(engine: Engine, value: str) -> None:
    with engine.begin() as conn:
        insert_game(conn, 1, result_type=value)
        assert result_type_of(conn, 1) == value


@pytest.mark.parametrize("value", ["ranking", "", "Faction", "SCORE", " score"])
def test_rejects_invalid_value(engine: Engine, value: str) -> None:
    with engine.begin() as conn:
        insert_game(conn, 1, result_type="score")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_game(conn, 2, result_type=value)
    with engine.begin() as conn:
        assert result_type_of(conn, 2) is None
        assert result_type_of(conn, 1) == "score"


def test_update_to_invalid_value_is_rejected(engine: Engine) -> None:
    with engine.begin() as conn:
        insert_game(conn, 1, result_type="faction")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("UPDATE games SET result_type = 'ranking' WHERE bgg_id = 1"))
    with engine.begin() as conn:
        assert result_type_of(conn, 1) == "faction"


def test_omitted_result_type_is_null(engine: Engine) -> None:
    with engine.begin() as conn:
        insert_game(conn, 1)
        assert result_type_of(conn, 1) is None


def test_column_is_plain_nullable_text_with_check(engine: Engine) -> None:
    sql = text(
        "SELECT data_type, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name = 'games' AND column_name = 'result_type'"
    )
    with engine.connect() as conn:
        row = conn.execute(sql).one()
        check = conn.scalar(CHECK_COUNT_SQL)
    # text 欄位、可為空、沒有預設值；不是 PostgreSQL 原生 enum（那會顯示 USER-DEFINED）
    assert tuple(row) == ("text", "YES", None)
    assert check == 1


def test_column_has_chinese_comment_that_explains_null(engine: Engine) -> None:
    sql = text(
        "SELECT col_description('games'::regclass, a.attnum) FROM pg_attribute a "
        "WHERE a.attrelid = 'games'::regclass AND a.attname = 'result_type'"
    )
    with engine.connect() as conn:
        comment = conn.scalar(sql)
    assert comment
    assert "尚未設定" in comment


def test_upgrade_keeps_existing_games_and_leaves_result_type_null() -> None:
    url = recreate_database(Settings().database_url, "games_result_type_up")
    migrate(url, revision="0003")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            insert_game(conn, 1)
            insert_game(conn, 2, name="另一款")
        assert not has_result_type_column(engine)

        migrate(url)

        with engine.connect() as conn:
            sql = text("SELECT bgg_id, name, result_type FROM games ORDER BY bgg_id")
            rows = [tuple(row) for row in conn.execute(sql)]
        assert rows == [(1, "範例1", None), (2, "另一款", None)]
    finally:
        engine.dispose()


def test_downgrade_removes_column_and_keeps_other_data() -> None:
    url = recreate_database(Settings().database_url, "games_result_type_down")
    migrate(url)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            insert_game(conn, 1, result_type="score")

        migrate(url, "downgrade", "0003")

        assert not has_result_type_column(engine)
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT name FROM games WHERE bgg_id = 1")) == "範例1"
            assert conn.scalar(CHECK_COUNT_SQL) == 0
    finally:
        engine.dispose()
