"""記錄一局遊戲的資料存取。交易範圍由 service 用 transaction() 決定。

回傳的紀錄用屬性存取，欄位名稱與資料表相同（service 的單元測試用的 FakeMatchesRepository
照同一個介面實作）。
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, exists, func, insert, or_, select, update

from app.core.db import SessionRepository
from app.domains.matches.models import Match, MatchParticipant, MatchTurn


@dataclass(frozen=True)
class MatchRecord:
    id: uuid.UUID
    game_id: int
    played_on: date
    location_type: str
    shop_id: uuid.UUID | None
    group_id: uuid.UUID | None
    created_by: uuid.UUID
    status: str
    result: dict[str, Any] | None
    progress: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ParticipantRecord:
    id: uuid.UUID
    match_id: uuid.UUID
    seat_number: int
    user_id: uuid.UUID | None
    display_name: str
    faction: str | None
    score: int | None
    placement: int | None
    is_winner: bool | None
    is_confirmed: bool
    confirmed_at: datetime | None


@dataclass(frozen=True)
class TurnRecord:
    id: uuid.UUID
    match_id: uuid.UUID
    turn_number: int
    seat_number: int | None
    game_data: dict[str, Any]
    recorded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


_MATCH_COLUMNS = (
    Match.id,
    Match.game_id,
    Match.played_on,
    Match.location_type,
    Match.shop_id,
    Match.group_id,
    Match.created_by,
    Match.status,
    Match.result,
    Match.progress,
    Match.created_at,
    Match.updated_at,
)
_PARTICIPANT_COLUMNS = (
    MatchParticipant.id,
    MatchParticipant.match_id,
    MatchParticipant.seat_number,
    MatchParticipant.user_id,
    MatchParticipant.display_name,
    MatchParticipant.faction,
    MatchParticipant.score,
    MatchParticipant.placement,
    MatchParticipant.is_winner,
    MatchParticipant.is_confirmed,
    MatchParticipant.confirmed_at,
)
_TURN_COLUMNS = (
    MatchTurn.id,
    MatchTurn.match_id,
    MatchTurn.turn_number,
    MatchTurn.seat_number,
    MatchTurn.game_data,
    MatchTurn.recorded_by,
    MatchTurn.created_at,
    MatchTurn.updated_at,
)


class MatchesRepository(SessionRepository):
    # --- 局 ---

    def add_match(self, **values: Any) -> uuid.UUID:
        return self.session.execute(insert(Match).values(**values).returning(Match.id)).scalar_one()

    def lock_match(self, match_id: uuid.UUID) -> MatchRecord | None:
        """以 SELECT ... FOR UPDATE 鎖住這局；同一局的寫入依序執行（design.md D6）。"""
        row = self.session.execute(
            select(*_MATCH_COLUMNS).where(Match.id == match_id).with_for_update()
        ).one_or_none()
        return None if row is None else MatchRecord(**row._mapping)

    def get_match(self, match_id: uuid.UUID) -> MatchRecord | None:
        row = self.session.execute(
            select(*_MATCH_COLUMNS).where(Match.id == match_id)
        ).one_or_none()
        return None if row is None else MatchRecord(**row._mapping)

    def update_match(self, match_id: uuid.UUID, values: Mapping[str, Any]) -> None:
        self.session.execute(
            update(Match).where(Match.id == match_id).values(**values, updated_at=func.now())
        )

    def list_matches(
        self,
        *,
        game_id: int | None = None,
        group_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MatchRecord], int]:
        conditions = []
        if game_id is not None:
            conditions.append(Match.game_id == game_id)
        if group_id is not None:
            conditions.append(Match.group_id == group_id)
        if user_id is not None:
            conditions.append(
                exists().where(
                    MatchParticipant.match_id == Match.id, MatchParticipant.user_id == user_id
                )
            )
        total = self.session.scalar(select(func.count()).select_from(Match).where(*conditions))
        rows = self.session.execute(
            select(*_MATCH_COLUMNS)
            .where(*conditions)
            .order_by(Match.played_on.desc(), Match.created_at.desc(), Match.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [MatchRecord(**row._mapping) for row in rows], total or 0

    # --- 參加者 ---

    def add_participant(
        self, match_id: uuid.UUID, seat_number: int, user_id: uuid.UUID | None, display_name: str
    ) -> uuid.UUID:
        return self.session.execute(
            insert(MatchParticipant)
            .values(
                match_id=match_id,
                seat_number=seat_number,
                user_id=user_id,
                display_name=display_name,
            )
            .returning(MatchParticipant.id)
        ).scalar_one()

    def list_participants(self, match_id: uuid.UUID) -> list[ParticipantRecord]:
        rows = self.session.execute(
            select(*_PARTICIPANT_COLUMNS)
            .where(MatchParticipant.match_id == match_id)
            .order_by(MatchParticipant.seat_number)
        ).all()
        return [ParticipantRecord(**row._mapping) for row in rows]

    def find_participant(
        self, match_id: uuid.UUID, participant_id: uuid.UUID
    ) -> ParticipantRecord | None:
        row = self.session.execute(
            select(*_PARTICIPANT_COLUMNS).where(
                MatchParticipant.match_id == match_id, MatchParticipant.id == participant_id
            )
        ).one_or_none()
        return None if row is None else ParticipantRecord(**row._mapping)

    def update_participant(self, participant_id: uuid.UUID, values: Mapping[str, Any]) -> None:
        self.session.execute(
            update(MatchParticipant).where(MatchParticipant.id == participant_id).values(**values)
        )

    def clear_confirmations(
        self, match_id: uuid.UUID, except_participant_id: uuid.UUID | None = None
    ) -> None:
        """清除這局所有參加者的確認，except_participant_id（覆蓋結果的人）除外。"""
        statement = (
            update(MatchParticipant)
            .where(MatchParticipant.match_id == match_id)
            .values(is_confirmed=False, confirmed_at=None)
        )
        if except_participant_id is not None:
            statement = statement.where(MatchParticipant.id != except_participant_id)
        self.session.execute(statement)

    def delete_participant(self, participant_id: uuid.UUID) -> None:
        self.session.execute(delete(MatchParticipant).where(MatchParticipant.id == participant_id))

    # --- 回合 ---

    def add_turn(
        self,
        match_id: uuid.UUID,
        turn_number: int,
        seat_number: int | None,
        game_data: dict[str, Any],
        recorded_by: uuid.UUID,
    ) -> TurnRecord:
        row = self.session.execute(
            insert(MatchTurn)
            .values(
                match_id=match_id,
                turn_number=turn_number,
                seat_number=seat_number,
                game_data=game_data,
                recorded_by=recorded_by,
            )
            .returning(*_TURN_COLUMNS)
        ).one()
        return TurnRecord(**row._mapping)

    def find_turn(self, match_id: uuid.UUID, turn_number: int) -> TurnRecord | None:
        row = self.session.execute(
            select(*_TURN_COLUMNS).where(
                MatchTurn.match_id == match_id, MatchTurn.turn_number == turn_number
            )
        ).one_or_none()
        return None if row is None else TurnRecord(**row._mapping)

    def list_turns(self, match_id: uuid.UUID) -> list[TurnRecord]:
        rows = self.session.execute(
            select(*_TURN_COLUMNS)
            .where(MatchTurn.match_id == match_id)
            .order_by(MatchTurn.turn_number)
        ).all()
        return [TurnRecord(**row._mapping) for row in rows]

    def update_turn(
        self,
        turn_id: uuid.UUID,
        seat_number: int | None,
        game_data: dict[str, Any],
        recorded_by: uuid.UUID,
    ) -> TurnRecord:
        row = self.session.execute(
            update(MatchTurn)
            .where(MatchTurn.id == turn_id)
            .values(
                seat_number=seat_number,
                game_data=game_data,
                recorded_by=recorded_by,
                updated_at=func.now(),
            )
            .returning(*_TURN_COLUMNS)
        ).one()
        return TurnRecord(**row._mapping)

    def turns_using_seat(self, match_id: uuid.UUID, seat_number: int) -> list[int]:
        """座位出現在 seat_number 或 game_data.played_seat_numbers 的回合編號（由小到大）。"""
        rows = self.session.scalars(
            select(MatchTurn.turn_number)
            .where(
                MatchTurn.match_id == match_id,
                or_(
                    MatchTurn.seat_number == seat_number,
                    MatchTurn.game_data["played_seat_numbers"].contains([seat_number]),
                ),
            )
            .order_by(MatchTurn.turn_number)
        )
        return list(rows)
