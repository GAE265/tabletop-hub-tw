import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

SHOP = uuid.UUID("c0ffee00-0000-4000-8000-0000000000aa")
USER = uuid.UUID("a1000000-0000-4000-8000-0000000000aa")


@pytest.fixture
def base(db: Engine):
    with db.begin() as conn:
        conn.execute(text("INSERT INTO booking_shops (id, name) VALUES (:i, 's')"), {"i": SHOP})
        conn.execute(
            text("INSERT INTO auth_users (id, display_name, role) VALUES (:i, 'u', 'player')"),
            {"i": USER},
        )
        ids = [
            conn.execute(
                text(
                    "INSERT INTO booking_tables (shop_id, table_code, max_capacity) "
                    "VALUES (:s, :c, 4) RETURNING id"
                ),
                {"s": SHOP, "c": c},
            ).scalar_one()
            for c in "AB"
        ]
    return ids


def _reservation(conn, code: str) -> uuid.UUID:
    return conn.execute(
        text(
            "INSERT INTO booking_reservations (shop_id, reservation_code, user_id, start_at, "
            "end_at, party_size, status, source) VALUES (:s, :c, :u, now(), now() + interval "
            "'1 hour', 2, 'confirmed', 'online') RETURNING id"
        ),
        {"s": SHOP, "c": code, "u": USER},
    ).scalar_one()


def _occupy(conn, reservation, table, start="2026-12-01 14:00+08", end="2026-12-01 16:00+08"):
    conn.execute(
        text(
            "INSERT INTO booking_reservation_tables "
            "(shop_id, reservation_id, table_id, start_at, end_at) VALUES (:s, :r, :t, :a, :b)"
        ),
        {"s": SHOP, "r": reservation, "t": table, "a": start, "b": end},
    )


def test_same_table_overlap_is_rejected(db, base):
    with pytest.raises(IntegrityError), db.begin() as conn:
        _occupy(conn, _reservation(conn, "R1"), base[0])
        _occupy(
            conn, _reservation(conn, "R2"), base[0], "2026-12-01 15:00+08", "2026-12-01 17:00+08"
        )


def test_adjacent_and_other_table_are_allowed(db, base):
    with db.begin() as conn:
        _occupy(conn, _reservation(conn, "R1"), base[0])
        _occupy(
            conn, _reservation(conn, "R2"), base[0], "2026-12-01 16:00+08", "2026-12-01 18:00+08"
        )
        _occupy(conn, _reservation(conn, "R3"), base[1])


def test_inactive_rows_do_not_block(db, base):
    with db.begin() as conn:
        first = _reservation(conn, "R1")
        _occupy(conn, first, base[0])
        conn.execute(
            text(
                "UPDATE booking_reservation_tables SET is_active = false WHERE reservation_id = :r"
            ),
            {"r": first},
        )
        _occupy(conn, _reservation(conn, "R2"), base[0])


def test_reverse_duplicate_link_is_rejected(db, base):
    with pytest.raises(IntegrityError), db.begin() as conn:
        for a, b in ((base[0], base[1]), (base[1], base[0])):
            conn.execute(
                text(
                    "INSERT INTO booking_table_links (shop_id, table_a_id, table_b_id) "
                    "VALUES (:s, :a, :b)"
                ),
                {"s": SHOP, "a": a, "b": b},
            )


def test_link_to_itself_is_rejected(db, base):
    with pytest.raises(IntegrityError), db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO booking_table_links (shop_id, table_a_id, table_b_id) "
                "VALUES (:s, :a, :a)"
            ),
            {"s": SHOP, "a": base[0]},
        )


def test_reservation_code_unique_per_shop(db, base):
    with pytest.raises(IntegrityError), db.begin() as conn:
        _reservation(conn, "SAME")
        _reservation(conn, "SAME")
