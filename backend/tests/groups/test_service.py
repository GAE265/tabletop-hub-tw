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
    assert group.games == []


def test_create_group_with_optional_fields(service, repo, shop_id):
    repo.add_game_row(7, "範例桌遊")
    group = make_group(service, shop_id, fee=300, game_ids=[7], description="新手可")
    assert group.fee == 300
    assert [(g.id, g.name) for g in group.games] == [(7, "範例桌遊")]
    assert group.description == "新手可"


def test_create_group_with_games_in_selected_order(service, repo, shop_id):
    repo.add_game_row(1, "阿瓦隆")
    repo.add_game_row(3, "馬可波羅")
    group = make_group(service, shop_id, game_ids=[3, 1])
    assert [g.id for g in group.games] == [3, 1]
    assert [g.name for g in group.games] == ["馬可波羅", "阿瓦隆"]


def test_create_group_without_games(service, shop_id):
    assert make_group(service, shop_id, game_ids=[]).games == []


def test_create_group_shop_not_found(service, repo):
    with pytest.raises(AppError) as exc_info:
        make_group(service, uuid.uuid4())
    assert_app_error(exc_info, 404, "GROUP_SHOP_NOT_FOUND")
    assert repo.groups == {}


def test_create_group_game_not_found(service, repo, shop_id):
    repo.add_game_row(1, "阿瓦隆")
    with pytest.raises(AppError) as exc_info:
        make_group(service, shop_id, game_ids=[1, 999, 998])
    assert_app_error(exc_info, 404, "GROUP_GAME_NOT_FOUND")
    assert exc_info.value.details == {"game_ids": [999, 998]}
    assert repo.groups == {}


def test_duplicate_game_ids_are_rejected(shop_id):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        create_input(shop_id, game_ids=[3, 3])
    with pytest.raises(ValidationError):
        update_input(game_ids=[3, 3])


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
    group = make_group(service, shop_id, fee=200, game_ids=[7], description="說明")
    updated = service.update_group(
        ORGANIZER, group.id, update_input(fee=None, game_ids=[], description=None)
    )
    assert (updated.fee, updated.games, updated.description) == (None, [], None)


def test_update_replaces_games(service, repo, shop_id):
    repo.add_game_row(1, "阿瓦隆")
    repo.add_game_row(2, "卡坦島")
    group = make_group(service, shop_id, game_ids=[1])
    updated = service.update_group(ORGANIZER, group.id, update_input(game_ids=[2, 1]))
    assert [g.id for g in updated.games] == [2, 1]


def test_update_other_fields_keeps_games(service, repo, shop_id):
    repo.add_game_row(1, "阿瓦隆")
    group = make_group(service, shop_id, game_ids=[1])
    updated = service.update_group(ORGANIZER, group.id, update_input(title="新標題"))
    assert [g.id for g in updated.games] == [1]


def test_update_games_cannot_be_null():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        update_input(game_ids=None)


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
        service.update_group(ORGANIZER, group.id, update_input(game_ids=[999]))
    assert_app_error(exc_info, 404, "GROUP_GAME_NOT_FOUND")
    assert exc_info.value.details == {"game_ids": [999]}


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


# --- 確定成團與通知（openspec/changes/add-groups-notifications/specs/groups-notifications）---


def notices(service, user: CurrentUser) -> list[tuple[str, uuid.UUID]]:
    """目前使用者的通知，新的在前，只取 (type, group_id)。"""
    return [(n.type, n.group.id) for n in service.list_notifications(user).items]


@pytest.mark.parametrize("user", [ORGANIZER, ADMIN])
def test_confirm_group(service, clock, shop_id, user):
    group = make_group(service, shop_id)
    assert group.confirmed_at is None
    updated = service.update_group(user, group.id, update_input(confirmed=True))
    assert updated.confirmed_at == clock.now
    assert updated.status == "open"


def test_confirmed_group_still_accepts_joins(service, shop_id):
    group = make_group(service, shop_id)
    service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    assert service.join_group(PLAYER_B, group.id).status == "member"


