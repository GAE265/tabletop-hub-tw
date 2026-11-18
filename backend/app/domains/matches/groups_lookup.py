"""把 groups 的 service 包成 matches 需要的「揪團成員」介面（AGENTS.md 4.2：只呼叫對方的
service，不碰它的 repository 或 models）。"""

import uuid
from dataclasses import dataclass

from app.core.auth import CurrentUser
from app.core.errors import AppError
from app.domains.groups.service import GroupsService


@dataclass(frozen=True)
class GroupMemberInfo:
    """揪團的一位正式成員：帳號與顯示名稱。"""

    user_id: uuid.UUID
    display_name: str


class GroupsServiceLookup:
    def __init__(self, service: GroupsService, user: CurrentUser) -> None:
        self._service = service
        self._user = user

    def get_members(self, group_id: uuid.UUID) -> list[GroupMemberInfo] | None:
        """揪團的正式成員（不含候補），依加入先後；找不到揪團時回 None。"""
        try:
            listing = self._service.list_members(self._user, group_id)
        except AppError as exc:
            if exc.code == "GROUP_NOT_FOUND":
                return None
            raise
        members = [m for m in listing.items if m.status == "member"]
        members.sort(key=lambda m: m.joined_at)
        return [GroupMemberInfo(m.user_id, m.display_name) for m in members]
