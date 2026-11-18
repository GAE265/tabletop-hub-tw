"""matches service 單元測試用的手寫 fake（AGENTS.md 7.5），在記憶體中照 repository 的介面運作。

這個檔案同時寫下 service 對 repository 與共用表讀取方法的期待（正式實作要照這個介面寫）：

repository（MatchesRepository）：
    transaction()、add_match(**values)、get_match(id)、lock_match(id)、update_match(id, values)、
    list_matches(...)、add_participant(...)、find_participant(...)、list_participants(id)、
    update_participant(id, values)、clear_confirmations(...)、delete_participant(id)、
    add_turn(...)、find_turn(...)、list_turns(id)、update_turn(...)、turns_using_seat(...)
共用表與揪團的讀取（各自一個小介面，正式實作見 design.md D8）：
    games.get_game(id)、shops.get_shop(id)、users.get_user(id)、groups.group_exists(id)

回傳的紀錄用屬性存取，欄位名稱與資料表相同。
"""

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
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


@dataclass
class ParticipantRecord:
    id: uuid.UUID
    match_id: uuid.UUID
    seat_number: int
    user_id: uuid.UUID | None
    display_name: str
    faction: str | None = None
    score: int | None = None
    placement: int | None = None
    is_winner: bool | None = None
    is_confirmed: bool = False
    confirmed_at: datetime | None = None


@dataclass
class TurnRecord:
    id: uuid.UUID
    match_id: uuid.UUID
    turn_number: int
    seat_number: int
    game_data: dict[str, Any]
    recorded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


@dataclass
class GameInfo:
    id: int
    name: str
    bgg_id: int
    result_type: str | None


@dataclass
class ShopInfo:
    id: uuid.UUID
    name: str


@dataclass
class UserInfo:
    id: uuid.UUID
    display_name: str


@dataclass
class FakeSharedData:
    """共用表與揪團的讀取：同一個物件同時當 games、shops、users、groups 傳給 service。"""

    games: dict[int, GameInfo] = field(default_factory=dict)
    shops: dict[uuid.UUID, ShopInfo] = field(default_factory=dict)
    users: dict[uuid.UUID, UserInfo] = field(default_factory=dict)
    groups: set[uuid.UUID] = field(default_factory=set)

    def add_game(
        self, game_id: int, name: str, bgg_id: int, result_type: str | None = "faction"
    ) -> int:
        self.games[game_id] = GameInfo(game_id, name, bgg_id, result_type)
        return game_id

    def add_shop(self, name: str = "測試桌遊店") -> uuid.UUID:
        shop = ShopInfo(uuid.uuid4(), name)
        self.shops[shop.id] = shop
        return shop.id

    def add_user(self, user_id: uuid.UUID, display_name: str) -> uuid.UUID:
        self.users[user_id] = UserInfo(user_id, display_name)
        return user_id

    def add_group(self) -> uuid.UUID:
        group_id = uuid.uuid4()
        self.groups.add(group_id)
        return group_id

    def get_game(self, game_id: int) -> GameInfo | None:
        return self.games.get(game_id)

    def get_shop(self, shop_id: uuid.UUID) -> ShopInfo | None:
        return self.shops.get(shop_id)

    def get_user(self, user_id: uuid.UUID) -> UserInfo | None:
        return self.users.get(user_id)

    def group_exists(self, group_id: uuid.UUID) -> bool:
        return group_id in self.groups


