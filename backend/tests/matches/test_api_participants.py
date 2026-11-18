"""matches API 測試：加入參加者、確認、移除參加者。連 `_test` 資料庫。

情境對應 openspec/changes/add-matches-record/specs/matches-record/spec.md
「加入參加者」「確認紀錄」「移除參加者」。
"""

import uuid

import pytest

from tests.conftest import TEST_ADMIN, TEST_PLAYER
from tests.matches.conftest import OUTSIDER, PLAYER_B, PLAYER_C
from tests.matches.support import (
    BASE,
    error_code,
    match_body,
    participant_named,
    result_body,
    turn_body,
)


def get(api, user, match_id: str) -> dict:
    return api(user, "GET", f"{BASE}/{match_id}").json()


def finish(api, match_id: str, user=TEST_PLAYER) -> None:
    response = api(user, "PUT", f"{BASE}/{match_id}/result", json=result_body())
    assert response.status_code == 200, response.text


# --- 加入參加者 ---


def test_player_joins_self(api, started: str):
    response = api(OUTSIDER, "POST", f"{BASE}/{started}/participants", json={})
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["user_id"] == str(OUTSIDER.id)
    assert body["display_name"] == "路人"
    assert body["seat_number"] == 5  # 1–4 已被占用，使用最小的空位
    assert body["is_confirmed"] is False


def test_player_joins_with_chosen_seat(api, white_rose_id: int):
    match_id = api(TEST_PLAYER, "POST", BASE, json=match_body(white_rose_id)).json()["id"]
    response = api(PLAYER_B, "POST", f"{BASE}/{match_id}/participants", json={"seat_number": 3})
    assert response.status_code == 201
    assert response.json()["seat_number"] == 3


def test_participant_adds_participant_without_account(api, started: str):
    response = api(
        PLAYER_B,
        "POST",
        f"{BASE}/{started}/participants",
        json={"display_name": "Bob", "seat_number": 6},
    )
    assert response.status_code == 201
    body = response.json()
    assert (body["display_name"], body["user_id"], body["seat_number"]) == ("Bob", None, 6)


def test_same_name_is_not_bound_to_account(api, started: str):
    response = api(
        TEST_PLAYER, "POST", f"{BASE}/{started}/participants", json={"display_name": "玩家乙"}
    )
    assert response.status_code == 201
    assert response.json()["user_id"] is None
    assert get(api, TEST_PLAYER, started)["account_count"] == 3


def test_taken_seat_is_conflict(api, started: str):
    response = api(OUTSIDER, "POST", f"{BASE}/{started}/participants", json={"seat_number": 2})
    assert (response.status_code, error_code(response)) == (409, "MATCH_SEAT_TAKEN")


def test_joining_twice_is_conflict(api, started: str):
    response = api(PLAYER_B, "POST", f"{BASE}/{started}/participants", json={})
    assert (response.status_code, error_code(response)) == (409, "MATCH_ALREADY_JOINED")


def test_non_participant_cannot_add_participant_without_account(api, started: str):
    response = api(OUTSIDER, "POST", f"{BASE}/{started}/participants", json={"display_name": "Bob"})
    assert response.status_code == 403
    assert get(api, TEST_PLAYER, started)["participant_count"] == 4


def test_admin_can_add_participant_without_account(api, started: str):
    response = api(
        TEST_ADMIN, "POST", f"{BASE}/{started}/participants", json={"display_name": "Bob"}
    )
    assert response.status_code == 201


def test_user_id_in_body_is_rejected(api, started: str):
    response = api(
        OUTSIDER, "POST", f"{BASE}/{started}/participants", json={"user_id": str(PLAYER_C.id)}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [{"display_name": ""}, {"display_name": "   "}, {"seat_number": 0}, {"seat_number": -2}],
)
def test_invalid_participant_body(api, started: str, body: dict):
    response = api(TEST_PLAYER, "POST", f"{BASE}/{started}/participants", json=body)
    assert response.status_code == 422


def test_cannot_join_finished_match(api, started: str):
    finish(api, started)
    response = api(OUTSIDER, "POST", f"{BASE}/{started}/participants", json={})
    assert (response.status_code, error_code(response)) == (409, "MATCH_FINISHED")


