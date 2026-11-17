"""訂位資料表：表名、欄位、型別與約束與舊訂位資料庫一致（shop_id 改指向 booking_shops、
customer_id 改指向 auth_users），並驗證擴充欄位與防止同桌重疊的 exclusion constraint。"""

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

SHOP = uuid.UUID("c0ffee00-0000-4000-8000-0000000000aa")
USER = uuid.UUID("a1000000-0000-4000-8000-0000000000aa")

OLD_TABLES = {
    "business_hours": {"id", "shop_id", "weekday", "open_time", "close_time"},
    "closing_hours": {"id", "shop_id", "closing_date", "start_time", "end_time", "reason"},
    "seating_tables": {
        "id",
        "shop_id",
        "table_code",
        "table_name",
        "min_capacity",
        "max_capacity",
        "location",
        "is_active",
        "created_at",
    },
    "seating_tables_rel": {
        "id",
        "seating_tables_id_a",
        "seating_tables_id_b",
        "shop_id",
        "is_combinable",
    },
    "pricing_rules": {
        "id",
        "shop_id",
        "rule_code",
        "rule_name",
        "rule_type",
        "price",
        "unit",
        "description",
        "is_active",
        "effective_from",
        "effective_to",
        "created_at",
    },
    "reservations": {
        "id",
        "shop_id",
        "reservation_code",
        "customer_id",
        "start_at",
        "end_at",
        "party_size",
        "status",
        "source",
        "special_requests",
        "internal_note",
        "created_at",
        "updated_at",
        # 擴充欄位
        "seated_at",
        "completed_at",
        "final_fee",
        "cancelled_at",
        "cancel_reason",
    },
    "reservation_tables": {
        "shop_id",
        "reservation_id",
        "table_id",
        # 擴充欄位
        "start_at",
        "end_at",
        "is_active",
    },
    "reservation_logs": {
        "id",
        "shop_id",
        "reservation_id",
        "action",
        "old_data",
        "new_data",
        "operator_type",
        "operator_id",
        "operator_name",
        "created_at",
    },
    "customer_inquiries": {
        "id",
        "shop_id",
        "customer_id",
        "channel",
        "question",
        "answer",
        "category",
        "status",
        "created_at",
        "resolved_at",
    },
    "faqs": {
        "id",
        "shop_id",
        "question",
        "answer",
        "category",
        "keywords",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    },
    "menu_categories": {"id", "shop_id", "name", "sort_order", "is_active"},
    "menu_items": {
        "id",
        "shop_id",
        "category_id",
        "name",
        "description",
        "price",
        "is_available",
        "sort_order",
        "is_test_data",
        "created_at",
    },
}


def _columns(db: Engine, table: str) -> dict[str, str]:
    with db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = :t"
            ),
            {"t": table},
        )
        return dict(rows.all())


@pytest.mark.parametrize("table", sorted(OLD_TABLES))
def test_table_has_old_database_columns(db: Engine, table: str):
    assert set(_columns(db, table)) == OLD_TABLES[table]


def test_ids_are_bigint_and_company_is_uuid(db: Engine):
    assert _columns(db, "reservations")["id"] == "bigint"
    assert _columns(db, "reservations")["shop_id"] == "uuid"
    assert _columns(db, "reservations")["customer_id"] == "uuid"
    assert _columns(db, "reservation_logs")["operator_id"] == "character varying"
    assert _columns(db, "seating_tables_rel")["seating_tables_id_a"] == "bigint"


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
                    "INSERT INTO seating_tables (shop_id, table_code, max_capacity) "
                    "VALUES (:s, :c, 4) RETURNING id"
                ),
                {"s": SHOP, "c": c},
            ).scalar_one()
            for c in "AB"
        ]
    return ids


def _reservation(conn, code: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO reservations (shop_id, reservation_code, customer_id, start_at, "
            "end_at, party_size, status, source) VALUES (:s, :c, :u, now(), now() + interval "
            "'1 hour', 2, 'confirmed', 'online') RETURNING id"
        ),
        {"s": SHOP, "c": code, "u": USER},
    ).scalar_one()


def _occupy(conn, reservation, table, start="2026-12-01 14:00+08", end="2026-12-01 16:00+08"):
    conn.execute(
        text(
            "INSERT INTO reservation_tables "
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
            text("UPDATE reservation_tables SET is_active = false WHERE reservation_id = :r"),
            {"r": first},
        )
        _occupy(conn, _reservation(conn, "R2"), base[0])


def test_reservation_code_unique_per_shop(db, base):
    with pytest.raises(IntegrityError), db.begin() as conn:
        _reservation(conn, "SAME")
        _reservation(conn, "SAME")


def test_status_check_and_default(db, base):
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO reservations (shop_id, reservation_code, customer_id, start_at, "
                "end_at, party_size) VALUES (:s, 'D', :u, now(), now() + interval '1 hour', 2)"
            ),
            {"s": SHOP, "u": USER},
        )
        row = conn.execute(text("SELECT status, source FROM reservations")).one()
    assert tuple(row) == ("pending", "customer_service")
    with pytest.raises(IntegrityError), db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO reservations (shop_id, reservation_code, customer_id, start_at, "
                "end_at, party_size, status) VALUES (:s, 'E', :u, now(), now() + interval "
                "'1 hour', 2, 'bogus')"
            ),
            {"s": SHOP, "u": USER},
        )


def test_rel_allows_old_duplicates(db, base):
    """舊庫的關係表沒有唯一限制，DML 匯入舊資料時不能被擋下。"""
    with db.begin() as conn:
        for a, b in ((base[0], base[1]), (base[1], base[0]), (base[0], base[1])):
            conn.execute(
                text(
                    "INSERT INTO seating_tables_rel "
                    "(shop_id, seating_tables_id_a, seating_tables_id_b) VALUES (:s, :a, :b)"
                ),
                {"s": SHOP, "a": a, "b": b},
            )
