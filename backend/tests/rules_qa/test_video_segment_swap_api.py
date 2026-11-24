"""換素材 API：PATCH /api/v1/rules-videos/{id}/segments/{segment_key}。

2026-11-25 永傑決定，最小版。

請求 `{"slot", "asset_key", "video_version"}`；`video_version` 是店員看到的那一版，不同就 409。
草稿 API 的每一段帶出放素材的格子（`slots`），每個素材帶出哪幾段用到它（`used_in_segments`）。

草稿用 tests/rules_qa/video_script_support.llm_output()：
s1 主畫面三張牌（items：red、blue 與牌背 back）、側欄是圖板 board（框線 h1 指 sidebar@zone_a，
第 2 句把 c1 移到 sidebar@zone_a）；s2 主畫面是 red。連 `_test` 資料庫，LLM 用 fake。
"""

import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

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


def _version(rules_db: Engine, project: uuid.UUID) -> int:
    return project_row(rules_db, project).video_version


def _swap(api, rules_db, project, segment="s1", slot="sidebar", asset="blue", version=None):
    body = {
        "slot": slot,
        "asset_key": asset,
        "video_version": _version(rules_db, project) if version is None else version,
    }
    return api.patch(f"{URL}/{project}/segments/{segment}", json=body)


def _segment(rules_db, project, key):
    video = project_row(rules_db, project).video
    return next(s for s in video["segments"] if s["segment_key"] == key)


# --- 草稿帶出每一段的素材 ---


def test_draft_lists_slots_and_asset_usage(api, as_shop_staff, project):
    draft = api.get(f"{URL}/{project}/draft").json()
    s1, s2 = draft["segments"]
    assert s1["slots"] == [
        {
            "slot": "main",
            "kind": "items",
            "asset_keys": ["red", "back", "blue"],
            "swappable": False,
        },
        {"slot": "sidebar", "kind": "asset", "asset_keys": ["board"], "swappable": True},
    ]
    assert s2["slots"] == [
        {"slot": "main", "kind": "asset", "asset_keys": ["red"], "swappable": True}
    ]
    used = {a["asset_key"]: a["used_in_segments"] for a in draft["assets"]}
    assert used == {"back": [1], "red": [1, 2], "blue": [1], "board": [1]}


# --- 換素材 ---


def test_swap_sidebar_asset(api, as_shop_staff, rules_db, project):
    before = _version(rules_db, project)
    response = _swap(api, rules_db, project)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["segment_key"] == "s1" and body["slot"] == "sidebar"
    assert (body["old_asset_key"], body["new_asset_key"]) == ("board", "blue")
    assert body["removed"]["highlights"] == ["h1"]
    assert body["removed"]["labels"] == []
    assert [(c["do"], c["target"]) for c in body["removed"]["cues"]] == [("move", "main.c1")]
    assert body["unused_assets"] == ["board"]
    assert body["video_version"] == before + 1
    s1 = _segment(rules_db, project, "s1")
    assert s1["slots"]["sidebar"]["asset_key"] == "blue"
    assert s1["highlights"] == []
    assert _version(rules_db, project) == before + 1


def test_swap_records_revision(api, as_shop_staff, rules_db, project):
    assert _swap(api, rules_db, project).status_code == 200
    record = _segment(rules_db, project, "s1")["revisions"][-1]
    assert record["kind"] == "asset_swap"
    assert record["number"] == 1
    assert "換素材" in record["request"]
    assert "slots" in record["changed"] and "highlights" in record["changed"]
    assert _segment(rules_db, project, "s1")["state"]["status"] == "stale"
    # 再換一次，編號接著往下
    assert _swap(api, rules_db, project, asset="board").status_code == 200
    assert _segment(rules_db, project, "s1")["revisions"][-1]["number"] == 2


def test_swap_main_asset_removes_nothing(api, as_shop_staff, rules_db, project):
    response = _swap(api, rules_db, project, segment="s2", slot="main", asset="blue")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["removed"] == {"highlights": [], "labels": [], "cues": []}
    assert body["unused_assets"] == []  # red 還用在 s1 的牌


