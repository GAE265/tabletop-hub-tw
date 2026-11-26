"""用一句話修改的 API 與工作（add-rules-video-mobile MR 11）。

- `POST /api/v1/rules-videos/{id}/revisions`：請求 `{"request", "segment_key"?, "video_version"}`，
  回 202 並建立 kind=revise 的工作（修改要求存在工作的 `input`）。
- 工作請 AI 算出提案，**不寫入草稿**；結果是三種之一：可以做（proposal）、版型做不到
  （unsupported，附替代做法）、不確定改哪一段（ambiguous，附候選段）。
- `GET /api/v1/rules-videos/{id}/revisions/{revision_id}`：看進度與結果
  （`revision_id` 是工作編號）。
- `PATCH /api/v1/rules-videos/{id}/revisions/{revision_id}`：`{"status": "applied",
  "alternative"?, "video_version"}` 套用；只有提案裡的段被取代，寫修改紀錄、標成要重做。
- 套用後不做規則涵蓋檢查（2026-11-26 永傑決定，之後再加），回應寫明「這次沒有做規則涵蓋檢查」。

草稿用 tests/rules_qa/video_script_support.llm_output()（s1 有金框 h1、s2 沒有框）。
修改的邏輯沿用命令列版（video_revision）；LLM 一律用 FakeLLMProvider（AGENTS.md 7.6）。
"""

import copy
import json
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.domains.rules_qa.video_draft import DraftJobHandler
from app.domains.rules_qa.video_jobs import JobRunner
from app.domains.rules_qa.video_revise import (
    COVERAGE_NOT_DONE_MESSAGE,
    REVISE_LLM_UNAVAILABLE_MESSAGE,
    REVISE_REJECTED_MESSAGE,
    RevisionJobHandler,
)
from app.integrations.llm.errors import LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider
from app.main import create_app
from tests.rules_qa.video_draft_support import add_manual, project_row, set_pages
from tests.rules_qa.video_script_support import coverage_output, llm_output
from tests.rules_qa.video_support import (
    OTHER_STAFF,
    insert_job,
    insert_project,
    job_row,
    seed_people,
)

URL = "/api/v1/rules-videos"
REQUEST = "情況一的金框改成紅框"


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


# --- 輔助 ---


def _code(response) -> str:
    return response.json()["error"]["code"]


def _version(rules_db: Engine, project: uuid.UUID) -> int:
    return project_row(rules_db, project).video_version


def _segment(rules_db: Engine, project: uuid.UUID, key: str) -> dict[str, Any]:
    video = project_row(rules_db, project).video
    return next(s for s in video["segments"] if s["segment_key"] == key)


def _editable(rules_db: Engine, project: uuid.UUID, key: str) -> dict[str, Any]:
    """草稿裡這一段的複本，拿掉程式維護的 state、revisions（LLM 回傳的段不含這兩個）。"""
    segment = copy.deepcopy(_segment(rules_db, project, key))
    segment.pop("state", None)
    segment.pop("revisions", None)
    return segment


def _entry(new: dict[str, Any], requested: list[str], summary: str = "改了") -> dict[str, Any]:
    return {
        "segment_key": new["segment_key"],
        "requested": requested,
        "summary": summary,
        "segment_json": json.dumps(new, ensure_ascii=False),
    }


def _revise(*entries: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "revise",
        "reason": None,
        "segments": list(entries),
        "alternatives": [],
        "candidates": [],
    }


def _unsupported(*alternatives: dict[str, Any], reason: str = "沒有旋轉動作") -> dict[str, Any]:
    return {
        "kind": "unsupported",
        "reason": reason,
        "segments": [],
        "alternatives": list(alternatives),
        "candidates": [],
    }


def _alternative(title: str, new: dict[str, Any]) -> dict[str, Any]:
    return {"title": title, "description": f"{title}的說明", "segments": [_entry(new, ["cues"])]}


def _ambiguous() -> dict[str, Any]:
    return {
        "kind": "ambiguous",
        "reason": "兩段都在講移除藍牌",
        "segments": [],
        "alternatives": [],
        "candidates": [
            {"segment_key": "s1", "reason": "情況一移除藍牌"},
            {"segment_key": "s2", "reason": "情況二移除藍牌"},
        ],
    }