def test_non_organizer_cannot_confirm(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    with pytest.raises(PermissionDenied):
        service.update_group(PLAYER_B, group.id, update_input(confirmed=True))
    assert service.get_group(ORGANIZER, group.id).confirmed_at is None
    assert notices(service, ORGANIZER) == []


def test_confirm_twice(service, clock, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    first = service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    clock.now += timedelta(minutes=5)
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    assert_app_error(exc_info, 409, "GROUP_ALREADY_CONFIRMED")
    assert service.get_group(ORGANIZER, group.id).confirmed_at == first.confirmed_at
    assert len(notices(service, PLAYER_B)) == 1


def test_confirm_cancelled_group(service, shop_id):
    group = make_group(service, shop_id)
    service.update_group(ORGANIZER, group.id, update_input(status="cancelled"))
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


def test_confirm_ended_group(service, clock, shop_id):
    group = make_group(service, shop_id)
    clock.now = END + timedelta(minutes=1)
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    assert_app_error(exc_info, 409, "GROUP_CLOSED")


@pytest.mark.parametrize("value", [False, None])
def test_confirmed_only_accepts_true(value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        update_input(confirmed=value)


def test_confirm_group_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.update_group(ORGANIZER, uuid.uuid4(), update_input(confirmed=True))
    assert_app_error(exc_info, 404, "GROUP_NOT_FOUND")


def test_confirm_notifies_members_except_actor_and_waitlist(service, shop_id):
    group = make_group(service, shop_id, capacity=3)
    service.join_group(PLAYER_B, group.id)
    service.join_group(PLAYER_C, group.id)
    service.join_group(PLAYER_D, group.id)  # 候補
    service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    assert notices(service, PLAYER_B) == [("group_confirmed", group.id)]
    assert notices(service, PLAYER_C) == [("group_confirmed", group.id)]
    assert notices(service, ORGANIZER) == []
    assert notices(service, PLAYER_D) == []


def test_admin_confirm_notifies_organizer_too(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.update_group(ADMIN, group.id, update_input(confirmed=True))
    assert notices(service, ORGANIZER) == [("group_confirmed", group.id)]
    assert notices(service, PLAYER_B) == [("group_confirmed", group.id)]
    assert notices(service, ADMIN) == []


def test_cancel_notifies_members_and_waitlist_except_actor(service, shop_id):
    group = full_group_with_waitlist(service, shop_id)
    service.update_group(ORGANIZER, group.id, update_input(status="cancelled"))
    assert notices(service, PLAYER_B) == [("group_cancelled", group.id)]
    assert notices(service, PLAYER_C) == [("group_cancelled", group.id)]
    assert notices(service, ORGANIZER) == []


def test_cancel_after_confirm_notifies_again(service, clock, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    clock.now += timedelta(minutes=1)
    service.update_group(ORGANIZER, group.id, update_input(status="cancelled"))
    assert notices(service, PLAYER_B) == [
        ("group_cancelled", group.id),
        ("group_confirmed", group.id),
    ]


def test_failed_cancel_does_not_notify(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    with pytest.raises(PermissionDenied):
        service.update_group(PLAYER_B, group.id, update_input(status="cancelled"))
    assert notices(service, ORGANIZER) == []
    assert notices(service, PLAYER_B) == []


def test_member_leaves_notifies_first_waitlisted(service, shop_id):
    group = full_group_with_waitlist(service, shop_id, waitlisted=(PLAYER_C, PLAYER_D))
    service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    assert notices(service, PLAYER_C) == [("waitlist_promoted", group.id)]
    assert notices(service, PLAYER_D) == []


def test_member_removed_by_organizer_notifies_promoted(service, shop_id):
    group = full_group_with_waitlist(service, shop_id)
    service.remove_member(ORGANIZER, group.id, PLAYER_B.id)
    assert notices(service, PLAYER_C) == [("waitlist_promoted", group.id)]
    assert notices(service, PLAYER_B) == []


def test_raising_capacity_notifies_each_promoted(service, repo, shop_id):
    extra = CurrentUser(id=uuid.uuid4(), role="player")
    repo.add_user(extra.id, "玩家戊")
    group = full_group_with_waitlist(service, shop_id, waitlisted=(PLAYER_C, PLAYER_D, extra))
    service.update_group(ORGANIZER, group.id, update_input(capacity=4))
    assert notices(service, PLAYER_C) == [("waitlist_promoted", group.id)]
    assert notices(service, PLAYER_D) == [("waitlist_promoted", group.id)]
    assert notices(service, extra) == []


def test_waitlisted_leaves_does_not_notify(service, shop_id):
    group = full_group_with_waitlist(service, shop_id, waitlisted=(PLAYER_C, PLAYER_D))
    service.remove_member(PLAYER_C, group.id, PLAYER_C.id)
    assert notices(service, PLAYER_D) == []


def test_member_leaves_without_waitlist_does_not_notify(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.remove_member(PLAYER_B, group.id, PLAYER_B.id)
    for user in (ORGANIZER, PLAYER_B):
        assert notices(service, user) == []


# --- 查詢通知與標成已讀 ---


def test_list_notifications_only_own_newest_first_and_paged(service, clock, shop_id):
    groups = []
    for title in ("第一團", "第二團", "第三團"):
        group = make_group(service, shop_id, title=title)
        service.join_group(PLAYER_B, group.id)
        service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
        groups.append(group)
        clock.now += timedelta(minutes=1)
    page = service.list_notifications(PLAYER_B, page=1, page_size=2)
    assert (page.total, page.unread_count) == (3, 3)
    assert [n.group.title for n in page.items] == ["第三團", "第二團"]
    first = page.items[0]
    assert first.type == "group_confirmed"
    assert first.group.id == groups[2].id
    assert first.group.start_at == START
    assert first.read_at is None
    assert first.created_at == NOW + timedelta(minutes=2)
    second = service.list_notifications(PLAYER_B, page=2, page_size=2)
    assert [n.group.title for n in second.items] == ["第一團"]
    assert second.unread_count == 3
    assert service.list_notifications(PLAYER_C).total == 0


def test_list_notifications_empty(service):
    result = service.list_notifications(PLAYER_D)
    assert (result.items, result.total, result.unread_count) == ([], 0, 0)


def test_notification_shows_current_group_title(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    service.update_group(ORGANIZER, group.id, update_input(title="改名後"))
    assert service.list_notifications(PLAYER_B).items[0].group.title == "改名後"


def confirmed_notice(service, shop_id):
    group = make_group(service, shop_id)
    service.join_group(PLAYER_B, group.id)
    service.update_group(ORGANIZER, group.id, update_input(confirmed=True))
    return service.list_notifications(PLAYER_B).items[0]


def test_mark_notification_read(service, clock, shop_id):
    notice = confirmed_notice(service, shop_id)
    clock.now += timedelta(minutes=3)
    read = service.mark_notification_read(PLAYER_B, notice.id)
    assert read.id == notice.id
    assert read.read_at == clock.now
    assert service.list_notifications(PLAYER_B).unread_count == 0


def test_mark_read_twice_keeps_first_time(service, clock, shop_id):
    notice = confirmed_notice(service, shop_id)
    first = service.mark_notification_read(PLAYER_B, notice.id)
    clock.now += timedelta(minutes=3)
    again = service.mark_notification_read(PLAYER_B, notice.id)
    assert again.read_at == first.read_at


def test_cannot_mark_others_notification(service, shop_id):
    notice = confirmed_notice(service, shop_id)
    with pytest.raises(AppError) as exc_info:
        service.mark_notification_read(PLAYER_C, notice.id)
    assert_app_error(exc_info, 404, "GROUP_NOTIFICATION_NOT_FOUND")
    assert service.list_notifications(PLAYER_B).unread_count == 1


def test_mark_read_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.mark_notification_read(PLAYER_B, uuid.uuid4())
    assert_app_error(exc_info, 404, "GROUP_NOTIFICATION_NOT_FOUND")
