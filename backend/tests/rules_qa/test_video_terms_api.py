"""用語對照表 API（spec rules-video-studio「用語對照表」，add-rules-video-mobile MR 3，D4）。"""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.core.auth import CurrentUser
from tests.conftest import TEST_ADMIN
from tests.rules_qa.video_support import seed_people

RED = {"en": "Red card", "zh": "紅牌", "key": "red", "category": "single"}
ZONE = {"en": "Zone A", "zh": "甲區", "key": "zone_a", "avoid": ["A區"]}
KNIGHTS = {"en": "Knight cards", "zh": "騎士牌", "key": "knight_cards", "category": "generic"}


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def game(add_game) -> int:
    return add_game("血與刃的白薔薇")


def _url(game: int) -> str:
    return f"/api/v1/games/{game}/video-terms"


def _put(api: TestClient, game: int, terms: list[dict[str, Any]]):
    return api.put(_url(game), json={"terms": terms})


def _code(response) -> str:
    return response.json()["error"]["code"]


# --- 上傳 ---


def test_admin_uploads(api, as_admin: CurrentUser, game):
    response = _put(api, game, [RED, ZONE, KNIGHTS])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["game_id"] == game
    # 回傳時每筆都補齊 5 個欄位：沒填的 avoid 是空陣列、category 是 null
    assert data["terms"] == [
        {**RED, "avoid": []},
        {**ZONE, "category": None},
        {**KNIGHTS, "avoid": []},
    ]
    assert data["updated_by"] == str(TEST_ADMIN.id) and data["updated_at"]


def test_upload_replaces_whole_table(api, as_admin, game):
    _put(api, game, [RED, ZONE, KNIGHTS])
    response = _put(api, game, [ZONE])
    assert [t["en"] for t in response.json()["terms"]] == ["Zone A"]
    assert [t["en"] for t in api.get(_url(game)).json()["terms"]] == ["Zone A"]


def test_empty_table_is_allowed(api, as_admin, game):
    response = _put(api, game, [])
    assert response.status_code == 200 and response.json()["terms"] == []
    assert api.get(_url(game)).status_code == 200  # 上傳空表 ≠ 從未上傳


def test_values_are_trimmed(api, as_admin, game):
    response = _put(api, game, [{"en": " Red card ", "zh": " 白薔薇 "}])
    term = response.json()["terms"][0]
    assert (term["en"], term["zh"]) == ("Red card", "白薔薇")


@pytest.mark.parametrize(
    "bad, location",
    [
        ({"en": "X"}, "zh"),
        ({"en": "X", "zh": "叉", "category": "unique"}, "category"),
        ({"en": "X", "zh": "叉", "avoid": "白玫瑰"}, "avoid"),
        ({"en": "X", "zh": "叉" * 101}, "zh"),
        ({"en": "X", "zh": "叉", "avoid": [""]}, "avoid"),
    ],
    ids=["missing_zh", "bad_category", "avoid_not_list", "zh_too_long", "avoid_empty_string"],
)
def test_invalid_entry_points_to_its_index(api, as_admin, game, bad, location):
    response = _put(api, game, [RED, ZONE, bad])
    assert response.status_code == 422
    locations = [e["loc"] for e in response.json()["error"]["details"]["errors"]]
    assert any(loc[:4] == ["body", "terms", 2, location] for loc in locations), locations


def test_too_many_entries(api, as_admin, game):
    terms = [{"en": f"Term {i}", "zh": f"詞{i}"} for i in range(501)]
    assert _put(api, game, terms).status_code == 422


def test_duplicate_en_ignores_case_and_spaces(api, as_admin, game):
    response = _put(api, game, [RED, {"en": " red CARD ", "zh": "紅色牌"}])
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_TERMS_DUPLICATE"
    assert "Red card" in response.json()["error"]["message"]


def test_duplicate_key_with_same_category_is_allowed(api, as_admin, game):
    # 規則書用兩個英文名稱指同一個區域（design.md D4）
    terms = [
        {"en": "White Rose placement area", "zh": "白薔薇區", "key": "white_rose_zone",
         "category": "single"},
        {"en": "Sanctuary", "zh": "聖所", "key": "White_Rose_Zone ", "category": "single"},
    ]  # fmt: skip
    assert _put(api, game, terms).status_code == 200


def test_duplicate_key_with_one_category_missing_is_allowed(api, as_admin, game):
    terms = [
        {"en": "White Rose placement area", "zh": "白薔薇區", "key": "white_rose_zone",
         "category": "single"},
        {"en": "Sanctuary", "zh": "聖所", "key": "white_rose_zone"},
    ]  # fmt: skip
    assert _put(api, game, terms).status_code == 200


def test_duplicate_key_with_different_category_is_422(api, as_admin, game):
    terms = [
        {"en": "Knight cards", "zh": "騎士牌", "key": "knight", "category": "generic"},
        {"en": "Red Knight", "zh": "紅騎士", "key": "knight", "category": "single"},
    ]
    response = _put(api, game, terms)
    assert response.status_code == 422
    assert _code(response) == "RULES_VIDEO_TERMS_CATEGORY_CONFLICT"
    assert "knight" in response.json()["error"]["message"]


def test_upload_for_unknown_game_is_404(api, as_admin, game):
    response = _put(api, game + 999, [RED])
    assert response.status_code == 404 and _code(response) == "GAME_NOT_FOUND"


def test_staff_cannot_upload(api, as_shop_staff, game):
    assert _put(api, game, [RED]).status_code == 403


def test_player_cannot_upload(api, as_player, game):
    assert _put(api, game, [RED]).status_code == 403


# --- 查看 ---


def test_staff_reads_uploaded_table(api, app, as_admin, game):
    from app.core.auth import get_current_user
    from tests.conftest import TEST_SHOP_STAFF

    _put(api, game, [RED, ZONE])
    app.dependency_overrides[get_current_user] = lambda: TEST_SHOP_STAFF
    response = api.get(_url(game))
    assert response.status_code == 200
    assert [t["key"] for t in response.json()["terms"]] == ["red", "zone_a"]


def test_never_uploaded_is_404(api, as_shop_staff, game):
    response = api.get(_url(game))
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_TERMS_NOT_FOUND"


def test_read_for_unknown_game_is_404(api, as_shop_staff, game):
    response = api.get(_url(game + 999))
    assert response.status_code == 404 and _code(response) == "GAME_NOT_FOUND"


def test_player_cannot_read(api, as_player, game):
    assert api.get(_url(game)).status_code == 403


# --- 沒登入 ---


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, game):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.get(_url(game)).status_code == 401
    assert client.put(_url(game), json={"terms": []}).status_code == 401
