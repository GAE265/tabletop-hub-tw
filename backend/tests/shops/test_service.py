"""shops service 的單元測試：使用手寫 fake，不連資料庫（AGENTS.md 7.5）。

權限一律以資料庫（auth_users.shop_id）為準，不看 CurrentUser.shop_id（標頭）。
"""

import uuid

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied

SHOP_A = uuid.UUID("c0000000-0000-4000-8000-00000000000a")
SHOP_B = uuid.UUID("c0000000-0000-4000-8000-00000000000b")
STAFF_A = CurrentUser(id=uuid.UUID("b0000000-0000-4000-8000-00000000000a"), role="shop_staff")
NEW_STAFF = CurrentUser(id=uuid.UUID("b0000000-0000-4000-8000-00000000000c"), role="shop_staff")
PLAYER = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000a"), role="player")
ADMIN = CurrentUser(id=uuid.UUID("d0000000-0000-4000-8000-00000000000a"), role="admin")

GAME_1, GAME_2 = 1, 2


@pytest.fixture
def world():
    from tests.shops.fakes import FakeAuthUsers, FakeBookingShops, FakeGames

    games = FakeGames()
    games.names = {GAME_1: "卡坦島", GAME_2: "狼人殺"}
    shops = FakeBookingShops()
    shops.shops = {
        SHOP_A: {"name": "甲店", "phone": None, "address": None},
        SHOP_B: {"name": "乙店", "phone": None, "address": None},
    }
    users = FakeAuthUsers()
    # 店員甲屬於甲店；新店員還沒有店
    users.shop_ids = {STAFF_A.id: SHOP_A, NEW_STAFF.id: None}
    return games, shops, users


@pytest.fixture
def service(world):
    from app.domains.shops.service import ShopsService
    from tests.shops.fakes import FakeShopGamesRepository

    games, shops, users = world
    return ShopsService(
        shop_games=FakeShopGamesRepository(games), shops=shops, users=users, games=games
    )


@pytest.fixture
def users(world):
    return world[2]


@pytest.fixture
def shops(world):
    return world[1]


def code_of(excinfo: pytest.ExceptionInfo[AppError]) -> str:
    return excinfo.value.code


# --- 新增店家 ---


def test_new_staff_creates_shop_and_is_bound(service, users, shops):
    created = service.create_shop(NEW_STAFF, name="丙店", phone="0912345678", address="台北市")
    assert created.name == "丙店"
    assert created.phone == "0912345678"
    assert created.address == "台北市"
    assert shops.shops[created.id]["name"] == "丙店"
    assert users.shop_ids[NEW_STAFF.id] == created.id


def test_staff_with_shop_cannot_create(service, users, shops):
    before = dict(shops.shops)
    with pytest.raises(AppError) as excinfo:
        service.create_shop(STAFF_A, name="丙店")
    assert excinfo.value.status_code == 409
    assert code_of(excinfo) == "SHOP_STAFF_ALREADY_HAS_SHOP"
    assert shops.shops == before
    assert users.shop_ids[STAFF_A.id] == SHOP_A


def test_staff_shop_in_header_is_ignored_when_database_says_no_shop(service, users):
    """標頭說有店、資料庫說沒有店：以資料庫為準，可以新增。"""
    stale = CurrentUser(id=NEW_STAFF.id, role="shop_staff", shop_id=SHOP_B)
    created = service.create_shop(stale, name="丙店")
    assert users.shop_ids[NEW_STAFF.id] == created.id


def test_admin_creates_without_binding(service, users, shops):
    created = service.create_shop(ADMIN, name="丁店")
    assert created.id in shops.shops
    assert ADMIN.id not in users.shop_ids


def test_player_cannot_create(service, shops):
    before = dict(shops.shops)
    with pytest.raises(PermissionDenied):
        service.create_shop(PLAYER, name="丙店")
    assert shops.shops == before


# --- 庫存：列出、加入、移除 ---


def test_staff_adds_and_lists_own_inventory(service):
    added = service.add_game(STAFF_A, SHOP_A, GAME_1)
    assert (added.game_id, added.name) == (GAME_1, "卡坦島")
    service.add_game(STAFF_A, SHOP_A, GAME_2)
    items = service.list_games(STAFF_A, SHOP_A)
    assert [(i.game_id, i.name) for i in items] == [(GAME_1, "卡坦島"), (GAME_2, "狼人殺")]


def test_empty_inventory_lists_nothing(service):
    assert service.list_games(STAFF_A, SHOP_A) == []


def test_duplicate_game_is_conflict(service):
    service.add_game(STAFF_A, SHOP_A, GAME_1)
    with pytest.raises(AppError) as excinfo:
        service.add_game(STAFF_A, SHOP_A, GAME_1)
    assert excinfo.value.status_code == 409
    assert code_of(excinfo) == "SHOP_GAME_ALREADY_EXISTS"


