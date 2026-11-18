"""matches API 測試共用的 fixture：app 改連 `_test` 資料庫，並準備店家、使用者、遊戲與揪團。"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings
from app.main import create_app
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF
from tests.matches.support import BASE, match_body

WHITE_ROSE_BGG_ID = 400566
OTHER_GAME_BGG_ID = 900001

PLAYER_B = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000b"), role="player")
PLAYER_C = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000c"), role="player")
OUTSIDER = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000d"), role="player")

USERS = [
    (TEST_PLAYER, "測試玩家"),
    (TEST_SHOP_STAFF, "測試店家人員"),
    (TEST_ADMIN, "測試管理員"),
    (PLAYER_B, "玩家乙"),
    (PLAYER_C, "玩家丙"),
    (OUTSIDER, "路人"),
]


@pytest.fixture
def app(make_settings: Callable[..., Settings], test_db_url: str, db: Engine) -> FastAPI:
    """覆寫根目錄的 app：連 `_test` 資料庫（db fixture 已清空資料表）。"""
    with db.begin() as conn:
        # CASCADE 會一併清空 groups、matches 等參照它們的資料表
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
        conn.execute(
            text("INSERT INTO booking_shops (id, name) VALUES (:id, '測試桌遊店')"),
            {"id": TEST_SHOP_ID},
        )
        for user, name in USERS:
            conn.execute(
                text(
                    "INSERT INTO auth_users (id, display_name, role, shop_id) "
                    "VALUES (:id, :name, :role, :shop)"
                ),
                {"id": user.id, "name": name, "role": user.role, "shop": user.shop_id},
            )
    return create_app(make_settings(database_url=test_db_url))


@pytest.fixture
def act_as(app: FastAPI) -> Callable[[CurrentUser], CurrentUser]:
    def _act_as(user: CurrentUser) -> CurrentUser:
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _act_as


@pytest.fixture
def api(client: TestClient, act_as: Callable[[CurrentUser], CurrentUser]):
    """以指定的使用者送出請求：api(user, "POST", url, json=...)。"""

    def _call(user: CurrentUser, method: str, url: str, **kwargs: Any):
        act_as(user)
        return client.request(method, url, **kwargs)

    return _call


def _insert_game(db: Engine, bgg_id: int, name: str, result_type: str | None) -> int:
    with db.begin() as conn:
        return conn.scalar(
            text(
                "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                "min_playtime, max_playtime, min_age, weight, categories, mechanics, result_type) "
                "VALUES (:bgg, :name, 'Example Game', 3, 5, 30, 60, 14, 2.0, "
                "ARRAY['Card Game'], ARRAY['Hidden Roles'], :rt) RETURNING id"
            ),
            {"bgg": bgg_id, "name": name, "rt": result_type},
        )


@pytest.fixture
def white_rose_id(app: FastAPI, db: Engine) -> int:
    """《血與刃的白薔薇》，結果類型 faction。"""
    return _insert_game(db, WHITE_ROSE_BGG_ID, "血與刃的白薔薇", "faction")


@pytest.fixture
def other_game_id(app: FastAPI, db: Engine) -> int:
    """沒有回合格式的遊戲，結果類型 score。"""
    return _insert_game(db, OTHER_GAME_BGG_ID, "其他遊戲", "score")


@pytest.fixture
def set_result_type(db: Engine) -> Callable[[int, str | None], None]:
    def _set(game_id: int, value: str | None) -> None:
        with db.begin() as conn:
            conn.execute(
                text("UPDATE games SET result_type = :v WHERE id = :id"),
                {"v": value, "id": game_id},
            )

    return _set


@pytest.fixture
def started(api, white_rose_id: int) -> str:
    """進行中的一局：1 測試玩家（開局）、2 玩家乙、3 玩家丙、4 Amy（沒帳號）。回傳局的 id。"""
    created = api(TEST_PLAYER, "POST", BASE, json=match_body(white_rose_id))
    assert created.status_code == 201, created.text
    match_id = created.json()["id"]
    for user in (PLAYER_B, PLAYER_C):
        joined = api(user, "POST", f"{BASE}/{match_id}/participants", json={})
        assert joined.status_code == 201, joined.text
    added = api(
        TEST_PLAYER, "POST", f"{BASE}/{match_id}/participants", json={"display_name": "Amy"}
    )
    assert added.status_code == 201, added.text
    return match_id


@pytest.fixture
def add_group(db: Engine, app: FastAPI) -> Callable[[], uuid.UUID]:
    """直接寫入一個揪團（開團主是測試玩家），回傳它的 id。"""

    def _add() -> uuid.UUID:
        with db.begin() as conn:
            return conn.scalar(
                text(
                    "INSERT INTO groups (shop_id, organizer_id, title, start_at, end_at, capacity) "
                    "VALUES (:shop, :org, '週末輕策略', '2030-01-01 11:00+00', "
                    "'2030-01-01 13:00+00', 4) RETURNING id"
                ),
                {"shop": TEST_SHOP_ID, "org": TEST_PLAYER.id},
            )

    return _add
