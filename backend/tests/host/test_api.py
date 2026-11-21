"""主持的三個一般請求（host spec §11）。對應情境 A-01 到 A-18、M-08、M-09。

主持不建資料表，所以這裡不需要資料庫；時間用假時鐘。
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.domains.host.graph import HostEvent, HostGraph
from app.domains.host.service import HostService
from tests.conftest import TEST_ADMIN, TEST_PLAYER
from tests.host.fakes import FakeClock

BASE = "/api/v1/hosting-sessions"
OTHER_PLAYER = CurrentUser(id=uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"), role="player")
SESSION_FIELDS = {
    "id",
    "status",
    "player_count",
    "turn_taking_mode",
    "voice",
    "step",
    "turn_number",
    "phase_number",
    "paused",
    "winner",
    "created_at",
}


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def host_service(app: FastAPI, clock: FakeClock) -> HostService:
    """把後端的主持 service 換成用假時鐘的那一個。圖還是真的。"""
    service = HostService(HostGraph(), clock=clock)
    app.state.host_service = service
    return service


@pytest.fixture
def act_as(app: FastAPI) -> Callable[[CurrentUser], None]:
    def _act_as(user: CurrentUser) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    return _act_as


def open_hosting(client: TestClient, **overrides: object) -> dict:
    response = client.post(BASE, json={"player_count": 7, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def connections(client: TestClient, session_id: str, **body: object):
    return client.post(f"{BASE}/{session_id}/connections", json=body)


def advance_to(service: HostService, session_id: str, turn_number: int, phase_number: int) -> None:
    sid = uuid.UUID(session_id)
    service.handle_event(sid, HostEvent.connected())
    # 開場 → 開局準備 → 夜晚第一步 → 夜晚第二步 → 第 1 回合階段 1
    presses = 4 + (turn_number - 1) * 3 + (phase_number - 1)
    for _ in range(presses):
        service.handle_event(sid, HostEvent.command("next"))


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error"]["code"] == code
    assert set(body["error"]) == {"code", "message", "details"}


# --- POST /hosting-sessions ---


def test_a01_player_opens_a_hosting(
    client: TestClient, as_player: CurrentUser, host_service: HostService, clock: FakeClock
):
    response = client.post(BASE, json={"player_count": 7})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session", "connection"}
    session = body["session"]
    assert set(session) == SESSION_FIELDS
    assert uuid.UUID(session["id"])
    assert session["status"] == "active"
    assert session["step"] == "opening"
    assert session["turn_number"] is None and session["phase_number"] is None
    assert session["player_count"] == 7
    assert session["turn_taking_mode"] == "auto"
    assert session["voice"] == "male"
    assert session["paused"] is False
    assert session["winner"] is None
    assert datetime.fromisoformat(session["created_at"]) == clock.now
    assert set(body["connection"]) == {"ticket", "expires_at"}
    assert body["connection"]["ticket"]
    expires_at = datetime.fromisoformat(body["connection"]["expires_at"])
    assert expires_at == clock.now + timedelta(seconds=60)
    assert expires_at.utcoffset() == timedelta(0)


def test_a01_optional_fields_are_respected(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    session = open_hosting(client, turn_taking_mode="push_to_talk", voice="female")["session"]
    assert session["turn_taking_mode"] == "push_to_talk"
    assert session["voice"] == "female"


def test_a02_shop_staff_can_open(
    client: TestClient, as_shop_staff: CurrentUser, host_service: HostService
):
    assert client.post(BASE, json={"player_count": 7}).status_code == 201


def test_a02_admin_can_open(client: TestClient, as_admin: CurrentUser, host_service: HostService):
    assert client.post(BASE, json={"player_count": 7}).status_code == 201


def test_a03_unauthenticated(jwt_client: TestClient):
    assert_error(jwt_client.post(BASE, json={"player_count": 7}), 401, "UNAUTHENTICATED")
    assert_error(jwt_client.get(BASE), 401, "UNAUTHENTICATED")
    assert_error(
        jwt_client.post(f"{BASE}/{uuid.uuid4()}/connections", json={}), 401, "UNAUTHENTICATED"
    )


@pytest.mark.parametrize("body", [{"player_count": 4}, {"player_count": 11}, {}])
def test_a04_bad_player_count_is_422(
    client: TestClient, as_player: CurrentUser, host_service: HostService, body: dict
):
    response = client.post(BASE, json=body)
    assert response.status_code == 422
    assert "error" in response.json()
    assert client.get(BASE).json()["total"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"player_count": 7, "voice": "robot"},
        {"player_count": 7, "turn_taking_mode": "server_vad"},
    ],
)
def test_a05_bad_voice_or_turn_taking_mode_is_422(
    client: TestClient, as_player: CurrentUser, host_service: HostService, body: dict
):
    assert client.post(BASE, json=body).status_code == 422


def test_a06_opening_again_replaces_the_old_hosting(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    old = open_hosting(client)["session"]
    advance_to(host_service, old["id"], 3, 1)

    response = client.post(BASE, json={"player_count": 7})

    # 是取代，不是衝突
    assert response.status_code == 201
    new = response.json()["session"]
    assert new["id"] != old["id"]
    assert new["step"] == "opening"
    assert_error(connections(client, old["id"]), 404, "HOST_SESSION_NOT_FOUND")
    assert connections(client, new["id"]).status_code == 201


# --- GET /hosting-sessions ---


def test_a07_no_hosting(client: TestClient, as_player: CurrentUser, host_service: HostService):
    response = client.get(BASE)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_a08_one_hosting_with_its_position(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    opened = open_hosting(client)["session"]
    advance_to(host_service, opened["id"], 2, 3)

    body = client.get(BASE).json()

    assert body["total"] == 1
    item = body["items"][0]
    assert set(item) == SESSION_FIELDS
    assert item["id"] == opened["id"]
    assert (item["step"], item["turn_number"], item["phase_number"]) == ("turn", 2, 3)


def test_a09_other_players_do_not_see_my_hosting(
    client: TestClient, host_service: HostService, act_as: Callable[[CurrentUser], None]
):
    act_as(TEST_PLAYER)
    open_hosting(client)
    act_as(OTHER_PLAYER)
    assert client.get(BASE).json() == {"items": [], "total": 0}


# --- POST /hosting-sessions/{id}/connections ---


def test_a10_owner_gets_a_ticket(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    opened = open_hosting(client)
    response = connections(client, opened["session"]["id"])
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session", "connection"}
    assert set(body["session"]) == SESSION_FIELDS
    assert body["session"]["id"] == opened["session"]["id"]
    assert body["connection"]["ticket"] != opened["connection"]["ticket"]


def test_a10_body_is_optional(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    opened = open_hosting(client)
    response = client.post(f"{BASE}/{opened['session']['id']}/connections")
    assert response.status_code == 201


def test_a11_someone_else_gets_403(
    client: TestClient, host_service: HostService, act_as: Callable[[CurrentUser], None]
):
    act_as(TEST_PLAYER)
    session_id = open_hosting(client)["session"]["id"]
    act_as(OTHER_PLAYER)
    assert_error(connections(client, session_id), 403, "PERMISSION_DENIED")


def test_a12_admin_gets_a_ticket_for_someone_elses_hosting(
    client: TestClient, host_service: HostService, act_as: Callable[[CurrentUser], None]
):
    act_as(TEST_PLAYER)
    session_id = open_hosting(client)["session"]["id"]
    act_as(TEST_ADMIN)
    response = connections(client, session_id)
    assert response.status_code == 201
    assert response.json()["session"]["id"] == session_id
    # 管理員的 GET 只列自己的
    assert client.get(BASE).json()["total"] == 0


def test_a13_someone_else_cannot_switch_turn_taking_mode(
    client: TestClient, host_service: HostService, act_as: Callable[[CurrentUser], None]
):
    act_as(TEST_PLAYER)
    session_id = open_hosting(client)["session"]["id"]
    act_as(OTHER_PLAYER)
    assert_error(
        connections(client, session_id, turn_taking_mode="push_to_talk"), 403, "PERMISSION_DENIED"
    )
    act_as(TEST_PLAYER)
    assert client.get(BASE).json()["items"][0]["turn_taking_mode"] == "auto"


def test_owner_can_ask_for_another_turn_taking_mode(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    session_id = open_hosting(client)["session"]["id"]
    response = connections(client, session_id, turn_taking_mode="push_to_talk")
    assert response.status_code == 201
    assert response.json()["session"]["turn_taking_mode"] == "push_to_talk"
    assert connections(client, session_id, turn_taking_mode="shout").status_code == 422


def test_a14_unknown_id_is_404(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    assert_error(connections(client, str(uuid.uuid4())), 404, "HOST_SESSION_NOT_FOUND")


def test_a15_no_device_for_30_minutes_is_404(
    client: TestClient, as_player: CurrentUser, host_service: HostService, clock: FakeClock
):
    session_id = open_hosting(client)["session"]["id"]
    clock.advance(minutes=30)
    assert_error(connections(client, session_id), 404, "HOST_SESSION_NOT_FOUND")
    assert client.get(BASE).json()["total"] == 0


def test_a16_ended_for_10_minutes_still_gets_a_ticket(
    client: TestClient, as_player: CurrentUser, host_service: HostService, clock: FakeClock
):
    session_id = open_hosting(client)["session"]["id"]
    advance_to(host_service, session_id, 2, 2)
    host_service.handle_event(uuid.UUID(session_id), HostEvent.command("end"))
    clock.advance(minutes=10)

    response = connections(client, session_id)

    assert response.status_code == 201
    session = response.json()["session"]
    # 拿通行碼時還是已結束，連上後才變回進行中
    assert session["status"] == "ended"
    assert (session["turn_number"], session["phase_number"]) == (2, 2)
    assert client.get(BASE).json()["items"][0]["status"] == "ended"


def test_a17_ended_for_30_minutes_is_404(
    client: TestClient, as_player: CurrentUser, host_service: HostService, clock: FakeClock
):
    session_id = open_hosting(client)["session"]["id"]
    host_service.device_connected(uuid.UUID(session_id))
    advance_to(host_service, session_id, 1, 1)
    host_service.handle_event(uuid.UUID(session_id), HostEvent.command("end"))
    clock.advance(minutes=30)
    assert_error(connections(client, session_id), 404, "HOST_SESSION_NOT_FOUND")


def test_a18_opens_normally_without_a_rules_index(client: TestClient, as_player: CurrentUser):
    """後端預設的接線（查規則接 rules_qa）在索引沒建好、甚至資料庫連不上時，也照常開主持。"""
    response = client.post(BASE, json={"player_count": 7})
    assert response.status_code == 201
    assert response.json()["session"]["step"] == "opening"


# --- 整局記憶：M-08、M-09 ---


def test_m08_ended_hosting_and_its_memory_are_cleared_after_30_minutes(
    client: TestClient, as_player: CurrentUser, host_service: HostService, clock: FakeClock
):
    session_id = open_hosting(client)["session"]["id"]
    advance_to(host_service, session_id, 1, 1)
    host_service.handle_event(uuid.UUID(session_id), HostEvent.command("end"))
    assert host_service.graph.exists(session_id) is True

    clock.advance(minutes=30)

    assert client.get(BASE).json() == {"items": [], "total": 0}
    assert host_service.graph.exists(session_id) is False


def test_m09_reopening_clears_the_old_hosting_and_its_memory(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    old_id = open_hosting(client)["session"]["id"]
    advance_to(host_service, old_id, 2, 1)

    new_id = open_hosting(client)["session"]["id"]

    assert host_service.graph.exists(old_id) is False
    assert host_service.graph.exists(new_id) is True
    assert [item["id"] for item in client.get(BASE).json()["items"]] == [new_id]


def test_no_endpoint_to_end_or_read_a_hosting(
    client: TestClient, as_player: CurrentUser, host_service: HostService
):
    """結束主持只走 WebSocket；沒有讀取整局記憶的端點（spec §11.1）。"""
    session_id = open_hosting(client)["session"]["id"]
    assert client.get(f"{BASE}/{session_id}").status_code in (404, 405)
    assert client.delete(f"{BASE}/{session_id}").status_code in (404, 405)
    assert client.patch(f"{BASE}/{session_id}", json={"status": "ended"}).status_code in (404, 405)