def test_add_participant_to_missing_match(api, started: str):
    response = api(OUTSIDER, "POST", f"{BASE}/{uuid.uuid4()}/participants", json={})
    assert (response.status_code, error_code(response)) == (404, "MATCH_NOT_FOUND")


# --- 確認 ---


def confirm(api, user, match_id: str, participant_id: str, value: object = True):
    return api(
        user,
        "PATCH",
        f"{BASE}/{match_id}/participants/{participant_id}",
        json={"is_confirmed": value},
    )


def test_participant_confirms(api, started: str):
    finish(api, started)
    mine = participant_named(get(api, PLAYER_B, started), "玩家乙")
    response = confirm(api, PLAYER_B, started, mine["id"])
    assert response.status_code == 200
    assert response.json()["is_confirmed"] is True
    assert get(api, PLAYER_B, started)["confirmed_count"] == 2


def test_everyone_with_account_confirming_makes_match_valid(api, started: str):
    finish(api, started)
    for user, name in ((PLAYER_B, "玩家乙"), (PLAYER_C, "玩家丙")):
        mine = participant_named(get(api, user, started), name)
        assert confirm(api, user, started, mine["id"]).status_code == 200
    body = get(api, OUTSIDER, started)
    assert (body["account_count"], body["confirmed_count"]) == (3, 3)
    assert body["is_valid"] is True  # 沒有帳號的 Amy 不影響


def test_confirming_again_changes_nothing(api, started: str):
    finish(api, started)
    mine = participant_named(get(api, PLAYER_B, started), "玩家乙")
    confirm(api, PLAYER_B, started, mine["id"])
    again = confirm(api, PLAYER_B, started, mine["id"])
    assert again.status_code == 200
    assert get(api, PLAYER_B, started)["confirmed_count"] == 2


def test_non_participant_cannot_confirm(api, started: str):
    finish(api, started)
    theirs = participant_named(get(api, PLAYER_B, started), "玩家乙")
    assert confirm(api, OUTSIDER, started, theirs["id"]).status_code == 403


def test_cannot_confirm_for_someone_else(api, started: str):
    finish(api, started)
    theirs = participant_named(get(api, PLAYER_B, started), "玩家丙")
    assert confirm(api, PLAYER_B, started, theirs["id"]).status_code == 403
    assert participant_named(get(api, PLAYER_C, started), "玩家丙")["is_confirmed"] is False


def test_participant_without_account_cannot_be_confirmed(api, started: str):
    finish(api, started)
    amy = participant_named(get(api, TEST_PLAYER, started), "Amy")
    assert confirm(api, TEST_PLAYER, started, amy["id"]).status_code == 403


def test_cannot_confirm_before_result(api, started: str):
    mine = participant_named(get(api, PLAYER_B, started), "玩家乙")
    response = confirm(api, PLAYER_B, started, mine["id"])
    assert (response.status_code, error_code(response)) == (409, "MATCH_RESULT_NOT_RECORDED")


def test_cancelling_confirmation_is_rejected(api, started: str):
    finish(api, started)
    mine = participant_named(get(api, PLAYER_B, started), "玩家乙")
    assert confirm(api, PLAYER_B, started, mine["id"], value=False).status_code == 422


def test_confirm_unknown_participant(api, started: str):
    finish(api, started)
    response = confirm(api, PLAYER_B, started, str(uuid.uuid4()))
    assert (response.status_code, error_code(response)) == (404, "MATCH_PARTICIPANT_NOT_FOUND")


def test_participant_of_another_match_is_not_found(api, started: str, white_rose_id: int):
    finish(api, started)
    other = api(PLAYER_B, "POST", BASE, json=match_body(white_rose_id)).json()
    response = confirm(api, PLAYER_B, started, other["participants"][0]["id"])
    assert (response.status_code, error_code(response)) == (404, "MATCH_PARTICIPANT_NOT_FOUND")


# --- 移除參加者 ---


def remove(api, user, match_id: str, participant_id: str):
    return api(user, "DELETE", f"{BASE}/{match_id}/participants/{participant_id}")


