"""主持的 WebSocket 端點（host spec §12.1、§12.4）。對應情境 W-01 到 W-06、W-09、W-10、W-12。

這裡走真的 FastAPI 端點與通行碼；語音模型是 FakeRealtimeVoiceProvider。
計時、重連、語音指令等細節在 test_relay 用假時鐘測。
"""

import time
import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.auth import CurrentUser, get_current_user
from app.domains.host.graph import HostEvent, HostGraph
from app.domains.host.service import HostService
from app.integrations.realtime_voice import FakeRealtimeVoiceProvider
from tests.conftest import TEST_PLAYER
from tests.host.fakes import FakeClock

BASE = "/api/v1/hosting-sessions"
OTHER_PLAYER = CurrentUser(id=uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"), role="player")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def host_service(app: FastAPI, clock: FakeClock) -> HostService:
    service = HostService(HostGraph(), clock=clock)
    app.state.host_service = service
    return service


@pytest.fixture
def voice(app: FastAPI) -> FakeRealtimeVoiceProvider:
    provider = FakeRealtimeVoiceProvider()
    app.state.realtime_voice = provider
    return provider


@pytest.fixture
def act_as(app: FastAPI) -> Callable[[CurrentUser], None]:
    def _act_as(user: CurrentUser) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    return _act_as


def open_hosting(client: TestClient) -> tuple[str, str]:
    body = client.post(BASE, json={"player_count": 7}).json()
    return body["session"]["id"], body["connection"]["ticket"]


def new_ticket(client: TestClient, session_id: str) -> str:
    return client.post(f"{BASE}/{session_id}/connections").json()["connection"]["ticket"]


def stream_url(session_id: str, ticket: str) -> str:
    return f"{BASE}/{session_id}/stream?ticket={ticket}"


def assert_closed_with(websocket, code: str) -> None:
    message = websocket.receive_json()
    assert message["type"] == "error"
    assert message["error"]["code"] == code
    assert set(message["error"]) == {"code", "message", "details"}
    with pytest.raises(WebSocketDisconnect):
        websocket.receive_json()


def wait_until(predicate: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "等不到預期的狀態"
        time.sleep(0.01)


def test_w01_valid_ticket_connects_and_first_message_is_state(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket = open_hosting(client)
    # 核對通行碼之前不連語音模型
    assert voice.connect_attempts == 0

    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        first = websocket.receive_json()
        assert first["type"] == "state"
        assert first["status"] == "active"
        assert first["step"] == "opening"
        assert first["turn_taking_mode"] == "auto"
        assert first["voice"] == "male"
        # 整合層收到開連線的要求
        assert voice.connect_attempts == 1
        assert voice.configs[0].voice == "male"


def test_w02_used_ticket_is_rejected(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket = open_hosting(client)
    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        websocket.receive_json()
    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        assert_closed_with(websocket, "HOST_TICKET_INVALID")
    assert voice.connect_attempts == 1


def test_w03_expired_ticket_is_rejected(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
    clock: FakeClock,
):
    session_id, ticket = open_hosting(client)
    clock.advance(seconds=61)
    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        assert_closed_with(websocket, "HOST_TICKET_INVALID")
    assert voice.connect_attempts == 0


def test_w03_missing_ticket_is_rejected(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, _ = open_hosting(client)
    with client.websocket_connect(f"{BASE}/{session_id}/stream") as websocket:
        assert_closed_with(websocket, "HOST_TICKET_INVALID")


def test_w04_ticket_of_another_hosting_is_rejected(
    client: TestClient,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
    act_as: Callable[[CurrentUser], None],
):
    act_as(TEST_PLAYER)
    _, alices_ticket = open_hosting(client)
    act_as(OTHER_PLAYER)
    bobs_session, _ = open_hosting(client)

    with client.websocket_connect(stream_url(bobs_session, alices_ticket)) as websocket:
        assert_closed_with(websocket, "HOST_TICKET_INVALID")
    assert voice.connect_attempts == 0


def test_unknown_hosting_is_not_found(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    with client.websocket_connect(stream_url(str(uuid.uuid4()), "anything")) as websocket:
        assert_closed_with(websocket, "HOST_SESSION_NOT_FOUND")


def test_w05_voice_model_unreachable(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket = open_hosting(client)
    voice.fail_connect(times=None)

    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        assert_closed_with(websocket, "HOST_REALTIME_UNAVAILABLE")

    # 這場主持還在
    assert client.get(BASE).json()["total"] == 1
    assert client.post(f"{BASE}/{session_id}/connections").status_code == 201


def test_w06_second_device_takes_over(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket_a = open_hosting(client)
    with client.websocket_connect(stream_url(session_id, ticket_a)) as device_a:
        assert device_a.receive_json()["type"] == "state"
        ticket_b = new_ticket(client, session_id)

        with client.websocket_connect(stream_url(session_id, ticket_b)) as device_b:
            assert device_b.receive_json()["type"] == "state"
            assert_closed_with(device_a, "HOST_SESSION_TAKEN_OVER")
            # B 正常
            device_b.send_json({"type": "command", "action": "next"})
            state = device_b.receive_json()
            while state["type"] != "state":
                state = device_b.receive_json()
            assert state["step"] == "setup"


def test_w09_and_w10_commands_over_the_real_socket(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket = open_hosting(client)
    sid = uuid.UUID(session_id)
    host_service.handle_event(sid, HostEvent.connected())
    for _ in range(4):
        host_service.handle_event(sid, HostEvent.command("next"))

    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        first = websocket.receive_json()
        assert (first["step"], first["turn_number"], first["phase_number"]) == ("turn", 1, 1)

        # W-10：看不懂的訊息只回錯誤，連線還在、流程不動
        websocket.send_json({"type": "command", "action": "jump"})
        error = websocket.receive_json()
        assert error["type"] == "error"
        assert error["error"]["code"] == "HOST_BAD_MESSAGE"

        # W-07：聲音原樣轉送給整合層
        websocket.send_bytes(b"\x01\x02\x03\x04")

        # W-09
        websocket.send_json({"type": "command", "action": "next"})
        # 階段 1 的規則要點還沒播完就換階段，所以先收到停播，再收到新的現況
        assert websocket.receive_json() == {"type": "flush"}
        state = websocket.receive_json()
        assert state["type"] == "state"
        assert state["phase_number"] == 2
        assert ("send_audio", b"\x01\x02\x03\x04") in voice.last_connection.actions


def test_w12_device_disconnect_closes_the_voice_connection(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket = open_hosting(client)
    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        websocket.receive_json()
    wait_until(lambda: voice.last_connection.closed)
    assert client.get(BASE).json()["total"] == 1


def test_reopening_kicks_the_device_of_the_old_hosting(
    client: TestClient,
    as_player: CurrentUser,
    host_service: HostService,
    voice: FakeRealtimeVoiceProvider,
):
    session_id, ticket = open_hosting(client)
    with client.websocket_connect(stream_url(session_id, ticket)) as websocket:
        websocket.receive_json()
        open_hosting(client)
        assert_closed_with(websocket, "HOST_SESSION_NOT_FOUND")
