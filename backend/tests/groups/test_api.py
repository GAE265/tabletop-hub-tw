"""groups API 測試：打端點、連 `_test` 資料庫，驗證狀態碼、錯誤代碼、回應格式與權限。

情境對應 openspec/changes/add-groups-calendar/specs/groups/spec.md。
"""

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF
from tests.groups.conftest import OTHER_SHOP_ID, PLAYER_B, PLAYER_C

BASE = "/api/v1/groups"
START = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0)
END = START + timedelta(hours=2)

ActAs = Callable[[CurrentUser], CurrentUser]


def iso(value: datetime) -> str:
    return value.isoformat()


def payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "shop_id": str(TEST_SHOP_ID),
        "title": "週末輕策略",
        "start_at": iso(START),
        "end_at": iso(END),
        "capacity": 4,
    }
    body.update(overrides)
    return body


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(BASE, json=payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- 開團 ---


def test_create_group(client: TestClient, as_player: CurrentUser):
    response = client.post(BASE, json=payload())
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["organizer"] == {"id": str(TEST_PLAYER.id), "display_name": "測試玩家"}
    assert body["shop"] == {"id": str(TEST_SHOP_ID), "name": "測試桌遊店"}
    assert body["status"] == "open"
    assert (body["member_count"], body["waitlist_count"], body["remaining_slots"]) == (1, 0, 3)
    assert body["my_status"] == "member"
    assert body["game"] is None
    assert body["fee"] is None
    assert body["description"] is None
    assert datetime.fromisoformat(body["start_at"]) == START
    assert body["start_at"].endswith("Z")
    assert "created_at" in body


def test_create_group_with_optional_fields(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str], int]
):
    game_id = add_game("範例桌遊")
    body = create(client, fee=300, game_id=game_id, description="新手可")
    assert body["fee"] == 300
    assert body["game"] == {"id": game_id, "name": "範例桌遊"}
    assert body["description"] == "新手可"


def test_shop_staff_can_create(client: TestClient, as_shop_staff: CurrentUser):
    body = create(client)
    assert body["organizer"]["id"] == str(TEST_SHOP_STAFF.id)


@pytest.mark.parametrize("field", ["shop_id", "title", "start_at", "end_at", "capacity"])
def test_create_missing_field(client: TestClient, as_player: CurrentUser, field: str):
    body = payload()
    del body[field]
    response = client.post(BASE, json=body)
    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "overrides",
    [
        {"capacity": 1},
        {"fee": -1},
        {"title": ""},
        {"start_at": "2030-01-01T10:00:00"},  # 沒有時區
        {"end_at": iso(START)},  # 結束等於開始
        {"end_at": iso(START - timedelta(minutes=1))},  # 結束早於開始
        {"start_at": iso(datetime.now(UTC) - timedelta(hours=1))},  # 開始時間已過
    ],
)
def test_create_invalid(client: TestClient, as_player: CurrentUser, overrides: dict, db: Engine):
    response = client.post(BASE, json=payload(**overrides))
    assert response.status_code == 422
    with db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM groups")) == 0


def test_create_shop_not_found(client: TestClient, as_player: CurrentUser, db: Engine):
    response = client.post(BASE, json=payload(shop_id=str(uuid.uuid4())))
    assert response.status_code == 404
    assert error_code(response) == "GROUP_SHOP_NOT_FOUND"
    with db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM groups")) == 0


def test_create_game_not_found(client: TestClient, as_player: CurrentUser):
    response = client.post(BASE, json=payload(game_id=999999))
    assert response.status_code == 404
    assert error_code(response) == "GROUP_GAME_NOT_FOUND"


def test_unauthenticated(jwt_client: TestClient):
    group_id = uuid.uuid4()
    assert jwt_client.post(BASE, json=payload()).status_code == 401
    assert jwt_client.get(BASE).status_code == 401
    assert jwt_client.post(f"{BASE}/{group_id}/members").status_code == 401