def _gold_to_red(rules_db, project) -> dict[str, Any]:
    new = _editable(rules_db, project, "s1")
    new["highlights"][0]["style"] = "red"
    return new


def _hide_title(rules_db, project, key: str = "s1") -> dict[str, Any]:
    """替代做法用的修改：拿掉第 1 句「顯示標題」的動作（cues 有變動）。"""
    new = _editable(rules_db, project, key)
    new["beats"][0]["cues"] = [c for c in new["beats"][0]["cues"] if c["do"] != "show"]
    return new


def _post(api, rules_db, project, request=REQUEST, segment=None, version=None):
    body: dict[str, Any] = {
        "request": request,
        "video_version": _version(rules_db, project) if version is None else version,
    }
    if segment is not None:
        body["segment_key"] = segment
    return api.post(f"{URL}/{project}/revisions", json=body)


def _run(rules_db, llm) -> None:
    assert JobRunner(sessionmaker(rules_db), {"revise": RevisionJobHandler(llm)}).run_once()


def _propose(api, rules_db, project, *outputs, segment=None, request=REQUEST) -> str:
    """送出修改並跑完工作，回傳修改編號（工作編號）。"""
    response = _post(api, rules_db, project, request=request, segment=segment)
    assert response.status_code == 202, response.text
    _run(rules_db, FakeLLMProvider(json_outputs=list(outputs)))
    return response.json()["id"]


def _get(api, project, revision):
    return api.get(f"{URL}/{project}/revisions/{revision}")


def _apply(api, rules_db, project, revision, alternative=None, version=None, status="applied"):
    body: dict[str, Any] = {
        "status": status,
        "video_version": _version(rules_db, project) if version is None else version,
    }
    if alternative is not None:
        body["alternative"] = alternative
    return api.patch(f"{URL}/{project}/revisions/{revision}", json=body)


# --- 送出修改 ---


def test_create_revision_starts_job(api, as_shop_staff, rules_db, project):
    response = _post(api, rules_db, project)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["request"] == REQUEST and body["segment_key"] is None
    assert body["outcome"] is None
    row = job_row(rules_db, uuid.UUID(body["id"]))
    assert row.kind == "revise"
    assert row.input == {"request": REQUEST, "segment_key": None}


def test_create_revision_for_one_segment(api, as_shop_staff, rules_db, project):
    response = _post(api, rules_db, project, request="  講慢一點  ", segment="s2")
    assert response.status_code == 202, response.text
    row = job_row(rules_db, uuid.UUID(response.json()["id"]))
    assert row.input == {"request": "講慢一點", "segment_key": "s2"}  # 前後空白去掉


@pytest.mark.parametrize("request_text", ["", "   ", "字" * 201])
def test_bad_request_text_is_422(api, as_shop_staff, rules_db, project, request_text):
    assert _post(api, rules_db, project, request=request_text).status_code == 422


def test_missing_version_is_422(api, as_shop_staff, project):
    response = api.post(f"{URL}/{project}/revisions", json={"request": REQUEST})
    assert response.status_code == 422


def test_unknown_segment_is_404(api, as_shop_staff, rules_db, project):
    response = _post(api, rules_db, project, segment="s9")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_SEGMENT_NOT_FOUND"


def test_old_version_is_409(api, as_shop_staff, rules_db, project):
    response = _post(api, rules_db, project, version=_version(rules_db, project) - 1)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_CONFLICT"


def test_no_draft_is_404(api, as_shop_staff, rules_db, game):
    project = insert_project(rules_db, game)
    response = api.post(f"{URL}/{project}/revisions", json={"request": REQUEST, "video_version": 0})
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


def test_running_job_is_409(api, as_shop_staff, rules_db, project):
    insert_job(rules_db, project, kind="render")
    response = _post(api, rules_db, project)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_JOB_RUNNING"


def test_backend_registers_revise_handler(app):
    assert isinstance(app.state.rules_video_job_handlers["revise"], RevisionJobHandler)


# --- 工作：算出提案（不寫入草稿） ---


