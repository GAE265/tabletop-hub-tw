"""白薔薇回合：整桌都不出牌的回合（played_seat_numbers 可以是空的）、司教（has_cardinal），
以及跨回合的規則：一局只有一朵白薔薇、一位司教。"""

import pytest

from tests.conftest import TEST_PLAYER
from tests.matches.conftest import OUTSIDER, PLAYER_B
from tests.matches.support import BASE, error_code, match_body, turn_body

# 這回合什麼都沒發生：五個計數都是 0、兩個開關都是 false
NOTHING_HAPPENED = {
    "double_blade_count": 0,
    "dark_blade_count": 0,
    "giant_blade_count": 0,
    "faithful_count": 0,
    "has_white_rose": False,
    "has_cardinal": False,
}


def empty_turn(turn_number: int = 1, **overrides) -> dict:
    """整桌都不出牌的回合；overrides 可以把某個計數或開關打開。"""
    return turn_body(turn_number, 1, played_seat_numbers=[], **{**NOTHING_HAPPENED, **overrides})


def post_turn(api, user, match_id: str, body: dict):
    return api(user, "POST", f"{BASE}/{match_id}/turns", json=body)


def turns_of(api, match_id: str) -> list[dict]:
    return api(TEST_PLAYER, "GET", f"{BASE}/{match_id}").json()["turns"]


# --- 整桌都不出牌 ---


def test_turn_where_nobody_plays_is_recorded(api, started: str):
    response = post_turn(api, TEST_PLAYER, started, empty_turn())
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
    response = post_turn(api, OUTSIDER, started, empty_turn())
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


# --- 有記錄到牌，就一定要選出牌座位 ---


@pytest.mark.parametrize(
    "happened",
    [
        {"double_blade_count": 2},
        {"dark_blade_count": 1},
        {"giant_blade_count": 1},
        {"faithful_count": 1},
        {"has_white_rose": True},
        {"has_cardinal": True},
    ],
    ids=["double-blade", "dark-blade", "giant-blade", "faithful", "white-rose", "cardinal"],
)
def test_something_happened_requires_played_seats(api, started: str, happened: dict):
    response = post_turn(api, TEST_PLAYER, started, empty_turn(**happened))
    assert (response.status_code, error_code(response)) == (422, "VALIDATION_ERROR")
    assert "請選出牌的座位" in response.text
    assert turns_of(api, started) == []


# --- 一局只有一朵白薔薇、一位司教 ---


ONCE_PER_MATCH = [
    ("has_white_rose", "MATCH_WHITE_ROSE_ALREADY_RECORDED"),
    ("has_cardinal", "MATCH_CARDINAL_ALREADY_RECORDED"),
]
ONCE_IDS = ["white-rose", "cardinal"]


@pytest.mark.parametrize(("field", "code"), ONCE_PER_MATCH, ids=ONCE_IDS)
def test_second_turn_with_same_unique_card_is_conflict(api, started: str, field: str, code: str):
    assert post_turn(api, TEST_PLAYER, started, turn_body(3, 1, **{field: True})).status_code == 201
    response = post_turn(api, PLAYER_B, started, turn_body(5, 2, **{field: True}))
    assert (response.status_code, error_code(response)) == (409, code)
    assert response.json()["error"]["details"]["turn_numbers"] == [3]
    assert [t["turn_number"] for t in turns_of(api, started)] == [3]


@pytest.mark.parametrize(("field", "code"), ONCE_PER_MATCH, ids=ONCE_IDS)
def test_overwrite_into_another_turn_is_still_conflict(api, started: str, field: str, code: str):
    post_turn(api, TEST_PLAYER, started, turn_body(3, 1, **{field: True}))
    post_turn(api, TEST_PLAYER, started, turn_body(5, 1))
    response = api(
        TEST_PLAYER,
        "POST",
        f"{BASE}/{started}/turns",
        json=turn_body(5, 1, **{field: True}),
        params={"overwrite": "true"},
    )
    assert (response.status_code, error_code(response)) == (409, code)


@pytest.mark.parametrize(("field", "code"), ONCE_PER_MATCH, ids=ONCE_IDS)
def test_overwriting_the_same_turn_can_keep_the_unique_card(
    api, started: str, field: str, code: str
):
    """編輯（覆蓋）原本就記了白薔薇／司教的那一回合，不算第二次。"""
    post_turn(api, TEST_PLAYER, started, turn_body(3, 1, **{field: True}))
    response = api(
        TEST_PLAYER,
        "POST",
        f"{BASE}/{started}/turns",
        json=turn_body(3, 2, **{field: True}),
        params={"overwrite": "true"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["game_data"][field] is True


def test_unique_cards_can_appear_in_different_turns_once_each(api, started: str):
    assert (
        post_turn(api, TEST_PLAYER, started, turn_body(1, 1, has_white_rose=True)).status_code
        == 201
    )
    assert (
        post_turn(api, TEST_PLAYER, started, turn_body(2, 1, has_cardinal=True)).status_code == 201
    )


@pytest.mark.parametrize(("field", "code"), ONCE_PER_MATCH, ids=ONCE_IDS)
def test_other_match_is_not_affected(api, started: str, white_rose_id: int, field: str, code: str):
    post_turn(api, TEST_PLAYER, started, turn_body(1, 1, **{field: True}))
    other = api(TEST_PLAYER, "POST", BASE, json=match_body(white_rose_id)).json()["id"]
    response = post_turn(
        api, TEST_PLAYER, other, turn_body(1, 1, played_seat_numbers=[1], **{field: True})
    )
    assert response.status_code == 201, response.text