def test_unknown_game_is_404(service):
    with pytest.raises(AppError) as excinfo:
        service.add_game(STAFF_A, SHOP_A, 999)
    assert excinfo.value.status_code == 404
    assert code_of(excinfo) == "GAME_NOT_FOUND"


def test_staff_removes_game(service):
    service.add_game(STAFF_A, SHOP_A, GAME_1)
    service.remove_game(STAFF_A, SHOP_A, GAME_1)
    assert service.list_games(STAFF_A, SHOP_A) == []


def test_removing_game_not_in_inventory_is_404(service):
    with pytest.raises(AppError) as excinfo:
        service.remove_game(STAFF_A, SHOP_A, GAME_1)
    assert excinfo.value.status_code == 404
    assert code_of(excinfo) == "SHOP_GAME_NOT_FOUND"


def test_inventories_are_separate_per_shop(service):
    admin_add = service.add_game(ADMIN, SHOP_B, GAME_2)
    assert admin_add.game_id == GAME_2
    service.add_game(STAFF_A, SHOP_A, GAME_1)
    assert [i.game_id for i in service.list_games(STAFF_A, SHOP_A)] == [GAME_1]
    assert [i.game_id for i in service.list_games(ADMIN, SHOP_B)] == [GAME_2]


# --- 權限 ---


@pytest.mark.parametrize("operation", ["list", "add", "remove"])
def test_staff_cannot_touch_another_shop(service, operation):
    with pytest.raises(PermissionDenied):
        _call(service, operation, STAFF_A, SHOP_B)


@pytest.mark.parametrize("operation", ["list", "add", "remove"])
def test_player_cannot_touch_inventory(service, operation):
    with pytest.raises(PermissionDenied):
        _call(service, operation, PLAYER, SHOP_A)


@pytest.mark.parametrize("operation", ["list", "add"])
def test_admin_can_manage_any_shop(service, operation):
    _call(service, operation, ADMIN, SHOP_B)


def test_staff_without_shop_cannot_touch_inventory(service):
    with pytest.raises(PermissionDenied):
        service.list_games(NEW_STAFF, SHOP_A)


def test_staff_permission_follows_database_not_header(service):
    """標頭帶乙店、資料庫是甲店：能管甲店，不能管乙店。"""
    header_says_b = CurrentUser(id=STAFF_A.id, role="shop_staff", shop_id=SHOP_B)
    service.add_game(header_says_b, SHOP_A, GAME_1)
    with pytest.raises(PermissionDenied):
        service.add_game(header_says_b, SHOP_B, GAME_1)


def test_unknown_shop_is_404(service):
    missing = uuid.UUID("c0000000-0000-4000-8000-0000000000ff")
    with pytest.raises(AppError) as excinfo:
        service.list_games(ADMIN, missing)
    assert excinfo.value.status_code == 404
    assert code_of(excinfo) == "SHOP_NOT_FOUND"


# --- 查庫存裡有哪些（給桌遊推薦用，不限角色） ---


def test_games_in_stock_returns_only_stocked_games(service):
    service.add_game(STAFF_A, SHOP_A, GAME_1)
    service.add_game(ADMIN, SHOP_B, GAME_2)

    assert service.games_in_stock(SHOP_A, [GAME_1, GAME_2]) == {GAME_1}
    assert service.games_in_stock(SHOP_B, [GAME_1, GAME_2]) == {GAME_2}


def test_games_in_stock_ignores_games_not_asked(service):
    service.add_game(STAFF_A, SHOP_A, GAME_1)
    service.add_game(STAFF_A, SHOP_A, GAME_2)

    assert service.games_in_stock(SHOP_A, [GAME_2]) == {GAME_2}
    assert service.games_in_stock(SHOP_A, []) == set()


def test_games_in_stock_of_unknown_shop_is_404(service):
    missing = uuid.UUID("c0000000-0000-4000-8000-0000000000ff")
    with pytest.raises(AppError) as excinfo:
        service.games_in_stock(missing, [GAME_1])
    assert excinfo.value.status_code == 404
    assert code_of(excinfo) == "SHOP_NOT_FOUND"


def test_games_in_stock_with_no_games_still_checks_the_shop(service):
    """桌遊推薦在呼叫 LLM 之前，用空的清單確認店家存在。"""
    missing = uuid.UUID("c0000000-0000-4000-8000-0000000000ff")
    with pytest.raises(AppError) as excinfo:
        service.games_in_stock(missing, [])
    assert code_of(excinfo) == "SHOP_NOT_FOUND"


def _call(service, operation: str, user: CurrentUser, shop_id: uuid.UUID):
    if operation == "list":
        return service.list_games(user, shop_id)
    if operation == "add":
        return service.add_game(user, shop_id, GAME_1)
    if operation == "remove":
        return service.remove_game(user, shop_id, GAME_1)
    raise AssertionError(operation)
