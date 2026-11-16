"""groups service 的單元測試：使用 FakeGroupsRepository，不連資料庫（AGENTS.md 7.5）。

情境對應 openspec/changes/add-groups-calendar/specs/groups/spec.md。
"""

import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied

NOW = datetime(2026, 11, 14, 4, 0, tzinfo=UTC)
# Windows 沒有內建時區資料庫，用固定的 UTC+8 代表台灣時間
TAIPEI = timezone(timedelta(hours=8))
START = NOW + timedelta(days=1)
END = START + timedelta(hours=2)

ORGANIZER = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
PLAYER_B = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000b"), role="player")
PLAYER_C = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000c"), role="player")
PLAYER_D = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000d"), role="player")
ADMIN = CurrentUser(id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), role="admin")


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def repo():
    from tests.groups.fakes import FakeGroupsRepository

    fake = FakeGroupsRepository(NOW)
    for user, name in [
        (ORGANIZER, "開團主"),
        (PLAYER_B, "玩家乙"),
        (PLAYER_C, "玩家丙"),
        (PLAYER_D, "玩家丁"),
        (ADMIN, "管理員"),
    ]:
        fake.add_user(user.id, name)
    return fake


@pytest.fixture
def shop_id(repo) -> uuid.UUID:
    return repo.add_shop("測試桌遊店")


@pytest.fixture
def service(repo, clock: Clock):
    from app.domains.groups.service import GroupsService

    return GroupsService(repo, now=clock)


def create_input(shop_id: uuid.UUID, **overrides: Any):
    from app.domains.groups.schemas import GroupCreate

    values: dict[str, Any] = {
        "shop_id": shop_id,
        "title": "週末輕策略",
        "start_at": START,
        "end_at": END,
        "capacity": 4,
    }
    values.update(overrides)
    return GroupCreate(**values)


def update_input(**values: Any):
    from app.domains.groups.schemas import GroupUpdate

    return GroupUpdate(**values)


def make_group(service, shop_id: uuid.UUID, **overrides: Any):
    return service.create_group(ORGANIZER, create_input(shop_id, **overrides))


def assert_app_error(exc_info: pytest.ExceptionInfo[AppError], status: int, code: str) -> None:
    assert exc_info.value.status_code == status
    assert exc_info.value.code == code


# --- 開團 ---


def test_create_group_organizer_becomes_first_member(service, shop_id):
    group = make_group(service, shop_id)
    assert group.organizer.id == ORGANIZER.id
    assert group.organizer.display_name == "開團主"
    assert group.shop.name == "測試桌遊店"
    assert group.status == "open"
    assert group.member_count == 1
    assert group.waitlist_count == 0
    assert group.remaining_slots == 3
    assert group.my_status == "member"
    assert group.game is None


def test_create_group_with_optional_fields(service, repo, shop_id):
    repo.add_game_row(7, "範例桌遊")
    group = make_group(service, shop_id, fee=300, game_id=7, description="新手可")
    assert group.fee == 300
    assert group.game is not None
    assert (group.game.id, group.game.name) == (7, "範例桌遊")
    assert group.description == "新手可"


def test_create_group_shop_not_found(service, repo):
    with pytest.raises(AppError) as exc_info:
        make_group(service, uuid.uuid4())
    assert_app_error(exc_info, 404, "GROUP_SHOP_NOT_FOUND")
    assert repo.groups == {}


def test_create_group_game_not_found(service, repo, shop_id):
    with pytest.raises(AppError) as exc_info:
        make_group(service, shop_id, game_id=999)
    assert_app_error(exc_info, 404, "GROUP_GAME_NOT_FOUND")
    assert repo.groups == {}


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (START, START),  # 結束等於開始
        (START, START - timedelta(minutes=1)),  # 結束早於開始
        (NOW - timedelta(minutes=1), END),  # 開始時間已過
    ],
)
def test_create_group_invalid_time(service, repo, shop_id, start, end):
    with pytest.raises(AppError) as exc_info:
        make_group(service, shop_id, start_at=start, end_at=end)
    assert_app_error(exc_info, 422, "GROUP_INVALID_TIME")
    assert repo.groups == {}