def test_proposal_does_not_change_draft(api, as_shop_staff, rules_db, project):
    before = project_row(rules_db, project).video
    version = _version(rules_db, project)
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    body = _get(api, project, revision).json()
    assert body["status"] == "succeeded", body["error"]
    assert body["outcome"] == "proposal"
    assert body["request"] == REQUEST
    [segment] = body["segments"]
    assert segment["segment_key"] == "s1" and segment["segment_number"] == 1
    assert segment["changed"] == ["highlights"] and segment["unrequested"] == []
    assert segment["summary"] == "改了"
    assert segment["beats"] == []  # 旁白、字幕沒變
    assert body["many_segments"] is False
    assert body["applied"] is False
    assert body["coverage_checked"] is False
    assert body["coverage_message"] == COVERAGE_NOT_DONE_MESSAGE
    # 草稿不變
    assert project_row(rules_db, project).video == before
    assert _version(rules_db, project) == version


def test_proposal_shows_text_before_and_after(api, as_shop_staff, rules_db, project):
    new = _editable(rules_db, project, "s2")
    new["beats"][0]["subtitle"] = "情況二：所有藍牌都移除。"
    new["beats"][0]["narration"] = "情況二：藍牌全部移除。"  # 沒被要求改旁白
    revision = _propose(api, rules_db, project, _revise(_entry(new, ["subtitle"])))
    [segment] = _get(api, project, revision).json()["segments"]
    assert segment["segment_number"] == 2
    assert segment["changed"] == ["narration", "subtitle"]
    assert segment["unrequested"] == ["narration"]
    [beat] = segment["beats"]
    assert beat["before"] == {
        "narration": "情況二：移除藍牌。",
        "subtitle": "情況二：移除所有藍牌。",
    }
    assert beat["after"] == {
        "narration": "情況二：藍牌全部移除。",
        "subtitle": "情況二：所有藍牌都移除。",
    }


def test_segment_option_limits_ai(api, as_shop_staff, rules_db, project):
    new = _editable(rules_db, project, "s2")
    new["beats"][0]["subtitle"] = "情況二：所有藍牌都移除。"
    response = _post(api, rules_db, project, segment="s2")
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(new, ["subtitle"]))])
    _run(rules_db, llm)
    assert "只能修改段 s2" in llm.calls[0].kwargs["input"]
    assert _get(api, project, response.json()["id"]).json()["segment_key"] == "s2"


def test_unsupported_lists_alternatives(api, as_shop_staff, rules_db, project):
    alt = _alternative("改成淡入", _hide_title(rules_db, project))
    revision = _propose(api, rules_db, project, _unsupported(alt), request="標題旋轉著飛進來")
    body = _get(api, project, revision).json()
    assert body["outcome"] == "unsupported"
    assert body["reason"] == "沒有旋轉動作"
    [choice] = body["alternatives"]
    assert (choice["number"], choice["title"]) == (1, "改成淡入")
    assert choice["description"] == "改成淡入的說明"
    assert choice["segments"][0]["segment_key"] == "s1"
    assert choice["segments"][0]["changed"] == ["cues"]
    assert body["segments"] == []
    # 做不到的需求記在工作結果，給第 3 階段參考
    result = job_row(rules_db, uuid.UUID(revision)).result
    assert result["request"] == "標題旋轉著飛進來" and result["reason"] == "沒有旋轉動作"


def test_unknown_action_turns_into_alternatives(api, as_shop_staff, rules_db, project):
    spin = _editable(rules_db, project, "s1")
    spin["beats"][0]["cues"][1]["do"] = "spin"
    alt = _alternative("改成淡入", _hide_title(rules_db, project))
    revision = _propose(
        api, rules_db, project, _revise(_entry(spin, ["cues"])), _unsupported(alt, reason="")
    )
    body = _get(api, project, revision).json()
    assert body["outcome"] == "unsupported"
    assert "spin" in body["reason"]
    result = job_row(rules_db, uuid.UUID(revision)).result
    assert result["unsupported_actions"] == ["spin"]


