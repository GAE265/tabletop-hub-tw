"""白薔薇回合：整桌都不出牌的回合（played_seat_numbers 可以是空的），以及司教（has_cardinal）。"""

from tests.conftest import TEST_PLAYER
from tests.matches.conftest import OUTSIDER
from tests.matches.support import BASE, error_code, turn_body


def post_turn(api, user, match_id: str, body: dict):
    return api(user, "POST", f"{BASE}/{match_id}/turns", json=body)


def turns_of(api, match_id: str) -> list[dict]:
    return api(TEST_PLAYER, "GET", f"{BASE}/{match_id}").json()["turns"]


# --- 整桌都不出牌 ---


def test_turn_where_nobody_plays_is_recorded(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 1, played_seat_numbers=[]))
    assert response.status_code == 201, response.text
    assert response.json()["game_data"]["played_seat_numbers"] == []
    [turn] = turns_of(api, started)
    assert turn["game_data"]["played_seat_numbers"] == []


def test_duplicate_played_seats_are_still_rejected(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 1, played_seat_numbers=[1, 1]))
    assert response.status_code == 422
    assert turns_of(api, started) == []


def test_played_seat_not_in_match_is_still_rejected(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 1, played_seat_numbers=[99]))
    assert (response.status_code, error_code(response)) == (422, "MATCH_SEAT_NOT_FOUND")


def test_non_participant_cannot_record_turn_where_nobody_plays(api, started: str):
    response = post_turn(api, OUTSIDER, started, turn_body(1, 1, played_seat_numbers=[]))
    assert response.status_code == 403
    assert turns_of(api, started) == []


# --- 司教 ---


def test_turn_with_cardinal_is_recorded(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 1, has_cardinal=True))
    assert response.status_code == 201, response.text
    assert response.json()["game_data"]["has_cardinal"] is True
    [turn] = turns_of(api, started)
    assert turn["game_data"]["has_cardinal"] is True


def test_has_cardinal_defaults_to_false_when_omitted(api, started: str):
    """舊紀錄與舊版前端不帶 has_cardinal，仍要能記錄，預設沒有司教。"""
    body = turn_body(1, 1)
    del body["game_data"]["has_cardinal"]
    response = post_turn(api, TEST_PLAYER, started, body)
    assert response.status_code == 201, response.text
    assert response.json()["game_data"]["has_cardinal"] is False


def test_has_cardinal_must_be_a_boolean(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 1, has_cardinal="yes"))
    assert response.status_code == 422
    assert turns_of(api, started) == []
