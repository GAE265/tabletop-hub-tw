"""把 groups 的 service 包成 matches 需要的「揪團是否存在」介面（AGENTS.md 4.2：只呼叫對方的
service，不碰它的 repository 或 models）。"""

import uuid

from app.core.auth import CurrentUser
from app.core.errors import AppError
from app.domains.groups.service import GroupsService


class GroupsServiceLookup:
    def __init__(self, service: GroupsService, user: CurrentUser) -> None:
        self._service = service
        self._user = user

    def group_exists(self, group_id: uuid.UUID) -> bool:
        try:
            self._service.get_group(self._user, group_id)
        except AppError as exc:
            if exc.code == "GROUP_NOT_FOUND":
                return False
            raise
        return True
