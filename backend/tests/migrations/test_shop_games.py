"""shops 的 migration：shop_games（每間店有哪些桌遊）。"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations

COLUMNS = {"id", "shop_id", "game_id", "created_at"}


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


@pytest.fixture(scope="module")
def migrated_url() -> str:
    url = recreate_database(Settings().database_url, "shop_games")
    migrate(url)
    return url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE booking_shops, games RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def insert_shop(engine: Engine) -> uuid.UUID:
    with engine.begin() as conn:
        return conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('測試店') RETURNING id"))


def insert_game(engine: Engine, bgg_id: int = 900001) -> int:
    with engine.begin() as conn:
        return conn.scalar(
            text(
                "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
                "VALUES (:b, '範例桌遊', 'Example Game', 2, 4, 30, 45, 10, 2.0, "
                "ARRAY['Card Game'], ARRAY['Hand Management']) RETURNING id"
            ),
            {"b": bgg_id},
        )


ADD = text("INSERT INTO shop_games (shop_id, game_id) VALUES (:s, :g)")


def test_upgrade_creates_table_with_columns(engine: Engine):
    with engine.connect() as conn:
        columns = set(
            conn.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'shop_games'"
                )
            ).all()
        )
    assert columns == COLUMNS


def test_id_is_generated_uuid_and_created_at_is_filled(engine: Engine):
    shop, game = insert_shop(engine), insert_game(engine)
    with engine.begin() as conn:
        conn.execute(ADD, {"s": shop, "g": game})
        row = conn.execute(text("SELECT id, created_at FROM shop_games")).one()
    assert isinstance(row.id, uuid.UUID)
    assert row.created_at is not None


def test_same_game_cannot_be_added_twice_to_one_shop(engine: Engine):
    shop, game = insert_shop(engine), insert_game(engine)
    with engine.begin() as conn:
        conn.execute(ADD, {"s": shop, "g": game})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(ADD, {"s": shop, "g": game})


def test_shop_and_game_must_exist(engine: Engine):
    shop, game = insert_shop(engine), insert_game(engine)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(ADD, {"s": uuid.uuid4(), "g": game})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(ADD, {"s": shop, "g": 999999})


def test_table_and_every_column_have_comments(engine: Engine):
    with engine.connect() as conn:
        table_comment = conn.scalar(
            text("SELECT obj_description('public.shop_games'::regclass, 'pg_class')")
        )
        missing = conn.scalars(
            text(
                "SELECT a.attname FROM pg_attribute a "
                "WHERE a.attrelid = 'public.shop_games'::regclass AND a.attnum > 0 "
                "AND NOT a.attisdropped "
                "AND col_description(a.attrelid, a.attnum) IS NULL"
            )
        ).all()
    assert table_comment
    assert missing == []


def test_downgrade_removes_table(migrated_url: str):
    url = recreate_database(Settings().database_url, "shop_games_down")
    migrate(url)
    migrate(url, "downgrade", "0014")
    engine = create_engine(url)
    with engine.connect() as conn:
        exists = conn.scalar(text("SELECT to_regclass('public.shop_games') IS NOT NULL"))
    engine.dispose()
    assert exists is False
