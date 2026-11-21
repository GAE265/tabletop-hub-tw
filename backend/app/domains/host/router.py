"""AI 語音主持 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md §4.2）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.auth import CurrentUser, get_current_user
from app.domains.host.schemas import (
    ConnectionCreate,
    ConnectionOut,
    HostingSessionCreate,
    HostingSessionList,
    HostingSessionOut,
    HostingSessionWithConnection,
)
from app.domains.host.service import ConnectionTicket, HostService, SessionView

router = APIRouter(prefix="/hosting-sessions", tags=["host"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_host_service(request: Request) -> HostService:
    """主持只在後端記憶體，所以整個後端共用啟動時建立的那一個（main.py）。"""
    return request.app.state.host_service


ServiceDep = Annotated[HostService, Depends(get_host_service)]


def _session_out(view: SessionView) -> HostingSessionOut:
    snapshot = view.snapshot
    return HostingSessionOut(
        id=view.id,
        status=snapshot.status,
        player_count=snapshot.player_count,
        turn_taking_mode=snapshot.turn_taking_mode,  # type: ignore[arg-type]
        voice=snapshot.voice,  # type: ignore[arg-type]
        step=snapshot.step,
        turn_number=snapshot.turn_number,
        phase_number=snapshot.phase_number,
        paused=snapshot.paused,
        winner=snapshot.winner,
        created_at=view.created_at,
    )


def _with_connection(view: SessionView, ticket: ConnectionTicket) -> HostingSessionWithConnection:
    return HostingSessionWithConnection(
        session=_session_out(view),
        connection=ConnectionOut(ticket=ticket.ticket, expires_at=ticket.expires_at),
    )


@router.post("", response_model=HostingSessionWithConnection, status_code=status.HTTP_201_CREATED)
def open_hosting_session(
    body: HostingSessionCreate, user: CurrentUserDep, service: ServiceDep
) -> HostingSessionWithConnection:
    """開一場主持（也是「重新開始」）：自己原本的那一場會被清掉。"""
    view, ticket = service.open_session(
        user,
        player_count=body.player_count,
        turn_taking_mode=body.turn_taking_mode,
        voice=body.voice,
    )
    return _with_connection(view, ticket)


@router.get("", response_model=HostingSessionList)
def list_hosting_sessions(user: CurrentUserDep, service: ServiceDep) -> HostingSessionList:
    """自己還保留著的主持（0 或 1 筆），給頁面決定要不要顯示「接著主持」。"""
    items = [_session_out(view) for view in service.list_sessions(user)]
    return HostingSessionList(items=items, total=len(items))


@router.post(
    "/{session_id}/connections",
    response_model=HostingSessionWithConnection,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    session_id: uuid.UUID,
    user: CurrentUserDep,
    service: ServiceDep,
    body: ConnectionCreate | None = None,
) -> HostingSessionWithConnection:
    """拿一次性通行碼：接著主持、重整頁面、切換接話方式。"""
    view, ticket = service.issue_ticket(
        user, session_id, turn_taking_mode=body.turn_taking_mode if body else None
    )
    return _with_connection(view, ticket)