def test_unused_asset_not_required_any_more(api, as_shop_staff, rules_db, project):
    before = api.get(f"{URL}/{project}/readiness").json()
    assert "board" in [m["asset_key"] for m in before["missing_photos"]]
    assert _swap(api, rules_db, project).status_code == 200
    after = api.get(f"{URL}/{project}/readiness").json()
    assert "board" not in [m["asset_key"] for m in after["missing_photos"]]
    assert "board" not in [m["asset_key"] for m in after["missing_regions"]]
    used = {
        a["asset_key"]: a["used_in_segments"]
        for a in api.get(f"{URL}/{project}/draft").json()["assets"]
    }
    assert used["board"] == []


@pytest.mark.parametrize(
    ("segment", "slot", "asset", "status", "code"),
    [
        ("s9", "main", "blue", 404, "RULES_VIDEO_SEGMENT_NOT_FOUND"),
        ("s1", "side", "blue", 422, "RULES_VIDEO_SLOT_NOT_FOUND"),
        ("s1", "main", "blue", 422, "RULES_VIDEO_SWAP_UNSUPPORTED"),
        ("s1", "sidebar", "nope", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "board", 422, "RULES_VIDEO_SWAP_SAME_ASSET"),
    ],
    ids=["segment-missing", "slot-missing", "items-slot", "asset-missing", "same-asset"],
)
def test_swap_rejected(api, as_shop_staff, rules_db, project, segment, slot, asset, status, code):
    before = project_row(rules_db, project).video
    response = _swap(api, rules_db, project, segment=segment, slot=slot, asset=asset)
    assert response.status_code == status and _code(response) == code
    assert project_row(rules_db, project).video == before


def test_unsupported_slot_message(api, as_shop_staff, rules_db, project):
    response = _swap(api, rules_db, project, slot="main")
    assert response.json()["error"]["message"] == "這一段目前不支援換素材"


def test_skipped_asset_is_invalid(api, as_shop_staff, rules_db, project):
    assert api.patch(f"{URL}/{project}/assets/blue", json={"skipped": True}).status_code == 200
    response = _swap(api, rules_db, project)
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_SWAP_ASSET_INVALID"


def test_drawn_asset_is_invalid(api, as_shop_staff, rules_db, project):
    video = project_row(rules_db, project).video
    video["assets"].append(
        {"asset_key": "dice", "kind": "drawn", "priority": "must", "reason": "r", "regions": {}}
    )
    with rules_db.begin() as conn:
        conn.execute(
            text("UPDATE rules_qa_video_projects SET video = CAST(:v AS jsonb) WHERE id = :p"),
            {"v": json.dumps(video, ensure_ascii=False), "p": project},
        )
    response = _swap(api, rules_db, project, asset="dice")
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_SWAP_ASSET_INVALID"


@pytest.mark.parametrize("missing", ["slot", "asset_key", "video_version"])
def test_missing_field_is_422(api, as_shop_staff, rules_db, project, missing):
    body = {"slot": "sidebar", "asset_key": "blue", "video_version": _version(rules_db, project)}
    body.pop(missing)
    assert api.patch(f"{URL}/{project}/segments/s1", json=body).status_code == 422


def test_stale_version_is_409(api, as_shop_staff, rules_db, project):
    before = project_row(rules_db, project).video
    stale = _version(rules_db, project) - 1
    response = _swap(api, rules_db, project, version=stale)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_CONFLICT"
    assert project_row(rules_db, project).video == before


def test_no_draft_is_404(api, as_shop_staff, rules_db, game):
    project = insert_project(rules_db, game)
    body = {"slot": "sidebar", "asset_key": "blue", "video_version": 0}
    response = api.patch(f"{URL}/{project}/segments/s1", json=body)
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


# --- 權限 ---


def test_admin_can_swap_other_shop(api, as_admin, rules_db, project):
    assert _swap(api, rules_db, project).status_code == 200


def test_other_shop_is_404(api, app, rules_db, project):
    from app.core.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: OTHER_STAFF
    response = _swap(api, rules_db, project)
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_player_is_403(api, as_player, rules_db, project):
    assert _swap(api, rules_db, project).status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, rules_db, project):
    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert _swap(client, rules_db, project).status_code == 401