# --- 揪團資料格式 ---


def test_status_is_ended_after_end_time(service, clock, shop_id):
    group = make_group(service, shop_id)
    clock.now = END + timedelta(seconds=1)
    assert service.get_group(ORGANIZER, group.id).status == "ended"


def test_times_are_returned_in_utc(service, shop_id):
    taipei = START.astimezone(TAIPEI)
    group = make_group(service, shop_id, start_at=taipei)
    assert group.start_at == START
    assert group.start_at.utcoffset() == timedelta(0)


def test_remaining_slots_when_full(service, shop_id):
    group = make_group(service, shop_id, capacity=2)
    service.join_group(PLAYER_B, group.id)
    service.join_group(PLAYER_C, group.id)
    view = service.get_group(PLAYER_C, group.id)
    assert (view.member_count, view.waitlist_count, view.remaining_slots) == (2, 1, 0)
    assert view.my_status == "waitlisted"


def test_get_group_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.get_group(ORGANIZER, uuid.uuid4())
    assert_app_error(exc_info, 404, "GROUP_NOT_FOUND")


# --- 報名 ---


def test_join_with_open_slot(service, shop_id):
    group = make_group(service, shop_id)
    result = service.join_group(PLAYER_B, group.id)
    assert (result.user_id, result.status, result.waitlist_position) == (
        PLAYER_B.id,
        "member",
        None,
    )
    assert service.get_group(PLAYER_B, group.id).member_count == 2


def test_join_when_full_goes_to_waitlist_in_order(service, shop_id):
    group = make_group(service, shop_id, capacity=2)
    service.join_group(PLAYER_B, group.id)
    first = service.join_group(PLAYER_C, group.id)
    second = service.join_group(PLAYER_D, group.id)
    assert (first.status, first.waitlist_position) == ("waitlisted", 1)
    assert (second.status, second.waitlist_position) == ("waitlisted", 2)
    assert service.get_group(ORGANIZER, group.id).member_count == 2


@pytest.mark.parametrize("full", [False, True])
def test_join_twice(service, shop_id, full):
    group = make_group(service, shop_id, capacity=2)
    if full:
        service.join_group(PLAYER_B, group.id)
        user = PLAYER_C  # 在候補中
    else:
        user = PLAYER_B  # 已是成員
    service.join_group(user, group.id)
    with pytest.raises(AppError) as exc_info:
        service.join_group(user, group.id)
    assert_app_error(exc_info, 409, "GROUP_ALREADY_JOINED")


def test_organizer_join_own_group_is_duplicate(service, shop_id):
    group = make_group(service, shop_id)
    with pytest.raises(AppError) as exc_info:
        service.join_group(ORGANIZER, group.id)
    assert_app_error(exc_info, 409, "GROUP_ALREADY_JOINED")


def test_join_cancelled_group(service, shop_id):
    group = make_group(service, shop_id)
    service.update_group(ORGANIZER, group.id, update_input(status="cancelled"))
    with pytest.raises(AppError) as exc_info:
        service.join_group(PLAYER_B, group.id)
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


def test_join_ended_group(service, clock, shop_id):
    group = make_group(service, shop_id)
    clock.now = END
    with pytest.raises(AppError) as exc_info:
        service.join_group(PLAYER_B, group.id)
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


def test_join_group_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.join_group(PLAYER_B, uuid.uuid4())
    assert_app_error(exc_info, 404, "GROUP_NOT_FOUND")


# --- 名單 ---


def test_list_members_order(service, shop_id):
    group = make_group(service, shop_id, capacity=2)
    service.join_group(PLAYER_B, group.id)
    service.join_group(PLAYER_C, group.id)
    members = service.list_members(ORGANIZER, group.id)
    assert members.total == 3
    assert [(m.user_id, m.status, m.waitlist_position) for m in members.items] == [
        (ORGANIZER.id, "member", None),
        (PLAYER_B.id, "member", None),
        (PLAYER_C.id, "waitlisted", 1),
    ]
    assert members.items[0].display_name == "開團主"