def test_ambiguous_lists_candidates(api, as_shop_staff, rules_db, project):
    revision = _propose(api, rules_db, project, _ambiguous(), request="移除藍牌講慢一點")
    body = _get(api, project, revision).json()
    assert body["outcome"] == "ambiguous"
    assert body["reason"] == "兩段都在講移除藍牌"
    assert body["candidates"] == [
        {"segment_key": "s1", "segment_number": 1, "reason": "情況一移除藍牌"},
        {"segment_key": "s2", "segment_number": 2, "reason": "情況二移除藍牌"},
    ]


def test_rejected_twice_fails_job(api, as_shop_staff, rules_db, project):
    before = project_row(rules_db, project).video
    bad = _editable(rules_db, project, "s1")
    bad["segment_key"] = "s9"
    revision = _propose(
        api, rules_db, project, _revise(_entry(bad, ["cues"])), _revise(_entry(bad, ["cues"]))
    )
    body = _get(api, project, revision).json()
    assert body["status"] == "failed"
    assert body["error"] == REVISE_REJECTED_MESSAGE
    assert job_row(rules_db, uuid.UUID(revision)).error_detail  # 檢查沒過的原因給開發者看
    assert project_row(rules_db, project).video == before


def test_llm_unavailable_fails_job(api, as_shop_staff, rules_db, project):
    revision = _propose(api, rules_db, project, LLMUnavailable("連不上"))
    body = _get(api, project, revision).json()
    assert body["status"] == "failed" and body["error"] == REVISE_LLM_UNAVAILABLE_MESSAGE


def test_get_queued_revision(api, as_shop_staff, rules_db, project):
    revision = _post(api, rules_db, project).json()["id"]
    body = _get(api, project, revision).json()
    assert body["status"] == "queued" and body["outcome"] is None


def test_get_unknown_revision_is_404(api, as_shop_staff, rules_db, project):
    draft_job = insert_job(rules_db, project, kind="draft", status="succeeded")
    for revision in (uuid.uuid4(), draft_job):  # 不存在、不是修改的工作
        response = _get(api, project, revision)
        assert response.status_code == 404 and _code(response) == "RULES_VIDEO_REVISION_NOT_FOUND"


# --- 套用 ---


