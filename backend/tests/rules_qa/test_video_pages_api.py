"""頁面文字 API（spec rules-video-studio「規則書頁面文字（MR 4）」，design.md D11）。

規則書頁面用 conftest 的 add_pages 直接寫進 games_manual（只用虛構的短文字）。
"""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.auth import get_current_user
from tests.conftest import TEST_ADMIN
from tests.rules_qa.video_support import OTHER_STAFF, insert_project, seed_people

PAGE_2 = "紅隊卡片\n隊長\n副隊長\n隊員"
PAGE_7 = "整理階段：\n\n把所有有蓋子的木箱排成一列。\n接著打開所有木箱。"
PAGE_8 = "# 收工\n\n籌碼收進收納盒時活動結束。\n\n重複第1~3步驟，直到有一組達成或時間用完。"
PAGE_8_LAST = "重複第1~3步驟，直到有一組達成或時間用完。"


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def game(api, add_game, add_pages) -> int:
    game = add_game("假遊戲")
    add_pages(game, [(2, PAGE_2), (7, PAGE_7), (8, PAGE_8)])
    return game


@pytest.fixture
def project(rules_db: Engine, game: int) -> uuid.UUID:
    return insert_project(rules_db, game)


def _url(project: uuid.UUID) -> str:
    return f"/api/v1/rules-videos/{project}/pages"


def _body(**extra: Any) -> dict[str, Any]:
    return {
        "chapter_pages": [7, 8],
        "reference_pages": [2],
        "texts": {"7": PAGE_7.replace("有蓋子的", "蓋好的"), "8": PAGE_8_LAST},
        **extra,
    }


def _code(response) -> str:
    return response.json()["error"]["code"]


def _page(data: dict[str, Any], number: int) -> dict[str, Any]:
    return next(p for p in data["pages"] if p["page"] == number)


# --- 查看 ---


def test_first_open_lists_available_pages(api, as_shop_staff, project):
    response = api.get(_url(project))
    assert response.status_code == 200
    data = response.json()
    assert data["available_pages"] == [2, 7, 8]
    assert data["chapter_pages"] == [] and data["reference_pages"] == []
    assert data["pages"] == [] and data["pages_version"] == 0


# --- 儲存 ---


def test_save_pages_reports_removed_and_changed(api, as_shop_staff, project, rules_db):
    response = api.put(_url(project), json=_body())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["chapter_pages"] == [7, 8] and data["reference_pages"] == [2]
    assert data["pages_version"] == 1

    page7 = _page(data, 7)
    assert page7["role"] == "chapter" and page7["original"] == PAGE_7
    assert page7["removed"] == []
    assert len(page7["changed"]) == 1
    assert page7["changed"][0]["original"] == "把所有有蓋子的木箱排成一列。"
    assert page7["changed"][0]["edited"] == "把所有蓋好的木箱排成一列。"

    page8 = _page(data, 8)
    assert page8["text"] == PAGE_8_LAST
    assert [b["lines"] for b in page8["removed"]] == [["# 收工", "籌碼收進收納盒時活動結束。"]]

    page2 = _page(data, 2)
    assert page2["role"] == "reference" and page2["text"] == PAGE_2  # 沒給文字的頁用原文
    assert page2["removed"] == [] and page2["changed"] == []
    for page in data["pages"]:
        assert page["original_changed"] is False

    # games_manual 不變
    with rules_db.connect() as conn:
        assert conn.scalar(text("SELECT content FROM games_manual WHERE page = 8")) == PAGE_8


def test_get_returns_saved_pages(api, as_shop_staff, project):
    api.put(_url(project), json=_body())
    data = api.get(_url(project)).json()
    assert _page(data, 8)["text"] == PAGE_8_LAST and data["pages_version"] == 1


def test_save_again_replaces_and_bumps_version(api, as_shop_staff, project):
    api.put(_url(project), json=_body())
    response = api.put(_url(project), json={"chapter_pages": [7], "reference_pages": []})
    data = response.json()
    assert data["pages_version"] == 2
    assert [p["page"] for p in data["pages"]] == [7]
    assert _page(data, 7)["text"] == PAGE_7  # 沒給文字：用原文


def test_save_updates_project_time(api, as_shop_staff, project):
    before = api.get(f"/api/v1/rules-videos/{project}").json()["updated_at"]
    api.put(_url(project), json=_body())
    assert api.get(f"/api/v1/rules-videos/{project}").json()["updated_at"] > before


@pytest.mark.parametrize(
    "change",
    [
        {"chapter_pages": []},
        {"chapter_pages": list(range(1, 22))},
        {"chapter_pages": [7, 7]},
        {"chapter_pages": [0]},
        {"chapter_pages": [7, 8], "reference_pages": [8]},
        {"texts": {"5": "沒選的頁"}},
        {"texts": {"7": "長" * 10001}},
    ],
    ids=["no_chapter", "too_many", "duplicate", "page_zero", "overlap", "unselected_text", "long"],
)
def test_invalid_pages_are_422(api, as_shop_staff, project, change):
    assert api.put(_url(project), json=_body(**change)).status_code == 422


def test_page_not_uploaded_is_422(api, as_shop_staff, project):
    body = {"chapter_pages": [7, 9], "reference_pages": [3]}
    response = api.put(_url(project), json=body)
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PAGES_MISSING"
    assert response.json()["error"]["details"]["missing"] == [3, 9]


def test_blank_chapter_text_is_422(api, as_shop_staff, project):
    body = {"chapter_pages": [7, 8], "texts": {"7": "  \n ", "8": ""}}
    response = api.put(_url(project), json=body)
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PAGES_EMPTY"


def test_blank_page_is_fine_when_another_chapter_page_has_text(api, as_shop_staff, project):
    body = {"chapter_pages": [7, 8], "texts": {"8": ""}}
    assert api.put(_url(project), json=body).status_code == 200


def test_original_reuploaded_after_editing(api, as_shop_staff, project, rules_db):
    api.put(_url(project), json=_body())
    with rules_db.begin() as conn:
        conn.execute(
            text("UPDATE games_manual SET content = :c WHERE page = 7"), {"c": "新的辨識結果"}
        )
    data = api.get(_url(project)).json()
    page7 = _page(data, 7)
    assert page7["original_changed"] is True
    assert page7["original"] == "新的辨識結果"
    assert page7["text"].startswith("整理階段：")  # 編輯過的文字保留
    assert _page(data, 8)["original_changed"] is False


# --- 權限 ---


def test_admin_can_edit_any_shop(api, app, rules_db, game):
    other = insert_project(rules_db, game, OTHER_STAFF)
    app.dependency_overrides[get_current_user] = lambda: TEST_ADMIN
    assert api.put(_url(other), json=_body()).status_code == 200


@pytest.mark.parametrize("method", ["get", "put"])
def test_other_shop_is_404(api, as_shop_staff, rules_db, game, method):
    other = insert_project(rules_db, game, OTHER_STAFF)
    response = getattr(api, method)(_url(other), **({"json": _body()} if method == "put" else {}))
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


@pytest.mark.parametrize("method", ["get", "put"])
def test_player_is_403(api, as_player, project, method):
    response = getattr(api, method)(_url(project), **({"json": _body()} if method == "put" else {}))
    assert response.status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, project):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.get(_url(project)).status_code == 401
    assert client.put(_url(project), json=_body()).status_code == 401
