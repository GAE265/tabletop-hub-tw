"""groups API 測試共用的 fixture：app 改連 `_test` 資料庫，並準備店家與使用者。"""

import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, text

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings
from app.main import create_app
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF

PLAYER_B = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000b"), role="player")
PLAYER_C = CurrentUser(id=uuid.UUID("a0000000-0000-4000-8000-00000000000c"), role="player")
OTHER_SHOP_ID = uuid.UUID("c0000000-0000-4000-8000-000000000002")

USERS = [
    (TEST_PLAYER, "測試玩家"),
    (TEST_SHOP_STAFF, "測試店家人員"),
    (TEST_ADMIN, "測試管理員"),
    (PLAYER_B, "玩家乙"),
    (PLAYER_C, "玩家丙"),
]


@pytest.fixture
def app(make_settings: Callable[..., Settings], test_db_url: str, db: Engine) -> FastAPI:
    """覆寫根目錄的 app：連 `_test` 資料庫（db fixture 已清空資料表）。"""
    with db.begin() as conn:
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
        for shop_id, name in [(TEST_SHOP_ID, "測試桌遊店"), (OTHER_SHOP_ID, "另一間店")]:
            conn.execute(
                text("INSERT INTO booking_shops (id, name) VALUES (:id, :name)"),
                {"id": shop_id, "name": name},
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
    """切換目前使用者（as_player 等 fixture 之外的其他玩家用這個）。"""

    def _act_as(user: CurrentUser) -> CurrentUser:
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _act_as


@pytest.fixture
def add_game(db: Engine) -> Callable[[str], int]:
    def _add_game(name: str = "範例桌遊") -> int:
        with db.begin() as conn:
            return conn.scalar(
                text(
                    "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                    "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
                    "VALUES (900001, :name, 'Example Game', 2, 4, 30, 45, 10, 2.0, "
                    "ARRAY['Card Game'], ARRAY['Hand Management']) RETURNING id"
                ),
                {"name": name},
            )

    return _add_game