def test_list_members_group_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.list_members(ORGANIZER, uuid.uuid4())
    assert_app_error(exc_info, 404, "GROUP_NOT_FOUND")


# --- 退出與遞補 ---


def full_group_with_waitlist(service, shop_id, waitlisted=(PLAYER_C,)):
    group = make_group(service, shop_id, capacity=2)
    service.join_group(PLAYER_B, group.id)
    for user in waitlisted:
        service.join_group(user, group.id)
    return group


def test_member_leaves_and_waitlist_promoted(service, shop_id):
    group = full_group_with_waitlist(service, shop_id)
    service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    view = service.get_group(PLAYER_C, group.id)
    assert (view.member_count, view.waitlist_count) == (2, 0)
    assert view.my_status == "member"


def test_member_leaves_without_waitlist(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    assert service.get_group(ORGANIZER, group.id).member_count == 1


def test_waitlisted_leaves_and_positions_shift(service, shop_id):
    group = full_group_with_waitlist(service, shop_id, waitlisted=(PLAYER_C, PLAYER_D))
    service.remove_member(PLAYER_C, group.id, PLAYER_C.id)
    members = service.list_members(ORGANIZER, group.id).items
    assert [(m.user_id, m.waitlist_position) for m in members if m.status == "waitlisted"] == [
        (PLAYER_D.id, 1)
    ]
    assert service.get_group(ORGANIZER, group.id).member_count == 2


@pytest.mark.parametrize("remover", [ORGANIZER, ADMIN])
def test_organizer_or_admin_removes_member(service, shop_id, remover):
    group = full_group_with_waitlist(service, shop_id)
    service.remove_member(remover, group.id, PLAYER_B.id)
    view = service.get_group(PLAYER_C, group.id)
    assert view.my_status == "member"
    assert view.member_count == 2


def test_player_cannot_remove_others(service, repo, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.join_group(PLAYER_C, group.id)
    with pytest.raises(PermissionDenied):
        service.remove_member(PLAYER_B, group.id, PLAYER_C.id)
    assert service.get_group(ORGANIZER, group.id).member_count == 3


@pytest.mark.parametrize("remover", [ORGANIZER, ADMIN])
def test_organizer_cannot_leave(service, shop_id, remover):
    group = make_group(service, shop_id)
    with pytest.raises(AppError) as exc_info:
        service.remove_member(remover, group.id, ORGANIZER.id)
    assert_app_error(exc_info, 409, "GROUP_ORGANIZER_CANNOT_LEAVE")


def test_remove_not_in_group(service, shop_id):
    group = make_group(service, shop_id)
    with pytest.raises(AppError) as exc_info:
        service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    assert_app_error(exc_info, 404, "GROUP_MEMBER_NOT_FOUND")


def test_leave_cancelled_group(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.update_group(ORGANIZER, group.id, update_input(status="cancelled"))
    with pytest.raises(AppError) as exc_info:
        service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


def test_leave_ended_group(service, clock, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    clock.now = END
    with pytest.raises(AppError) as exc_info:
        service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


def test_remove_group_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.remove_member(PLAYER_B, uuid.uuid4(), PLAYER_B.id)
    assert_app_error(exc_info, 404, "GROUP_NOT_FOUND")


# --- 修改與取消 ---


def test_organizer_updates_title(service, shop_id):
    group = make_group(service, shop_id, fee=200)
    updated = service.update_group(ORGANIZER, group.id, update_input(title="新標題"))
    assert updated.title == "新標題"
    assert (updated.fee, updated.capacity, updated.start_at) == (200, 4, START)


def test_update_can_clear_optional_fields(service, repo, shop_id):
    repo.add_game_row(7, "範例桌遊")
    group = make_group(service, shop_id, fee=200, game_id=7, description="說明")
    updated = service.update_group(
        ORGANIZER, group.id, update_input(fee=None, game_id=None, description=None)
    )
    assert (updated.fee, updated.game, updated.description) == (None, None, None)


@pytest.mark.parametrize("user", [ORGANIZER, ADMIN])
def test_cancel_group(service, shop_id, user):
    group = make_group(service, shop_id)
    updated = service.update_group(user, group.id, update_input(status="cancelled"))
    assert updated.status == "cancelled"
    assert service.list_groups(ORGANIZER).total == 0
    assert service.get_group(ORGANIZER, group.id).status == "cancelled"


@pytest.mark.parametrize(
    "user",
    [
        PLAYER_B,
        # 同一間店的店家人員，也不能改別人開的揪團
        CurrentUser(id=uuid.uuid4(), role="shop_staff", shop_id=uuid.uuid4()),
    ],
)
def test_non_organizer_cannot_update(service, repo, shop_id, user):
    group = make_group(service, shop_id)
    if user.role == "shop_staff":
        user = CurrentUser(id=user.id, role="shop_staff", shop_id=shop_id)
    with pytest.raises(PermissionDenied):
        service.update_group(user, group.id, update_input(title="改掉"))
    assert service.get_group(ORGANIZER, group.id).title == "週末輕策略"


def test_capacity_below_members(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.join_group(PLAYER_C, group.id)
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(capacity=2))
    assert_app_error(exc_info, 409, "GROUP_CAPACITY_BELOW_MEMBERS")
    assert service.get_group(ORGANIZER, group.id).capacity == 4


def test_raising_capacity_promotes_waitlist(service, shop_id):
    group = full_group_with_waitlist(service, shop_id, waitlisted=(PLAYER_C, PLAYER_D))
    updated = service.update_group(ORGANIZER, group.id, update_input(capacity=3))
    assert (updated.member_count, updated.waitlist_count) == (3, 1)
    assert service.get_group(PLAYER_C, group.id).my_status == "member"
    assert service.get_group(PLAYER_D, group.id).my_status == "waitlisted"


def test_update_cancelled_group(service, shop_id):
    group = make_group(service, shop_id)
    service.update_group(ORGANIZER, group.id, update_input(status="cancelled"))
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(title="復活"))
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


def test_update_ended_group(service, clock, shop_id):
    group = make_group(service, shop_id)
    clock.now = END
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(title="補記"))
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


@pytest.mark.parametrize(
    "values",
    [
        {"end_at": START - timedelta(minutes=1)},
        {"start_at": END},
        {"start_at": NOW - timedelta(minutes=1)},
    ],
)
def test_update_invalid_time(service, shop_id, values):
    group = make_group(service, shop_id)
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(**values))
    assert_app_error(exc_info, 422, "GROUP_INVALID_TIME")


def test_update_game_not_found(service, shop_id):
    group = make_group(service, shop_id)
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(game_id=999))
    assert_app_error(exc_info, 404, "GROUP_GAME_NOT_FOUND")


