"""揪團 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md 4.2）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.domains.groups.repository import GroupsRepository
from app.domains.groups.schemas import (
    GroupCreate,
    GroupListResponse,
    GroupResponse,
    GroupUpdate,
    JoinResponse,
    MemberListResponse,
)
from app.domains.groups.service import GroupsService

router = APIRouter(prefix="/groups", tags=["groups"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_groups_service(session: Annotated[Session, Depends(get_session)]) -> GroupsService:
    return GroupsService(GroupsRepository(session))


ServiceDep = Annotated[GroupsService, Depends(get_groups_service)]


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupCreate, user: CurrentUserDep, service: ServiceDep) -> GroupResponse:
    return service.create_group(user, body)


@router.get("", response_model=GroupListResponse)
def list_groups(
    user: CurrentUserDep,
    service: ServiceDep,
    start_from: AwareDatetime | None = None,
    start_before: AwareDatetime | None = None,
    shop_id: uuid.UUID | None = None,
    organizer_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GroupListResponse:
    return service.list_groups(
        user,
        start_from=start_from,
        start_before=start_before,
        shop_id=shop_id,
        organizer_id=organizer_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep) -> GroupResponse:
    return service.get_group(user, group_id)


@router.patch("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: uuid.UUID, body: GroupUpdate, user: CurrentUserDep, service: ServiceDep
) -> GroupResponse:
    return service.update_group(user, group_id, body)


@router.get("/{group_id}/members", response_model=MemberListResponse)
def list_members(
    group_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep
) -> MemberListResponse:
    return service.list_members(user, group_id)


@router.post(
    "/{group_id}/members", response_model=JoinResponse, status_code=status.HTTP_201_CREATED
)
def join_group(group_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep) -> JoinResponse:
    """報名。額滿時同樣回 201，status=waitlisted 並附候補順位。"""
    return service.join_group(user, group_id)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    group_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep
) -> Response:
    """自己退出，或由開團主、管理員移除。成員離開後，候補第一位自動遞補。"""
    service.remove_member(user, group_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
