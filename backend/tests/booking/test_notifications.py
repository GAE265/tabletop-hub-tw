"""訂位通知（add-booking-notifications 的 booking-notifications）：打真實端點與資料庫。"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import Engine, text

from tests.booking.conftest import (
    ADMIN_H,
    OTHER_SHOP,
    PLAYER2_H,
    PLAYER_H,
    SHOP,
    STAFF_H,
    header,
)
from tests.booking.test_api import book, code, payload

URL = "/api/v1/booking-notifications"

STAFF2 = uuid.UUID("a2000000-0000-4000-8000-000000000002")
OTHER_STAFF = uuid.UUID("a2000000-0000-4000-8000-000000000003")
STAFF2_H = header(STAFF2, "shop_staff", SHOP)
OTHER_STAFF_ONLY_H = header(OTHER_STAFF, "shop_staff", OTHER_SHOP)


@pytest.fixture
def more_staff(seeded, db: Engine) -> None:
    """測試店再一位店家人員，別家店一位店家人員。"""
    with db.begin() as conn:
        for uid, name, shop in ((STAFF2, "店員二", SHOP), (OTHER_STAFF, "別家店員", OTHER_SHOP)):
            conn.execute(
                text(
                    "INSERT INTO auth_users (id, display_name, role, shop_id) "
                    "VALUES (:i, :n, 'shop_staff', :s)"
                ),
                {"i": uid, "n": name, "s": shop},
            )


def notices(api, headers, **params):
    response = api.get(URL, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def count_rows(db: Engine) -> int:
    with db.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM booking_notifications"))


# --- 訂位成功時產生通知 ---


def test_booking_notifies_player_and_every_staff_of_the_shop(api, more_staff):
    item = book(api)

    mine = notices(api, PLAYER_H)
    assert mine["total"] == 1 and mine["unread_count"] == 1
    notice = mine["items"][0]
    assert notice["type"] == "booking_confirmed"
    assert notice["read_at"] is None and notice["created_at"]
    assert notice["booking"] == {
        "id": item["id"],
        "reservation_code": item["reservation_code"],
        "shop_name": "測試店",
        "start_at": item["start_at"],
        "end_at": item["end_at"],
        "party_size": 4,
    }

    for headers in (STAFF_H, STAFF2_H):
        staff = notices(api, headers)
        assert [n["type"] for n in staff["items"]] == ["shop_new_booking"]
        assert staff["items"][0]["booking"]["id"] == item["id"]


def test_staff_of_other_shop_gets_nothing(api, more_staff):
    book(api)
    assert notices(api, OTHER_STAFF_ONLY_H) == {"items": [], "total": 0, "unread_count": 0}
    assert notices(api, PLAYER2_H)["total"] == 0


def test_each_player_only_gets_own_booking(api, more_staff):
    item = book(api, headers=PLAYER2_H)
    assert [n["booking"]["id"] for n in notices(api, PLAYER2_H)["items"]] == [item["id"]]
    assert notices(api, PLAYER_H)["total"] == 0
    assert notices(api, ADMIN_H)["total"] == 0


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (payload(party=200), 409),  # 桌位不足
        ({"shop_id": str(SHOP)}, 422),  # 缺少欄位
    ],
)
def test_failed_booking_writes_no_notification(api, db, more_staff, body, status):
    response = api.post("/api/v1/bookings", json=body, headers=PLAYER_H)
    assert response.status_code == status
    assert count_rows(db) == 0


# --- 查詢 ---


def test_list_newest_first_with_unread_count(api, clock, more_staff):
    first = book(api, start=(14, 0), end=(16, 0))
    clock.now += timedelta(minutes=1)
    second = book(api, start=(18, 0), end=(20, 0))
    mine = notices(api, PLAYER_H)
    assert [n["booking"]["id"] for n in mine["items"]] == [second["id"], first["id"]]

    api.patch(f"{URL}/{mine['items'][1]['id']}", json={"read": True}, headers=PLAYER_H)
    again = notices(api, PLAYER_H)
    assert again["total"] == 2 and again["unread_count"] == 1


def test_pagination(api, more_staff):
    for start in ((14, 0), (17, 0), (20, 0)):
        book(api, start=start, end=(start[0] + 1, 0))
    page = notices(api, PLAYER_H, page=2, page_size=2)
    assert len(page["items"]) == 1
    assert page["total"] == 3 and page["unread_count"] == 3


def test_page_size_out_of_range_is_422(api):
    assert api.get(URL, headers=PLAYER_H, params={"page_size": 101}).status_code == 422


# --- 標成已讀 ---


def test_mark_read(api, more_staff):
    book(api)
    notice = notices(api, PLAYER_H)["items"][0]
    response = api.patch(f"{URL}/{notice['id']}", json={"read": True}, headers=PLAYER_H)
    assert response.status_code == 200
    read = response.json()
    assert read["id"] == notice["id"] and read["read_at"] is not None
    assert notices(api, PLAYER_H)["unread_count"] == 0


def test_mark_read_twice_keeps_first_time(api, clock, more_staff):
    book(api)
    notice = notices(api, PLAYER_H)["items"][0]
    first = api.patch(f"{URL}/{notice['id']}", json={"read": True}, headers=PLAYER_H).json()
    clock.now += timedelta(minutes=5)
    second = api.patch(f"{URL}/{notice['id']}", json={"read": True}, headers=PLAYER_H)
    assert second.status_code == 200
    assert second.json()["read_at"] == first["read_at"]


def test_cannot_mark_others_notification(api, more_staff):
    book(api)
    notice = notices(api, STAFF_H)["items"][0]
    response = api.patch(f"{URL}/{notice['id']}", json={"read": True}, headers=PLAYER_H)
    assert response.status_code == 404 and code(response) == "BOOKING_NOTIFICATION_NOT_FOUND"
    assert notices(api, STAFF_H)["unread_count"] == 1


def test_unknown_notification_is_404(api):
    response = api.patch(f"{URL}/{uuid.uuid4()}", json={"read": True}, headers=PLAYER_H)
    assert response.status_code == 404 and code(response) == "BOOKING_NOTIFICATION_NOT_FOUND"


@pytest.mark.parametrize("body", [{"read": False}, {}, {"read": None}])
def test_mark_read_requires_true(api, more_staff, body):
    book(api)
    notice = notices(api, PLAYER_H)["items"][0]
    assert api.patch(f"{URL}/{notice['id']}", json=body, headers=PLAYER_H).status_code == 422


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.get(URL).status_code == 401
    assert client.patch(f"{URL}/{uuid.uuid4()}", json={"read": True}).status_code == 401
