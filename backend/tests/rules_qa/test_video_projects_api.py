"""影片專案 API（spec rules-video-studio「影片專案與權限」，add-rules-video-mobile MR 1）。

連 `_test` 資料庫；身分用 conftest 的 as_player／as_shop_staff／as_admin（AGENTS.md 4.5）。
"""

import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.auth import CurrentUser, get_current_user
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF

URL = "/api/v1/rules-videos"
OTHER_SHOP_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
OTHER_STAFF = CurrentUser(
    id=uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"), role="shop_staff", shop_id=OTHER_SHOP_ID
)


@pytest.fixture
def people(rules_db: Engine) -> None:
    """兩間店；conftest 的三種測試身分，加上別家店的店員（created_by 參照 auth_users）。"""
    with rules_db.begin() as conn:
        for shop, name in ((TEST_SHOP_ID, "測試店"), (OTHER_SHOP_ID, "別家店")):
            conn.execute(
                text("INSERT INTO booking_shops (id, name) VALUES (:i, :n)"), {"i": shop, "n": name}
            )
        for user, name in (
            (TEST_PLAYER, "玩家"),
            (TEST_SHOP_STAFF, "店員"),
            (TEST_ADMIN, "管理員"),
            (OTHER_STAFF, "別家店員"),
        ):
            conn.execute(
                text(
                    "INSERT INTO auth_users (id, display_name, role, shop_id) "
                    "VALUES (:i, :n, :r, :s)"
                ),
                {"i": user.id, "n": name, "r": user.role, "s": user.shop_id},
            )


@pytest.fixture
def api(app: FastAPI, people: None) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def game(add_game: Callable[[str], int]) -> int:
    return add_game("血與刃的白薔薇")


