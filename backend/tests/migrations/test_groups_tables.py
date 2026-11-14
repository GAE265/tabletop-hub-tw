"""groups 的 migration：groups、group_members 兩張表（spec groups「資料表」）。"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations

NEW_TABLES = {"groups", "group_members"}


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
    url = recreate_database(Settings().database_url, "groups_tables")
    migrate(url)
    return url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops, games RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def table_names(engine: Engine) -> set[str]:
    sql = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    with engine.connect() as conn:
        return set(conn.scalars(sql).all())


def insert_shop(conn: Connection) -> uuid.UUID:
    return conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('測試店') RETURNING id"))


def insert_user(conn: Connection, name: str = "玩家") -> uuid.UUID:
    return conn.scalar(
        text("INSERT INTO auth_users (display_name, role) VALUES (:n, 'player') RETURNING id"),
        {"n": name},
    )


def insert_game(conn: Connection) -> int:
    return conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (900001, '範例桌遊', 'Example Game', 2, 4, 30, 45, 10, 2.0, "
            "ARRAY['Card Game'], ARRAY['Hand Management']) RETURNING id"
        )
    )


def insert_group(
    conn: Connection,
    shop_id: uuid.UUID,
    organizer_id: uuid.UUID,
    *,
    capacity: int = 4,
    start: str = "2030-01-01 11:00+00",
    end: str = "2030-01-01 13:00+00",
    game_id: int | None = None,
) -> uuid.UUID:
    return conn.scalar(
        text(
            "INSERT INTO groups (shop_id, organizer_id, title, start_at, end_at, capacity, game_id)"
            " VALUES (:shop, :org, '週末揪團', :start, :end, :cap, :game) RETURNING id"
        ),
        {
            "shop": shop_id,
            "org": organizer_id,
            "start": start,
            "end": end,
            "cap": capacity,
            "game": game_id,
        },
    )


def test_upgrade_creates_tables(engine: Engine):
    assert NEW_TABLES <= table_names(engine)


def test_ids_are_generated_uuids(engine: Engine):
    with engine.begin() as conn:
        shop, user = insert_shop(conn), insert_user(conn)
        group_id = insert_group(conn, shop, user)
        member_id = conn.scalar(
            text(
                "INSERT INTO group_members (group_id, user_id, status) "
                "VALUES (:g, :u, 'member') RETURNING id"
            ),
            {"g": group_id, "u": user},
        )
        joined_at = conn.scalar(
            text("SELECT joined_at FROM group_members WHERE id = :id"), {"id": member_id}
        )
        status = conn.scalar(text("SELECT status FROM groups WHERE id = :id"), {"id": group_id})
    assert isinstance(group_id, uuid.UUID)
    assert isinstance(member_id, uuid.UUID)
    assert joined_at is not None
    assert status == "open"


def test_member_unique_per_group(engine: Engine):
    with engine.begin() as conn:
        shop, user = insert_shop(conn), insert_user(conn)
        group_id = insert_group(conn, shop, user)
    insert_member = text(
        "INSERT INTO group_members (group_id, user_id, status) VALUES (:g, :u, 'member')"
    )
    with engine.begin() as conn:
        conn.execute(insert_member, {"g": group_id, "u": user})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert_member, {"g": group_id, "u": user})


@pytest.mark.parametrize(
    ("overrides", "label"),
    [
        ({"capacity": 1}, "capacity 小於 2"),
        ({"start": "2030-01-01 13:00+00", "end": "2030-01-01 13:00+00"}, "結束等於開始"),
        ({"start": "2030-01-01 13:00+00", "end": "2030-01-01 12:00+00"}, "結束早於開始"),
    ],
)
def test_group_check_constraints(engine: Engine, overrides: dict, label: str):
    with engine.begin() as conn:
        shop, user = insert_shop(conn), insert_user(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_group(conn, shop, user, **overrides)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE groups SET fee = -1",
        "UPDATE groups SET status = 'ended'",
    ],
)
def test_group_value_checks(engine: Engine, sql: str):
    with engine.begin() as conn:
        shop, user = insert_shop(conn), insert_user(conn)
        insert_group(conn, shop, user)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(sql))


def test_member_status_check(engine: Engine):
    with engine.begin() as conn:
        shop, user = insert_shop(conn), insert_user(conn)
        group_id = insert_group(conn, shop, user)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("INSERT INTO group_members (group_id, user_id, status) VALUES (:g, :u, 'x')"),
            {"g": group_id, "u": user},
        )


def test_foreign_keys(engine: Engine):
    with engine.begin() as conn:
        user = insert_user(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_group(conn, uuid.uuid4(), user)


def test_deleting_game_sets_null(engine: Engine):
    with engine.begin() as conn:
        shop, user, game = insert_shop(conn), insert_user(conn), insert_game(conn)
        group_id = insert_group(conn, shop, user, game_id=game)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE id = :id"), {"id": game})
        remaining = conn.scalar(text("SELECT game_id FROM groups WHERE id = :id"), {"id": group_id})
        count = conn.scalar(text("SELECT count(*) FROM groups"))
    assert remaining is None
    assert count == 1


def test_deleting_group_deletes_members(engine: Engine):
    with engine.begin() as conn:
        shop, user = insert_shop(conn), insert_user(conn)
        group_id = insert_group(conn, shop, user)
        conn.execute(
            text("INSERT INTO group_members (group_id, user_id, status) VALUES (:g, :u, 'member')"),
            {"g": group_id, "u": user},
        )
        conn.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group_id})
        count = conn.scalar(text("SELECT count(*) FROM group_members"))
    assert count == 0


def test_downgrade_removes_tables():
    url = recreate_database(Settings().database_url, "groups_downgrade")
    migrate(url)
    migrate(url, "downgrade", "0002")
    engine = create_engine(url)
    try:
        names = table_names(engine)
        assert not (NEW_TABLES & names)
        assert {"auth_users", "booking_shops", "games"} <= names
    finally:
        engine.dispose()
