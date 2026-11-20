"""shops API 測試：打真實端點與資料庫。

權限一律以資料庫（auth_users.shop_id）為準；標頭或 CurrentUser 帶的店家不算。
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF
from tests.shops.conftest import NEW_STAFF, OTHER_SHOP_ID

SHOPS = "/api/v1/shops"


def games_url(shop_id: uuid.UUID, game_id: int | None = None) -> str:
    base = f"{SHOPS}/{shop_id}/games"
    return base if game_id is None else f"{base}/{game_id}"


def code(response) -> str:
    return response.json()["error"]["code"]


def user_shop_id(db: Engine, user_id: uuid.UUID) -> uuid.UUID | None:
    with db.connect() as conn:
        return conn.scalar(text("SELECT shop_id FROM auth_users WHERE id = :i"), {"i": user_id})


def shop_count(db: Engine) -> int:
    with db.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM booking_shops"))


# --- 新增店家：POST /api/v1/shops ---


def test_new_staff_creates_shop_and_is_bound(client: TestClient, act_as, db: Engine):
    act_as(NEW_STAFF)
    response = client.post(
        SHOPS, json={"name": "新桌遊店", "phone": "0912345678", "address": "台北"}
    )
    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["phone"], body["address"]) == ("新桌遊店", "0912345678", "台北")
    assert user_shop_id(db, NEW_STAFF.id) == uuid.UUID(body["id"])


def test_phone_and_address_are_optional(client: TestClient, act_as):
    act_as(NEW_STAFF)
    response = client.post(SHOPS, json={"name": "新桌遊店"})
    assert response.status_code == 201
    assert response.json()["phone"] is None
    assert response.json()["address"] is None


def test_new_shop_can_be_managed_right_away_with_same_identity(
    client: TestClient, act_as, add_game
):
    """新增後身分（標頭）不會更新，仍要能立刻管理新店的庫存。"""
    act_as(NEW_STAFF)
    shop_id = uuid.UUID(client.post(SHOPS, json={"name": "新桌遊店"}).json()["id"])
    game_id = add_game()
    assert client.get(games_url(shop_id)).status_code == 200
    assert client.post(games_url(shop_id), json={"game_id": game_id}).status_code == 201


def test_staff_with_shop_cannot_create(client: TestClient, as_shop_staff, db: Engine):
    before = shop_count(db)
    response = client.post(SHOPS, json={"name": "第二間"})
    assert response.status_code == 409
    assert code(response) == "SHOP_STAFF_ALREADY_HAS_SHOP"
    assert shop_count(db) == before
    assert user_shop_id(db, TEST_SHOP_STAFF.id) == TEST_SHOP_ID


def test_admin_creates_without_binding(client: TestClient, as_admin, db: Engine):
    response = client.post(SHOPS, json={"name": "管理員開的店"})
    assert response.status_code == 201
    assert user_shop_id(db, TEST_ADMIN.id) is None


def test_player_cannot_create(client: TestClient, as_player, db: Engine):
    before = shop_count(db)
    response = client.post(SHOPS, json={"name": "玩家開的店"})
    assert response.status_code == 403
    assert shop_count(db) == before


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "   "}, {"phone": "0912345678"}])
def test_name_is_required(client: TestClient, act_as, body: dict):
    act_as(NEW_STAFF)
    response = client.post(SHOPS, json=body)
    assert response.status_code == 422
    assert code(response) == "VALIDATION_ERROR"


def test_unauthenticated_create_is_401(jwt_client: TestClient):
    response = jwt_client.post(SHOPS, json={"name": "新桌遊店"})
    assert response.status_code == 401


def test_dev_header_without_shop_can_create(client: TestClient, db: Engine):
    """開發標頭：還沒有店的店員只帶 `<user>:shop_staff`，經過真正的身分解析也能新增。"""
    response = client.post(
        SHOPS, json={"name": "新桌遊店"}, headers={"X-Dev-User": f"{NEW_STAFF.id}:shop_staff"}
    )
    assert response.status_code == 201
    assert user_shop_id(db, NEW_STAFF.id) == uuid.UUID(response.json()["id"])


# --- 庫存：列出 GET /api/v1/shops/{shop_id}/games ---


def test_staff_lists_own_inventory(client: TestClient, as_shop_staff, add_game, stock):
    game_id = add_game("卡坦島")
    stock(TEST_SHOP_ID, game_id)
    response = client.get(games_url(TEST_SHOP_ID))
    assert response.status_code == 200
    assert response.json() == {"items": [{"game_id": game_id, "name": "卡坦島"}], "total": 1}


def test_empty_inventory(client: TestClient, as_shop_staff):
    response = client.get(games_url(TEST_SHOP_ID))
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_inventories_are_separate_per_shop(client: TestClient, as_admin, add_game, stock):
    mine, theirs = add_game("甲店的"), add_game("乙店的")
    stock(TEST_SHOP_ID, mine)
    stock(OTHER_SHOP_ID, theirs)
    assert [i["game_id"] for i in client.get(games_url(TEST_SHOP_ID)).json()["items"]] == [mine]
    assert [i["game_id"] for i in client.get(games_url(OTHER_SHOP_ID)).json()["items"]] == [theirs]


# --- 庫存：加入 POST /api/v1/shops/{shop_id}/games ---


def test_staff_adds_game(client: TestClient, as_shop_staff, add_game):
    game_id = add_game("卡坦島")
    response = client.post(games_url(TEST_SHOP_ID), json={"game_id": game_id})
    assert response.status_code == 201
    assert response.json() == {"game_id": game_id, "name": "卡坦島"}
    listed = client.get(games_url(TEST_SHOP_ID)).json()
    assert [i["game_id"] for i in listed["items"]] == [game_id]


def test_duplicate_game_is_409(client: TestClient, as_shop_staff, add_game, stock):
    game_id = add_game()
    stock(TEST_SHOP_ID, game_id)
    response = client.post(games_url(TEST_SHOP_ID), json={"game_id": game_id})
    assert response.status_code == 409
    assert code(response) == "SHOP_GAME_ALREADY_EXISTS"


def test_same_game_can_be_in_two_shops(client: TestClient, as_admin, add_game):
    game_id = add_game()
    assert client.post(games_url(TEST_SHOP_ID), json={"game_id": game_id}).status_code == 201
    assert client.post(games_url(OTHER_SHOP_ID), json={"game_id": game_id}).status_code == 201


def test_unknown_game_is_404(client: TestClient, as_shop_staff):
    response = client.post(games_url(TEST_SHOP_ID), json={"game_id": 999999})
    assert response.status_code == 404
    assert code(response) == "GAME_NOT_FOUND"


@pytest.mark.parametrize("body", [{}, {"game_id": "abc"}])
def test_add_needs_game_id(client: TestClient, as_shop_staff, body: dict):
    response = client.post(games_url(TEST_SHOP_ID), json=body)
    assert response.status_code == 422


# --- 庫存：移除 DELETE /api/v1/shops/{shop_id}/games/{game_id} ---


def test_staff_removes_game(client: TestClient, as_shop_staff, add_game, stock):
    game_id = add_game()
    stock(TEST_SHOP_ID, game_id)
    response = client.delete(games_url(TEST_SHOP_ID, game_id))
    assert response.status_code == 204
    assert client.get(games_url(TEST_SHOP_ID)).json()["total"] == 0


def test_removing_game_not_in_inventory_is_404(client: TestClient, as_shop_staff, add_game):
    response = client.delete(games_url(TEST_SHOP_ID, add_game()))
    assert response.status_code == 404
    assert code(response) == "SHOP_GAME_NOT_FOUND"


# --- 權限 ---


def operations(shop_id: uuid.UUID, game_id: int):
    return [
        ("get", games_url(shop_id), None),
        ("post", games_url(shop_id), {"game_id": game_id}),
        ("delete", games_url(shop_id, game_id), None),
    ]


def send(client: TestClient, method: str, url: str, body: dict | None):
    return (
        client.request(method, url, json=body) if body is not None else client.request(method, url)
    )


@pytest.mark.parametrize("index", [0, 1, 2])
def test_staff_cannot_touch_another_shop(client: TestClient, as_shop_staff, add_game, index: int):
    method, url, body = operations(OTHER_SHOP_ID, add_game())[index]
    assert send(client, method, url, body).status_code == 403


@pytest.mark.parametrize("index", [0, 1, 2])
def test_player_cannot_touch_inventory(client: TestClient, as_player, add_game, index: int):
    method, url, body = operations(TEST_SHOP_ID, add_game())[index]
    assert send(client, method, url, body).status_code == 403


def test_staff_without_shop_cannot_touch_inventory(client: TestClient, act_as):
    act_as(NEW_STAFF)
    assert client.get(games_url(TEST_SHOP_ID)).status_code == 403


def test_admin_manages_any_shop(client: TestClient, as_admin, add_game):
    game_id = add_game()
    assert client.post(games_url(OTHER_SHOP_ID), json={"game_id": game_id}).status_code == 201
    assert client.get(games_url(OTHER_SHOP_ID)).json()["total"] == 1
    assert client.delete(games_url(OTHER_SHOP_ID, game_id)).status_code == 204


def test_permission_follows_database_not_header(client: TestClient, act_as, add_game):
    """身分裡帶別間店，但資料庫是 TEST_SHOP_ID：管得了 TEST_SHOP_ID，管不了別間。"""
    from app.core.auth import CurrentUser

    act_as(CurrentUser(id=TEST_SHOP_STAFF.id, role="shop_staff", shop_id=OTHER_SHOP_ID))
    game_id = add_game()
    assert client.post(games_url(TEST_SHOP_ID), json={"game_id": game_id}).status_code == 201
    assert client.post(games_url(OTHER_SHOP_ID), json={"game_id": game_id}).status_code == 403


def test_unknown_shop_is_404(client: TestClient, as_admin):
    response = client.get(games_url(uuid.UUID("c0000000-0000-4000-8000-0000000000ff")))
    assert response.status_code == 404
    assert code(response) == "SHOP_NOT_FOUND"


def test_unauthenticated_inventory_is_401(jwt_client: TestClient):
    assert jwt_client.get(games_url(TEST_SHOP_ID)).status_code == 401


def test_player_default_identity_is_forbidden(client: TestClient):
    """沒帶標頭就是預設測試玩家，不是店員。"""
    assert client.get(games_url(TEST_SHOP_ID)).status_code == 403
    assert TEST_PLAYER.role == "player"
