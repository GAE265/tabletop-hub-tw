"""host 的 service：開主持、列出、通行碼、權限、一人一場、30 分鐘清除（host spec §2、§11）。

單元測試：圖跑真的（只在記憶體），時間用假時鐘，不連資料庫。
"""

import ast
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied
from app.domains.host import service as service_module
from app.domains.host.graph import HostEvent, HostGraph
from app.domains.host.service import (
    HostService,
    HostTicketInvalid,
)
from tests.host.fakes import FakeClock

ALICE = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
BOB = CurrentUser(id=uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"), role="player")
STAFF = CurrentUser(
    id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
    role="shop_staff",
    shop_id=uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
)
ADMIN = CurrentUser(id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), role="admin")
STRANGER = CurrentUser(id=uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"), role="visitor")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def graph() -> HostGraph:
    return HostGraph()


@pytest.fixture
def service(graph: HostGraph, clock: FakeClock) -> HostService:
    return HostService(graph, clock=clock)


def open_session(service: HostService, user: CurrentUser = ALICE, **overrides: object):
    kwargs: dict[str, object] = {"player_count": 7, "turn_taking_mode": "auto", "voice": "male"}
    kwargs.update(overrides)
    return service.open_session(user, **kwargs)  # type: ignore[arg-type]


def assert_not_found(exc: pytest.ExceptionInfo[AppError]) -> None:
    assert exc.value.status_code == 404
    assert exc.value.code == "HOST_SESSION_NOT_FOUND"


# --- 開主持 ---


def test_open_session_starts_at_opening_with_a_ticket(service: HostService, clock: FakeClock):
    view, ticket = open_session(service)
    assert view.owner_id == ALICE.id
    assert view.created_at == clock.now
    assert view.snapshot.status == "active"
    assert view.snapshot.step == "opening"
    assert (view.snapshot.player_count, view.snapshot.turn_taking_mode, view.snapshot.voice) == (
        7,
        "auto",
        "male",
    )
    assert ticket.session_id == view.id
    assert ticket.ticket
    # 通行碼 60 秒後到期（D12 §5）
    assert ticket.expires_at == clock.now + timedelta(seconds=60)


@pytest.mark.parametrize("user", [ALICE, STAFF, ADMIN])
def test_every_role_can_open(service: HostService, user: CurrentUser):
    view, _ = open_session(service, user)
    assert view.owner_id == user.id


def test_unknown_role_cannot_open(service: HostService):
    with pytest.raises(PermissionDenied):
        open_session(service, STRANGER)


def test_tickets_are_unguessable_and_unique(service: HostService):
    view, first = open_session(service)
    _, second = service.issue_ticket(ALICE, view.id)
    assert first.ticket != second.ticket
    assert len(first.ticket) >= 32


def test_m09_opening_again_clears_the_old_hosting_and_its_memory(
    service: HostService, graph: HostGraph
):
    old, _ = open_session(service)
    service.handle_event(old.id, HostEvent.connected())
    assert graph.exists(str(old.id))

    new, _ = open_session(service, player_count=5)

    assert new.id != old.id
    assert graph.exists(str(old.id)) is False
    assert [view.id for view in service.list_sessions(ALICE)] == [new.id]
    with pytest.raises(AppError) as exc:
        service.issue_ticket(ALICE, old.id)
    assert_not_found(exc)


def test_opening_again_does_not_touch_other_peoples_hosting(service: HostService):
    bobs, _ = open_session(service, BOB)
    open_session(service, ALICE)
    open_session(service, ALICE)
    assert [view.id for view in service.list_sessions(BOB)] == [bobs.id]


# --- 列出 ---


def test_list_is_empty_without_a_hosting(service: HostService):
    assert service.list_sessions(ALICE) == []


def test_list_only_shows_my_own_even_for_admin(service: HostService):
    mine, _ = open_session(service, ALICE)
    assert [view.id for view in service.list_sessions(ALICE)] == [mine.id]
    assert service.list_sessions(BOB) == []
    assert service.list_sessions(ADMIN) == []


def test_list_shows_current_position(service: HostService):
    view, _ = open_session(service)
    # 開場 → 開局準備 → 夜晚第一步 → 夜晚第二步 → 第 1 回合階段 1：按 4 次下一步
    for event in (
        HostEvent.connected(),
        HostEvent.command("next"),
        HostEvent.command("next"),
        HostEvent.command("next"),
        HostEvent.command("next"),
    ):
        service.handle_event(view.id, event)
    listed = service.list_sessions(ALICE)[0]
    assert (listed.snapshot.step, listed.snapshot.turn_number, listed.snapshot.phase_number) == (
        "turn",
        1,
        1,
    )


# --- 通行碼與權限 ---


def test_owner_and_admin_can_get_a_ticket(service: HostService):
    view, _ = open_session(service)
    assert service.issue_ticket(ALICE, view.id)[1].session_id == view.id
    assert service.issue_ticket(ADMIN, view.id)[1].session_id == view.id


def test_someone_else_cannot_get_a_ticket(service: HostService):
    view, _ = open_session(service)
    with pytest.raises(PermissionDenied) as exc:
        service.issue_ticket(BOB, view.id, turn_taking_mode="push_to_talk")
    assert exc.value.code == "PERMISSION_DENIED"
    # 接話方式沒變
    assert service.list_sessions(ALICE)[0].snapshot.turn_taking_mode == "auto"


def test_ticket_for_an_unknown_hosting_is_not_found(service: HostService):
    with pytest.raises(AppError) as exc:
        service.issue_ticket(ALICE, uuid.uuid4())
    assert_not_found(exc)


def test_ticket_with_another_turn_taking_mode_carries_it(service: HostService):
    view, _ = open_session(service)
    switched, ticket = service.issue_ticket(ALICE, view.id, turn_taking_mode="push_to_talk")
    assert ticket.turn_taking_mode == "push_to_talk"
    # 回應裡的現況已經是新的接話方式；真的切換發生在裝置用這張通行碼連上的時候
    assert switched.snapshot.turn_taking_mode == "push_to_talk"
    _, same = service.issue_ticket(ALICE, view.id)
    assert same.turn_taking_mode is None


def test_redeem_ticket_once(service: HostService):
    view, ticket = open_session(service)
    redeemed = service.redeem_ticket(view.id, ticket.ticket)
    assert redeemed.session_id == view.id
    with pytest.raises(HostTicketInvalid):
        service.redeem_ticket(view.id, ticket.ticket)


def test_redeem_ticket_expires_after_60_seconds(service: HostService, clock: FakeClock):
    view, ticket = open_session(service)
    clock.advance(seconds=59)
    _, late = service.issue_ticket(ALICE, view.id)
    clock.advance(seconds=2)
    with pytest.raises(HostTicketInvalid):
        service.redeem_ticket(view.id, ticket.ticket)
    assert service.redeem_ticket(view.id, late.ticket).session_id == view.id


def test_redeem_ticket_only_works_for_its_own_hosting(service: HostService):
    alices, ticket = open_session(service, ALICE)
    bobs, _ = open_session(service, BOB)
    with pytest.raises(HostTicketInvalid):
        service.redeem_ticket(bobs.id, ticket.ticket)
    # 用錯地方不會把通行碼用掉
    assert service.redeem_ticket(alices.id, ticket.ticket).session_id == alices.id


def test_redeem_unknown_ticket(service: HostService):
    view, _ = open_session(service)
    with pytest.raises(HostTicketInvalid):
        service.redeem_ticket(view.id, "no-such-ticket")


def test_redeem_ticket_of_a_cleared_hosting_is_not_found(service: HostService):
    old, ticket = open_session(service)
    open_session(service)
    with pytest.raises(AppError) as exc:
        service.redeem_ticket(old.id, ticket.ticket)
    assert_not_found(exc)


# --- 30 分鐘清除 ---


def test_hosting_without_any_device_is_cleared_after_30_minutes(
    service: HostService, graph: HostGraph, clock: FakeClock
):
    view, _ = open_session(service)
    clock.advance(minutes=29, seconds=59)
    assert len(service.list_sessions(ALICE)) == 1
    clock.advance(seconds=1)
    assert service.list_sessions(ALICE) == []
    assert graph.exists(str(view.id)) is False
    with pytest.raises(AppError) as exc:
        service.issue_ticket(ALICE, view.id)
    assert_not_found(exc)


def test_hosting_with_a_device_connected_is_not_cleared(service: HostService, clock: FakeClock):
    view, _ = open_session(service)
    service.device_connected(view.id)
    clock.advance(minutes=120)
    assert len(service.list_sessions(ALICE)) == 1


def test_30_minutes_count_from_when_the_device_left(service: HostService, clock: FakeClock):
    view, _ = open_session(service)
    clock.advance(minutes=20)
    service.device_connected(view.id)
    clock.advance(minutes=50)
    service.device_disconnected(view.id)
    clock.advance(minutes=29)
    assert len(service.list_sessions(ALICE)) == 1
    clock.advance(minutes=1)
    assert service.list_sessions(ALICE) == []


def test_m08_ended_hosting_is_cleared_with_its_memory_after_30_minutes(
    service: HostService, graph: HostGraph, clock: FakeClock
):
    view, _ = open_session(service)
    service.device_connected(view.id)
    service.handle_event(view.id, HostEvent.connected())
    clock.advance(minutes=45)
    service.handle_event(view.id, HostEvent.command("end"))
    assert service.list_sessions(ALICE)[0].snapshot.status == "ended"

    clock.advance(minutes=29)
    assert len(service.list_sessions(ALICE)) == 1
    assert graph.exists(str(view.id)) is True

    clock.advance(minutes=1)
    # 已結束滿 30 分鐘：就算裝置還連著也清掉，連圖裡的整局記憶一起
    assert service.list_sessions(ALICE) == []
    assert graph.exists(str(view.id)) is False


def test_ended_hosting_can_still_get_a_ticket_within_30_minutes(
    service: HostService, clock: FakeClock
):
    view, _ = open_session(service)
    service.handle_event(view.id, HostEvent.connected())
    service.handle_event(view.id, HostEvent.command("end"))
    clock.advance(minutes=10)
    again, ticket = service.issue_ticket(ALICE, view.id)
    # 拿通行碼不會改變狀態；連上後才變回進行中
    assert again.snapshot.status == "ended"
    assert ticket.session_id == view.id


def test_continuing_an_ended_hosting_stops_the_ended_countdown(
    service: HostService, clock: FakeClock
):
    view, _ = open_session(service)
    service.device_connected(view.id)
    service.handle_event(view.id, HostEvent.connected())
    service.handle_event(view.id, HostEvent.command("end"))
    clock.advance(minutes=20)
    # 接著主持：連上後狀態變回進行中
    service.handle_event(view.id, HostEvent.connected())
    assert service.list_sessions(ALICE)[0].snapshot.status == "active"
    clock.advance(minutes=60)
    assert len(service.list_sessions(ALICE)) == 1


def test_handle_event_on_a_cleared_hosting_is_not_found(service: HostService, clock: FakeClock):
    view, _ = open_session(service)
    clock.advance(minutes=31)
    with pytest.raises(AppError) as exc:
        service.handle_event(view.id, HostEvent.command("next"))
    assert_not_found(exc)


def test_expired_tickets_are_forgotten(service: HostService, clock: FakeClock):
    view, _ = open_session(service)
    service.device_connected(view.id)
    for _ in range(5):
        service.issue_ticket(ALICE, view.id)
    assert service.pending_ticket_count() == 6
    clock.advance(seconds=61)
    service.issue_ticket(ALICE, view.id)
    assert service.pending_ticket_count() == 1


# --- 分層（AGENTS.md §4.2） ---


def test_service_does_not_import_fastapi() -> None:
    tree = ast.parse(Path(service_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert name.split(".")[0] not in ("fastapi", "starlette"), name