# --- 列表 ---


def test_list_filters(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    a = create(client)
    b = create(
        client,
        shop_id=str(OTHER_SHOP_ID),
        start_at=iso(START + timedelta(days=6)),
        end_at=iso(END + timedelta(days=6)),
    )
    act_as(PLAYER_B)
    c = create(
        client, start_at=iso(START + timedelta(hours=3)), end_at=iso(END + timedelta(hours=3))
    )

    response = client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert [g["id"] for g in body["items"]] == [a["id"], c["id"], b["id"]]
    assert body["total"] == 3

    day = client.get(
        BASE,
        params={
            "start_from": iso(START - timedelta(hours=1)),
            "start_before": iso(START + timedelta(days=1)),
        },
    ).json()
    assert [g["id"] for g in day["items"]] == [a["id"], c["id"]]
    assert day["total"] == 2

    by_organizer = client.get(BASE, params={"organizer_id": str(PLAYER_B.id)}).json()
    assert [g["id"] for g in by_organizer["items"]] == [c["id"]]

    by_shop = client.get(BASE, params={"shop_id": str(OTHER_SHOP_ID)}).json()
    assert [g["id"] for g in by_shop["items"]] == [b["id"]]

    page2 = client.get(BASE, params={"page": 2, "page_size": 2}).json()
    assert [g["id"] for g in page2["items"]] == [b["id"]]
    assert page2["total"] == 3


def test_list_my_status_depends_on_viewer(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    create(client)
    assert client.get(BASE).json()["items"][0]["my_status"] == "member"
    act_as(PLAYER_B)
    assert client.get(BASE).json()["items"][0]["my_status"] is None


def test_list_excludes_cancelled(client: TestClient, as_player: CurrentUser):
    group = create(client)
    client.patch(f"{BASE}/{group['id']}", json={"status": "cancelled"})
    assert client.get(BASE).json() == {"items": [], "total": 0}


def test_list_empty(client: TestClient, as_player: CurrentUser):
    response = client.get(BASE)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


@pytest.mark.parametrize(
    "params", [{"start_from": "abc"}, {"page_size": 101}, {"page": 0}, {"shop_id": "x"}]
)
def test_list_invalid_params(client: TestClient, as_player: CurrentUser, params: dict):
    response = client.get(BASE, params=params)
    assert response.status_code == 422


# --- 單一揪團 ---


def test_get_group(client: TestClient, as_player: CurrentUser):
    group = create(client)
    response = client.get(f"{BASE}/{group['id']}")
    assert response.status_code == 200
    assert response.json() == group


def test_get_cancelled_group(client: TestClient, as_player: CurrentUser):
    group = create(client)
    client.patch(f"{BASE}/{group['id']}", json={"status": "cancelled"})
    response = client.get(f"{BASE}/{group['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_get_ended_group(client: TestClient, as_player: CurrentUser, db: Engine):
    group = create(client)
    with db.begin() as conn:
        conn.execute(
            text(
                "UPDATE groups SET start_at = now() - interval '3 hours', "
                "end_at = now() - interval '1 hour' WHERE id = :id"
            ),
            {"id": group["id"]},
        )
    assert client.get(f"{BASE}/{group['id']}").json()["status"] == "ended"


def test_get_group_not_found(client: TestClient, as_player: CurrentUser):
    response = client.get(f"{BASE}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert error_code(response) == "GROUP_NOT_FOUND"


def test_get_group_invalid_id(client: TestClient, as_player: CurrentUser):
    assert client.get(f"{BASE}/not-a-uuid").status_code == 422


# --- 修改與取消 ---


def test_organizer_updates(client: TestClient, as_player: CurrentUser):
    group = create(client, fee=200)
    response = client.patch(f"{BASE}/{group['id']}", json={"title": "新標題"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "新標題"
    assert (body["fee"], body["capacity"], body["start_at"]) == (200, 4, group["start_at"])


def test_organizer_cancels(client: TestClient, as_player: CurrentUser):
    group = create(client)
    response = client.patch(f"{BASE}/{group['id']}", json={"status": "cancelled"})
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_admin_cancels_others_group(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client)
    act_as(TEST_ADMIN)
    response = client.patch(f"{BASE}/{group['id']}", json={"status": "cancelled"})
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.parametrize("user", [PLAYER_B, TEST_SHOP_STAFF])
def test_non_organizer_cannot_update(client: TestClient, act_as: ActAs, user: CurrentUser):
    act_as(TEST_PLAYER)
    group = create(client)  # 在 TEST_SHOP_ID，與店家人員同一間店
    act_as(user)
    response = client.patch(f"{BASE}/{group['id']}", json={"title": "改掉"})
    assert response.status_code == 403
    assert client.get(f"{BASE}/{group['id']}").json()["title"] == "週末輕策略"


def test_capacity_below_members(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client)
    for user in (PLAYER_B, PLAYER_C):
        act_as(user)
        client.post(f"{BASE}/{group['id']}/members")
    act_as(TEST_PLAYER)
    response = client.patch(f"{BASE}/{group['id']}", json={"capacity": 2})
    assert response.status_code == 409
    assert error_code(response) == "GROUP_CAPACITY_BELOW_MEMBERS"


def test_raise_capacity_promotes(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client, capacity=2)
    for user in (PLAYER_B, PLAYER_C, TEST_ADMIN):
        act_as(user)
        client.post(f"{BASE}/{group['id']}/members")
    act_as(TEST_PLAYER)
    response = client.patch(f"{BASE}/{group['id']}", json={"capacity": 3})
    assert response.status_code == 200
    assert (response.json()["member_count"], response.json()["waitlist_count"]) == (3, 1)
    act_as(PLAYER_C)
    assert client.get(f"{BASE}/{group['id']}").json()["my_status"] == "member"


def test_update_cancelled_group(client: TestClient, as_player: CurrentUser):
    group = create(client)
    client.patch(f"{BASE}/{group['id']}", json={"status": "cancelled"})
    response = client.patch(f"{BASE}/{group['id']}", json={"title": "復活"})
    assert response.status_code == 409
    assert error_code(response) == "GROUP_CLOSED"


@pytest.mark.parametrize(
    "body",
    [
        {"end_at": iso(START - timedelta(minutes=1))},
        {"status": "open"},
        {"status": "ended"},
        {"title": None},
        {"capacity": 1},
    ],
)
def test_update_invalid(client: TestClient, as_player: CurrentUser, body: dict):
    group = create(client)
    response = client.patch(f"{BASE}/{group['id']}", json=body)
    assert response.status_code == 422


def test_update_not_found(client: TestClient, as_player: CurrentUser):
    response = client.patch(f"{BASE}/{uuid.uuid4()}", json={"title": "x"})
    assert response.status_code == 404
    assert error_code(response) == "GROUP_NOT_FOUND"


# --- 報名 ---


def test_join(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client)
    act_as(PLAYER_B)
    response = client.post(f"{BASE}/{group['id']}/members")
    assert response.status_code == 201
    assert response.json() == {
        "user_id": str(PLAYER_B.id),
        "status": "member",
        "waitlist_position": None,
    }
    assert client.get(f"{BASE}/{group['id']}").json()["member_count"] == 2


def test_join_full_goes_to_waitlist(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client, capacity=2)
    act_as(PLAYER_B)
    client.post(f"{BASE}/{group['id']}/members")
    act_as(PLAYER_C)
    first = client.post(f"{BASE}/{group['id']}/members")
    act_as(TEST_ADMIN)
    second = client.post(f"{BASE}/{group['id']}/members")
    assert first.status_code == 201
    assert (first.json()["status"], first.json()["waitlist_position"]) == ("waitlisted", 1)
    assert (second.json()["status"], second.json()["waitlist_position"]) == ("waitlisted", 2)
    assert client.get(f"{BASE}/{group['id']}").json()["member_count"] == 2


def test_join_twice(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client)
    act_as(PLAYER_B)
    client.post(f"{BASE}/{group['id']}/members")
    response = client.post(f"{BASE}/{group['id']}/members")
    assert response.status_code == 409
    assert error_code(response) == "GROUP_ALREADY_JOINED"


def test_join_cancelled(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client)
    client.patch(f"{BASE}/{group['id']}", json={"status": "cancelled"})
    act_as(PLAYER_B)
    response = client.post(f"{BASE}/{group['id']}/members")
    assert response.status_code == 409
    assert error_code(response) == "GROUP_CLOSED"


def test_join_ended(client: TestClient, act_as: ActAs, db: Engine):
    act_as(TEST_PLAYER)
    group = create(client)
    with db.begin() as conn:
        conn.execute(
            text(
                "UPDATE groups SET start_at = now() - interval '3 hours', "
                "end_at = now() - interval '1 hour' WHERE id = :id"
            ),
            {"id": group["id"]},
        )
    act_as(PLAYER_B)
    response = client.post(f"{BASE}/{group['id']}/members")
    assert response.status_code == 409
    assert error_code(response) == "GROUP_CLOSED"


def test_join_not_found(client: TestClient, as_player: CurrentUser):
    response = client.post(f"{BASE}/{uuid.uuid4()}/members")
    assert response.status_code == 404
    assert error_code(response) == "GROUP_NOT_FOUND"


def test_concurrent_join_last_slot(client: TestClient, act_as: ActAs, test_db_url: str):
    """只剩一個名額時，另一個交易先鎖住揪團並補滿，等待中的報名要進候補，不能超收。"""
    from app.domains.groups.repository import GroupsRepository
    from app.domains.groups.service import GroupsService

    act_as(TEST_PLAYER)
    group_id = uuid.UUID(create(client, capacity=2)["id"])
    engine = create_engine(test_db_url)
    result: dict[str, Any] = {}

    def join_c() -> None:
        with Session(engine) as session:
            result["c"] = GroupsService(GroupsRepository(session)).join_group(PLAYER_C, group_id)

    try:
        with Session(engine) as session:
            repo = GroupsRepository(session)
            with repo.transaction():
                assert repo.lock_group(group_id) is not None
                worker = threading.Thread(target=join_c)
                worker.start()
                time.sleep(0.5)
                assert worker.is_alive(), "報名應該等待揪團的鎖"
                repo.add_member(group_id, PLAYER_B.id, "member", datetime.now(UTC))
        worker.join(timeout=10)
    finally:
        engine.dispose()

    assert result["c"].status == "waitlisted"
    view = client.get(f"{BASE}/{group_id}").json()
    assert (view["member_count"], view["waitlist_count"]) == (2, 1)


# --- 名單 ---


def test_list_members(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client, capacity=2)
    act_as(PLAYER_B)
    client.post(f"{BASE}/{group['id']}/members")
    act_as(PLAYER_C)
    client.post(f"{BASE}/{group['id']}/members")
    response = client.get(f"{BASE}/{group['id']}/members")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [
        (m["user_id"], m["display_name"], m["status"], m["waitlist_position"])
        for m in body["items"]
    ] == [
        (str(TEST_PLAYER.id), "測試玩家", "member", None),
        (str(PLAYER_B.id), "玩家乙", "member", None),
        (str(PLAYER_C.id), "玩家丙", "waitlisted", 1),
    ]
    assert all("joined_at" in m for m in body["items"])


def test_list_members_not_found(client: TestClient, as_player: CurrentUser):
    response = client.get(f"{BASE}/{uuid.uuid4()}/members")
    assert response.status_code == 404
    assert error_code(response) == "GROUP_NOT_FOUND"


# --- 退出與遞補 ---


def full_group(client: TestClient, act_as: ActAs) -> str:
    """開團主 TEST_PLAYER、成員 PLAYER_B、候補 PLAYER_C，capacity=2。"""
    act_as(TEST_PLAYER)
    group_id = create(client, capacity=2)["id"]
    for user in (PLAYER_B, PLAYER_C):
        act_as(user)
        client.post(f"{BASE}/{group_id}/members")
    return group_id


def test_leave_promotes_waitlist(client: TestClient, act_as: ActAs):
    group_id = full_group(client, act_as)
    act_as(PLAYER_B)
    response = client.delete(f"{BASE}/{group_id}/members/{PLAYER_B.id}")
    assert response.status_code == 204
    act_as(PLAYER_C)
    view = client.get(f"{BASE}/{group_id}").json()
    assert (view["member_count"], view["waitlist_count"], view["my_status"]) == (2, 0, "member")


def test_waitlisted_leaves(client: TestClient, act_as: ActAs):
    group_id = full_group(client, act_as)
    act_as(TEST_ADMIN)
    client.post(f"{BASE}/{group_id}/members")  # 候補第 2 位
    act_as(PLAYER_C)
    assert client.delete(f"{BASE}/{group_id}/members/{PLAYER_C.id}").status_code == 204
    items = client.get(f"{BASE}/{group_id}/members").json()["items"]
    assert [
        (m["user_id"], m["waitlist_position"]) for m in items if m["status"] == "waitlisted"
    ] == [(str(TEST_ADMIN.id), 1)]


@pytest.mark.parametrize("remover", [TEST_PLAYER, TEST_ADMIN])
def test_organizer_or_admin_removes(client: TestClient, act_as: ActAs, remover: CurrentUser):
    group_id = full_group(client, act_as)
    act_as(remover)
    assert client.delete(f"{BASE}/{group_id}/members/{PLAYER_B.id}").status_code == 204
    act_as(PLAYER_C)
    assert client.get(f"{BASE}/{group_id}").json()["my_status"] == "member"


def test_player_cannot_remove_others(client: TestClient, act_as: ActAs):
    group_id = full_group(client, act_as)
    act_as(PLAYER_C)
    response = client.delete(f"{BASE}/{group_id}/members/{PLAYER_B.id}")
    assert response.status_code == 403
    assert client.get(f"{BASE}/{group_id}").json()["member_count"] == 2


def test_organizer_cannot_leave(client: TestClient, as_player: CurrentUser):
    group = create(client)
    response = client.delete(f"{BASE}/{group['id']}/members/{TEST_PLAYER.id}")
    assert response.status_code == 409
    assert error_code(response) == "GROUP_ORGANIZER_CANNOT_LEAVE"


def test_leave_not_in_group(client: TestClient, act_as: ActAs):
    act_as(TEST_PLAYER)
    group = create(client)
    act_as(PLAYER_B)
    response = client.delete(f"{BASE}/{group['id']}/members/{PLAYER_B.id}")
    assert response.status_code == 404
    assert error_code(response) == "GROUP_MEMBER_NOT_FOUND"


def test_leave_cancelled_group(client: TestClient, act_as: ActAs):
    group_id = full_group(client, act_as)
    act_as(TEST_PLAYER)
    client.patch(f"{BASE}/{group_id}", json={"status": "cancelled"})
    act_as(PLAYER_B)
    response = client.delete(f"{BASE}/{group_id}/members/{PLAYER_B.id}")
    assert response.status_code == 409
    assert error_code(response) == "GROUP_CLOSED"


def test_leave_group_not_found(client: TestClient, as_player: CurrentUser):
    response = client.delete(f"{BASE}/{uuid.uuid4()}/members/{TEST_PLAYER.id}")
    assert response.status_code == 404
    assert error_code(response) == "GROUP_NOT_FOUND"
