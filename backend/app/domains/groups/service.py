"""揪團與候補的商業規則：開團、報名與候補、退出與遞補、修改與取消、權限。

不 import FastAPI（AGENTS.md 4.2）；錯誤一律拋 AppError，由錯誤處理器轉成統一格式。
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied
from app.domains.groups.repository import GroupRecord, GroupView
from app.domains.groups.schemas import (
    GameRef,
    GroupCreate,
    GroupListResponse,
    GroupResponse,
    GroupUpdate,
    JoinResponse,
    MemberListResponse,
    MemberResponse,
    ShopRef,
    UserRef,
)


class GroupsRepositoryProtocol(Protocol):
    """service 需要的資料存取介面；正式實作是 GroupsRepository，測試用 FakeGroupsRepository。"""

    def transaction(self) -> Any: ...
    def shop_exists(self, shop_id: uuid.UUID) -> bool: ...
    def game_exists(self, game_id: int) -> bool: ...
    def add_group(self, **values: Any) -> uuid.UUID: ...
    def lock_group(self, group_id: uuid.UUID) -> GroupRecord | None: ...
    def update_group(self, group_id: uuid.UUID, values: dict[str, Any]) -> None: ...
    def count_members(self, group_id: uuid.UUID) -> int: ...
    def find_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> Any: ...
    def add_member(
        self, group_id: uuid.UUID, user_id: uuid.UUID, status: str, joined_at: datetime
    ) -> None: ...
    def delete_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> None: ...
    def promote_waitlisted(self, group_id: uuid.UUID, count: int) -> int: ...
    def waitlist_position(self, group_id: uuid.UUID, user_id: uuid.UUID) -> int | None: ...
    def get_group(self, group_id: uuid.UUID, viewer_id: uuid.UUID) -> GroupView | None: ...
    def list_groups(self, **filters: Any) -> tuple[list[GroupView], int]: ...
    def list_members(self, group_id: uuid.UUID) -> list[Any]: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> AppError:
    return AppError(404, "GROUP_NOT_FOUND", "找不到這個揪團")


def _closed() -> AppError:
    return AppError(409, "GROUP_CLOSED", "揪團已取消或已結束")


def _invalid_time(message: str) -> AppError:
    return AppError(422, "GROUP_INVALID_TIME", message)


def _is_closed(record: GroupRecord, now: datetime) -> bool:
    return record.status == "cancelled" or record.end_at <= now


def _can_manage(user: CurrentUser, record: GroupRecord) -> bool:
    """開團主或管理員可以修改揪團、移除他人。店家人員不因為店家相同就有權限。"""
    return user.id == record.organizer_id or user.role == "admin"


class GroupsService:
    def __init__(
        self, repository: GroupsRepositoryProtocol, now: Callable[[], datetime] = _utc_now
    ) -> None:
        self._repo = repository
        self._now = now

    # --- 開團 ---

    def create_group(self, user: CurrentUser, data: GroupCreate) -> GroupResponse:
        now = self._now()
        self._check_times(data.start_at, data.end_at, now, check_start=True)
        if not self._repo.shop_exists(data.shop_id):
            raise AppError(404, "GROUP_SHOP_NOT_FOUND", "找不到這間店家")
        self._check_game(data.game_id)

        with self._repo.transaction():
            group_id = self._repo.add_group(
                shop_id=data.shop_id,
                organizer_id=user.id,
                title=data.title,
                description=data.description,
                start_at=data.start_at,
                end_at=data.end_at,
                capacity=data.capacity,
                fee=data.fee,
                game_id=data.game_id,
            )
            # 開團主自動成為第一位成員（AGENTS.md §10.3）
            self._repo.add_member(group_id, user.id, "member", now)
        return self.get_group(user, group_id)

    # --- 查詢 ---

    def get_group(self, user: CurrentUser, group_id: uuid.UUID) -> GroupResponse:
        view = self._repo.get_group(group_id, user.id)
        if view is None:
            raise _not_found()
        return self._to_response(view, self._now())

    def list_groups(
        self,
        user: CurrentUser,
        *,
        start_from: datetime | None = None,
        start_before: datetime | None = None,
        shop_id: uuid.UUID | None = None,
        organizer_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> GroupListResponse:
        views, total = self._repo.list_groups(
            viewer_id=user.id,
            start_from=start_from,
            start_before=start_before,
            shop_id=shop_id,
            organizer_id=organizer_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        now = self._now()
        return GroupListResponse(items=[self._to_response(v, now) for v in views], total=total)

    def list_members(self, user: CurrentUser, group_id: uuid.UUID) -> MemberListResponse:
        if self._repo.get_group(group_id, user.id) is None:
            raise _not_found()
        items: list[MemberResponse] = []
        position = 0
        for member in self._repo.list_members(group_id):
            waitlist_position = None
            if member.status == "waitlisted":
                position += 1
                waitlist_position = position
            items.append(
                MemberResponse(
                    user_id=member.user_id,
                    display_name=member.display_name,
                    status=member.status,
                    waitlist_position=waitlist_position,
                    joined_at=member.joined_at.astimezone(UTC),
                )
            )
        return MemberListResponse(items=items, total=len(items))

    # --- 修改與取消 ---

    def update_group(
        self, user: CurrentUser, group_id: uuid.UUID, data: GroupUpdate
    ) -> GroupResponse:
        fields = data.model_dump(exclude_unset=True)
        with self._repo.transaction():
            record = self._lock(group_id)
            if not _can_manage(user, record):
                raise PermissionDenied()
            now = self._now()
            if _is_closed(record, now):
                raise _closed()

            if "start_at" in fields or "end_at" in fields:
                self._check_times(
                    fields.get("start_at", record.start_at),
                    fields.get("end_at", record.end_at),
                    now,
                    check_start="start_at" in fields,
                )
            if "game_id" in fields:
                self._check_game(fields["game_id"])

            open_slots = 0
            if "capacity" in fields:
                members = self._repo.count_members(group_id)
                if fields["capacity"] < members:
                    raise AppError(
                        409,
                        "GROUP_CAPACITY_BELOW_MEMBERS",
                        "人數上限不能少於目前的成員數",
                        {"member_count": members},
                    )
                open_slots = fields["capacity"] - members

            self._repo.update_group(group_id, fields)
            # 調高人數上限時，候補依報名先後遞補
            if open_slots > 0 and fields.get("status") != "cancelled":
                self._repo.promote_waitlisted(group_id, open_slots)
        return self.get_group(user, group_id)

    # --- 報名 ---

    def join_group(self, user: CurrentUser, group_id: uuid.UUID) -> JoinResponse:
        with self._repo.transaction():
            record = self._lock(group_id)
            # 鎖住之後才取時間，報名時間的先後才會和實際取得名額的順序一致
            now = self._now()
            if _is_closed(record, now):
                raise _closed()
            if self._repo.find_member(group_id, user.id) is not None:
                raise AppError(409, "GROUP_ALREADY_JOINED", "已經報名過這個揪團")
            full = self._repo.count_members(group_id) >= record.capacity
            status = "waitlisted" if full else "member"
            self._repo.add_member(group_id, user.id, status, now)
            position = self._repo.waitlist_position(group_id, user.id) if full else None
        return JoinResponse(user_id=user.id, status=status, waitlist_position=position)

    # --- 退出與遞補 ---

    def remove_member(self, user: CurrentUser, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        with self._repo.transaction():
            record = self._lock(group_id)
            if user_id != user.id and not _can_manage(user, record):
                raise PermissionDenied()
            if user_id == record.organizer_id:
                raise AppError(
                    409,
                    "GROUP_ORGANIZER_CANNOT_LEAVE",
                    "開團主不能退出自己的揪團，請改用取消揪團",
                )
            if _is_closed(record, self._now()):
                raise _closed()
            member = self._repo.find_member(group_id, user_id)
            if member is None:
                raise AppError(404, "GROUP_MEMBER_NOT_FOUND", "這位使用者不在揪團名單上")
            self._repo.delete_member(group_id, user_id)
            if member.status == "member":
                open_slots = record.capacity - self._repo.count_members(group_id)
                self._repo.promote_waitlisted(group_id, open_slots)

    # --- 內部 ---

    def _lock(self, group_id: uuid.UUID) -> GroupRecord:
        record = self._repo.lock_group(group_id)
        if record is None:
            raise _not_found()
        return record

    def _check_game(self, game_id: int | None) -> None:
        if game_id is not None and not self._repo.game_exists(game_id):
            raise AppError(404, "GROUP_GAME_NOT_FOUND", "找不到這款遊戲")

    @staticmethod
    def _check_times(
        start_at: datetime, end_at: datetime, now: datetime, *, check_start: bool
    ) -> None:
        if end_at <= start_at:
            raise _invalid_time("結束時間要晚於開始時間")
        if check_start and start_at < now:
            raise _invalid_time("開始時間不能早於現在")

    @staticmethod
    def _to_response(view: GroupView, now: datetime) -> GroupResponse:
        if view.status == "cancelled":
            status = "cancelled"
        elif view.end_at <= now:
            status = "ended"
        else:
            status = "open"
        game = (
            GameRef(id=view.game_id, name=view.game_name or "")
            if view.game_id is not None
            else None
        )
        return GroupResponse(
            id=view.id,
            title=view.title,
            description=view.description,
            start_at=view.start_at.astimezone(UTC),
            end_at=view.end_at.astimezone(UTC),
            capacity=view.capacity,
            fee=view.fee,
            status=status,
            shop=ShopRef(id=view.shop_id, name=view.shop_name),
            organizer=UserRef(id=view.organizer_id, display_name=view.organizer_name),
            game=game,
            member_count=view.member_count,
            waitlist_count=view.waitlist_count,
            remaining_slots=max(view.capacity - view.member_count, 0),
            my_status=view.my_status,
            created_at=view.created_at.astimezone(UTC),
        )