def test_participant_can_quit(api, started: str):
    mine = participant_named(get(api, PLAYER_B, started), "玩家乙")
    response = remove(api, PLAYER_B, started, mine["id"])
    assert response.status_code == 204
    body = get(api, TEST_PLAYER, started)
    assert (body["participant_count"], body["account_count"]) == (3, 2)
    assert all(p["display_name"] != "玩家乙" for p in body["participants"])


def test_participant_removes_participant_without_account(api, started: str):
    amy = participant_named(get(api, PLAYER_B, started), "Amy")
    assert remove(api, PLAYER_B, started, amy["id"]).status_code == 204
    body = get(api, TEST_PLAYER, started)
    assert (body["participant_count"], body["account_count"]) == (3, 3)


def test_participant_removes_another_account_participant(api, started: str):
    theirs = participant_named(get(api, PLAYER_B, started), "玩家丙")
    assert remove(api, PLAYER_B, started, theirs["id"]).status_code == 204
    assert get(api, TEST_PLAYER, started)["account_count"] == 2


def test_removed_seat_can_be_used_again(api, started: str):
    mine = participant_named(get(api, PLAYER_B, started), "玩家乙")
    remove(api, PLAYER_B, started, mine["id"])
    response = api(OUTSIDER, "POST", f"{BASE}/{started}/participants", json={"seat_number": 2})
    assert response.status_code == 201


def test_non_participant_cannot_remove(api, started: str):
    theirs = participant_named(get(api, PLAYER_B, started), "玩家乙")
    assert remove(api, OUTSIDER, started, theirs["id"]).status_code == 403
    assert get(api, TEST_PLAYER, started)["participant_count"] == 4


def test_admin_can_remove(api, started: str):
    theirs = participant_named(get(api, PLAYER_B, started), "玩家乙")
    assert remove(api, TEST_ADMIN, started, theirs["id"]).status_code == 204


def test_cannot_remove_from_finished_match(api, started: str):
    finish(api, started)
    theirs = participant_named(get(api, PLAYER_B, started), "玩家乙")
    response = remove(api, TEST_PLAYER, started, theirs["id"])
    assert (response.status_code, error_code(response)) == (409, "MATCH_FINISHED")
    assert get(api, TEST_PLAYER, started)["participant_count"] == 4


def test_cannot_remove_seat_that_led_a_turn(api, started: str):
    api(
        TEST_PLAYER,
        "POST",
        f"{BASE}/{started}/turns",
        json=turn_body(1, 2, played_seat_numbers=[1]),
    )
    theirs = participant_named(get(api, PLAYER_B, started), "玩家乙")
    response = remove(api, TEST_PLAYER, started, theirs["id"])
    assert (response.status_code, error_code(response)) == (409, "MATCH_PARTICIPANT_HAS_TURNS")
    details = response.json()["error"]["details"]
    assert details["seat_number"] == 2
    assert details["turn_numbers"] == [1]
    assert get(api, TEST_PLAYER, started)["participant_count"] == 4


def test_cannot_remove_seat_that_played_in_a_turn(api, started: str):
    api(
        TEST_PLAYER,
        "POST",
        f"{BASE}/{started}/turns",
        json=turn_body(1, 1, played_seat_numbers=[1, 3]),
    )
    theirs = participant_named(get(api, PLAYER_B, started), "玩家丙")
    response = remove(api, TEST_PLAYER, started, theirs["id"])
    assert (response.status_code, error_code(response)) == (409, "MATCH_PARTICIPANT_HAS_TURNS")


def test_seat_not_used_by_any_turn_can_be_removed(api, started: str):
    api(
        TEST_PLAYER,
        "POST",
        f"{BASE}/{started}/turns",
        json=turn_body(1, 1, played_seat_numbers=[1, 2]),
    )
    amy = participant_named(get(api, TEST_PLAYER, started), "Amy")  # 座位 4 沒有出現在任何回合
    assert remove(api, TEST_PLAYER, started, amy["id"]).status_code == 204


def test_remove_unknown_participant(api, started: str):
    response = remove(api, TEST_PLAYER, started, str(uuid.uuid4()))
    assert (response.status_code, error_code(response)) == (404, "MATCH_PARTICIPANT_NOT_FOUND")
