"""GroupsServiceLookup：matches 透過 groups 的 service 讀揪團成員（AGENTS.md 4.2）。

只留正式成員（不含候補），依加入順序；揪團不存在回 None。用手寫 fake 取代 GroupsService。
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError

USER = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
GROUP_ID = uuid.uuid4()


def member(name: str, status: str, minute: int):
    from app.domains.groups.schemas import MemberResponse

    return MemberResponse(
        user_id=uuid.uuid4(),
        display_name=name,
        status=status,
        waitlist_position=1 if status == "waitlisted" else None,
        joined_at=datetime(2030, 1, 1, 10, minute, tzinfo=UTC),
    )


class FakeGroupsService:
    def __init__(self, members=None, error: AppError | None = None) -> None:
        self.members = members or []
        self.error = error
        self.calls: list[tuple[CurrentUser, uuid.UUID]] = []

    def list_members(self, user: CurrentUser, group_id: uuid.UUID):
        from app.domains.groups.schemas import MemberListResponse

        self.calls.append((user, group_id))
        if self.error is not None:
            raise self.error
        return MemberListResponse(items=self.members, total=len(self.members))


def lookup(service: FakeGroupsService):
    from app.domains.matches.groups_lookup import GroupsServiceLookup

    return GroupsServiceLookup(service, USER)  # type: ignore[arg-type]


def test_returns_only_members_in_order_of_joining():
    service = FakeGroupsService(
        [member("乙", "member", 1), member("甲", "member", 0), member("丙", "waitlisted", 2)]
    )
    found = lookup(service).get_members(GROUP_ID)
    assert [m.display_name for m in found] == ["甲", "乙"]
    assert service.calls == [(USER, GROUP_ID)]


def test_missing_group_returns_none():
    error = AppError(404, "GROUP_NOT_FOUND", "找不到這個揪團")
    assert lookup(FakeGroupsService(error=error)).get_members(GROUP_ID) is None


def test_other_errors_are_not_swallowed():
    error = AppError(503, "SOMETHING_ELSE", "壞了")
    with pytest.raises(AppError):
        lookup(FakeGroupsService(error=error)).get_members(GROUP_ID)
