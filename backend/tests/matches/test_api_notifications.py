"""戰績通知 API 測試：結算時寫入通知、查詢、標成已讀。連 `_test` 資料庫。

情境對應 docs/mr_info/feature-matches-notifications.md 的後端情境表（標「API」的列）。
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.conftest import TEST_PLAYER
from tests.matches.conftest import OUTSIDER, PLAYER_B, PLAYER_C
from tests.matches.support import BASE, error_code, result_body

NOTIFICATIONS = "/api/v1/match-notifications"
FIVE_SEATS = {1: "rose", 2: "rose", 3: "blood_blade", 4: "blood_blade", 5: "rose"}


@pytest.fixture
def five(api, started: str) -> str:
    """5 人的一局：1 測試玩家、2 玩家乙、3 玩家丙（有帳號）、4 Amy、5 Bob（沒有帳號）。"""
    added = api(TEST_PLAYER, "POST", f"{BASE}/{started}/participants", json={"display_name": "Bob"})
    assert added.status_code == 201, added.text
    return started


def put_result(api, user, match_id: str, overwrite: bool = False, **body: Any):
    params = {"overwrite": "true"} if overwrite else None
    payload = result_body(**body) if body else result_body(factions=FIVE_SEATS)
    return api(user, "PUT", f"{BASE}/{match_id}/result", json=payload, params=params)


def mine(api, user, **params: Any) -> dict[str, Any]:
    response = api(user, "GET", NOTIFICATIONS, params=params or None)
    assert response.status_code == 200, response.text
    return response.json()


def mark_read(api, user, notification_id: str, body: Any = None):
    return api(
        user,
        "PATCH",
        f"{NOTIFICATIONS}/{notification_id}",
        json={"read": True} if body is None else body,
    )


def row_count(db: Engine) -> int:
    with db.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM matches_notifications"))


# --- 結算時寫入 ---


def test_result_notifies_other_account_participants(api, db: Engine, five: str):
    assert put_result(api, TEST_PLAYER, five).status_code == 200
    for user in (PLAYER_B, PLAYER_C):
        body = mine(api, user)
        assert (body["total"], body["unread_count"]) == (1, 1)
        assert body["items"][0]["type"] == "match_result_recorded"
    # 沒有帳號的 Amy、Bob 與記錄者都沒有
    assert row_count(db) == 2


def test_recorder_gets_no_notification(api, five: str):
    put_result(api, TEST_PLAYER, five)
    assert mine(api, TEST_PLAYER) == {"items": [], "total": 0, "unread_count": 0}


def test_overwrite_notifies_again(api, five: str):
    put_result(api, TEST_PLAYER, five)
    assert put_result(api, TEST_PLAYER, five, overwrite=True).status_code == 200
    for user in (PLAYER_B, PLAYER_C):
        assert mine(api, user)["total"] == 2


def test_overwrite_marks_previous_unread_as_read(api, five: str):
    put_result(api, TEST_PLAYER, five)
    put_result(api, TEST_PLAYER, five, overwrite=True)
    body = mine(api, PLAYER_B)
    assert (body["total"], body["unread_count"]) == (2, 1)
    newest, older = body["items"]
    assert newest["read_at"] is None
    assert older["read_at"] is not None


def test_duplicate_result_sends_no_notification(api, db: Engine, five: str):
    put_result(api, TEST_PLAYER, five)
    response = put_result(api, PLAYER_B, five)
    assert (response.status_code, error_code(response)) == (409, "MATCH_RESULT_ALREADY_RECORDED")
    assert row_count(db) == 2
    assert mine(api, PLAYER_C)["unread_count"] == 1


@pytest.mark.parametrize(
    ("case", "status"),
    [("invalid_faction", 422), ("not_participant", 403), ("no_result_type", 409)],
)
def test_failed_result_writes_no_notification(
    api,
    db: Engine,
    white_rose_id: int,
    set_result_type: Callable[[int, str | None], None],
    five: str,
    case: str,
    status: int,
):
    user = TEST_PLAYER
    body: dict[str, Any] = {}
    if case == "invalid_faction":
        body = {"winning": "no_such_faction", "factions": FIVE_SEATS}
    elif case == "not_participant":
        user = OUTSIDER
    else:
        set_result_type(white_rose_id, None)
    assert put_result(api, user, five, **body).status_code == status
    assert row_count(db) == 0


# --- 查詢 ---


def test_list_only_own_notifications(api, five: str):
    put_result(api, TEST_PLAYER, five)
    b_ids = {n["id"] for n in mine(api, PLAYER_B)["items"]}
    c_ids = {n["id"] for n in mine(api, PLAYER_C)["items"]}
    assert len(b_ids) == len(c_ids) == 1
    assert b_ids.isdisjoint(c_ids)
    assert mine(api, OUTSIDER)["total"] == 0


def test_notifications_newest_first_with_pagination(api, five: str):
    for overwrite in (False, True, True):
        assert put_result(api, TEST_PLAYER, five, overwrite=overwrite).status_code == 200
    first = mine(api, PLAYER_B, page=1, page_size=2)
    assert (len(first["items"]), first["total"], first["unread_count"]) == (2, 3, 1)
    newest, second = first["items"]
    assert newest["created_at"] >= second["created_at"]
    assert newest["read_at"] is None
    last = mine(api, PLAYER_B, page=2, page_size=2)
    assert (len(last["items"]), last["total"], last["unread_count"]) == (1, 3, 1)
    assert last["items"][0]["created_at"] <= second["created_at"]


def test_notification_includes_match_and_recorder(api, five: str):
    put_result(api, TEST_PLAYER, five)
    item = mine(api, PLAYER_B)["items"][0]
    assert item["match"] == {"id": five, "game_name": "血與刃的白薔薇", "played_on": "2026-11-20"}
    assert item["recorded_by"] == {"id": str(TEST_PLAYER.id), "display_name": "測試玩家"}
    assert item["read_at"] is None
    assert item["created_at"]


# --- 標成已讀 ---


def test_mark_read(api, five: str):
    put_result(api, TEST_PLAYER, five)
    notification = mine(api, PLAYER_B)["items"][0]
    response = mark_read(api, PLAYER_B, notification["id"])
    assert response.status_code == 200
    assert response.json()["id"] == notification["id"]
    assert response.json()["read_at"] is not None
    assert mine(api, PLAYER_B)["unread_count"] == 0


def test_mark_read_twice_keeps_first_time(api, five: str):
    put_result(api, TEST_PLAYER, five)
    notification_id = mine(api, PLAYER_B)["items"][0]["id"]
    first = mark_read(api, PLAYER_B, notification_id)
    second = mark_read(api, PLAYER_B, notification_id)
    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["read_at"] == first.json()["read_at"]


def test_cannot_mark_others_notification(api, five: str):
    put_result(api, TEST_PLAYER, five)
    notification_id = mine(api, PLAYER_B)["items"][0]["id"]
    response = mark_read(api, PLAYER_C, notification_id)
    assert (response.status_code, error_code(response)) == (404, "MATCH_NOTIFICATION_NOT_FOUND")
    assert mine(api, PLAYER_B)["unread_count"] == 1


def test_mark_missing_notification(api, five: str):
    response = mark_read(api, PLAYER_B, str(uuid.uuid4()))
    assert (response.status_code, error_code(response)) == (404, "MATCH_NOTIFICATION_NOT_FOUND")


@pytest.mark.parametrize("body", [{"read": False}, {}])
def test_mark_read_requires_true(api, five: str, body: dict[str, Any]):
    put_result(api, TEST_PLAYER, five)
    notification_id = mine(api, PLAYER_B)["items"][0]["id"]
    assert mark_read(api, PLAYER_B, notification_id, body).status_code == 422
    assert mine(api, PLAYER_B)["unread_count"] == 1
