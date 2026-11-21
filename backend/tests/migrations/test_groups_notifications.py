"""0013：groups.confirmed_at 與 groups_notifications（add-groups-notifications）。"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate


@pytest.fixture(scope="module")
def url() -> str:
    url = recreate_database(Settings().database_url, "groups_notifications")
    migrate(url, "upgrade", "0013")
    return url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def seed_group(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    shop = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
    user = conn.scalar(
        text("INSERT INTO auth_users (display_name, role) VALUES ('甲', 'player') RETURNING id")
    )
    group = conn.scalar(
        text(
            "INSERT INTO groups (shop_id, organizer_id, title, start_at, end_at, capacity) "
            "VALUES (:s, :u, '團', now() + interval '1 day', now() + interval '2 days', 4) "
            "RETURNING id"
        ),
        {"s": shop, "u": user},
    )
    return group, user


def insert_notice(conn: Connection, group: uuid.UUID, user: uuid.UUID, type_: str) -> uuid.UUID:
    return conn.scalar(
        text(
            "INSERT INTO groups_notifications (user_id, group_id, type) "
            "VALUES (:u, :g, :t) RETURNING id"
        ),
        {"u": user, "g": group, "t": type_},
    )


def test_confirmed_at_is_nullable_with_comment(engine: Engine):
    column = next(c for c in inspect(engine).get_columns("groups") if c["name"] == "confirmed_at")
    assert column["nullable"]
    assert column["comment"]
    assert "空值" in column["comment"]


def test_notifications_table_and_columns_have_chinese_comments(engine: Engine):
    inspector = inspect(engine)
    assert inspector.get_table_comment("groups_notifications")["text"]
    columns = {c["name"]: c for c in inspector.get_columns("groups_notifications")}
    assert set(columns) == {"id", "user_id", "group_id", "type", "read_at", "created_at"}
    for column in columns.values():
        assert column["comment"], column["name"]
    assert columns["read_at"]["nullable"]
    assert "未讀" in columns["read_at"]["comment"]


@pytest.mark.parametrize("type_", ["group_confirmed", "group_cancelled", "waitlist_promoted"])
def test_insert_notification_defaults(engine: Engine, type_: str):
    with engine.begin() as conn:
        group, user = seed_group(conn)
        notice = insert_notice(conn, group, user, type_)
        row = conn.execute(
            text("SELECT read_at, created_at FROM groups_notifications WHERE id = :id"),
            {"id": notice},
        ).one()
    assert row.read_at is None
    assert row.created_at is not None


def test_unknown_type_is_rejected(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        group, user = seed_group(conn)
        insert_notice(conn, group, user, "group_renamed")


def test_deleting_group_deletes_its_notifications(engine: Engine):
    with engine.begin() as conn:
        group, user = seed_group(conn)
        insert_notice(conn, group, user, "group_confirmed")
        conn.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group})
        assert conn.scalar(text("SELECT count(*) FROM groups_notifications")) == 0


def test_downgrade_removes_table_and_column(url: str):
    try:
        migrate(url, "downgrade", "0012")
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            assert "groups_notifications" not in inspector.get_table_names()
            assert "confirmed_at" not in {c["name"] for c in inspector.get_columns("groups")}
        finally:
            engine.dispose()
    finally:
        migrate(url, "upgrade", "0013")
