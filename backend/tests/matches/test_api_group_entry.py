"""從揪團進入戰局：帶 group_id 開局會自動加入揪團的正式成員（連 `_test` 資料庫）。

權限：帶 group_id 開局只有該揪團的開團主、正式成員與管理員可以，其他人 403。
"""

import uuid

from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_STAFF
from tests.matches.conftest import OUTSIDER, PLAYER_B, PLAYER_C
from tests.matches.support import BASE, error_code, match_body


def seats(match: dict) -> dict[str, int]:
    return {p["display_name"]: p["seat_number"] for p in match["participants"]}


def create(api, user, game_id: int, group_id, **overrides):
    body = match_body(game_id, group_id=str(group_id), **overrides)
    return api(user, "POST", BASE, json=body)


def test_members_are_added_with_seats_in_order_of_joining(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B, PLAYER_C])
    response = create(api, TEST_PLAYER, white_rose_id, group_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["group_id"] == str(group_id)
    assert seats(body) == {"測試玩家": 1, "玩家乙": 2, "玩家丙": 3}
    assert (body["participant_count"], body["account_count"], body["confirmed_count"]) == (3, 3, 0)
    assert {p["user_id"] for p in body["participants"]} == {
        str(TEST_PLAYER.id),
        str(PLAYER_B.id),
        str(PLAYER_C.id),
    }


def test_waitlisted_users_are_not_added(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B], waitlisted=[PLAYER_C])
    response = create(api, TEST_PLAYER, white_rose_id, group_id)
    assert seats(response.json()) == {"測試玩家": 1, "玩家乙": 2}


def test_seat_order_follows_joining_order(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_C, PLAYER_B])
    response = create(api, TEST_PLAYER, white_rose_id, group_id)
    assert seats(response.json()) == {"測試玩家": 1, "玩家丙": 2, "玩家乙": 3}


def test_creator_keeps_chosen_seat_others_take_lowest_free(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B, PLAYER_C])
    response = create(api, TEST_PLAYER, white_rose_id, group_id, seat_number=2)
    assert seats(response.json()) == {"測試玩家": 2, "玩家乙": 1, "玩家丙": 3}


def test_member_who_is_not_organizer_can_create(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B, PLAYER_C])
    response = create(api, PLAYER_B, white_rose_id, group_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_by"]["id"] == str(PLAYER_B.id)
    assert seats(body) == {"玩家乙": 1, "測試玩家": 2, "玩家丙": 3}
    assert [p["user_id"] for p in body["participants"]].count(str(PLAYER_B.id)) == 1


def test_admin_not_in_group_can_create_and_gets_all_members(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B])
    response = create(api, TEST_ADMIN, white_rose_id, group_id)
    assert response.status_code == 201, response.text
    assert seats(response.json()) == {"測試管理員": 1, "測試玩家": 2, "玩家乙": 3}


def test_non_member_gets_403_and_no_match_is_created(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B])
    response = create(api, OUTSIDER, white_rose_id, group_id)
    assert response.status_code == 403
    assert api(TEST_ADMIN, "GET", BASE, params={"group_id": str(group_id)}).json()["total"] == 0


def test_waitlisted_user_gets_403(api, white_rose_id, add_group):
    group_id = add_group(waitlisted=[PLAYER_C])
    assert create(api, PLAYER_C, white_rose_id, group_id).status_code == 403


def test_shop_staff_not_in_group_gets_403(api, white_rose_id, add_group):
    group_id = add_group()
    assert create(api, TEST_SHOP_STAFF, white_rose_id, group_id).status_code == 403


def test_unknown_group_is_404(api, white_rose_id):
    response = create(api, TEST_PLAYER, white_rose_id, uuid.uuid4())
    assert (response.status_code, error_code(response)) == (404, "MATCH_GROUP_NOT_FOUND")


def test_without_group_id_only_creator_joins(api, white_rose_id, add_group):
    add_group(members=[PLAYER_B, PLAYER_C])
    response = api(TEST_PLAYER, "POST", BASE, json=match_body(white_rose_id))
    assert response.status_code == 201
    assert seats(response.json()) == {"測試玩家": 1}


def test_auto_added_member_can_be_removed_later(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B, PLAYER_C])
    match = create(api, TEST_PLAYER, white_rose_id, group_id).json()
    target = next(p for p in match["participants"] if p["display_name"] == "玩家丙")
    removed = api(TEST_PLAYER, "DELETE", f"{BASE}/{match['id']}/participants/{target['id']}")
    assert removed.status_code == 204
    after = api(TEST_PLAYER, "GET", f"{BASE}/{match['id']}").json()
    assert seats(after) == {"測試玩家": 1, "玩家乙": 2}


def test_group_matches_can_be_listed_by_group(api, white_rose_id, add_group):
    group_id = add_group(members=[PLAYER_B])
    create(api, TEST_PLAYER, white_rose_id, group_id)
    api(TEST_PLAYER, "POST", BASE, json=match_body(white_rose_id))
    listed = api(PLAYER_B, "GET", BASE, params={"group_id": str(group_id)}).json()
    assert listed["total"] == 1