class FakeMatchesRepository:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.matches: dict[uuid.UUID, MatchRecord] = {}
        self.participants: list[ParticipantRecord] = []
        self.turns: list[TurnRecord] = []
        self.committed = 0
        self.rolled_back = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.rolled_back += 1
            raise
        self.committed += 1

    # --- 局 ---

    def add_match(self, **values: Any) -> uuid.UUID:
        match = MatchRecord(
            id=uuid.uuid4(),
            status="in_progress",
            result=None,
            progress=values.pop("progress", None),
            created_at=self.now,
            updated_at=self.now,
            **values,
        )
        self.matches[match.id] = match
        return match.id

    def get_match(self, match_id: uuid.UUID) -> MatchRecord | None:
        """讀取用，不上鎖（正式實作的 lock_match 是 SELECT ... FOR UPDATE）。"""
        return self.matches.get(match_id)

    def lock_match(self, match_id: uuid.UUID) -> MatchRecord | None:
        return self.matches.get(match_id)

    def update_match(self, match_id: uuid.UUID, values: Mapping[str, Any]) -> None:
        match = self.matches[match_id]
        for key, value in values.items():
            setattr(match, key, value)
        match.updated_at = self.now

    def list_matches(
        self,
        *,
        game_id: int | None = None,
        group_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MatchRecord], int]:
        found = []
        for match in self.matches.values():
            if game_id is not None and match.game_id != game_id:
                continue
            if group_id is not None and match.group_id != group_id:
                continue
            if user_id is not None and not any(
                p.match_id == match.id and p.user_id == user_id for p in self.participants
            ):
                continue
            found.append(match)
        found.sort(key=lambda m: m.played_on, reverse=True)
        start = (page - 1) * page_size
        return found[start : start + page_size], len(found)

    # --- 參加者 ---

    def add_participant(
        self, match_id: uuid.UUID, seat_number: int, user_id: uuid.UUID | None, display_name: str
    ) -> uuid.UUID:
        participant = ParticipantRecord(
            id=uuid.uuid4(),
            match_id=match_id,
            seat_number=seat_number,
            user_id=user_id,
            display_name=display_name,
        )
        self.participants.append(participant)
        return participant.id

    def list_participants(self, match_id: uuid.UUID) -> list[ParticipantRecord]:
        found = [p for p in self.participants if p.match_id == match_id]
        return sorted(found, key=lambda p: p.seat_number)

    def find_participant(
        self, match_id: uuid.UUID, participant_id: uuid.UUID
    ) -> ParticipantRecord | None:
        for participant in self.participants:
            if participant.match_id == match_id and participant.id == participant_id:
                return participant
        return None

    def update_participant(self, participant_id: uuid.UUID, values: Mapping[str, Any]) -> None:
        for participant in self.participants:
            if participant.id == participant_id:
                for key, value in values.items():
                    setattr(participant, key, value)

    def clear_confirmations(
        self, match_id: uuid.UUID, except_participant_id: uuid.UUID | None = None
    ) -> None:
        for participant in self.participants:
            if participant.match_id == match_id and participant.id != except_participant_id:
                participant.is_confirmed = False
                participant.confirmed_at = None

    def delete_participant(self, participant_id: uuid.UUID) -> None:
        self.participants = [p for p in self.participants if p.id != participant_id]

    # --- 回合 ---

    def add_turn(
        self,
        match_id: uuid.UUID,
        turn_number: int,
        seat_number: int,
        game_data: dict[str, Any],
        recorded_by: uuid.UUID,
    ) -> TurnRecord:
        turn = TurnRecord(
            id=uuid.uuid4(),
            match_id=match_id,
            turn_number=turn_number,
            seat_number=seat_number,
            game_data=game_data,
            recorded_by=recorded_by,
            created_at=self.now,
            updated_at=self.now,
        )
        self.turns.append(turn)
        return turn

    def find_turn(self, match_id: uuid.UUID, turn_number: int) -> TurnRecord | None:
        for turn in self.turns:
            if turn.match_id == match_id and turn.turn_number == turn_number:
                return turn
        return None

    def list_turns(self, match_id: uuid.UUID) -> list[TurnRecord]:
        found = [t for t in self.turns if t.match_id == match_id]
        return sorted(found, key=lambda t: t.turn_number)

    def update_turn(
        self,
        turn_id: uuid.UUID,
        seat_number: int,
        game_data: dict[str, Any],
        recorded_by: uuid.UUID,
    ) -> TurnRecord:
        for turn in self.turns:
            if turn.id == turn_id:
                turn.seat_number = seat_number
                turn.game_data = game_data
                turn.recorded_by = recorded_by
                turn.updated_at = self.now
                return turn
        raise KeyError(turn_id)

    def turns_using_seat(self, match_id: uuid.UUID, seat_number: int) -> list[int]:
        """座位出現在 seat_number 或 game_data.played_seat_numbers 的回合編號（由小到大）。"""
        numbers = []
        for turn in self.list_turns(match_id):
            played = turn.game_data.get("played_seat_numbers", [])
            if turn.seat_number == seat_number or seat_number in played:
                numbers.append(turn.turn_number)
        return numbers
