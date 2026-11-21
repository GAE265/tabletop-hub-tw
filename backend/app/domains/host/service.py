"""主持的 service：開主持、列出、通行碼、權限、一人一場、30 分鐘清除（host spec §2、§11）。

主持不存資料：一場主持只在後端記憶體，沒有 repository 與 models（spec §1）。
整局記憶在圖裡（graph.py）；這裡管的是「誰開的、有沒有裝置連著、什麼時候清掉」。
"""

import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from app.core.auth import CurrentUser, require_role
from app.core.errors import AppError, PermissionDenied
from app.domains.host.graph import Effect, HostEvent, HostGraph, HostSnapshot, Outcome

# 通行碼的有效時間（D12 §5）
TICKET_TTL = timedelta(seconds=60)
# 沒有任何裝置連著、或已結束之後，一場主持還保留多久（spec §2.1）
RETENTION = timedelta(minutes=30)


class HostTicketInvalid(Exception):
    """通行碼不對、過期、用過了，或不是這一場主持的。"""


def _not_found(session_id: uuid.UUID) -> AppError:
    return AppError(404, "HOST_SESSION_NOT_FOUND", "找不到這場主持，可能已經被清掉了")


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SessionView:
    """一場主持對外的樣子：誰開的、什麼時候開的、現況。"""

    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    snapshot: HostSnapshot


@dataclass(frozen=True)
class ConnectionTicket:
    """一次性通行碼。turn_taking_mode 有值代表連上時要切換成這個接話方式。"""

    ticket: str
    session_id: uuid.UUID
    expires_at: datetime
    turn_taking_mode: str | None = None


@dataclass
class _Session:
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    # 有沒有裝置連著；沒有的話，從什麼時候開始沒有
    connected: bool
    idle_since: datetime
    # 什麼時候結束的；進行中是 None
    ended_at: datetime | None = None