def test_update_group_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, uuid.uuid4(), update_input(title="x"))
    assert_app_error(exc_info, 404, "GROUP_NOT_FOUND")


# --- 列表 ---


def test_list_groups_filters_and_pages(service, repo, shop_id):
    other_shop = repo.add_shop("另一間店")
    a = make_group(service, shop_id, start_at=START, end_at=END)
    b = make_group(
        service, other_shop, start_at=START + timedelta(days=6), end_at=END + timedelta(days=6)
    )
    c = service.create_group(
        PLAYER_B,
        create_input(shop_id, start_at=START + timedelta(hours=3), end_at=END + timedelta(hours=3)),
    )

    everything = service.list_groups(ORGANIZER)
    assert [g.id for g in everything.items] == [a.id, c.id, b.id]
    assert everything.total == 3

    day = service.list_groups(
        ORGANIZER, start_from=START - timedelta(hours=1), start_before=START + timedelta(days=1)
    )
    assert [g.id for g in day.items] == [a.id, c.id]

    assert [g.id for g in service.list_groups(ORGANIZER, organizer_id=PLAYER_B.id).items] == [c.id]
    assert [g.id for g in service.list_groups(ORGANIZER, shop_id=other_shop).items] == [b.id]

    page2 = service.list_groups(ORGANIZER, page=2, page_size=2)
    assert [g.id for g in page2.items] == [b.id]
    assert page2.total == 3


def test_list_groups_empty(service):
    result = service.list_groups(ORGANIZER)
    assert (result.items, result.total) == ([], 0)
