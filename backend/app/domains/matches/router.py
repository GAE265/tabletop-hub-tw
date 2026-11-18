"""記錄一局遊戲的 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md 4.2）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.core.games.repository import GameRepository
from app.domains.auth.repository import AuthUserRepository
from app.domains.booking.repository import BookingRepository
from app.domains.groups.router import get_groups_service
from app.domains.groups.service import GroupsService
from app.domains.matches.groups_lookup import GroupsServiceLookup
from app.domains.matches.repository import MatchesRepository
from app.domains.matches.schemas import (
    MatchCreate,
    MatchListResponse,
    MatchResponse,
    ParticipantConfirm,
    ParticipantCreate,
    ParticipantResponse,
    ResultRequest,
    TurnCreate,
    TurnResponse,
)
from app.domains.matches.service import MatchesService

router = APIRouter(prefix="/matches", tags=["matches"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_matches_service(
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUserDep,
    groups_service: Annotated[GroupsService, Depends(get_groups_service)],
) -> MatchesService:
    return MatchesService(
        MatchesRepository(session),
        games=GameRepository(session),
        shops=BookingRepository(session),
        users=AuthUserRepository(session),
        groups=GroupsServiceLookup(groups_service, user),
    )


ServiceDep = Annotated[MatchesService, Depends(get_matches_service)]


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
def create_match(body: MatchCreate, user: CurrentUserDep, service: ServiceDep) -> MatchResponse:
    """開局。開局者自動成為參加者，座位自己選。"""
    return service.create_match(user, body)


@router.get("", response_model=MatchListResponse)
def list_matches(
    user: CurrentUserDep,
    service: ServiceDep,
    game_id: int | None = None,
    group_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MatchListResponse:
    return service.list_matches(
        user, game_id=game_id, group_id=group_id, user_id=user_id, page=page, page_size=page_size
    )


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(match_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep) -> MatchResponse:
    return service.get_match(user, match_id)


@router.post(
    "/{match_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_participant(
    match_id: uuid.UUID, body: ParticipantCreate, user: CurrentUserDep, service: ServiceDep
) -> ParticipantResponse:
    """不帶 display_name＝自己加入；帶 display_name＝新增沒有帳號的參加者。"""
    return service.add_participant(user, match_id, body)


@router.patch("/{match_id}/participants/{participant_id}", response_model=ParticipantResponse)
def confirm_participant(
    match_id: uuid.UUID,
    participant_id: uuid.UUID,
    body: ParticipantConfirm,
    user: CurrentUserDep,
    service: ServiceDep,
) -> ParticipantResponse:
    """參加者確認這局的紀錄。"""
    return service.confirm_participant(user, match_id, participant_id, body)


@router.delete("/{match_id}/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(
    match_id: uuid.UUID, participant_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep
) -> Response:
    """退出，或移除沒有帳號的人與其他參加者。"""
    service.remove_participant(user, match_id, participant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{match_id}/turns", response_model=TurnResponse, status_code=status.HTTP_201_CREATED)
def record_turn(
    match_id: uuid.UUID,
    body: TurnCreate,
    response: Response,
    user: CurrentUserDep,
    service: ServiceDep,
    overwrite: bool = False,
) -> TurnResponse:
    """記錄一個回合。同一回合已有紀錄時回 409；帶 overwrite=true 才覆蓋（覆蓋成功回 200）。"""
    turn, created = service.record_turn(user, match_id, body, overwrite=overwrite)
    if not created:
        response.status_code = status.HTTP_200_OK
    return turn


@router.put("/{match_id}/result", response_model=MatchResponse)
def record_result(
    match_id: uuid.UUID,
    body: ResultRequest,
    user: CurrentUserDep,
    service: ServiceDep,
    overwrite: bool = False,
) -> MatchResponse:
    """記錄結果。已有結果時回 409；帶 overwrite=true 才覆蓋，並清除其他人的確認。"""
    return service.record_result(user, match_id, body, overwrite=overwrite)