def test_apply_proposal(api, as_shop_staff, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    s2_before = _segment(rules_db, project, "s2")
    version = _version(rules_db, project)
    response = _apply(api, rules_db, project, revision)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["applied"] is True and body["applied_alternative"] is None
    assert body["video_version"] == version + 1
    assert body["coverage_message"] == COVERAGE_NOT_DONE_MESSAGE
    s1 = _segment(rules_db, project, "s1")
    assert s1["highlights"][0]["style"] == "red"
    assert s1["state"]["status"] == "stale"
    record = s1["revisions"][-1]
    assert record["kind"] == "revision" and record["request"] == REQUEST
    assert record["changed"] == ["highlights"] and record["unrequested"] == []
    assert record["number"] == 1
    assert _segment(rules_db, project, "s2") == s2_before  # 沒在提案裡的段原封不動
    assert _version(rules_db, project) == version + 1
    assert _get(api, project, revision).json()["applied"] is True


def test_apply_alternative(api, as_shop_staff, rules_db, project):
    first = _alternative("拿掉標題", _hide_title(rules_db, project))
    second_new = _editable(rules_db, project, "s2")
    second_new["beats"][0]["subtitle"] = "情況二：所有藍牌都移除。"
    second = {
        "title": "改字幕",
        "description": "改字幕的說明",
        "segments": [_entry(second_new, ["subtitle"])],
    }
    revision = _propose(api, rules_db, project, _unsupported(first, second))
    response = _apply(api, rules_db, project, revision, alternative=2)
    assert response.status_code == 200, response.text
    assert response.json()["applied_alternative"] == 2
    s2 = _segment(rules_db, project, "s2")
    assert s2["beats"][0]["subtitle"] == "情況二：所有藍牌都移除。"
    assert s2["revisions"][-1]["kind"] == "alternative"
    assert s2["revisions"][-1]["request"] == REQUEST
    assert "revisions" not in _segment(rules_db, project, "s1")  # 第 1 個替代做法沒套用


def test_revision_number_follows_asset_swap(api, as_shop_staff, rules_db, project):
    swap = api.patch(
        f"{URL}/{project}/segments/s1",
        json={"slot": "sidebar", "asset_key": "blue", "video_version": _version(rules_db, project)},
    )
    assert swap.status_code == 200, swap.text
    new = _editable(rules_db, project, "s1")
    new["highlights"][0]["style"] = "red"
    revision = _propose(api, rules_db, project, _revise(_entry(new, ["highlights"])))
    assert _apply(api, rules_db, project, revision).status_code == 200
    assert [r["number"] for r in _segment(rules_db, project, "s1")["revisions"]] == [1, 2]


def test_apply_with_old_version_is_409(api, as_shop_staff, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    before = project_row(rules_db, project).video
    response = _apply(api, rules_db, project, revision, version=_version(rules_db, project) - 1)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_CONFLICT"
    assert project_row(rules_db, project).video == before


def test_apply_after_draft_changed_is_409(api, as_shop_staff, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    swap = api.patch(
        f"{URL}/{project}/segments/s2",
        json={"slot": "main", "asset_key": "blue", "video_version": _version(rules_db, project)},
    )
    assert swap.status_code == 200, swap.text
    before = project_row(rules_db, project).video
    response = _apply(api, rules_db, project, revision)  # 帶的是最新版本，但提案是舊版算的
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_REVISION_STALE"
    assert project_row(rules_db, project).video == before


def test_apply_twice_is_409(api, as_shop_staff, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    assert _apply(api, rules_db, project, revision).status_code == 200
    response = _apply(api, rules_db, project, revision)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_REVISION_APPLIED"


def test_apply_unfinished_is_409(api, as_shop_staff, rules_db, project):
    revision = _post(api, rules_db, project).json()["id"]
    response = _apply(api, rules_db, project, revision)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_REVISION_NOT_READY"


def test_apply_failed_is_409(api, as_shop_staff, rules_db, project):
    revision = _propose(api, rules_db, project, LLMUnavailable("連不上"))
    response = _apply(api, rules_db, project, revision)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_REVISION_FAILED"


def test_apply_ambiguous_is_409(api, as_shop_staff, rules_db, project):
    revision = _propose(api, rules_db, project, _ambiguous())
    response = _apply(api, rules_db, project, revision)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_REVISION_AMBIGUOUS"


@pytest.mark.parametrize(
    ("outputs", "alternative", "code"),
    [
        ("unsupported", None, "RULES_VIDEO_REVISION_ALTERNATIVE_REQUIRED"),
        ("unsupported", 2, "RULES_VIDEO_REVISION_ALTERNATIVE_INVALID"),
        ("proposal", 1, "RULES_VIDEO_REVISION_ALTERNATIVE_INVALID"),
    ],
)
def test_apply_alternative_errors(
    api, as_shop_staff, rules_db, project, outputs, alternative, code
):
    if outputs == "unsupported":
        output = _unsupported(_alternative("拿掉標題", _hide_title(rules_db, project)))
    else:
        output = _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    revision = _propose(api, rules_db, project, output)
    response = _apply(api, rules_db, project, revision, alternative=alternative)
    assert response.status_code == 422 and _code(response) == code


def test_apply_needs_applied_status(api, as_shop_staff, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    assert _apply(api, rules_db, project, revision, status="cancelled").status_code == 422


def test_apply_unknown_revision_is_404(api, as_shop_staff, rules_db, project):
    response = _apply(api, rules_db, project, uuid.uuid4())
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_REVISION_NOT_FOUND"


# --- 權限 ---


def test_admin_can_revise_other_shop(api, as_admin, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    assert _apply(api, rules_db, project, revision).status_code == 200


def test_other_shop_is_404(api, app, rules_db, project):
    from app.core.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: OTHER_STAFF
    response = _post(api, rules_db, project)
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_other_shop_cannot_see_or_apply(api, app, as_shop_staff, rules_db, project):
    revision = _propose(
        api, rules_db, project, _revise(_entry(_gold_to_red(rules_db, project), ["highlights"]))
    )
    from app.core.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: OTHER_STAFF
    assert _get(api, project, revision).status_code == 404
    assert _apply(api, rules_db, project, revision).status_code == 404


def test_player_is_403(api, as_player, rules_db, project):
    assert _post(api, rules_db, project).status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, rules_db, project):
    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert _post(client, rules_db, project, version=1).status_code == 401