def _as(app: FastAPI, user: CurrentUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _body(game: int, **extra: object) -> dict[str, object]:
    return {"game_id": game, "chapter_number": 11, "chapter_title": "步驟三", **extra}


def _code(response) -> str:
    return response.json()["error"]["code"]


# --- 建立 ---


def test_staff_creates_project(api: TestClient, as_shop_staff: CurrentUser, game: int):
    response = api.post(URL, json=_body(game))
    assert response.status_code == 201, response.text
    data = response.json()
    assert uuid.UUID(data["id"])
    assert data["game_id"] == game and data["game_name"] == "血與刃的白薔薇"
    assert data["shop_id"] == str(TEST_SHOP_ID)
    assert data["created_by"] == str(TEST_SHOP_STAFF.id)
    assert data["chapter_number"] == 11 and data["chapter_title"] == "步驟三"
    assert data["step"] == "pages"  # MR 1 固定值（design.md D1）
    assert data["created_at"] and data["updated_at"]


def test_staff_may_pass_own_shop(api: TestClient, as_shop_staff: CurrentUser, game: int):
    response = api.post(URL, json=_body(game, shop_id=str(TEST_SHOP_ID)))
    assert response.status_code == 201, response.text


def test_admin_creates_project_for_a_shop(api: TestClient, as_admin: CurrentUser, game: int):
    response = api.post(URL, json=_body(game, shop_id=str(OTHER_SHOP_ID)))
    assert response.status_code == 201, response.text
    assert response.json()["shop_id"] == str(OTHER_SHOP_ID)


def test_same_chapter_twice_is_allowed(api: TestClient, as_shop_staff: CurrentUser, game: int):
    # 同店同一章可以建立第二個專案（2026-11-21 永傑決定）
    first = api.post(URL, json=_body(game))
    second = api.post(URL, json=_body(game))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.parametrize(
    "change",
    [
        {"chapter_title": None},
        {"chapter_number": None},
        {"chapter_number": 0},
        {"chapter_title": "   "},
        {"chapter_title": "長" * 51},
    ],
    ids=["no_title", "no_number", "number_zero", "blank_title", "title_too_long"],
)
def test_invalid_fields_are_422(
    api: TestClient, as_shop_staff: CurrentUser, game: int, change: dict[str, object]
):
    body = _body(game)
    for key, value in change.items():
        if value is None:
            del body[key]
        else:
            body[key] = value
    assert api.post(URL, json=body).status_code == 422


def test_title_of_50_characters_is_accepted(api: TestClient, as_shop_staff: CurrentUser, game: int):
    response = api.post(URL, json=_body(game, chapter_title="長" * 50))
    assert response.status_code == 201, response.text


def test_title_is_trimmed(api: TestClient, as_shop_staff: CurrentUser, game: int):
    response = api.post(URL, json=_body(game, chapter_title="  步驟三  "))
    assert response.json()["chapter_title"] == "步驟三"


def test_unknown_game_is_404(api: TestClient, as_shop_staff: CurrentUser, game: int):
    response = api.post(URL, json=_body(game + 999))
    assert response.status_code == 404 and _code(response) == "GAME_NOT_FOUND"


def test_admin_without_shop_is_422(api: TestClient, as_admin: CurrentUser, game: int):
    assert api.post(URL, json=_body(game)).status_code == 422


def test_admin_with_unknown_shop_is_404(api: TestClient, as_admin: CurrentUser, game: int):
    response = api.post(URL, json=_body(game, shop_id=str(uuid.uuid4())))
    assert response.status_code == 404 and _code(response) == "BOOKING_SHOP_NOT_FOUND"


def test_staff_with_other_shop_is_403(api: TestClient, as_shop_staff: CurrentUser, game: int):
    response = api.post(URL, json=_body(game, shop_id=str(OTHER_SHOP_ID)))
    assert response.status_code == 403


def test_player_cannot_create(api: TestClient, as_player: CurrentUser, game: int):
    assert api.post(URL, json=_body(game)).status_code == 403


# --- 列表與查看 ---


def _create(api: TestClient, app: FastAPI, user: CurrentUser, game: int, **extra: object) -> str:
    _as(app, user)
    response = api.post(URL, json=_body(game, **extra))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_staff_lists_only_own_shop(api: TestClient, app: FastAPI, game: int):
    mine = _create(api, app, TEST_SHOP_STAFF, game)
    _create(api, app, OTHER_STAFF, game)
    _as(app, TEST_SHOP_STAFF)
    data = api.get(URL).json()
    assert data["total"] == 1
    assert [p["id"] for p in data["items"]] == [mine]


def test_admin_lists_all(api: TestClient, app: FastAPI, game: int):
    _create(api, app, TEST_SHOP_STAFF, game)
    _create(api, app, OTHER_STAFF, game)
    _as(app, TEST_ADMIN)
    assert api.get(URL).json()["total"] == 2


def test_list_is_newest_first_and_paged(api: TestClient, app: FastAPI, game: int):
    first = _create(api, app, TEST_SHOP_STAFF, game)
    second = _create(api, app, TEST_SHOP_STAFF, game)
    _as(app, TEST_SHOP_STAFF)
    page1 = api.get(URL, params={"page": 1, "page_size": 1}).json()
    page2 = api.get(URL, params={"page": 2, "page_size": 1}).json()
    assert page1["total"] == page2["total"] == 2
    assert [p["id"] for p in page1["items"]] == [second]
    assert [p["id"] for p in page2["items"]] == [first]


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}],
    ids=["page_zero", "page_size_zero", "page_size_too_large"],
)
def test_invalid_paging_is_422(api: TestClient, as_shop_staff: CurrentUser, params: dict[str, int]):
    assert api.get(URL, params=params).status_code == 422


def test_get_own_project(api: TestClient, app: FastAPI, game: int):
    project = _create(api, app, TEST_SHOP_STAFF, game)
    response = api.get(f"{URL}/{project}")
    assert response.status_code == 200
    assert response.json()["id"] == project and response.json()["step"] == "pages"


def test_other_shop_project_is_404(api: TestClient, app: FastAPI, game: int):
    project = _create(api, app, OTHER_STAFF, game)
    _as(app, TEST_SHOP_STAFF)
    response = api.get(f"{URL}/{project}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_admin_gets_any_project(api: TestClient, app: FastAPI, game: int):
    project = _create(api, app, OTHER_STAFF, game)
    _as(app, TEST_ADMIN)
    assert api.get(f"{URL}/{project}").status_code == 200


def test_unknown_project_is_404(api: TestClient, as_shop_staff: CurrentUser):
    response = api.get(f"{URL}/{uuid.uuid4()}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_malformed_project_id_is_422(api: TestClient, as_shop_staff: CurrentUser):
    assert api.get(f"{URL}/not-a-uuid").status_code == 422


@pytest.mark.parametrize("path", ["", f"/{uuid.uuid4()}"], ids=["list", "get"])
def test_player_cannot_read(api: TestClient, as_player: CurrentUser, path: str):
    assert api.get(f"{URL}{path}").status_code == 403


# --- 沒登入 ---


def test_unauthenticated_in_jwt_mode(test_db_url: str, make_settings, people: None):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
