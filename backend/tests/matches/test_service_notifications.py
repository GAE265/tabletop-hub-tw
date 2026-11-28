"""戰績通知的 service 單元測試：使用 FakeMatchesRepository，不連資料庫（AGENTS.md 7.5）。

情境對應 docs/mr_info/feature-matches-notifications.md 的後端情境表（標「單元」的列）。
service 在 fixture 裡才 import：程式還沒寫的時候，每個測試各自失敗。
"""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.core.auth import CurrentUser

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
WHITE_ROSE_BGG_ID = 400566
WHITE_ROSE = 1

CREATOR = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
PLAYER_B = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000b"), role="player")
PLAYER_C = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000c"), role="player")
ADMIN = CurrentUser(id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), role="admin")


class Clock:
    def __call__(self) -> datetime:
        return NOW


@pytest.fixture
def repo():
    from tests.matches.fakes import FakeMatchesRepository

    return FakeMatchesRepository(NOW)


@pytest.fixture
def service(repo):
    from app.domains.matches.service import MatchesService
    from tests.matches.fakes import FakeSharedData

    shared = FakeSharedData()
    for user, name in [
        (CREATOR, "開局者"),
        (PLAYER_B, "玩家乙"),
        (PLAYER_C, "玩家丙"),
        (ADMIN, "管理員"),
    ]:
        shared.add_user(user.id, name)
    shared.add_game(WHITE_ROSE, "血與刃的白薔薇", WHITE_ROSE_BGG_ID, "faction")
    return MatchesService(
        repo, games=shared, shops=shared, users=shared, groups=shared, now=Clock()
    )


def result_input(winning: str = "rose"):
    from app.domains.matches.schemas import ResultRequest

    factions = {1: "rose", 2: "rose", 3: "blood_blade", 4: "blood_blade"}
    return ResultRequest(
        winning_faction=winning,
        participants=[{"seat_number": s, "faction": f} for s, f in factions.items()],
    )


@pytest.fixture
def match_id(service) -> uuid.UUID:
    """座位 1 開局者、2 玩家乙、3 玩家丙（都有帳號）、4 Amy（沒有帳號）。"""
    from app.domains.matches.schemas import MatchCreate, ParticipantCreate

    match = service.create_match(
        CREATOR,
        MatchCreate(game_id=WHITE_ROSE, played_on=date(2026, 11, 20), location_type="home"),
    )
    service.add_participant(PLAYER_B, match.id, ParticipantCreate())
    service.add_participant(PLAYER_C, match.id, ParticipantCreate())
    service.add_participant(CREATOR, match.id, ParticipantCreate(display_name="Amy"))
    return match.id


def recipients(repo) -> list[uuid.UUID | None]:
    return [n.user_id for n in repo.notifications]


def test_notify_skips_participants_without_account(service, repo, match_id):
    service.record_result(CREATOR, match_id, result_input())
    assert None not in recipients(repo)
    assert sorted(recipients(repo)) == sorted([PLAYER_B.id, PLAYER_C.id])
    assert all(n.type == "match_result_recorded" for n in repo.notifications)
    assert all(n.recorded_by == CREATOR.id for n in repo.notifications)


def test_admin_recorder_notifies_every_account_participant(service, repo, match_id):
    service.record_result(ADMIN, match_id, result_input())
    assert sorted(recipients(repo)) == sorted([CREATOR.id, PLAYER_B.id, PLAYER_C.id])
    assert all(n.recorded_by == ADMIN.id for n in repo.notifications)


def test_overwrite_by_another_participant_notifies_previous_recorder(service, match_id):
    service.record_result(CREATOR, match_id, result_input("rose"))
    service.record_result(PLAYER_B, match_id, result_input("blood_blade"), overwrite=True)

    creator = service.list_notifications(CREATOR)
    assert (creator.total, creator.unread_count) == (1, 1)
    assert creator.items[0].recorded_by.id == PLAYER_B.id

    # 覆蓋的人自己不收新的；他手上那則「請確認開局者的結果」也已作廢、標成已讀
    overwriter = service.list_notifications(PLAYER_B)
    assert (overwriter.total, overwriter.unread_count) == (1, 0)

    other = service.list_notifications(PLAYER_C)
    assert (other.total, other.unread_count) == (2, 1)