class HostService:
    """整個後端共用一個（首版後端固定一台，spec §1）。"""

    def __init__(self, graph: HostGraph, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self.graph = graph
        self._clock = clock
        self._sessions: dict[uuid.UUID, _Session] = {}
        self._tickets: dict[str, ConnectionTicket] = {}
        self._lock = threading.RLock()

    # --- 三個一般請求 ---

    def open_session(
        self, user: CurrentUser, *, player_count: int, turn_taking_mode: str, voice: str
    ) -> tuple[SessionView, ConnectionTicket]:
        """開一場主持。這個人原本的那一場直接清掉，不回 409（D13 §5）。"""
        require_role(user, "player", "shop_staff", "admin")
        with self._lock:
            self._purge_expired()
            for session in [s for s in self._sessions.values() if s.owner_id == user.id]:
                self._remove(session.id)
            now = self._clock()
            session = _Session(
                id=uuid.uuid4(), owner_id=user.id, created_at=now, connected=False, idle_since=now
            )
            self.graph.create(
                str(session.id),
                player_count=player_count,
                turn_taking_mode=turn_taking_mode,
                voice=voice,
            )
            self._sessions[session.id] = session
            return self._view(session), self._new_ticket(session.id, None)

    def list_sessions(self, user: CurrentUser) -> list[SessionView]:
        """自己還保留著的主持（0 或 1 筆）。管理員也只列自己的。"""
        require_role(user, "player", "shop_staff", "admin")
        with self._lock:
            self._purge_expired()
            return [self._view(s) for s in self._sessions.values() if s.owner_id == user.id]

    def issue_ticket(
        self, user: CurrentUser, session_id: uuid.UUID, *, turn_taking_mode: str | None = None
    ) -> tuple[SessionView, ConnectionTicket]:
        """拿一次性通行碼：接著主持、重整頁面、切換接話方式。只有開的人與管理員能拿。"""
        require_role(user, "player", "shop_staff", "admin")
        with self._lock:
            session = self._get(session_id)
            if user.role != "admin" and session.owner_id != user.id:
                raise PermissionDenied("這場主持不是你開的")
            view = self._view(session)
            if turn_taking_mode is not None and turn_taking_mode != view.snapshot.turn_taking_mode:
                # 真的切換發生在裝置用這張通行碼連上的時候；回應先給新的接話方式
                view = replace(
                    view, snapshot=replace(view.snapshot, turn_taking_mode=turn_taking_mode)
                )
            else:
                turn_taking_mode = None
            return view, self._new_ticket(session.id, turn_taking_mode)

    # --- 給 WebSocket 與轉送那一段用 ---

    def redeem_ticket(self, session_id: uuid.UUID, ticket: str) -> ConnectionTicket:
        """核對並用掉通行碼。這場主持不在了拋 404；通行碼不對拋 HostTicketInvalid。"""
        with self._lock:
            self._get(session_id)
            found = self._tickets.get(ticket)
            if found is None or found.session_id != session_id:
                raise HostTicketInvalid
            del self._tickets[ticket]
            return found

    def device_connected(self, session_id: uuid.UUID) -> None:
        with self._lock:
            self._get(session_id).connected = True

    def device_disconnected(self, session_id: uuid.UUID) -> None:
        """裝置斷線：這場主持保留，從現在起算 30 分鐘。已經被清掉就不做事。"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.connected = False
                session.idle_since = self._clock()

    def snapshot(self, session_id: uuid.UUID) -> HostSnapshot:
        with self._lock:
            return self._view(self._get(session_id)).snapshot

    def handle_event(
        self,
        session_id: uuid.UUID,
        event: HostEvent,
        *,
        on_effect: Callable[[Effect], None] | None = None,
    ) -> Outcome:
        """把一件事交給圖處理，並記下這場主持是不是結束了（30 分鐘從結束起算）。"""
        with self._lock:
            self._get(session_id)
        try:
            outcome = self.graph.handle(str(session_id), event, on_effect=on_effect)
        except KeyError:
            raise _not_found(session_id) from None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and self.graph.exists(str(session_id)):
                ended = self.graph.snapshot(str(session_id)).status == "ended"
                if ended and session.ended_at is None:
                    session.ended_at = self._clock()
                elif not ended:
                    session.ended_at = None
        return outcome

    def pending_ticket_count(self) -> int:
        with self._lock:
            return len(self._tickets)

    # --- 內部 ---

    def _get(self, session_id: uuid.UUID) -> _Session:
        self._purge_expired()
        session = self._sessions.get(session_id)
        if session is None:
            raise _not_found(session_id)
        return session

    def _view(self, session: _Session) -> SessionView:
        return SessionView(
            id=session.id,
            owner_id=session.owner_id,
            created_at=session.created_at,
            snapshot=self.graph.snapshot(str(session.id)),
        )

    def _new_ticket(self, session_id: uuid.UUID, turn_taking_mode: str | None) -> ConnectionTicket:
        ticket = ConnectionTicket(
            ticket=secrets.token_urlsafe(32),
            session_id=session_id,
            expires_at=self._clock() + TICKET_TTL,
            turn_taking_mode=turn_taking_mode,
        )
        self._tickets[ticket.ticket] = ticket
        return ticket

    def _purge_expired(self) -> None:
        """清掉過期的通行碼，以及沒有裝置連著或已結束滿 30 分鐘的主持。"""
        now = self._clock()
        for key in [key for key, ticket in self._tickets.items() if ticket.expires_at <= now]:
            del self._tickets[key]
        for session in list(self._sessions.values()):
            idle = not session.connected and now - session.idle_since >= RETENTION
            ended = session.ended_at is not None and now - session.ended_at >= RETENTION
            if idle or ended:
                self._remove(session.id)

    def _remove(self, session_id: uuid.UUID) -> None:
        """清掉一場主持，連圖裡的整局記憶與還沒用的通行碼一起。"""
        self._sessions.pop(session_id, None)
        for key in [key for key, t in self._tickets.items() if t.session_id == session_id]:
            del self._tickets[key]
        self.graph.delete(str(session_id))
