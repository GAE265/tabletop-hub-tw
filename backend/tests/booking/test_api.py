"""訂位 API 測試：打真實端點與資料庫（時間固定為 2026-11-16 10:00 台北）。"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from tests.booking.conftest import (
    ADMIN_H,
    OTHER_SHOP,
    OTHER_STAFF_H,
    PLAYER,
    PLAYER2_H,
    PLAYER_H,
    SHOP,
    STAFF_H,
)

TZ = ZoneInfo("Asia/Taipei")
WED = (2026, 11, 25)  # 星期三
SAT = (2026, 11, 28)  # 星期六
TUE = (2026, 11, 24)  # 星期二（公休）


def at(day: tuple[int, int, int], hour: int, minute: int = 0) -> str:
    return datetime(*day, hour, minute, tzinfo=TZ).isoformat()


def payload(day=WED, start=(14, 0), end=(16, 0), party=4, **extra):
    return {
        "shop_id": str(SHOP),
        "party_size": party,
        "start_at": at(day, *start),
        "end_at": at(day, *end),
        **extra,
    }


def book(api, headers=PLAYER_H, **kw):
    response = api.post("/api/v1/bookings", json=payload(**kw), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def patch(api, booking_id, body, headers=PLAYER_H):
    return api.patch(f"/api/v1/bookings/{booking_id}", json=body, headers=headers)


def code(response) -> str:
    return response.json()["error"]["code"]


# --- 建立與費用 ---


def test_create_confirmed_with_table_and_fee(api):
    item = book(api)
    assert item["status"] == "confirmed" and item["source"] == "online"
    assert item["reservation_code"].startswith("BK")
    assert [t["table_code"] for t in item["tables"]] == ["G"]  # 4 人，最小可容納的桌（G 容量 4）
    assert item["estimated_fee"]["venue_fee"] == "480.00"
    assert item["estimated_fee"]["drink_reminder"] is None


def test_weekend_has_drink_reminder(api):
    item = book(api, day=SAT)
    assert item["estimated_fee"]["venue_fee"] == "640.00"
    assert item["estimated_fee"]["drink_reminder"]


def test_quote_does_not_write(api, db):
    response = api.post("/api/v1/booking-quotes", json=payload(), headers=PLAYER_H)
    assert response.status_code == 200
    assert "fee" in response.json()
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM reservations")).scalar_one() == 0


@pytest.mark.parametrize(
    ("kw", "error"),
    [
        ({"day": TUE}, "BOOKING_CLOSED_DAY"),
        ({"start": (12, 0), "end": (14, 0)}, "BOOKING_OUTSIDE_BUSINESS_HOURS"),
        ({"day": (2026, 12, 2), "start": (14, 0), "end": (16, 0)}, "BOOKING_CLOSING_PERIOD"),
        ({"start": (14, 0), "end": (14, 45)}, "BOOKING_TOO_SHORT"),
        ({"day": (2027, 3, 3)}, "BOOKING_TOO_FAR"),
    ],
)
def test_time_rules_are_enforced(api, kw, error):
    response = api.post("/api/v1/bookings", json=payload(**kw), headers=PLAYER_H)
    assert response.status_code == 422 and code(response) == error


def test_missing_fields_is_422(api):
    response = api.post("/api/v1/bookings", json={"shop_id": str(SHOP)}, headers=PLAYER_H)
    assert response.status_code == 422 and code(response) == "VALIDATION_ERROR"


def test_player_without_phone_cannot_book(api, db):
    with db.begin() as conn:
        conn.execute(text("UPDATE auth_users SET phone = NULL WHERE id = :i"), {"i": PLAYER})
    response = api.post("/api/v1/bookings", json=payload(), headers=PLAYER_H)
    assert response.status_code == 422 and code(response) == "BOOKING_PHONE_REQUIRED"


def test_no_table_when_party_too_large(api):
    response = api.post("/api/v1/bookings", json=payload(party=200), headers=PLAYER_H)
    assert response.status_code == 409 and code(response) == "BOOKING_NO_TABLE_AVAILABLE"


def test_other_user_cannot_take_the_same_table(api):
    first = book(api, party=7)
    second = book(api, headers=PLAYER2_H, party=7)
    assert first["tables"] != second["tables"]


# --- 同電話重疊 ---


def test_overlap_requires_confirmation_then_replaces_old(api, db):
    old = book(api)
    ask = api.post("/api/v1/bookings", json=payload(), headers=PLAYER_H)
    assert ask.status_code == 409 and code(ask) == "BOOKING_OVERLAP_CONFIRM_REQUIRED"
    assert ask.json()["error"]["details"]["overlaps"][0]["id"] == old["id"]
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM reservations")).scalar_one() == 1

    new = api.post("/api/v1/bookings", json=payload(confirm_overlap=True), headers=PLAYER_H)
    assert new.status_code == 201
    got = api.get(f"/api/v1/bookings/{old['id']}", headers=PLAYER_H).json()
    assert got["status"] == "cancelled" and "取代" in got["cancel_reason"]


def test_overlap_confirmed_but_no_table_keeps_old(api):
    old = book(api)
    response = api.post(
        "/api/v1/bookings", json=payload(party=200, confirm_overlap=True), headers=PLAYER_H
    )
    assert response.status_code == 409
    assert (
        api.get(f"/api/v1/bookings/{old['id']}", headers=PLAYER_H).json()["status"] == "confirmed"
    )


# --- 修改與合併 ---


def test_modify_keeps_original_table_when_possible(api):
    item = book(api)
    response = patch(api, item["id"], {"start_at": at(WED, 15, 0), "end_at": at(WED, 17, 0)})
    assert response.status_code == 200
    body = response.json()
    assert body["tables"] == item["tables"] and body["notice"]


def test_modify_reallocates_when_party_grows(api):
    item = book(api, party=4)
    body = patch(api, item["id"], {"party_size": 9}).json()
    assert [t["table_code"] for t in body["tables"]] == ["C"]


def test_failed_modify_keeps_original(api):
    item = book(api)
    response = patch(api, item["id"], {"start_at": at(WED, 11), "end_at": at(WED, 13)})
    assert response.status_code == 422
    after = api.get(f"/api/v1/bookings/{item['id']}", headers=PLAYER_H).json()
    assert after["start_at"] == item["start_at"] and after["status"] == "confirmed"


def test_modify_overlapping_own_booking_asks_then_merges(api):
    a = book(api, start=(14, 0), end=(16, 0))
    b = book(api, start=(17, 0), end=(19, 0))
    ask = patch(api, b["id"], {"start_at": at(WED, 15), "end_at": at(WED, 18)})
    assert ask.status_code == 409 and code(ask) == "BOOKING_MERGE_CONFIRM_REQUIRED"

    merged = patch(
        api,
        b["id"],
        {"start_at": at(WED, 15), "end_at": at(WED, 18), "merge": True, "party_size": 6},
    )
    assert merged.status_code == 200
    new = merged.json()
    assert new["id"] not in (a["id"], b["id"]) and new["party_size"] == 6
    assert "2026-11-25T14:00" in new["start_at"] and "2026-11-25T18:00" in new["end_at"]
    for old in (a, b):
        got = api.get(f"/api/v1/bookings/{old['id']}", headers=PLAYER_H).json()
        assert got["status"] == "cancelled" and "合併" in got["cancel_reason"]


def test_failed_merge_keeps_both(api):
    a = book(api, start=(14, 0), end=(16, 0))
    b = book(api, start=(17, 0), end=(19, 0))
    response = patch(
        api,
        b["id"],
        {"start_at": at(WED, 15), "end_at": at(WED, 23), "merge": True, "party_size": 4},
    )
    assert response.status_code == 422
    for old in (a, b):
        assert (
            api.get(f"/api/v1/bookings/{old['id']}", headers=PLAYER_H).json()["status"]
            == "confirmed"
        )


# --- 取消與釋放 ---


def test_cancel_before_start_releases_table(api):
    item = book(api, party=7)
    response = patch(api, item["id"], {"status": "cancelled"})
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    again = book(api, headers=PLAYER2_H, party=7)
    assert again["tables"] == item["tables"]


def test_cancel_after_start_becomes_no_show(api, clock):
    item = book(api)
    clock.now = datetime(2026, 11, 25, 6, 30, tzinfo=UTC)  # 14:30 台北，已開始
    body = patch(api, item["id"], {"status": "cancelled"}).json()
    assert body["status"] == "no_show"


def test_cannot_cancel_twice(api):
    item = book(api)
    patch(api, item["id"], {"status": "cancelled"})
    assert patch(api, item["id"], {"status": "cancelled"}).status_code == 409


# --- 店員操作 ---


def test_staff_seat_then_complete_with_final_fee(api, clock):
    item = book(api, party=2)
    clock.now = datetime(2026, 11, 25, 6, 0, tzinfo=UTC)
    seated = patch(api, item["id"], {"status": "seated"}, STAFF_H).json()
    assert seated["status"] == "seated" and seated["seated_at"]
    assert patch(api, item["id"], {"status": "cancelled"}).status_code == 409  # 入座後不可取消

    clock.now = datetime(2026, 11, 25, 8, 20, tzinfo=UTC)  # 實際 2 小時 20 分
    done = patch(api, item["id"], {"status": "completed"}, STAFF_H).json()
    assert done["status"] == "completed" and done["final_fee"] == "360.00"  # 2 人 × 3 小時 × 60


def test_no_show_back_to_seated_when_table_free(api):
    item = book(api)
    assert patch(api, item["id"], {"status": "no_show"}, STAFF_H).status_code == 200
    assert patch(api, item["id"], {"status": "seated"}, STAFF_H).json()["status"] == "seated"


def test_no_show_back_to_seated_rejected_when_table_taken(api):
    item = book(api, party=7)
    patch(api, item["id"], {"status": "no_show"}, STAFF_H)
    book(api, headers=PLAYER2_H, party=7)  # 別人訂走同一桌
    response = patch(api, item["id"], {"status": "seated"}, STAFF_H)
    assert response.status_code == 409 and code(response) == "BOOKING_TABLE_TAKEN"
    assert api.get(f"/api/v1/bookings/{item['id']}", headers=STAFF_H).json()["status"] == "no_show"


def test_staff_change_tables_and_conflict(api, seeded):
    first = book(api, party=7)
    second = book(api, headers=PLAYER2_H, party=7)
    target = second["tables"][0]["id"]
    clash = api.put(
        f"/api/v1/bookings/{first['id']}/tables", json={"table_ids": [target]}, headers=STAFF_H
    )
    assert clash.status_code == 409 and code(clash) == "BOOKING_TABLE_TAKEN"
    free = str(seeded["tables"]["G"])
    ok = api.put(
        f"/api/v1/bookings/{first['id']}/tables", json={"table_ids": [free]}, headers=STAFF_H
    )
    assert ok.status_code == 200 and ok.json()["tables"][0]["table_code"] == "G"


def test_shop_list_by_date_range(api):
    book(api)
    response = api.get(
        f"/api/v1/shops/{SHOP}/bookings",
        params={"from": at(WED, 0), "to": at(WED, 23, 59)},
        headers=STAFF_H,
    )
    assert response.status_code == 200 and response.json()["total"] == 1


# --- 權限 ---


def test_player_cannot_read_or_change_others_booking(api):
    item = book(api)
    assert api.get(f"/api/v1/bookings/{item['id']}", headers=PLAYER2_H).status_code == 403
    assert patch(api, item["id"], {"status": "cancelled"}, PLAYER2_H).status_code == 403
    assert patch(api, item["id"], {"party_size": 2}, PLAYER2_H).status_code == 403


def test_player_cannot_do_staff_actions(api):
    item = book(api)
    assert patch(api, item["id"], {"status": "seated"}).status_code == 403
    assert (
        api.put(
            f"/api/v1/bookings/{item['id']}/tables",
            json={"table_ids": [item["tables"][0]["id"]]},
            headers=PLAYER_H,
        ).status_code
        == 403
    )
    assert (
        api.get(
            f"/api/v1/shops/{SHOP}/bookings",
            params={"from": at(WED, 0), "to": at(WED, 23)},
            headers=PLAYER_H,
        ).status_code
        == 403
    )


def test_staff_cannot_touch_other_shop(api):
    item = book(api)
    assert patch(api, item["id"], {"status": "seated"}, OTHER_STAFF_H).status_code == 403
    response = api.get(
        f"/api/v1/shops/{SHOP}/bookings",
        params={"from": at(WED, 0), "to": at(WED, 23)},
        headers=OTHER_STAFF_H,
    )
    assert response.status_code == 403


def test_admin_can_do_everything(api):
    item = book(api)
    assert patch(api, item["id"], {"status": "seated"}, ADMIN_H).status_code == 200


def test_staff_cannot_create_booking(api):
    assert api.post("/api/v1/bookings", json=payload(), headers=STAFF_H).status_code == 403


def test_unknown_booking_is_404(api):
    response = api.get("/api/v1/bookings/999999999", headers=PLAYER_H)
    assert response.status_code == 404 and code(response) == "BOOKING_NOT_FOUND"


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.get("/api/v1/bookings").status_code == 401


def test_logs_record_operator(api, db):
    item = book(api)
    patch(api, item["id"], {"status": "seated"}, STAFF_H)
    with db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT action, operator_type, operator_name FROM reservation_logs "
                "ORDER BY created_at"
            )
        ).all()
    assert [(r.action, r.operator_type) for r in rows] == [
        ("create", "customer"),
        ("seat", "staff"),
    ]
    assert rows[0].operator_name == "玩家一"


# --- 店家清單 ---


def test_list_shops_returns_active_shops(api):
    response = api.get("/api/v1/shops", headers=PLAYER_H)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert sorted((s["id"], s["name"]) for s in body["items"]) == sorted(
        [(str(SHOP), "測試店"), (str(OTHER_SHOP), "別家店")]
    )


def test_list_shops_excludes_inactive(api, db):
    with db.begin() as conn:
        conn.execute(
            text("UPDATE booking_shops SET is_active = false WHERE id = :s"),
            {"s": SHOP},
        )
    response = api.get("/api/v1/shops", headers=PLAYER_H)
    assert response.status_code == 200
    assert [s["name"] for s in response.json()["items"]] == ["別家店"]


def test_list_shops_empty_returns_zero(api, db):
    with db.begin() as conn:
        conn.execute(text("UPDATE booking_shops SET is_active = false"))
    response = api.get("/api/v1/shops", headers=PLAYER_H)
    assert response.status_code == 200 and response.json() == {"items": [], "total": 0}


def test_list_shops_requires_auth(test_db_url, make_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    response = client.get("/api/v1/shops")
    assert response.status_code == 401 and code(response) == "UNAUTHENTICATED"
