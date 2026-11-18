"""matches service 的單元測試：使用 FakeMatchesRepository，不連資料庫（AGENTS.md 7.5）。

情境對應 openspec/changes/add-matches-record/specs/matches-record/spec.md。
欄位格式驗證（422 VALIDATION_ERROR）在 test_api_*.py 測；這裡測商業規則與權限。
service 在 fixture 裡才 import：程式還沒寫的時候，每個測試各自失敗。
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
WHITE_ROSE_BGG_ID = 400566

CREATOR = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
PLAYER_B = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000b"), role="player")
PLAYER_C = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000c"), role="player")
OUTSIDER = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000d"), role="player")
ADMIN = CurrentUser(id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), role="admin")

WHITE_ROSE, OTHER_GAME, NO_RESULT_TYPE, COOPERATIVE = 1, 2, 3, 4


class Clock:
    def __call__(self) -> datetime:
        return NOW


@pytest.fixture
def repo():
    from tests.matches.fakes import FakeMatchesRepository

    return FakeMatchesRepository(NOW)


@pytest.fixture
def shared():
    from tests.matches.fakes import FakeSharedData

    data = FakeSharedData()
    for user, name in [
        (CREATOR, "開局者"),
        (PLAYER_B, "玩家乙"),
        (PLAYER_C, "玩家丙"),
        (OUTSIDER, "路人"),
        (ADMIN, "管理員"),
    ]:
        data.add_user(user.id, name)
    data.add_game(WHITE_ROSE, "血與刃的白薔薇", WHITE_ROSE_BGG_ID, "faction")
    data.add_game(OTHER_GAME, "其他遊戲", 900001, "score")
    data.add_game(NO_RESULT_TYPE, "血與刃的白薔薇（未設定）", WHITE_ROSE_BGG_ID, None)
    data.add_game(COOPERATIVE, "合作遊戲", 900002, "cooperative")
    return data


@pytest.fixture
def service(repo, shared):
    from app.domains.matches.service import MatchesService

    return MatchesService(
        repo, games=shared, shops=shared, users=shared, groups=shared, now=Clock()
    )


# --- 輔助 ---


def create_input(**overrides: Any):
    from app.domains.matches.schemas import MatchCreate

    values: dict[str, Any] = {
        "game_id": WHITE_ROSE,
        "played_on": date(2026, 11, 20),
        "location_type": "home",
    }
    values.update(overrides)
    return MatchCreate(**values)


def participant_input(**values: Any):
    from app.domains.matches.schemas import ParticipantCreate

    return ParticipantCreate(**values)


def game_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "played_seat_numbers": [1, 2],
        "double_blade_count": 1,
        "dark_blade_count": 1,
        "giant_blade_count": 0,
        "faithful_count": 2,
        "has_white_rose": False,
    }
    data.update(overrides)
    return data


def turn_input(turn_number: int = 1, seat_number: int = 1, **data_overrides: Any):
    from app.domains.matches.schemas import TurnCreate

    return TurnCreate(
        turn_number=turn_number, seat_number=seat_number, game_data=game_data(**data_overrides)
    )


def result_input(winning: str = "rose", factions: dict[int, str] | None = None):
    from app.domains.matches.schemas import ResultRequest

    factions = factions or {1: "rose", 2: "rose", 3: "blood_blade", 4: "blood_blade"}
    return ResultRequest(
        winning_faction=winning,
        participants=[{"seat_number": s, "faction": f} for s, f in factions.items()],
    )


def confirm_input(value: bool = True):
    from app.domains.matches.schemas import ParticipantConfirm

    return ParticipantConfirm(is_confirmed=value)


@pytest.fixture
def match_id(service) -> uuid.UUID:
    """座位 1 開局者、2 玩家乙、3 玩家丙（都有帳號）、4 Amy（沒有帳號）。"""
    match = service.create_match(CREATOR, create_input())
    service.add_participant(PLAYER_B, match.id, participant_input())
    service.add_participant(PLAYER_C, match.id, participant_input())
    service.add_participant(CREATOR, match.id, participant_input(display_name="Amy"))
    return match.id


def seat_of(service, match_id: uuid.UUID, user: CurrentUser):
    match = service.get_match(user, match_id)
    return next(p for p in match.participants if p.user_id == user.id)


def assert_app_error(exc_info: pytest.ExceptionInfo[AppError], status: int, code: str) -> None:
    assert exc_info.value.status_code == status
    assert exc_info.value.code == code


# --- 開局 ---


def test_create_match_creator_becomes_participant_with_lowest_seat(service):
    match = service.create_match(CREATOR, create_input())
    assert match.created_by.id == CREATOR.id
    assert match.created_by.display_name == "開局者"
    assert match.status == "in_progress"
    assert match.result is None
    assert match.game.name == "血與刃的白薔薇"
    [participant] = match.participants
    assert participant.seat_number == 1
    assert participant.user_id == CREATOR.id
    assert participant.display_name == "開局者"
    assert participant.is_confirmed is False
    assert (match.participant_count, match.account_count, match.confirmed_count) == (1, 1, 0)


def test_create_match_creator_chooses_seat(service):
    match = service.create_match(CREATOR, create_input(seat_number=4))
    assert match.participants[0].seat_number == 4


def test_create_match_at_shop(service, shared):
    shop_id = shared.add_shop("測試桌遊店")
    match = service.create_match(
        CREATOR, create_input(location_type="shop", shop_id=shop_id, game_id=OTHER_GAME)
    )
    assert match.location_type == "shop"
    assert match.shop.name == "測試桌遊店"


def test_create_match_at_home_has_no_shop(service):
    assert service.create_match(CREATOR, create_input()).shop is None


def test_create_match_for_group_does_not_require_membership(service, shared):
    group_id = shared.add_group()
    match = service.create_match(CREATOR, create_input(group_id=group_id))
    assert match.group_id == group_id


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"game_id": 999}, "MATCH_GAME_NOT_FOUND"),
        ({"location_type": "shop", "shop_id": uuid.uuid4()}, "MATCH_SHOP_NOT_FOUND"),
        ({"group_id": uuid.uuid4()}, "MATCH_GROUP_NOT_FOUND"),
    ],
)
def test_create_match_references_must_exist(service, repo, overrides, code):
    with pytest.raises(AppError) as exc_info:
        service.create_match(CREATOR, create_input(**overrides))
    assert_app_error(exc_info, 404, code)
    assert repo.matches == {}


# --- 查詢 ---


def test_get_match_not_found(service):
    with pytest.raises(AppError) as exc_info:
        service.get_match(CREATOR, uuid.uuid4())
    assert_app_error(exc_info, 404, "MATCH_NOT_FOUND")


def test_get_match_is_open_to_non_participants(service, match_id):
    assert service.get_match(OUTSIDER, match_id).id == match_id


def test_get_match_counts_and_is_valid(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    match = service.confirm_participant(
        PLAYER_B, match_id, seat_of(service, match_id, PLAYER_B).id, confirm_input()
    )
    assert match.is_confirmed is True
    detail = service.get_match(OUTSIDER, match_id)
    assert (detail.participant_count, detail.account_count, detail.confirmed_count) == (4, 3, 2)
    assert detail.is_valid is False


def test_all_account_participants_confirmed_makes_match_valid_without_name_only(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    for user in (PLAYER_B, PLAYER_C):
        service.confirm_participant(
            user, match_id, seat_of(service, match_id, user).id, confirm_input()
        )
    detail = service.get_match(OUTSIDER, match_id)
    assert (detail.account_count, detail.confirmed_count) == (3, 3)
    assert detail.is_valid is True


def test_match_without_result_is_not_valid(service, match_id):
    assert service.get_match(CREATOR, match_id).is_valid is False


def test_list_matches_filters_and_total(service, shared):
    first = service.create_match(CREATOR, create_input(game_id=WHITE_ROSE))
    service.create_match(PLAYER_B, create_input(game_id=OTHER_GAME))
    by_game = service.list_matches(OUTSIDER, game_id=WHITE_ROSE)
    assert by_game.total == 1
    assert [item.id for item in by_game.items] == [first.id]
    by_user = service.list_matches(OUTSIDER, user_id=PLAYER_B.id)
    assert by_user.total == 1


# --- 加入參加者 ---


def test_player_joins_self_with_lowest_free_seat(service, match_id):
    match = service.get_match(OUTSIDER, match_id)
    joined = service.add_participant(OUTSIDER, match.id, participant_input())
    assert (joined.seat_number, joined.user_id, joined.display_name) == (5, OUTSIDER.id, "路人")
    assert joined.is_confirmed is False


def test_player_joins_with_chosen_seat(service):
    match = service.create_match(CREATOR, create_input())
    joined = service.add_participant(PLAYER_B, match.id, participant_input(seat_number=3))
    assert joined.seat_number == 3


def test_join_twice_is_conflict(service, match_id):
    with pytest.raises(AppError) as exc_info:
        service.add_participant(PLAYER_B, match_id, participant_input())
    assert_app_error(exc_info, 409, "MATCH_ALREADY_JOINED")


def test_join_taken_seat_is_conflict(service, match_id):
    with pytest.raises(AppError) as exc_info:
        service.add_participant(OUTSIDER, match_id, participant_input(seat_number=2))
    assert_app_error(exc_info, 409, "MATCH_SEAT_TAKEN")


def test_participant_adds_name_only_participant(service, match_id):
    amy = service.add_participant(
        PLAYER_B, match_id, participant_input(display_name="Bob", seat_number=6)
    )
    assert (amy.user_id, amy.display_name, amy.seat_number) == (None, "Bob", 6)


def test_same_name_as_an_account_is_not_bound_to_it(service, match_id):
    added = service.add_participant(CREATOR, match_id, participant_input(display_name="玩家乙"))
    assert added.user_id is None
    assert service.get_match(CREATOR, match_id).account_count == 3


def test_outsider_cannot_add_name_only_participant(service, match_id, repo):
    before = len(repo.participants)
    with pytest.raises(PermissionDenied):
        service.add_participant(OUTSIDER, match_id, participant_input(display_name="Bob"))
    assert len(repo.participants) == before


def test_admin_can_add_name_only_participant(service, match_id):
    added = service.add_participant(ADMIN, match_id, participant_input(display_name="Bob"))
    assert added.user_id is None


def test_cannot_join_finished_match(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    with pytest.raises(AppError) as exc_info:
        service.add_participant(OUTSIDER, match_id, participant_input())
    assert_app_error(exc_info, 409, "MATCH_FINISHED")


def test_add_participant_to_missing_match(service):
    with pytest.raises(AppError) as exc_info:
        service.add_participant(OUTSIDER, uuid.uuid4(), participant_input())
    assert_app_error(exc_info, 404, "MATCH_NOT_FOUND")


# --- 記錄回合 ---


def test_participant_records_turn(service, match_id):
    turn, created = service.record_turn(PLAYER_B, match_id, turn_input(1, 2))
    assert created is True
    assert (turn.turn_number, turn.seat_number, turn.recorded_by) == (1, 2, PLAYER_B.id)
    assert turn.game_data["played_seat_numbers"] == [1, 2]
    assert [t.turn_number for t in service.get_match(CREATOR, match_id).turns] == [1]


def test_leader_does_not_have_to_be_in_played_seats(service, match_id):
    turn, _ = service.record_turn(CREATOR, match_id, turn_input(1, 3, played_seat_numbers=[1]))
    assert turn.seat_number == 3


def test_name_only_participant_can_lead_a_turn(service, match_id):
    turn, _ = service.record_turn(CREATOR, match_id, turn_input(1, 4, played_seat_numbers=[4]))
    assert turn.seat_number == 4


def test_outsider_cannot_record_turn(service, match_id, repo):
    with pytest.raises(PermissionDenied):
        service.record_turn(OUTSIDER, match_id, turn_input())
    assert repo.turns == []


def test_admin_can_record_turn(service, match_id):
    _, created = service.record_turn(ADMIN, match_id, turn_input())
    assert created is True


def test_duplicate_turn_is_conflict_and_keeps_old_record(service, match_id, repo):
    service.record_turn(CREATOR, match_id, turn_input(1, 1))
    with pytest.raises(AppError) as exc_info:
        service.record_turn(PLAYER_B, match_id, turn_input(1, 2, faithful_count=9))
    assert_app_error(exc_info, 409, "MATCH_TURN_ALREADY_RECORDED")
    existing = exc_info.value.details["existing"]
    assert existing["turn_number"] == 1
    assert existing["seat_number"] == 1
    assert existing["recorded_by"] == CREATOR.id or existing["recorded_by"] == str(CREATOR.id)
    [stored] = repo.turns
    assert (stored.seat_number, stored.game_data["faithful_count"]) == (1, 2)


def test_overwrite_replaces_turn_and_recorder(service, match_id, repo):
    service.record_turn(CREATOR, match_id, turn_input(1, 1))
    turn, created = service.record_turn(
        PLAYER_B, match_id, turn_input(1, 2, faithful_count=5), overwrite=True
    )
    assert created is False
    assert (turn.seat_number, turn.game_data["faithful_count"], turn.recorded_by) == (
        2,
        5,
        PLAYER_B.id,
    )
    assert len(repo.turns) == 1


def test_overwrite_of_missing_turn_creates_it(service, match_id):
    _, created = service.record_turn(CREATOR, match_id, turn_input(2, 1), overwrite=True)
    assert created is True


def test_turn_seat_must_exist(service, match_id, repo):
    with pytest.raises(AppError) as exc_info:
        service.record_turn(CREATOR, match_id, turn_input(1, 9))
    assert_app_error(exc_info, 422, "MATCH_SEAT_NOT_FOUND")
    assert repo.turns == []


def test_played_seats_must_exist(service, match_id, repo):
    with pytest.raises(AppError) as exc_info:
        service.record_turn(CREATOR, match_id, turn_input(1, 1, played_seat_numbers=[1, 9, 8]))
    assert_app_error(exc_info, 422, "MATCH_SEAT_NOT_FOUND")
    assert sorted(exc_info.value.details["seat_numbers"]) == [8, 9]
    assert repo.turns == []


def test_game_without_turn_format_is_not_supported(service):
    match = service.create_match(CREATOR, create_input(game_id=OTHER_GAME))
    with pytest.raises(AppError) as exc_info:
        service.record_turn(CREATOR, match.id, turn_input(1, 1))
    assert_app_error(exc_info, 422, "MATCH_TURN_NOT_SUPPORTED")


def test_record_turn_for_missing_match(service):
    with pytest.raises(AppError) as exc_info:
        service.record_turn(CREATOR, uuid.uuid4(), turn_input())
    assert_app_error(exc_info, 404, "MATCH_NOT_FOUND")


def test_turns_can_still_be_recorded_when_result_type_is_empty(service):
    match = service.create_match(CREATOR, create_input(game_id=NO_RESULT_TYPE))
    _, created = service.record_turn(CREATOR, match.id, turn_input(1, 1, played_seat_numbers=[1]))
    assert created is True


# --- 記錄結果 ---


def test_record_result_sets_winners_and_leaves_score_empty(service, match_id):
    match = service.record_result(CREATOR, match_id, result_input("rose"))
    assert match.status == "finished"
    assert match.result == {"type": "faction", "winning_faction": "rose"}
    by_seat = {p.seat_number: p for p in match.participants}
    assert [by_seat[s].is_winner for s in (1, 2, 3, 4)] == [True, True, False, False]
    assert [by_seat[s].faction for s in (1, 2, 3, 4)] == [
        "rose",
        "rose",
        "blood_blade",
        "blood_blade",
    ]
    assert all(p.score is None and p.placement is None for p in match.participants)


def test_result_recorder_is_confirmed_others_are_not(service, match_id):
    match = service.record_result(PLAYER_B, match_id, result_input())
    confirmed = {p.display_name: p.is_confirmed for p in match.participants}
    assert confirmed == {"開局者": False, "玩家乙": True, "玩家丙": False, "Amy": False}


def test_any_account_participant_can_record_result_not_only_creator(service, match_id):
    assert service.record_result(PLAYER_C, match_id, result_input()).status == "finished"


def test_outsider_cannot_record_result(service, match_id):
    with pytest.raises(PermissionDenied):
        service.record_result(OUTSIDER, match_id, result_input())
    assert service.get_match(CREATOR, match_id).status == "in_progress"


def test_result_without_any_turn_is_allowed(service, match_id):
    assert service.get_match(CREATOR, match_id).turns == []
    assert service.record_result(CREATOR, match_id, result_input()).status == "finished"


def test_duplicate_result_is_conflict_and_keeps_old_result(service, match_id):
    service.record_result(CREATOR, match_id, result_input("rose"))
    with pytest.raises(AppError) as exc_info:
        service.record_result(PLAYER_B, match_id, result_input("blood_blade"))
    assert_app_error(exc_info, 409, "MATCH_RESULT_ALREADY_RECORDED")
    assert service.get_match(CREATOR, match_id).result["winning_faction"] == "rose"


def test_overwriting_result_clears_others_confirmation_but_keeps_overwriter(service, match_id):
    service.record_result(CREATOR, match_id, result_input("rose"))
    service.confirm_participant(
        PLAYER_C, match_id, seat_of(service, match_id, PLAYER_C).id, confirm_input()
    )
    match = service.record_result(PLAYER_B, match_id, result_input("blood_blade"), overwrite=True)
    assert match.result["winning_faction"] == "blood_blade"
    confirmed = {p.display_name: p.is_confirmed for p in match.participants}
    assert confirmed == {"開局者": False, "玩家乙": True, "玩家丙": False, "Amy": False}
    assert match.is_valid is False


def test_admin_overwrite_who_is_not_participant_clears_everyone(service, match_id):
    service.record_result(CREATOR, match_id, result_input("rose"))
    match = service.record_result(ADMIN, match_id, result_input("blood_blade"), overwrite=True)
    assert not any(p.is_confirmed for p in match.participants)


def test_result_when_result_type_is_empty_is_conflict(service):
    match = service.create_match(CREATOR, create_input(game_id=NO_RESULT_TYPE))
    with pytest.raises(AppError) as exc_info:
        service.record_result(CREATOR, match.id, result_input(factions={1: "rose"}))
    assert_app_error(exc_info, 409, "MATCH_GAME_RESULT_TYPE_NOT_SET")
    assert service.get_match(CREATOR, match.id).status == "in_progress"


@pytest.mark.parametrize("game_id", [OTHER_GAME, COOPERATIVE])
def test_result_types_other_than_faction_are_not_supported_yet(service, game_id):
    match = service.create_match(CREATOR, create_input(game_id=game_id))
    with pytest.raises(AppError) as exc_info:
        service.record_result(CREATOR, match.id, result_input(factions={1: "rose"}))
    assert_app_error(exc_info, 422, "MATCH_RESULT_TYPE_NOT_SUPPORTED")


def test_result_missing_seats_lists_them(service, match_id):
    factions = {1: "rose", 2: "rose"}  # 少了座位 3、4
    with pytest.raises(AppError) as exc_info:
        service.record_result(CREATOR, match_id, result_input(factions=factions))
    assert_app_error(exc_info, 422, "MATCH_RESULT_SEATS_INCOMPLETE")
    assert sorted(exc_info.value.details["missing_seat_numbers"]) == [3, 4]
    assert service.get_match(CREATOR, match_id).status == "in_progress"


def test_result_with_unknown_seat_is_rejected(service, match_id):
    factions = {1: "rose", 2: "rose", 3: "blood_blade", 4: "rose", 5: "rose"}  # 沒有座位 5
    with pytest.raises(AppError) as exc_info:
        service.record_result(CREATOR, match_id, result_input(factions=factions))
    assert_app_error(exc_info, 422, "MATCH_SEAT_NOT_FOUND")
    assert exc_info.value.details["seat_numbers"] == [5]
    assert service.get_match(CREATOR, match_id).status == "in_progress"


# --- 確認 ---


def test_participant_confirms_own_record(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    mine = seat_of(service, match_id, PLAYER_B)
    confirmed = service.confirm_participant(PLAYER_B, match_id, mine.id, confirm_input())
    assert confirmed.is_confirmed is True
    assert service.get_match(CREATOR, match_id).confirmed_count == 2


def test_confirm_twice_is_idempotent(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    mine = seat_of(service, match_id, PLAYER_B)
    service.confirm_participant(PLAYER_B, match_id, mine.id, confirm_input())
    again = service.confirm_participant(PLAYER_B, match_id, mine.id, confirm_input())
    assert again.is_confirmed is True
    assert service.get_match(CREATOR, match_id).confirmed_count == 2


def test_cannot_confirm_for_someone_else(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    theirs = seat_of(service, match_id, PLAYER_C)
    with pytest.raises(PermissionDenied):
        service.confirm_participant(PLAYER_B, match_id, theirs.id, confirm_input())
    assert seat_of(service, match_id, PLAYER_C).is_confirmed is False


def test_outsider_cannot_confirm(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    with pytest.raises(PermissionDenied):
        service.confirm_participant(
            OUTSIDER, match_id, seat_of(service, match_id, PLAYER_B).id, confirm_input()
        )


def test_name_only_participant_cannot_be_confirmed_by_anyone(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    amy = next(p for p in service.get_match(CREATOR, match_id).participants if p.user_id is None)
    with pytest.raises(PermissionDenied):
        service.confirm_participant(CREATOR, match_id, amy.id, confirm_input())


def test_admin_can_confirm(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    mine = seat_of(service, match_id, PLAYER_B)
    assert service.confirm_participant(ADMIN, match_id, mine.id, confirm_input()).is_confirmed


def test_cannot_confirm_before_result(service, match_id):
    mine = seat_of(service, match_id, PLAYER_B)
    with pytest.raises(AppError) as exc_info:
        service.confirm_participant(PLAYER_B, match_id, mine.id, confirm_input())
    assert_app_error(exc_info, 409, "MATCH_RESULT_NOT_RECORDED")


def test_confirm_unknown_participant(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    with pytest.raises(AppError) as exc_info:
        service.confirm_participant(PLAYER_B, match_id, uuid.uuid4(), confirm_input())
    assert_app_error(exc_info, 404, "MATCH_PARTICIPANT_NOT_FOUND")


# --- 移除參加者 ---


def test_participant_can_quit(service, match_id):
    service.remove_participant(PLAYER_B, match_id, seat_of(service, match_id, PLAYER_B).id)
    detail = service.get_match(CREATOR, match_id)
    assert (detail.participant_count, detail.account_count) == (3, 2)
    assert all(p.user_id != PLAYER_B.id for p in detail.participants)


def test_participant_removes_name_only_participant(service, match_id):
    amy = next(p for p in service.get_match(CREATOR, match_id).participants if p.user_id is None)
    service.remove_participant(PLAYER_B, match_id, amy.id)
    detail = service.get_match(CREATOR, match_id)
    assert (detail.participant_count, detail.account_count) == (3, 3)


def test_participant_removes_another_account_participant(service, match_id):
    service.remove_participant(PLAYER_B, match_id, seat_of(service, match_id, PLAYER_C).id)
    assert all(p.user_id != PLAYER_C.id for p in service.get_match(CREATOR, match_id).participants)


def test_removed_seat_can_be_taken_again(service, match_id):
    service.remove_participant(PLAYER_B, match_id, seat_of(service, match_id, PLAYER_B).id)
    joined = service.add_participant(OUTSIDER, match_id, participant_input(seat_number=2))
    assert joined.seat_number == 2


def test_outsider_cannot_remove(service, match_id):
    target = seat_of(service, match_id, PLAYER_B)
    with pytest.raises(PermissionDenied):
        service.remove_participant(OUTSIDER, match_id, target.id)
    assert service.get_match(CREATOR, match_id).participant_count == 4


def test_admin_can_remove(service, match_id):
    service.remove_participant(ADMIN, match_id, seat_of(service, match_id, PLAYER_B).id)
    assert service.get_match(CREATOR, match_id).participant_count == 3


def test_cannot_remove_from_finished_match(service, match_id):
    service.record_result(CREATOR, match_id, result_input())
    with pytest.raises(AppError) as exc_info:
        service.remove_participant(CREATOR, match_id, seat_of(service, match_id, PLAYER_B).id)
    assert_app_error(exc_info, 409, "MATCH_FINISHED")
    assert service.get_match(CREATOR, match_id).participant_count == 4


def test_cannot_remove_seat_that_led_a_turn(service, match_id):
    service.record_turn(CREATOR, match_id, turn_input(1, 2, played_seat_numbers=[1]))
    service.record_turn(CREATOR, match_id, turn_input(3, 2, played_seat_numbers=[1]))
    with pytest.raises(AppError) as exc_info:
        service.remove_participant(CREATOR, match_id, seat_of(service, match_id, PLAYER_B).id)
    assert_app_error(exc_info, 409, "MATCH_PARTICIPANT_HAS_TURNS")
    assert exc_info.value.details["seat_number"] == 2
    assert exc_info.value.details["turn_numbers"] == [1, 3]
    assert service.get_match(CREATOR, match_id).participant_count == 4


def test_cannot_remove_seat_that_played_in_a_turn(service, match_id):
    service.record_turn(CREATOR, match_id, turn_input(1, 1, played_seat_numbers=[1, 3]))
    with pytest.raises(AppError) as exc_info:
        service.remove_participant(CREATOR, match_id, seat_of(service, match_id, PLAYER_C).id)
    assert_app_error(exc_info, 409, "MATCH_PARTICIPANT_HAS_TURNS")
    assert exc_info.value.details["turn_numbers"] == [1]


def test_seat_not_in_any_turn_can_be_removed_even_if_match_has_turns(service, match_id):
    service.record_turn(CREATOR, match_id, turn_input(1, 1, played_seat_numbers=[1, 2]))
    amy = next(p for p in service.get_match(CREATOR, match_id).participants if p.user_id is None)
    service.remove_participant(CREATOR, match_id, amy.id)
    assert service.get_match(CREATOR, match_id).participant_count == 3


def test_overwriting_the_turn_frees_the_seat_for_removal(service, match_id):
    service.record_turn(CREATOR, match_id, turn_input(1, 2, played_seat_numbers=[1]))
    service.record_turn(
        CREATOR, match_id, turn_input(1, 1, played_seat_numbers=[1]), overwrite=True
    )
    service.remove_participant(CREATOR, match_id, seat_of(service, match_id, PLAYER_B).id)
    assert service.get_match(CREATOR, match_id).participant_count == 3


def test_remove_unknown_participant(service, match_id):
    with pytest.raises(AppError) as exc_info:
        service.remove_participant(CREATOR, match_id, uuid.uuid4())
    assert_app_error(exc_info, 404, "MATCH_PARTICIPANT_NOT_FOUND")
