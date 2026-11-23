"""草稿 API（spec rules-video-studio「草稿（MR 5）」，design.md D11）。

建立工作：POST /rules-videos/{id}/jobs（kind=draft）；查看：GET /rules-videos/{id}/draft。
工作用 JobRunner.run_once() 執行，LLM 用 FakeLLMProvider。
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.domains.rules_qa.video_draft import (
    PAGES_STALE_HINT,
    TERMS_MISSING_HINT,
    DraftJobHandler,
)
from app.domains.rules_qa.video_jobs import JobRunner
from app.integrations.llm.fake import FakeLLMProvider
from tests.rules_qa.video_draft_support import add_manual, set_pages, upload_terms
from tests.rules_qa.video_script_support import coverage_output, coverage_rule, llm_output
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
    return project


def _code(response) -> str:
    return response.json()["error"]["code"]


def _draft(rules_db: Engine, project: uuid.UUID, coverage=None) -> None:
    """建立並執行一個草稿工作。"""
    insert_job(rules_db, project, kind="draft")
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage or coverage_output()])
    assert JobRunner(sessionmaker(rules_db), {"draft": DraftJobHandler(llm)}).run_once()


# --- 建立草稿工作 ---


def test_create_draft_job_is_202(api, as_shop_staff, project):
    response = api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["kind"] == "draft" and data["status"] == "queued"
    assert data["project_id"] == str(project)


def test_pages_not_set_is_422(api, as_shop_staff, rules_db, game):
    bare = insert_project(rules_db, game)
    response = api.post(f"{URL}/{bare}/jobs", json={"kind": "draft"})
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PAGES_NOT_SET"
    assert api.get(f"{URL}/{bare}/jobs").json()["total"] == 0  # 沒有建立工作


def test_second_job_while_running_is_409(api, as_shop_staff, project):
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    response = api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_JOB_RUNNING"


@pytest.mark.parametrize("body", [{"kind": "revise"}, {"kind": "x"}, {}])
def test_unsupported_kind_is_422(api, as_shop_staff, project, body):
    # revise 的建立在之後的 MR 才開放（render 在 MR 9 開放，見 test_video_render_api.py）
    assert api.post(f"{URL}/{project}/jobs", json=body).status_code == 422


def test_other_shop_is_404(api, as_shop_staff, rules_db, game):
    other = insert_project(rules_db, game, OTHER_STAFF)
    set_pages(rules_db, other)
    response = api.post(f"{URL}/{other}/jobs", json={"kind": "draft"})
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"
    response = api.get(f"{URL}/{other}/draft")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_player_is_403(api, as_player, project):
    assert api.post(f"{URL}/{project}/jobs", json={"kind": "draft"}).status_code == 403
    assert api.get(f"{URL}/{project}/draft").status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, project):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.post(f"{URL}/{project}/jobs", json={"kind": "draft"}).status_code == 401
    assert client.get(f"{URL}/{project}/draft").status_code == 401


def test_draft_handler_is_registered(make_settings, test_db_url):
    from app.main import create_app

    app = create_app(make_settings(database_url=test_db_url))
    assert isinstance(app.state.rules_video_job_handlers["draft"], DraftJobHandler)


# --- 查看草稿 ---


def test_no_draft_yet_is_404(api, as_shop_staff, project):
    response = api.get(f"{URL}/{project}/draft")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


def test_view_draft(api, as_shop_staff, rules_db, project):
    rule = coverage_rule(narration=("incomplete", ["b1"], "同時翻開"))
    _draft(rules_db, project, coverage_output([rule]))
    response = api.get(f"{URL}/{project}/draft")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["video_version"] == 1
    assert [s["segment_key"] for s in data["segments"]] == ["s1", "s2"]
    first = data["segments"][0]
    assert first["source_pages"] == [5]
    assert first["beats"][0]["beat_key"] and first["beats"][0]["narration"]
    assert first["beats"][0]["subtitle"]
    assets = {a["asset_key"]: a for a in data["assets"]}
    assert set(assets) == {"back", "red", "blue", "board"}
    board = assets["board"]
    assert board["priority"] == "must" and board["shot"] and board["has_photo"] is False
    assert board["regions"] == ["zone_a"]
    assert data["coverage"]["status"] == "done"
    assert data["coverage"]["total_rules"] == 1
    issue = data["coverage"]["issues"][0]
    assert issue["narration_status"] == "incomplete" and issue["narration_missing"] == "同時翻開"
    assert data["pages_stale"] is False and data["pages_stale_message"] is None


def test_step_becomes_draft(api, as_shop_staff, rules_db, project):
    assert api.get(f"{URL}/{project}").json()["step"] == "pages"
    _draft(rules_db, project)
    assert api.get(f"{URL}/{project}").json()["step"] == "draft"


@pytest.mark.parametrize(
    "terms, status, hint",
    [(None, "used", None), ([], "empty", None), ("missing", "missing", TERMS_MISSING_HINT)],
    ids=["used", "empty", "missing"],
)
def test_terms_hint(api, as_shop_staff, rules_db, project, game, terms, status, hint):
    if terms != "missing":
        upload_terms(rules_db, game, terms)
    _draft(rules_db, project)
    data = api.get(f"{URL}/{project}/draft").json()
    assert data["terms"]["status"] == status and data["terms"]["message"] == hint
    assert TERMS_MISSING_HINT == "這款遊戲還沒有用語對照表，草稿的用詞品質可能下降"


def test_pages_changed_after_draft_is_marked(api, as_shop_staff, rules_db, project):
    _draft(rules_db, project)
    body = {"chapter_pages": [5], "reference_pages": [3], "texts": {"5": "店員又改了"}}
    assert api.put(f"{URL}/{project}/pages", json=body).status_code == 200
    data = api.get(f"{URL}/{project}/draft").json()
    assert data["pages_stale"] is True
    assert data["pages_stale_message"] == PAGES_STALE_HINT
    assert PAGES_STALE_HINT == "這份草稿依舊的頁面文字產生，建議重新產生"


def test_coverage_not_done_is_shown(api, as_shop_staff, rules_db, project):
    _draft(rules_db, project, coverage_output([]))
    coverage = api.get(f"{URL}/{project}/draft").json()["coverage"]
    assert coverage["status"] == "not_done" and "沒有拆出任何規則" in coverage["reason"]
    assert coverage["issues"] == []


def test_coverage_stale_when_narration_changed(api, as_shop_staff, rules_db, project):
    # 涵蓋檢查「過期」看旁白與字幕的雜湊（2026-11-21 永傑決定；原本看 video_version）
    _draft(rules_db, project)
    with rules_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE rules_qa_video_projects SET video = jsonb_set(video, "
                "'{segments,0,beats,0,narration}', '\"改過的旁白\"'), "
                "video_version = video_version + 1 WHERE id = :p"
            ),
            {"p": project},
        )
    assert api.get(f"{URL}/{project}/draft").json()["coverage"]["status"] == "stale"


def test_coverage_not_stale_when_only_assets_changed(api, as_shop_staff, rules_db, project):
    # 上傳照片、改區域會讓 video_version 加 1，但旁白字幕沒變，涵蓋檢查不算過期
    _draft(rules_db, project)
    with rules_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE rules_qa_video_projects SET video = jsonb_set(video, "
                "'{assets,0,file}', '\"photo.jpg\"'), video_version = video_version + 1 "
                "WHERE id = :p"
            ),
            {"p": project},
        )
    assert api.get(f"{URL}/{project}/draft").json()["coverage"]["status"] == "done"
