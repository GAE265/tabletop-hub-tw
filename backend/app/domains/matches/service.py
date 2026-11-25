"""記錄一局遊戲的商業規則：開局、參加者、回合紀錄與覆蓋、結果、確認、移除、權限。

不 import FastAPI（AGENTS.md 4.2）；錯誤一律拋 AppError，由錯誤處理器轉成統一格式。
寫入都在交易裡先鎖住這局（lock_match），同一局的寫入依序執行（design.md D6）。
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied
from app.domains.matches.game_definitions import GameDefinition, get_definition
from app.domains.matches.schemas import (
    GameRef,
    MatchCreate,
    MatchListResponse,
    MatchResponse,
    ParticipantConfirm,
    ParticipantCreate,
    ParticipantResponse,
    ResultRequest,
    ShopRef,
    TurnCreate,
    TurnResponse,
    UserRef,
)


class MatchesRepositoryProtocol(Protocol):
    """service 需要的資料存取介面；正式實作是 MatchesRepository，測試用 FakeMatchesRepository。"""

    def transaction(self) -> Any: ...
    def add_match(self, **values: Any) -> uuid.UUID: ...
    def get_match(self, match_id: uuid.UUID) -> Any: ...
    def lock_match(self, match_id: uuid.UUID) -> Any: ...
    def update_match(self, match_id: uuid.UUID, values: dict[str, Any]) -> None: ...
    def list_matches(self, **filters: Any) -> tuple[list[Any], int]: ...
    def add_participant(
        self, match_id: uuid.UUID, seat_number: int, user_id: uuid.UUID | None, display_name: str
    ) -> uuid.UUID: ...
    def list_participants(self, match_id: uuid.UUID) -> list[Any]: ...
    def find_participant(self, match_id: uuid.UUID, participant_id: uuid.UUID) -> Any: ...
    def update_participant(self, participant_id: uuid.UUID, values: dict[str, Any]) -> None: ...
    def clear_confirmations(
        self, match_id: uuid.UUID, except_participant_id: uuid.UUID | None = None
    ) -> None: ...
    def delete_participant(self, participant_id: uuid.UUID) -> None: ...
    def add_turn(
        self,
        match_id: uuid.UUID,
        turn_number: int,
        seat_number: int | None,
        game_data: dict[str, Any],
        recorded_by: uuid.UUID,
    ) -> Any: ...
    def find_turn(self, match_id: uuid.UUID, turn_number: int) -> Any: ...
    def list_turns(self, match_id: uuid.UUID) -> list[Any]: ...
    def update_turn(
        self,
        turn_id: uuid.UUID,
        seat_number: int | None,
        game_data: dict[str, Any],
        recorded_by: uuid.UUID,
    ) -> Any: ...
    def turns_using_seat(self, match_id: uuid.UUID, seat_number: int) -> list[int]: ...


class GameReader(Protocol):
    def get_game(self, game_id: int) -> Any: ...


class ShopReader(Protocol):
    def get_shop(self, shop_id: uuid.UUID) -> Any: ...


class UserReader(Protocol):
    def get_user(self, user_id: uuid.UUID) -> Any: ...


class GroupLookup(Protocol):
    def get_members(self, group_id: uuid.UUID) -> list[Any] | None:
        """揪團的正式成員（不含候補），依加入順序；揪團不存在回 None。"""
        ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> AppError:
    return AppError(404, "MATCH_NOT_FOUND", "找不到這一局")


def _participant_not_found() -> AppError:
    return AppError(404, "MATCH_PARTICIPANT_NOT_FOUND", "找不到這位參加者")


def _finished() -> AppError:
    return AppError(409, "MATCH_FINISHED", "這一局已經結束，不能再加入或移除參加者")


def _validation_error(message: str, exc: ValidationError | None = None) -> AppError:
    errors = []
    if exc is not None:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return AppError(422, "VALIDATION_ERROR", message, {"errors": errors})


def _is_participant(user: CurrentUser, participants: list[Any]) -> bool:
    return any(p.user_id == user.id for p in participants)


def _require_participant(user: CurrentUser, participants: list[Any]) -> None:
    """這局有帳號的參加者或管理員才能做；開局者沒有額外權限（design.md D5）。"""
    if user.role != "admin" and not _is_participant(user, participants):
        raise PermissionDenied()


def _lowest_free_seat(participants: list[Any]) -> int:
    return _lowest_free_seat_from({p.seat_number for p in participants})


def _lowest_free_seat_from(taken: set[int]) -> int:
    seat = 1
    while seat in taken:
        seat += 1
    return seat


class MatchesService:
    def __init__(
        self,
        repository: MatchesRepositoryProtocol,
        *,
        games: GameReader,
        shops: ShopReader,
        users: UserReader,
        groups: GroupLookup,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repo = repository
        self._games = games
        self._shops = shops
        self._users = users
        self._groups = groups
        self._now = now

    # --- 開局 ---

    def create_match(self, user: CurrentUser, data: MatchCreate) -> MatchResponse:
        if self._games.get_game(data.game_id) is None:
            raise AppError(404, "MATCH_GAME_NOT_FOUND", "找不到這款遊戲")
        if data.shop_id is not None and self._shops.get_shop(data.shop_id) is None:
            raise AppError(404, "MATCH_SHOP_NOT_FOUND", "找不到這間店家")
        group_members: list[Any] = []
        if data.group_id is not None:
            found = self._groups.get_members(data.group_id)
            if found is None:
                raise AppError(404, "MATCH_GROUP_NOT_FOUND", "找不到這個揪團")
            # 只有該揪團的開團主與正式成員（開團主一定是成員）或管理員可以替揪團開局
            if user.role != "admin" and all(m.user_id != user.id for m in found):
                raise PermissionDenied()
            group_members = found
        creator = self._users.get_user(user.id)
        if creator is None:
            raise AppError(404, "MATCH_USER_NOT_FOUND", "找不到目前使用者的帳號")

        with self._repo.transaction():
            match_id = self._repo.add_match(
                game_id=data.game_id,
                played_on=data.played_on,
                location_type=data.location_type,
                shop_id=data.shop_id,
                group_id=data.group_id,
                created_by=user.id,
                progress=data.progress,
            )
            # 開局者自動成為參加者，座位由他自己選，沒帶就給最小的空位（也就是 1）
            self._repo.add_participant(
                match_id, data.seat_number or 1, user.id, creator.display_name
            )
            # 帶揪團開局：其他正式成員依加入順序，各給最小的空位
            taken = {data.seat_number or 1}
            for member in group_members:
                if member.user_id == user.id:
                    continue
                seat = _lowest_free_seat_from(taken)
                taken.add(seat)
                self._repo.add_participant(match_id, seat, member.user_id, member.display_name)
        return self._load(match_id)

    # --- 查詢 ---

    def get_match(self, user: CurrentUser, match_id: uuid.UUID) -> MatchResponse:
        return self._load(match_id)

    def list_matches(
        self,
        user: CurrentUser,
        *,
        game_id: int | None = None,
        group_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MatchListResponse:
        records, total = self._repo.list_matches(
            game_id=game_id, group_id=group_id, user_id=user_id, page=page, page_size=page_size
        )
        return MatchListResponse(items=[self._to_response(m) for m in records], total=total)

    # --- 參加者 ---

    def add_participant(
        self, user: CurrentUser, match_id: uuid.UUID, data: ParticipantCreate
    ) -> ParticipantResponse:
        with self._repo.transaction():
            match = self._lock(match_id)
            participants = self._repo.list_participants(match_id)
            if data.display_name is None:
                # 玩家自己按加入，名稱取自帳號
                if match.status == "finished":
                    raise _finished()
                if _is_participant(user, participants):
                    raise AppError(409, "MATCH_ALREADY_JOINED", "你已經在這一局了")
                account = self._users.get_user(user.id)
                if account is None:
                    raise AppError(404, "MATCH_USER_NOT_FOUND", "找不到目前使用者的帳號")
                user_id, name = user.id, account.display_name
            else:
                # 新增沒有帳號的人：不以名字比對帳號，user_id 一律為空
                _require_participant(user, participants)
                if match.status == "finished":
                    raise _finished()
                user_id, name = None, data.display_name
            seat = data.seat_number or _lowest_free_seat(participants)
            if any(p.seat_number == seat for p in participants):
                raise AppError(
                    409, "MATCH_SEAT_TAKEN", f"座位 {seat} 已經有人", {"seat_number": seat}
                )
            participant_id = self._repo.add_participant(match_id, seat, user_id, name)
        return self._participant_response(self._repo.find_participant(match_id, participant_id))

    def remove_participant(
        self, user: CurrentUser, match_id: uuid.UUID, participant_id: uuid.UUID
    ) -> None:
        with self._repo.transaction():
            match = self._lock(match_id)
            participants = self._repo.list_participants(match_id)
            _require_participant(user, participants)
            target = self._repo.find_participant(match_id, participant_id)
            if target is None:
                raise _participant_not_found()
            if match.status == "finished":
                raise _finished()
            turn_numbers = self._repo.turns_using_seat(match_id, target.seat_number)
            if turn_numbers:
                raise AppError(
                    409,
                    "MATCH_PARTICIPANT_HAS_TURNS",
                    f"座位 {target.seat_number} 已出現在回合 {turn_numbers}，不能移除",
                    {"seat_number": target.seat_number, "turn_numbers": turn_numbers},
                )
            self._repo.delete_participant(participant_id)

    def confirm_participant(
        self,
        user: CurrentUser,
        match_id: uuid.UUID,
        participant_id: uuid.UUID,
        data: ParticipantConfirm,
    ) -> ParticipantResponse:
        with self._repo.transaction():
            match = self._lock(match_id)
            target = self._repo.find_participant(match_id, participant_id)
            if target is None:
                raise _participant_not_found()
            # 只有本人（或 admin）能確認；沒有帳號的人不需要也不能被確認
            if target.user_id is None or (user.role != "admin" and target.user_id != user.id):
                raise PermissionDenied()
            if match.status != "finished":
                raise AppError(409, "MATCH_RESULT_NOT_RECORDED", "還沒有記錄結果，不能確認")
            if not target.is_confirmed:
                self._repo.update_participant(
                    participant_id, {"is_confirmed": True, "confirmed_at": self._now()}
                )
        return self._participant_response(self._repo.find_participant(match_id, participant_id))

    # --- 回合 ---

    def record_turn(
        self,
        user: CurrentUser,
        match_id: uuid.UUID,
        data: TurnCreate,
        *,
        overwrite: bool = False,
    ) -> tuple[TurnResponse, bool]:
        """回傳 (回合紀錄, 是否新增)；覆蓋既有紀錄時第二個值是 False。"""
        with self._repo.transaction():
            match = self._lock(match_id)
            participants = self._repo.list_participants(match_id)
            _require_participant(user, participants)
            definition = self._definition_for(match)
            if definition is None:
                raise AppError(422, "MATCH_TURN_NOT_SUPPORTED", "這款遊戲還不支援記錄回合")
            try:
                game_data = definition.turn_model.model_validate(data.game_data).model_dump()
            except ValidationError as exc:
                raise _validation_error("game_data 格式不符合這款遊戲的定義", exc) from exc

            seats = {p.seat_number for p in participants}
            used = set(definition.played_seats(game_data))
            if data.seat_number is not None:
                used.add(data.seat_number)
            unknown = sorted(used - seats)
            if unknown:
                raise AppError(
                    422,
                    "MATCH_SEAT_NOT_FOUND",
                    f"這一局沒有座位 {unknown}",
                    {"seat_numbers": unknown},
                )

            existing = self._repo.find_turn(match_id, data.turn_number)
            if existing is not None and not overwrite:
                raise AppError(
                    409,
                    "MATCH_TURN_ALREADY_RECORDED",
                    f"第 {data.turn_number} 回合已經有紀錄",
                    {"existing": self._existing_turn_details(existing)},
                )
            self._check_once_per_match(match_id, data.turn_number, definition, game_data)
            if existing is None:
                turn = self._repo.add_turn(
                    match_id, data.turn_number, data.seat_number, game_data, user.id
                )
                return self._turn_response(turn), True
            turn = self._repo.update_turn(existing.id, data.seat_number, game_data, user.id)
            return self._turn_response(turn), False

    def _check_once_per_match(
        self,
        match_id: uuid.UUID,
        turn_number: int,
        definition: GameDefinition,
        game_data: dict,
    ) -> None:
        """白薔薇、司教這類一局只出現一次的欄位，別的回合已經記過就是 409。

        正在記錄（或覆蓋）的這一回合不算，所以編輯原本就有白薔薇的回合可以保留。
        """
        wanted = [once for once in definition.once_per_match if game_data.get(once.field)]
        if not wanted:
            return
        others = [t for t in self._repo.list_turns(match_id) if t.turn_number != turn_number]
        for once in wanted:
            taken = [t.turn_number for t in others if t.game_data.get(once.field)]
            if taken:
                raise AppError(
                    409,
                    once.error_code,
                    f"這一局第 {taken[0]} 回合已經記錄過{once.label}",
                    {"turn_numbers": taken},
                )

    # --- 結果 ---

    def record_result(
        self,
        user: CurrentUser,
        match_id: uuid.UUID,
        data: ResultRequest,
        *,
        overwrite: bool = False,
    ) -> MatchResponse:
        with self._repo.transaction():
            match = self._lock(match_id)
            participants = self._repo.list_participants(match_id)
            _require_participant(user, participants)

            game = self._games.get_game(match.game_id)
            if game.result_type is None:
                raise AppError(
                    409,
                    "MATCH_GAME_RESULT_TYPE_NOT_SET",
                    "這款遊戲還沒有設定結果類型，不能記錄結果",
                )
            definition = get_definition(game.bgg_id)
            if game.result_type != "faction" or definition is None:
                raise AppError(
                    422,
                    "MATCH_RESULT_TYPE_NOT_SUPPORTED",
                    f"結果類型 {game.result_type} 還不支援",
                    {"result_type": game.result_type},
                )
            if match.result is not None and not overwrite:
                raise AppError(
                    409,
                    "MATCH_RESULT_ALREADY_RECORDED",
                    "這一局已經有結果",
                    {"result": match.result},
                )
            factions = self._validated_factions(definition, data, participants)

            recorder = next((p for p in participants if p.user_id == user.id), None)
            for participant in participants:
                faction = factions[participant.seat_number]
                self._repo.update_participant(
                    participant.id,
                    {"faction": faction, "is_winner": faction == data.winning_faction},
                )
            # 覆蓋時，除了這次記錄的人，其他人的確認都清除；記錄的人自動算已確認
            self._repo.clear_confirmations(match_id, recorder.id if recorder is not None else None)
            if recorder is not None:
                self._repo.update_participant(
                    recorder.id, {"is_confirmed": True, "confirmed_at": self._now()}
                )
            self._repo.update_match(
                match_id,
                {
                    "status": "finished",
                    "result": {"type": "faction", "winning_faction": data.winning_faction},
                },
            )
        return self._load(match_id)

    # --- 內部 ---

    def _lock(self, match_id: uuid.UUID) -> Any:
        match = self._repo.lock_match(match_id)
        if match is None:
            raise _not_found()
        return match

    def _definition_for(self, match: Any) -> GameDefinition | None:
        game = self._games.get_game(match.game_id)
        return None if game is None else get_definition(game.bgg_id)

    @staticmethod
    def _validated_factions(
        definition: GameDefinition, data: ResultRequest, participants: list[Any]
    ) -> dict[int, str]:
        valid = set(definition.factions)
        bad = [data.winning_faction] if data.winning_faction not in valid else []
        bad += [p.faction for p in data.participants if p.faction not in valid]
        if bad:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "陣營不合法",
                {"invalid": bad, "valid_factions": sorted(valid)},
            )
        seats = {p.seat_number for p in participants}
        submitted = {p.seat_number for p in data.participants}
        if submitted - seats:
            unknown = sorted(submitted - seats)
            raise AppError(
                422, "MATCH_SEAT_NOT_FOUND", f"這一局沒有座位 {unknown}", {"seat_numbers": unknown}
            )
        if seats - submitted:
            missing = sorted(seats - submitted)
            raise AppError(
                422,
                "MATCH_RESULT_SEATS_INCOMPLETE",
                f"結果缺少座位 {missing}",
                {"missing_seat_numbers": missing},
            )
        return {p.seat_number: p.faction for p in data.participants}

    def _load(self, match_id: uuid.UUID) -> MatchResponse:
        match = self._repo.get_match(match_id)
        if match is None:
            raise _not_found()
        return self._to_response(match)

    def _to_response(self, match: Any) -> MatchResponse:
        game = self._games.get_game(match.game_id)
        shop = self._shops.get_shop(match.shop_id) if match.shop_id is not None else None
        creator = self._users.get_user(match.created_by)
        participants = self._repo.list_participants(match.id)
        turns = self._repo.list_turns(match.id)
        account_count = sum(1 for p in participants if p.user_id is not None)
        confirmed_count = sum(1 for p in participants if p.user_id is not None and p.is_confirmed)
        return MatchResponse(
            id=match.id,
            game=GameRef(id=game.id, name=game.name),
            played_on=match.played_on,
            location_type=match.location_type,
            shop=None if shop is None else ShopRef(id=shop.id, name=shop.name),
            group_id=match.group_id,
            created_by=UserRef(id=creator.id, display_name=creator.display_name),
            status=match.status,
            result=match.result,
            progress=match.progress,
            participants=[self._participant_response(p) for p in participants],
            turns=[self._turn_response(t) for t in turns],
            participant_count=len(participants),
            account_count=account_count,
            confirmed_count=confirmed_count,
            is_valid=match.status == "finished" and confirmed_count == account_count,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )

    @staticmethod
    def _participant_response(record: Any) -> ParticipantResponse:
        return ParticipantResponse(
            id=record.id,
            seat_number=record.seat_number,
            user_id=record.user_id,
            display_name=record.display_name,
            faction=record.faction,
            score=record.score,
            placement=record.placement,
            is_winner=record.is_winner,
            is_confirmed=record.is_confirmed,
        )

    @staticmethod
    def _turn_response(record: Any) -> TurnResponse:
        return TurnResponse(
            id=record.id,
            turn_number=record.turn_number,
            seat_number=record.seat_number,
            game_data=record.game_data,
            recorded_by=record.recorded_by,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _existing_turn_details(record: Any) -> dict[str, Any]:
        return {
            "turn_number": record.turn_number,
            "seat_number": record.seat_number,
            "game_data": record.game_data,
            "recorded_by": str(record.recorded_by),
        }
