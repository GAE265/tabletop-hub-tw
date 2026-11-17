"""matches API 測試：開局、查詢一局、列表。連 `_test` 資料庫。

情境對應 openspec/changes/add-matches-record/specs/matches-record/spec.md
「開局」「查詢一局」。
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF
from tests.matches.conftest import OUTSIDER, PLAYER_B, PLAYER_C
from tests.matches.support import (
    BASE,
    error_code,
    match_body,
    participant_named,
    result_body,
    turn_body,
)

# --- 開局 ---


def test_create_match_at_shop(client: TestClient, as_player: CurrentUser, white_rose_id: int):
    response = client.post(
        BASE, json=match_body(white_rose_id, location_type="shop", shop_id=str(TEST_SHOP_ID))
    )
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["game"] == {"id": white_rose_id, "name": "血與刃的白薔薇"}
    assert body["played_on"] == "2026-11-20"
    assert body["location_type"] == "shop"
    assert body["shop"] == {"id": str(TEST_SHOP_ID), "name": "測試桌遊店"}
    assert body["group_id"] is None
    assert body["created_by"] == {"id": str(TEST_PLAYER.id), "display_name": "測試玩家"}
    assert body["status"] == "in_progress"
    assert body["result"] is None
    assert body["turns"] == []
    [participant] = body["participants"]
    assert participant["seat_number"] == 1
    assert participant["user_id"] == str(TEST_PLAYER.id)
    assert participant["display_name"] == "測試玩家"
    assert participant["is_confirmed"] is False
    assert (body["participant_count"], body["account_count"], body["confirmed_count"]) == (1, 1, 0)
    assert body["is_valid"] is False


def test_create_match_at_home(client: TestClient, as_player: CurrentUser, white_rose_id: int):
    response = client.post(BASE, json=match_body(white_rose_id))
    assert response.status_code == 201
    assert response.json()["location_type"] == "home"
    assert response.json()["shop"] is None


def test_create_match_for_group(
    client: TestClient, as_player: CurrentUser, white_rose_id: int, add_group
):
    group_id = str(add_group())
    response = client.post(BASE, json=match_body(white_rose_id, group_id=group_id))
    assert response.status_code == 201
    assert response.json()["group_id"] == group_id


def test_creator_can_choose_seat(client: TestClient, as_player: CurrentUser, white_rose_id: int):
    response = client.post(BASE, json=match_body(white_rose_id, seat_number=4))
    assert response.status_code == 201
    assert response.json()["participants"][0]["seat_number"] == 4


def test_creator_does_not_have_to_be_group_member(
    client: TestClient, as_player: CurrentUser, white_rose_id: int, add_group, api
):
    group_id = str(add_group())  # 開團主是 TEST_PLAYER；路人不是成員
    response = api(OUTSIDER, "POST", BASE, json=match_body(white_rose_id, group_id=group_id))
    assert response.status_code == 201


def test_create_match_with_progress(client: TestClient, as_player: CurrentUser, white_rose_id: int):
    response = client.post(BASE, json=match_body(white_rose_id, progress="第五關"))
    assert response.status_code == 201
    assert response.json()["progress"] == "第五關"


def test_shop_staff_can_create_match(
    client: TestClient, as_shop_staff: CurrentUser, white_rose_id: int
):
    response = client.post(BASE, json=match_body(white_rose_id))
    assert response.status_code == 201
    assert response.json()["created_by"]["id"] == str(TEST_SHOP_STAFF.id)


@pytest.mark.parametrize("missing", ["game_id", "played_on", "location_type"])
def test_create_match_requires_fields(
    client: TestClient, as_player: CurrentUser, white_rose_id: int, missing: str
):
    body = match_body(white_rose_id)
    del body[missing]
    response = client.post(BASE, json=body)
    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "overrides",
    [
        {"location_type": "shop"},  # 桌遊店要帶 shop_id
        {"location_type": "home", "shop_id": str(TEST_SHOP_ID)},  # 自家不能帶 shop_id
    ],
)
def test_location_type_and_shop_must_agree(
    client: TestClient, as_player: CurrentUser, white_rose_id: int, overrides: dict[str, Any]
):
    response = client.post(BASE, json=match_body(white_rose_id, **overrides))
    assert response.status_code == 422


@pytest.mark.parametrize("location_type", ["Shop", "", "office"])
def test_location_type_must_be_valid(
    client: TestClient, as_player: CurrentUser, white_rose_id: int, location_type: str
):
    response = client.post(BASE, json=match_body(white_rose_id, location_type=location_type))
    assert response.status_code == 422


@pytest.mark.parametrize("seat_number", [0, -1])
def test_creator_seat_must_be_positive(
    client: TestClient, as_player: CurrentUser, white_rose_id: int, seat_number: int
):
    response = client.post(BASE, json=match_body(white_rose_id, seat_number=seat_number))
    assert response.status_code == 422


def test_create_match_references_must_exist(
    client: TestClient, as_player: CurrentUser, white_rose_id: int
):
    missing_game = client.post(BASE, json=match_body(999999))
    assert (missing_game.status_code, error_code(missing_game)) == (404, "MATCH_GAME_NOT_FOUND")
    missing_shop = client.post(
        BASE,
        json=match_body(white_rose_id, location_type="shop", shop_id=str(uuid.uuid4())),
    )
    assert (missing_shop.status_code, error_code(missing_shop)) == (404, "MATCH_SHOP_NOT_FOUND")
    missing_group = client.post(BASE, json=match_body(white_rose_id, group_id=str(uuid.uuid4())))
    assert (missing_group.status_code, error_code(missing_group)) == (404, "MATCH_GROUP_NOT_FOUND")


# --- 查詢一局 ---


def test_get_match(client: TestClient, as_player: CurrentUser, started: str):
    response = client.get(f"{BASE}/{started}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == started
    assert [p["seat_number"] for p in body["participants"]] == [1, 2, 3, 4]
    assert body["turns"] == []
    for key in ("participant_count", "account_count", "confirmed_count", "is_valid"):
        assert key in body


def test_counts_with_account_and_name_only_participants(api, started: str):
    api(TEST_PLAYER, "POST", f"{BASE}/{started}/participants", json={"display_name": "Bob"})
    api(PLAYER_B, "PUT", f"{BASE}/{started}/result", json=result_body(factions=_five_seats()))
    me = participant_named(api(TEST_PLAYER, "GET", f"{BASE}/{started}").json(), "測試玩家")
    api(
        TEST_PLAYER,
        "PATCH",
        f"{BASE}/{started}/participants/{me['id']}",
        json={"is_confirmed": True},
    )
    body = api(OUTSIDER, "GET", f"{BASE}/{started}").json()
    # 5 位參加者、3 位有帳號、玩家乙（記錄結果）與測試玩家已確認
    assert (body["participant_count"], body["account_count"], body["confirmed_count"]) == (5, 3, 2)
    assert body["is_valid"] is False


def _five_seats() -> dict[int, str]:
    return {1: "rose", 2: "rose", 3: "blood_blade", 4: "blood_blade", 5: "blood_blade"}


def test_other_player_sees_new_turn_after_refresh(api, started: str):
    created = api(PLAYER_B, "POST", f"{BASE}/{started}/turns", json=turn_body(1, 2))
    assert created.status_code == 201
    body = api(TEST_PLAYER, "GET", f"{BASE}/{started}").json()
    assert [t["turn_number"] for t in body["turns"]] == [1]


def test_unconfirmed_result_is_still_returned(api, started: str):
    api(TEST_PLAYER, "PUT", f"{BASE}/{started}/result", json=result_body())
    body = api(PLAYER_C, "GET", f"{BASE}/{started}").json()
    assert body["result"] == {"type": "faction", "winning_faction": "rose"}
    assert body["status"] == "finished"
    assert body["is_valid"] is False


def test_non_participant_can_read_match(api, started: str):
    assert api(OUTSIDER, "GET", f"{BASE}/{started}").status_code == 200


def test_get_missing_match(client: TestClient, as_player: CurrentUser, app):
    response = client.get(f"{BASE}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert error_code(response) == "MATCH_NOT_FOUND"


# --- 列表 ---


def test_list_matches_filters_orders_and_paginates(
    api, white_rose_id: int, other_game_id: int, add_group
):
    group_id = str(add_group())
    api(TEST_PLAYER, "POST", BASE, json=match_body(white_rose_id, played_on="2026-11-18"))
    api(
        TEST_PLAYER,
        "POST",
        BASE,
        json=match_body(white_rose_id, played_on="2026-11-20", group_id=group_id),
    )
    api(PLAYER_B, "POST", BASE, json=match_body(other_game_id, played_on="2026-11-19"))

    everything = api(OUTSIDER, "GET", BASE).json()
    assert everything["total"] == 3
    assert [m["played_on"] for m in everything["items"]] == [
        "2026-11-20",
        "2026-11-19",
        "2026-11-18",
    ]

    by_game = api(OUTSIDER, "GET", BASE, params={"game_id": white_rose_id}).json()
    assert by_game["total"] == 2
    by_group = api(OUTSIDER, "GET", BASE, params={"group_id": group_id}).json()
    assert by_group["total"] == 1
    by_user = api(OUTSIDER, "GET", BASE, params={"user_id": str(PLAYER_B.id)}).json()
    assert by_user["total"] == 1
    assert by_user["items"][0]["game"]["id"] == other_game_id

    page = api(OUTSIDER, "GET", BASE, params={"page": 2, "page_size": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1


def test_admin_can_list(api, white_rose_id: int):
    assert api(TEST_ADMIN, "GET", BASE).status_code == 200
