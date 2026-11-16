import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_session
from app.domains.booking.repository import BookingRepository
from app.domains.booking.router import get_booking_service
from app.domains.booking.service import BookingService
from app.main import create_app
from tests.booking.support import CAPACITY, LINK_SPECS

SHOP = uuid.UUID("c0ffee00-0000-4000-8000-000000000001")
OTHER_SHOP = uuid.UUID("c0ffee00-0000-4000-8000-000000000002")
PLAYER = uuid.UUID("a1000000-0000-4000-8000-000000000001")
PLAYER2 = uuid.UUID("a1000000-0000-4000-8000-000000000002")
STAFF = uuid.UUID("a2000000-0000-4000-8000-000000000001")
ADMIN = uuid.UUID("a3000000-0000-4000-8000-000000000001")

SESSION = Depends(get_session)

NOW = datetime(2026, 11, 16, 2, 0, tzinfo=UTC)  # 2026-11-16 10:00 台北，星期一


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def header(user: uuid.UUID, role: str, shop: uuid.UUID | None = None) -> dict[str, str]:
    value = f"{user}:{role}" + (f":{shop}" if shop else "")
    return {"X-Dev-User": value}


PLAYER_H = header(PLAYER, "player")
PLAYER2_H = header(PLAYER2, "player")
STAFF_H = header(STAFF, "shop_staff", SHOP)
OTHER_STAFF_H = header(STAFF, "shop_staff", OTHER_SHOP)
ADMIN_H = header(ADMIN, "admin")


@pytest.fixture
def seeded(db: Engine) -> dict[str, dict[str, uuid.UUID]]:
    """兩間店、四個使用者，以及虛構的 9 桌配置、營業時間（週二公休）與費率。"""
    tables: dict[str, uuid.UUID] = {}
    with db.begin() as conn:
        for shop, name in ((SHOP, "測試店"), (OTHER_SHOP, "別家店")):
            conn.execute(
                text("INSERT INTO booking_shops (id, name) VALUES (:i, :n)"), {"i": shop, "n": name}
            )
        users = [
            (PLAYER, "玩家一", "player", None, "0911000001"),
            (PLAYER2, "玩家二", "player", None, "0911000002"),
            (STAFF, "店員", "shop_staff", SHOP, None),
            (ADMIN, "管理員", "admin", None, None),
        ]
        for uid, name, role, shop, phone in users:
            conn.execute(
                text(
                    "INSERT INTO auth_users (id, display_name, role, shop_id, phone) "
                    "VALUES (:i, :n, :r, :s, :p)"
                ),
                {"i": uid, "n": name, "r": role, "s": shop, "p": phone},
            )
        for weekday in (0, 1, 3, 4, 5, 6):
            conn.execute(
                text(
                    "INSERT INTO booking_business_hours (shop_id, weekday, open_time, close_time) "
                    "VALUES (:s, :w, '13:00', '22:00')"
                ),
                {"s": SHOP, "w": weekday},
            )
        conn.execute(
            text(
                "INSERT INTO booking_closing_hours (shop_id, closing_date, start_time, end_time) "
                "VALUES (:s, '2026-12-02', '15:00', '17:00')"
            ),
            {"s": SHOP},
        )
        for code, cap in CAPACITY.items():
            tables[code] = conn.execute(
                text(
                    "INSERT INTO booking_tables (shop_id, table_code, min_capacity, max_capacity) "
                    "VALUES (:s, :c, 1, :m) RETURNING id"
                ),
                {"s": SHOP, "c": code, "m": cap},
            ).scalar_one()
        for a, b, combinable in LINK_SPECS:
            conn.execute(
                text(
                    "INSERT INTO booking_table_links "
                    "(shop_id, table_a_id, table_b_id, is_combinable) VALUES (:s, :a, :b, :c)"
                ),
                {"s": SHOP, "a": tables[a], "b": tables[b], "c": combinable},
            )
        rules = [
            ("WEEKDAY_HOURLY_FEE", 60),
            ("WEEKEND_HOURLY_FEE", 80),
            ("BILLING_ROUNDING_UNIT_HOURS", 1),
            ("BILLING_MAX_HOURS", 5),
            ("BOOKING_MIN_HOURS", 1),
        ]
        for code, price in rules:
            conn.execute(
                text(
                    "INSERT INTO booking_pricing_rules "
                    "(shop_id, rule_code, rule_name, rule_type, price, unit) "
                    "VALUES (:s, :c, :c, 'other', :p, 'x')"
                ),
                {"s": SHOP, "c": code, "p": price},
            )
    return {"tables": tables}


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def api(
    test_db_url: str, db: Engine, seeded: Any, clock: Clock, make_settings: Callable[..., Settings]
) -> Iterator[TestClient]:
    app: FastAPI = create_app(make_settings(database_url=test_db_url))

    def service_dep(session: Session = SESSION) -> BookingService:
        return BookingService(BookingRepository(session), now=clock)

    app.dependency_overrides[get_booking_service] = service_dep
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
