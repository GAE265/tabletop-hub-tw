"""matches API 測試：記錄回合（含覆蓋、競爭）與記錄結果。連 `_test` 資料庫。

情境對應 openspec/changes/add-matches-record/specs/matches-record/spec.md
「記錄回合」「記錄結果」。
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tests.conftest import TEST_ADMIN, TEST_PLAYER
from tests.matches.conftest import OUTSIDER, PLAYER_B, PLAYER_C
from tests.matches.support import (
    BASE,
    error_code,
    game_data,
    match_body,
    participant_named,
    result_body,
    turn_body,
)


def get(api, user, match_id: str) -> dict:
    return api(user, "GET", f"{BASE}/{match_id}").json()


def post_turn(api, user, match_id: str, body: dict, overwrite: bool = False):
    params = {"overwrite": "true"} if overwrite else None
    return api(user, "POST", f"{BASE}/{match_id}/turns", json=body, params=params)


def put_result(api, user, match_id: str, body: dict, overwrite: bool = False):
    params = {"overwrite": "true"} if overwrite else None
    return api(user, "PUT", f"{BASE}/{match_id}/result", json=body, params=params)


# --- 記錄回合 ---


def test_participant_records_turn(api, started: str):
    response = post_turn(api, PLAYER_B, started, turn_body(1, 2))
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["turn_number"] == 1
    assert body["seat_number"] == 2
    assert body["game_data"] == game_data()
    assert body["recorded_by"] == str(PLAYER_B.id)


def test_admin_can_record_turn(api, started: str):
    assert post_turn(api, TEST_ADMIN, started, turn_body()).status_code == 201


def test_duplicate_turn_is_conflict_and_old_record_is_unchanged(api, started: str):
    post_turn(api, TEST_PLAYER, started, turn_body(1, 1, faithful_count=2))
    response = post_turn(api, PLAYER_B, started, turn_body(1, 2, faithful_count=9))
    assert response.status_code == 409
    assert error_code(response) == "MATCH_TURN_ALREADY_RECORDED"
    existing = response.json()["error"]["details"]["existing"]
    assert existing["turn_number"] == 1
    assert existing["game_data"]["faithful_count"] == 2
    [turn] = get(api, TEST_PLAYER, started)["turns"]
    assert (turn["seat_number"], turn["game_data"]["faithful_count"]) == (1, 2)


def test_overwrite_replaces_turn(api, started: str):
    post_turn(api, TEST_PLAYER, started, turn_body(1, 1, faithful_count=2))
    response = post_turn(api, PLAYER_B, started, turn_body(1, 2, faithful_count=9), overwrite=True)
    assert response.status_code == 200
    body = response.json()
    assert (body["seat_number"], body["game_data"]["faithful_count"]) == (2, 9)
    assert body["recorded_by"] == str(PLAYER_B.id)
    assert len(get(api, TEST_PLAYER, started)["turns"]) == 1


def test_overwrite_of_missing_turn_creates_it(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(2, 1), overwrite=True)
    assert response.status_code == 201


def test_turn_seat_must_exist(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 9))
    assert (response.status_code, error_code(response)) == (422, "MATCH_SEAT_NOT_FOUND")


def test_played_seat_must_exist(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 1, played_seat_numbers=[1, 9]))
    assert (response.status_code, error_code(response)) == (422, "MATCH_SEAT_NOT_FOUND")
    assert response.json()["error"]["details"]["seat_numbers"] == [9]
    assert get(api, TEST_PLAYER, started)["turns"] == []


@pytest.mark.parametrize(
    "played_seat_numbers",
    [[1, 1], [0], [-1], ["1"], "1", None],
    ids=["duplicate", "zero", "negative", "string-item", "not-a-list", "null"],
)
def test_played_seat_numbers_must_be_valid(api, started: str, played_seat_numbers: Any):
    response = post_turn(
        api, TEST_PLAYER, started, turn_body(1, 1, played_seat_numbers=played_seat_numbers)
    )
    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
    assert get(api, TEST_PLAYER, started)["turns"] == []


def test_played_seat_numbers_is_required(api, started: str):
    body = turn_body(1, 1)
    del body["game_data"]["played_seat_numbers"]
    assert post_turn(api, TEST_PLAYER, started, body).status_code == 422


@pytest.mark.parametrize(
    "bad",
    [
        {"has_white_rose": None},  # 缺 has_white_rose（下面會刪掉）
        {"faithful_count": -1},
        {"faithful_count": "2"},
        {"double_blade_count": 1.5},
        {"ghost_count": 1},  # 幽魂不記，不接受其他欄位
    ],
    ids=["missing-field", "negative", "string", "float", "extra-field"],
)
def test_game_data_must_match_the_game_definition(api, started: str, bad: dict[str, Any]):
    body = turn_body(1, 1)
    if "has_white_rose" in bad:
        del body["game_data"]["has_white_rose"]
    else:
        body["game_data"].update(bad)
    response = post_turn(api, TEST_PLAYER, started, body)
    assert response.status_code == 422
    assert get(api, TEST_PLAYER, started)["turns"] == []


@pytest.mark.parametrize("turn_number", [0, -1])
def test_turn_number_must_be_positive(api, started: str, turn_number: int):
    assert post_turn(api, TEST_PLAYER, started, turn_body(turn_number, 1)).status_code == 422


def test_non_participant_cannot_record_turn(api, started: str):
    response = post_turn(api, OUTSIDER, started, turn_body())
    assert response.status_code == 403
    assert get(api, TEST_PLAYER, started)["turns"] == []


def test_game_without_turn_format_is_not_supported(api, other_game_id: int):
    match_id = api(TEST_PLAYER, "POST", BASE, json=match_body(other_game_id)).json()["id"]
    response = post_turn(api, TEST_PLAYER, match_id, turn_body(1, 1))
    assert (response.status_code, error_code(response)) == (422, "MATCH_TURN_NOT_SUPPORTED")


def test_record_turn_for_missing_match(api, started: str):
    response = post_turn(api, TEST_PLAYER, str(uuid.uuid4()), turn_body())
    assert (response.status_code, error_code(response)) == (404, "MATCH_NOT_FOUND")


def test_two_simultaneous_requests_for_same_turn(client: TestClient, act_as, started: str):
    act_as(PLAYER_B)
    barrier = threading.Barrier(2)

    def send(seat: int) -> int:
        barrier.wait()
        return client.post(f"{BASE}/{started}/turns", json=turn_body(1, seat)).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(send, [1, 2]))
    assert statuses == [201, 409]
    assert len(client.get(f"{BASE}/{started}").json()["turns"]) == 1


def hold_match_lock(db: Engine, match_id: str, request, expect_status: int):
    """持有這局的鎖時送出請求，請求必須等鎖放開才完成，且結果是 expect_status。"""
    from app.domains.matches.repository import MatchesRepository

    result: dict[str, Any] = {}

    def run() -> None:
        result["status"] = request().status_code

    with Session(db) as session:
        repo = MatchesRepository(session)
        with repo.transaction():
            assert repo.lock_match(uuid.UUID(match_id)) is not None
            worker = threading.Thread(target=run)
            worker.start()
            time.sleep(0.5)
            assert worker.is_alive(), "請求應該等待這局的鎖"
    worker.join(timeout=10)
    assert result["status"] == expect_status


def test_record_turn_waits_for_match_lock(api, db: Engine, client: TestClient, started: str):
    api(PLAYER_B, "GET", f"{BASE}/{started}")
    hold_match_lock(
        db,
        started,
        lambda: client.post(f"{BASE}/{started}/turns", json=turn_body(1, 1)),
        expect_status=201,
    )


def test_remove_participant_waits_for_match_lock(api, db: Engine, client: TestClient, started: str):
    amy = participant_named(get(api, TEST_PLAYER, started), "Amy")
    hold_match_lock(
        db,
        started,
        lambda: client.delete(f"{BASE}/{started}/participants/{amy['id']}"),
        expect_status=204,
    )


# --- 記錄結果 ---


def test_record_result(api, started: str):
    post_turn(api, TEST_PLAYER, started, turn_body(1, 1))
    response = put_result(api, TEST_PLAYER, started, result_body("rose"))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "finished"
    assert body["result"] == {"type": "faction", "winning_faction": "rose"}
    by_seat = {p["seat_number"]: p for p in body["participants"]}
    assert [by_seat[s]["faction"] for s in (1, 2, 3, 4)] == [
        "rose",
        "rose",
        "blood_blade",
        "blood_blade",
    ]
    assert [by_seat[s]["is_winner"] for s in (1, 2, 3, 4)] == [True, True, False, False]
    assert all(p["score"] is None and p["placement"] is None for p in body["participants"])


def test_result_without_any_turn(api, started: str):
    assert get(api, TEST_PLAYER, started)["turns"] == []
    assert put_result(api, TEST_PLAYER, started, result_body()).status_code == 200


def test_score_and_placement_are_null_in_database(api, db: Engine, started: str):
    put_result(api, TEST_PLAYER, started, result_body())
    with db.connect() as conn:
        rows = conn.execute(
            text("SELECT score, placement FROM match_participants WHERE match_id = :m"),
            {"m": started},
        ).all()
    assert len(rows) == 4
    assert all(score is None and placement is None for score, placement in rows)


def test_result_recorder_is_confirmed_and_others_are_not(api, started: str):
    body = put_result(api, PLAYER_B, started, result_body()).json()
    confirmed = {p["display_name"]: p["is_confirmed"] for p in body["participants"]}
    assert confirmed == {"測試玩家": False, "玩家乙": True, "玩家丙": False, "Amy": False}


def test_participant_who_is_not_creator_can_record_result(api, started: str):
    assert put_result(api, PLAYER_C, started, result_body()).status_code == 200


@pytest.mark.parametrize("bad", ["ghost", "Rose", ""])
def test_winning_faction_must_be_valid(api, started: str, bad: str):
    response = put_result(api, TEST_PLAYER, started, result_body(bad))
    assert response.status_code == 422
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"


def test_participant_faction_must_be_valid(api, started: str):
    factions = {1: "rose", 2: "ghost", 3: "blood_blade", 4: "blood_blade"}
    response = put_result(api, TEST_PLAYER, started, result_body(factions=factions))
    assert response.status_code == 422
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"


def test_result_missing_seats_lists_them(api, started: str):
    factions = {1: "rose", 2: "rose", 3: "blood_blade"}  # 這局有座位 1–4，缺 4
    response = put_result(api, TEST_PLAYER, started, result_body(factions=factions))
    assert (response.status_code, error_code(response)) == (422, "MATCH_RESULT_SEATS_INCOMPLETE")
    assert response.json()["error"]["details"]["missing_seat_numbers"] == [4]
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"


def test_result_with_unknown_seat_is_rejected(api, started: str):
    factions = {1: "rose", 2: "rose", 3: "blood_blade", 4: "blood_blade", 5: "rose"}
    response = put_result(api, TEST_PLAYER, started, result_body(factions=factions))
    assert (response.status_code, error_code(response)) == (422, "MATCH_SEAT_NOT_FOUND")
    assert response.json()["error"]["details"]["seat_numbers"] == [5]
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"


def test_result_with_duplicate_seat_is_rejected(api, started: str):
    body = result_body()
    body["participants"].append({"seat_number": 1, "faction": "blood_blade"})
    response = put_result(api, TEST_PLAYER, started, body)
    assert (response.status_code, error_code(response)) == (422, "VALIDATION_ERROR")
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"


@pytest.mark.parametrize("extra", [{"is_winner": True}, {"score": 3}])
def test_result_does_not_accept_winner_or_score(api, started: str, extra: dict[str, Any]):
    body = result_body()
    body["participants"][0].update(extra)
    assert put_result(api, TEST_PLAYER, started, body).status_code == 422


def test_non_participant_cannot_record_result(api, started: str):
    assert put_result(api, OUTSIDER, started, result_body()).status_code == 403
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"


def test_duplicate_result_is_conflict_and_old_result_is_kept(api, started: str):
    put_result(api, TEST_PLAYER, started, result_body("rose"))
    response = put_result(api, PLAYER_B, started, result_body("blood_blade"))
    assert (response.status_code, error_code(response)) == (409, "MATCH_RESULT_ALREADY_RECORDED")
    assert get(api, TEST_PLAYER, started)["result"]["winning_faction"] == "rose"


def test_overwriting_result_clears_other_confirmations(api, started: str):
    put_result(api, TEST_PLAYER, started, result_body("rose"))
    mine = participant_named(get(api, PLAYER_C, started), "玩家丙")
    api(
        PLAYER_C,
        "PATCH",
        f"{BASE}/{started}/participants/{mine['id']}",
        json={"is_confirmed": True},
    )
    response = put_result(api, PLAYER_B, started, result_body("blood_blade"), overwrite=True)
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["winning_faction"] == "blood_blade"
    confirmed = {p["display_name"]: p["is_confirmed"] for p in body["participants"]}
    assert confirmed == {"測試玩家": False, "玩家乙": True, "玩家丙": False, "Amy": False}
    assert body["is_valid"] is False


def test_admin_overwrite_leaves_nobody_confirmed(api, started: str):
    put_result(api, TEST_PLAYER, started, result_body("rose"))
    response = put_result(api, TEST_ADMIN, started, result_body("blood_blade"), overwrite=True)
    assert response.status_code == 200
    assert not any(p["is_confirmed"] for p in response.json()["participants"])


def test_result_type_empty_is_conflict_but_turns_still_work(
    api, started: str, white_rose_id: int, set_result_type
):
    set_result_type(white_rose_id, None)
    response = put_result(api, TEST_PLAYER, started, result_body())
    assert (response.status_code, error_code(response)) == (409, "MATCH_GAME_RESULT_TYPE_NOT_SET")
    assert get(api, TEST_PLAYER, started)["status"] == "in_progress"
    assert post_turn(api, TEST_PLAYER, started, turn_body()).status_code == 201


@pytest.mark.parametrize("result_type", ["score", "cooperative"])
def test_other_result_types_are_not_supported_yet(
    api, started: str, white_rose_id: int, set_result_type, result_type: str
):
    set_result_type(white_rose_id, result_type)
    response = put_result(api, TEST_PLAYER, started, result_body())
    assert (response.status_code, error_code(response)) == (
        422,
        "MATCH_RESULT_TYPE_NOT_SUPPORTED",
    )


def test_result_for_missing_match(api, started: str):
    response = put_result(api, TEST_PLAYER, str(uuid.uuid4()), result_body())
    assert (response.status_code, error_code(response)) == (404, "MATCH_NOT_FOUND")
