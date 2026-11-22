"""AI 語音主持 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md §4.2）。"""

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, status

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError
from app.domains.host.relay import HostRelay
from app.domains.host.schemas import (
    ConnectionCreate,
    ConnectionOut,
    HostingSessionCreate,
    HostingSessionList,
    HostingSessionOut,
    HostingSessionWithConnection,
    error_message,
)
from app.domains.host.service import ConnectionTicket, HostService, HostTicketInvalid, SessionView
from app.integrations.realtime_voice import RealtimeVoiceProvider, get_realtime_voice_provider

logger = logging.getLogger(__name__)

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


# --- WebSocket：聲音與即時訊息（spec §12） ---


def _realtime_voice(app: FastAPI) -> RealtimeVoiceProvider:
    """即時語音的實作，第一次用到時依 HOST_REALTIME_PROVIDER 建立；測試會換成 fake。"""
    provider = getattr(app.state, "realtime_voice", None)
    if provider is None:
        provider = get_realtime_voice_provider(app.state.settings)
        app.state.realtime_voice = provider
    return provider


class _WebSocketDevice:
    """把 FastAPI 的 WebSocket 包成轉送那一段認得的裝置。"""

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket
        self._closed = False

    async def send_json(self, message: dict[str, Any]) -> None:
        await self._websocket.send_json(message)

    async def send_bytes(self, data: bytes) -> None:
        await self._websocket.send_bytes(data)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._websocket.close()


@router.websocket("/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: uuid.UUID, ticket: str = "") -> None:
    """裝置把一次性通行碼放在網址上（瀏覽器的 WebSocket 不能自訂標頭）。

    核對通行碼之後才連語音模型。別人拿不到通行碼，所以操作不了別人的主持。
    """
    await websocket.accept()
    service: HostService = websocket.app.state.host_service
    device = _WebSocketDevice(websocket)
    try:
        redeemed = service.redeem_ticket(session_id, ticket)
    except HostTicketInvalid:
        await device.send_json(error_message("HOST_TICKET_INVALID"))
        await device.close()
        return
    except AppError:
        await device.send_json(error_message("HOST_SESSION_NOT_FOUND"))
        await device.close()
        return

    relay = HostRelay(
        service=service,
        provider=_realtime_voice(websocket.app),
        session_id=session_id,
        device=device,
        turn_taking_mode=redeemed.turn_taking_mode,
    )
    if not await relay.start():
        return
    try:
        while not relay.closed:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                await relay.handle_device_audio(message["bytes"])
            elif message.get("text") is not None:
                await relay.handle_device_text(message["text"])
    except (WebSocketDisconnect, RuntimeError):
        # 裝置斷線，或後端已經先關掉這條連線（被取代、連不回語音模型）
        logger.debug("主持 %s 的裝置連線結束", session_id)
    finally:
        await relay.close()
