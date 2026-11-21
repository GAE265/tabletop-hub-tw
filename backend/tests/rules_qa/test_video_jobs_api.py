"""工作查詢 API（spec rules-video-studio「非同步工作」，add-rules-video-mobile MR 2）。"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.auth import CurrentUser, get_current_user
from tests.conftest import TEST_ADMIN
from tests.rules_qa.video_support import (
    OTHER_STAFF,
    insert_job,
    insert_project,
    seed_people,
)

URL = "/api/v1/rules-videos"


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def project(api: TestClient, rules_db: Engine, add_game) -> uuid.UUID:
    return insert_project(rules_db, add_game("血與刃的白薔薇"))


def _code(response) -> str:
    return response.json()["error"]["code"]


def test_get_job(api, as_shop_staff, rules_db, project):
    job = insert_job(rules_db, project, status="running", started_minutes_ago=1)
    with rules_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE rules_qa_video_jobs SET progress = 0.5, message = '段影片 2／3', "
                "error_detail = '給開發者看' WHERE id = :i"
            ),
            {"i": job},
        )
    response = api.get(f"{URL}/{project}/jobs/{job}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job) and data["project_id"] == str(project)
    assert data["kind"] == "draft" and data["status"] == "running"
    assert data["progress"] == 0.5 and data["message"] == "段影片 2／3"
    assert data["error"] is None and data["result"] is None
    assert data["created_at"] and data["started_at"] and data["finished_at"] is None
    assert "error_detail" not in data  # 給開發者看的不在 API 回傳


def test_list_jobs_newest_first_and_paged(api, as_shop_staff, rules_db, project):
    old = insert_job(rules_db, project, status="failed")
    middle = insert_job(rules_db, project, status="succeeded")
    new = insert_job(rules_db, project, status="queued")
    data = api.get(f"{URL}/{project}/jobs").json()
    assert data["total"] == 3
    assert [j["id"] for j in data["items"]] == [str(new), str(middle), str(old)]
    page2 = api.get(f"{URL}/{project}/jobs", params={"page": 2, "page_size": 2}).json()
    assert [j["id"] for j in page2["items"]] == [str(old)]


def test_admin_reads_any_shop(api, app, rules_db, add_game):
    other = insert_project(rules_db, add_game("別家的遊戲"), OTHER_STAFF)
    job = insert_job(rules_db, other)
    app.dependency_overrides[get_current_user] = lambda: TEST_ADMIN
    assert api.get(f"{URL}/{other}/jobs/{job}").status_code == 200


@pytest.mark.parametrize("path", ["/jobs", "/jobs/{job}"], ids=["list", "get"])
def test_other_shop_is_404(api, as_shop_staff, rules_db, add_game, path):
    other = insert_project(rules_db, add_game("別家的遊戲"), OTHER_STAFF)
    job = insert_job(rules_db, other)
    response = api.get(f"{URL}/{other}" + path.format(job=job))
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_job_of_another_project_is_404(api, as_shop_staff, rules_db, project, add_game):
    other = insert_project(rules_db, add_game("另一款"))
    job = insert_job(rules_db, other)
    response = api.get(f"{URL}/{project}/jobs/{job}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_JOB_NOT_FOUND"


def test_unknown_job_is_404(api, as_shop_staff, project):
    response = api.get(f"{URL}/{project}/jobs/{uuid.uuid4()}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_JOB_NOT_FOUND"


def test_unknown_project_is_404(api, as_shop_staff):
    response = api.get(f"{URL}/{uuid.uuid4()}/jobs")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}], ids=["page0", "size0", "size101"]
)
def test_invalid_paging_is_422(api, as_shop_staff, project, params):
    assert api.get(f"{URL}/{project}/jobs", params=params).status_code == 422


@pytest.mark.parametrize("path", ["/jobs", f"/jobs/{uuid.uuid4()}"], ids=["list", "get"])
def test_player_is_403(api, as_player: CurrentUser, project, path):
    assert api.get(f"{URL}/{project}{path}").status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, project):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.get(f"{URL}/{project}/jobs").status_code == 401
