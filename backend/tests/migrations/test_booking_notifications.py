"""0014：booking_notifications（add-booking-notifications）。"""

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
    url = recreate_database(Settings().database_url, "booking_notifications")
    migrate(url, "upgrade", "0014")
    return url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def seed_reservation(conn: Connection) -> tuple[int, uuid.UUID]:
    shop = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
    user = conn.scalar(
        text("INSERT INTO auth_users (display_name, role) VALUES ('甲', 'player') RETURNING id")
    )
    reservation = conn.scalar(
        text(
            "INSERT INTO reservations "
            "(shop_id, reservation_code, customer_id, start_at, end_at, party_size) "
            "VALUES (:s, 'BK1', :u, now() + interval '1 day', now() + interval '2 days', 4) "
            "RETURNING id"
        ),
        {"s": shop, "u": user},
    )
    return reservation, user


def insert_notice(conn: Connection, reservation: int, user: uuid.UUID, type_: str) -> uuid.UUID:
    return conn.scalar(
        text(
            "INSERT INTO booking_notifications (user_id, reservation_id, type) "
            "VALUES (:u, :r, :t) RETURNING id"
        ),
        {"u": user, "r": reservation, "t": type_},
    )


def test_table_and_columns_have_chinese_comments(engine: Engine):
    inspector = inspect(engine)
    assert inspector.get_table_comment("booking_notifications")["text"]
    columns = {c["name"]: c for c in inspector.get_columns("booking_notifications")}
    assert set(columns) == {"id", "user_id", "reservation_id", "type", "read_at", "created_at"}
    for column in columns.values():
        assert column["comment"], column["name"]
    assert columns["read_at"]["nullable"]
    assert "未讀" in columns["read_at"]["comment"]


@pytest.mark.parametrize("type_", ["booking_confirmed", "shop_new_booking"])
def test_insert_notification_defaults(engine: Engine, type_: str):
    with engine.begin() as conn:
        reservation, user = seed_reservation(conn)
        notice = insert_notice(conn, reservation, user, type_)
        row = conn.execute(
            text("SELECT read_at, created_at FROM booking_notifications WHERE id = :id"),
            {"id": notice},
        ).one()
    assert row.read_at is None
    assert row.created_at is not None


def test_unknown_type_is_rejected(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        reservation, user = seed_reservation(conn)
        insert_notice(conn, reservation, user, "booking_overtime")


def test_unknown_reservation_is_rejected(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _, user = seed_reservation(conn)
        insert_notice(conn, 999999, user, "booking_confirmed")


def test_downgrade_removes_table(url: str):
    try:
        migrate(url, "downgrade", "0013")
        engine = create_engine(url)
        try:
            assert "booking_notifications" not in inspect(engine).get_table_names()
        finally:
            engine.dispose()
    finally:
        migrate(url, "upgrade", "0014")
