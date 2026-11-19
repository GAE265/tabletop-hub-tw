"""白薔薇回合的「本回合首家」是選填：不帶 seat_number 也能記錄（欄位可為空）。"""

from tests.conftest import TEST_PLAYER
from tests.matches.conftest import PLAYER_B
from tests.matches.support import BASE, game_data, participant_named, turn_body


def turn_without_first_seat(turn_number: int = 1, **overrides) -> dict:
    return {"turn_number": turn_number, "game_data": game_data(**overrides)}


def post_turn(api, user, match_id: str, body: dict, overwrite: bool = False):
    params = {"overwrite": "true"} if overwrite else None
    return api(user, "POST", f"{BASE}/{match_id}/turns", json=body, params=params)


def test_turn_without_first_seat_is_recorded(api, started: str):
    response = post_turn(api, PLAYER_B, started, turn_without_first_seat())
    assert response.status_code == 201, response.text
    assert response.json()["seat_number"] is None
    [turn] = api(TEST_PLAYER, "GET", f"{BASE}/{started}").json()["turns"]
    assert turn["seat_number"] is None
    assert turn["game_data"]["played_seat_numbers"] == [1, 2]


def test_turn_with_explicit_null_first_seat_is_recorded(api, started: str):
    body = {**turn_without_first_seat(), "seat_number": None}
    assert post_turn(api, TEST_PLAYER, started, body).status_code == 201


def test_turn_with_first_seat_still_works(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, turn_body(1, 3))
    assert (response.status_code, response.json()["seat_number"]) == (201, 3)


def test_unknown_first_seat_is_still_rejected(api, started: str):
    assert post_turn(api, TEST_PLAYER, started, turn_body(1, 9)).status_code == 422


def test_zero_first_seat_is_rejected(api, started: str):
    body = {**turn_without_first_seat(), "seat_number": 0}
    assert post_turn(api, TEST_PLAYER, started, body).status_code == 422


def test_overwrite_can_clear_first_seat(api, started: str):
    post_turn(api, TEST_PLAYER, started, turn_body(1, 1))
    response = post_turn(api, TEST_PLAYER, started, turn_without_first_seat(), overwrite=True)
    assert (response.status_code, response.json()["seat_number"]) == (200, None)


def test_duplicate_turn_conflict_shows_empty_first_seat(api, started: str):
    post_turn(api, TEST_PLAYER, started, turn_without_first_seat())
    response = post_turn(api, PLAYER_B, started, turn_body(1, 2))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["existing"]["seat_number"] is None


def test_seat_that_did_not_play_can_be_removed_when_first_seat_is_empty(api, started: str):
    """Amy 座位 4 沒有出牌，首家為空的回合不會擋住移除。"""
    post_turn(api, TEST_PLAYER, started, turn_without_first_seat())
    match = api(TEST_PLAYER, "GET", f"{BASE}/{started}").json()
    amy = participant_named(match, "Amy")
    removed = api(TEST_PLAYER, "DELETE", f"{BASE}/{started}/participants/{amy['id']}")
    assert removed.status_code == 204
