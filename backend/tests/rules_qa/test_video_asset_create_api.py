"""新增素材：POST /api/v1/rules-videos/{id}/assets（2026-11-25 永傑決定，換素材完整版）。

店員換素材時，正確的素材不在清單裡（例如要多拍一張牌）：先新增一個照片素材，再換上去。
請求 `{"label", "shot", "video_version"}`；代號由後端產生。`video_version` 不同就 409。
草稿用 tests/rules_qa/video_script_support.llm_output()；連 `_test` 資料庫，LLM 用 fake。
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user
from app.domains.rules_qa.video_draft import DraftJobHandler
from app.domains.rules_qa.video_jobs import JobRunner
from app.integrations.llm.fake import FakeLLMProvider
from app.main import create_app
from tests.rules_qa.video_draft_support import add_manual, project_row, set_pages
from tests.rules_qa.video_script_support import coverage_output, llm_output
from tests.rules_qa.video_support import OTHER_STAFF, insert_job, insert_project, seed_people

URL = "/api/v1/rules-videos"


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def game(api, add_game, add_pages) -> int:
    game = add_game("假遊戲")
    add_manual(add_pages, game)
    return game


@pytest.fixture
def project(rules_db: Engine, game: int) -> uuid.UUID:
    project = insert_project(rules_db, game)
    set_pages(rules_db, project)
    insert_job(rules_db, project, kind="draft")
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    assert JobRunner(sessionmaker(rules_db), {"draft": DraftJobHandler(llm)}).run_once()
    return project


def _code(response) -> str:
    return response.json()["error"]["code"]


def _version(rules_db, project) -> int:
    return project_row(rules_db, project).video_version


def _create(api, rules_db, project, label="白薔薇", shot="整張牌正面朝上", version=None):
    body = {
        "label": label,
        "shot": shot,
        "video_version": _version(rules_db, project) if version is None else version,
    }
    return api.post(f"{URL}/{project}/assets", json=body)


def test_create_asset(api, as_shop_staff, rules_db, project):
    before = _version(rules_db, project)
    response = _create(api, rules_db, project)
    assert response.status_code == 201, response.text
    body = response.json()
    key = body["asset_key"]
    assert body["label"] == "白薔薇" and body["shot"] == "整張牌正面朝上"
    assert body["kind"] == "flat_photo" and body["has_photo"] is False
    assert body["video_version"] == before + 1
    video = project_row(rules_db, project).video
    assert key in [a["asset_key"] for a in video["assets"]]
    draft = api.get(f"{URL}/{project}/draft").json()
    created = next(a for a in draft["assets"] if a["asset_key"] == key)
    assert created["used_in_segments"] == []  # 還沒換上去，不用拍


def test_create_then_swap_requires_photo(api, as_shop_staff, rules_db, project):
    key = _create(api, rules_db, project).json()["asset_key"]
    body = {"slot": "main", "asset_key": key, "video_version": _version(rules_db, project)}
    response = api.patch(f"{URL}/{project}/segments/s2", json=body)
    assert response.status_code == 200, response.text
    missing = api.get(f"{URL}/{project}/readiness").json()["missing_photos"]
    assert key in [m["asset_key"] for m in missing]


def test_shot_is_optional(api, as_shop_staff, rules_db, project):
    response = _create(api, rules_db, project, shot=None)
    assert response.status_code == 201, response.text
    assert response.json()["shot"] is None


@pytest.mark.parametrize("label", ["", "   ", "很" * 31], ids=["empty", "blank", "too-long"])
def test_bad_label_is_422(api, as_shop_staff, rules_db, project, label):
    before = project_row(rules_db, project).video
    assert _create(api, rules_db, project, label=label).status_code == 422
    assert project_row(rules_db, project).video == before


def test_label_taken_is_422(api, as_shop_staff, rules_db, project):
    assert _create(api, rules_db, project).status_code == 201
    response = _create(api, rules_db, project)
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_ASSET_LABEL_TAKEN"


def test_stale_version_is_409(api, as_shop_staff, rules_db, project):
    before = project_row(rules_db, project).video
    response = _create(api, rules_db, project, version=_version(rules_db, project) - 1)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_CONFLICT"
    assert project_row(rules_db, project).video == before


def test_no_draft_is_404(api, as_shop_staff, rules_db, game):
    project = insert_project(rules_db, game)
    body = {"label": "白薔薇", "shot": None, "video_version": 0}
    response = api.post(f"{URL}/{project}/assets", json=body)
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


def test_admin_can_create(api, as_admin, rules_db, project):
    assert _create(api, rules_db, project).status_code == 201


def test_other_shop_is_404(api, app, rules_db, project):
    app.dependency_overrides[get_current_user] = lambda: OTHER_STAFF
    response = _create(api, rules_db, project)
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_player_is_403(api, as_player, rules_db, project):
    assert _create(api, rules_db, project).status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, rules_db, project):
    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert _create(client, rules_db, project).status_code == 401
