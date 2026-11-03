import os
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterator
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.core.auth import CurrentUser, get_current_user, require_role
from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app
from tests.db_utils import BACKEND_DIR, recreate_database, run_migrations

UNREACHABLE_DB = "postgresql+psycopg://nobody:nobody@127.0.0.1:1/none"

# 測試專用的身分，刻意與 app/dev 的開發帳號不同，測試不依賴 seed。
TEST_SHOP_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
TEST_PLAYER = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
TEST_SHOP_STAFF = CurrentUser(
    id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"), role="shop_staff", shop_id=TEST_SHOP_ID
)
TEST_ADMIN = CurrentUser(id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), role="admin")


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    def _make(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "database_url": UNREACHABLE_DB,
            "auth_mode": "dev",
            "llm_provider": "fake",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return _make


def add_probe_routes(app: FastAPI) -> None:
    """測試專用的路由，用來觀察錯誤處理與身分取得。"""
    router = APIRouter(prefix="/_probe")

    @router.get("/me")
    def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict[str, object]:
        return {"id": str(user.id), "role": user.role, "shop_id": str(user.shop_id or "")}

    @router.get("/admin-only")
    def admin_only(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict[str, str]:
        require_role(user, "admin")
        return {"ok": "yes"}

    @router.get("/conflict")
    def conflict() -> None:
        raise AppError(409, "BOOKING_TABLE_TAKEN", "桌位已被訂走", {"table_id": "t1"})

    @router.get("/boom")
    def boom() -> None:
        raise RuntimeError("super-secret-internal-detail")

    @router.get("/items")
    def items(n: int) -> dict[str, int]:
        return {"n": n}

    app.include_router(router)


@pytest.fixture
def app(make_settings: Callable[..., Settings]) -> FastAPI:
    application = create_app(make_settings())
    add_probe_routes(application)
    return application


@pytest.fixture
def jwt_app(make_settings: Callable[..., Settings]) -> FastAPI:
    application = create_app(make_settings(auth_mode="jwt"))
    add_probe_routes(application)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def jwt_client(jwt_app: FastAPI) -> TestClient:
    return TestClient(jwt_app, raise_server_exceptions=False)


@pytest.fixture
def as_player(app: FastAPI) -> CurrentUser:
    app.dependency_overrides[get_current_user] = lambda: TEST_PLAYER
    return TEST_PLAYER


@pytest.fixture
def as_shop_staff(app: FastAPI) -> CurrentUser:
    app.dependency_overrides[get_current_user] = lambda: TEST_SHOP_STAFF
    return TEST_SHOP_STAFF


@pytest.fixture
def as_admin(app: FastAPI) -> CurrentUser:
    app.dependency_overrides[get_current_user] = lambda: TEST_ADMIN
    return TEST_ADMIN


# --- 需要真實 PostgreSQL 的 fixture ---


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """以 DATABASE_URL 為基礎，建立並升級一個獨立的 `_test` 資料庫，不碰開發資料。"""
    base_url = Settings().database_url
    url = recreate_database(base_url, "test")
    run_migrations(url)
    return url


@pytest.fixture
def db(test_db_url: str) -> Iterator[Engine]:
    engine = create_engine(test_db_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops CASCADE"))
    yield engine
    engine.dispose()


@pytest.fixture
def run_seed(test_db_url: str) -> Callable[..., subprocess.CompletedProcess[str]]:
    """以 subprocess 執行 seed 指令（任何地方都不得 import app/dev/）。"""

    def _run(auth_mode: str = "dev") -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "DATABASE_URL": test_db_url,
            "AUTH_MODE": auth_mode,
            "PYTHONUTF8": "1",
        }
        return subprocess.run(
            [sys.executable, "-m", "app.dev.seed"],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    return _run
