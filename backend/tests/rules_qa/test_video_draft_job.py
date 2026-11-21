"""草稿工作的處理函式（spec rules-video-studio「草稿（MR 5）」，design.md D11）。

工作用 JobRunner.run_once() 執行（不開執行緒）；LLM 一律用 FakeLLMProvider（AGENTS.md 7.6）。
"""

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.domains.rules_qa.video_draft import (
    DRAFT_CONFLICT_MESSAGE,
    DRAFT_LLM_REJECTED_MESSAGE,
    DRAFT_LLM_UNAVAILABLE_MESSAGE,
    DraftJobHandler,
)
from app.domains.rules_qa.video_jobs import JobRunner
from app.integrations.llm.errors import LLMOutputRejected, LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider
from tests.rules_qa.video_draft_support import (
    EDITED_MARK,
    ORIGINAL_ONLY,
    FakeHookLLM,
    add_manual,
    project_row,
    set_pages,
    upload_terms,
)
from tests.rules_qa.video_script_support import (
    FAKE_REFERENCE_PAGE,
    coverage_output,
    coverage_rule,
    llm_output,
)
from tests.rules_qa.video_support import insert_job, insert_project, job_row, seed_people


@pytest.fixture
def factory(rules_db: Engine) -> sessionmaker[Session]:
    seed_people(rules_db)
    return sessionmaker(rules_db)


@pytest.fixture
def game(factory, add_game, add_pages) -> int:
    game = add_game("假遊戲")
    add_manual(add_pages, game)
    return game


@pytest.fixture
def project(rules_db: Engine, game: int) -> uuid.UUID:
    project = insert_project(rules_db, game)
    set_pages(rules_db, project)
    return project


def _run(factory, rules_db, project, llm) -> uuid.UUID:
    job = insert_job(rules_db, project, kind="draft")
    assert JobRunner(factory, {"draft": DraftJobHandler(llm)}).run_once()
    return job


def _bad_output() -> dict:
    bad = llm_output()
    bad["segments"][0]["beats"][0]["narration"] = "每次都洗牌。"
    return bad


# --- 成功 ---


def test_draft_is_saved_with_coverage(factory, rules_db, project):
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    job = _run(factory, rules_db, project, llm)
    row = job_row(rules_db, job)
    assert row.status == "succeeded", row.error
    saved = project_row(rules_db, project)
    assert [s["segment_key"] for s in saved.video["segments"]] == ["s1", "s2"]
    assert saved.video_version == 1
    assert saved.coverage["status"] == "done" and saved.coverage["report"]["rules"]
    assert saved.coverage_version == 1
    assert saved.draft_pages_version == saved.pages_version == 1
    result = row.result
    assert result["segments"] == 2 and result["beats"] == 3
    assert result["assets"] == 4 and result["pending_photos"] == 4
    assert result["coverage"] == "done" and result["terms"] == "missing"
    assert isinstance(result["cleanup"], list)


def test_ai_and_coverage_read_edited_text(factory, rules_db, project):
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    _run(factory, rules_db, project, llm)
    draft_input = llm.calls[0].kwargs["input"]
    coverage_input = llm.calls[1].kwargs["input"]
    for text_ in (draft_input, coverage_input):
        assert EDITED_MARK in text_  # 編輯後才有的句子
        assert ORIGINAL_ONLY not in text_  # 店員刪掉的段落
    assert FAKE_REFERENCE_PAGE.splitlines()[0] in draft_input  # 參考頁給 AI 查牌名
    assert FAKE_REFERENCE_PAGE.splitlines()[0] not in coverage_input  # 涵蓋檢查只看本章頁


@pytest.mark.parametrize("terms, status", [(None, "used"), ([], "empty")], ids=["used", "empty"])
def test_terms_status(factory, rules_db, project, game, terms, status):
    upload_terms(rules_db, game, terms)
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    job = _run(factory, rules_db, project, llm)
    assert job_row(rules_db, job).result["terms"] == status
    used = "紅牌" in llm.calls[0].kwargs["input"]
    assert used is (status == "used")


def test_rewrite_once_then_succeed(factory, rules_db, project):
    llm = FakeLLMProvider(json_outputs=[_bad_output(), llm_output(), coverage_output()])
    job = _run(factory, rules_db, project, llm)
    assert job_row(rules_db, job).status == "succeeded"
    assert len(llm.calls) == 3  # 產生、改寫、涵蓋檢查


def test_regenerate_replaces_and_bumps_version(factory, rules_db, project):
    _run(
        factory, rules_db, project, FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    )
    second = llm_output()
    second["segments"][1]["beats"][0]["subtitle"] = "Second draft."
    _run(factory, rules_db, project, FakeLLMProvider(json_outputs=[second, coverage_output()]))
    saved = project_row(rules_db, project)
    assert saved.video_version == 2 and saved.coverage_version == 2
    assert saved.video["segments"][1]["beats"][0]["subtitle"] == "Second draft."


# --- 失敗時原本的草稿不變 ---


def _with_existing_draft(factory, rules_db, project):
    _run(
        factory, rules_db, project, FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    )
    return project_row(rules_db, project)


def test_rejected_twice_keeps_previous_draft(factory, rules_db, project):
    before = _with_existing_draft(factory, rules_db, project)
    llm = FakeLLMProvider(json_outputs=[_bad_output(), _bad_output()])
    row = job_row(rules_db, _run(factory, rules_db, project, llm))
    assert row.status == "failed"
    # 整本範圍（2026-11-22 永傑決定）：店員看到的訊息不含檢查細節，原因改放 error_detail
    assert row.error.startswith("AI 產生的草稿沒有通過檢查")
    assert "使用了「次」" not in row.error and "使用了「次」" in row.error_detail
    after = project_row(rules_db, project)
    assert after.video == before.video and after.video_version == before.video_version


@pytest.mark.parametrize(
    "error, message",
    [
        (LLMUnavailable("連不上"), DRAFT_LLM_UNAVAILABLE_MESSAGE),
        (LLMOutputRejected("被擋下"), DRAFT_LLM_REJECTED_MESSAGE),
    ],
    ids=["unavailable", "rejected"],
)
def test_llm_failure_keeps_previous_draft(factory, rules_db, project, error, message):
    before = _with_existing_draft(factory, rules_db, project)
    row = job_row(rules_db, _run(factory, rules_db, project, FakeLLMProvider(json_outputs=[error])))
    assert row.status == "failed" and row.error == message
    after = project_row(rules_db, project)
    assert after.video == before.video and after.video_version == before.video_version


def test_project_changed_during_job_is_not_overwritten(factory, rules_db, project):
    before = _with_existing_draft(factory, rules_db, project)

    def someone_edits() -> None:
        with rules_db.begin() as conn:
            conn.execute(
                text(
                    "UPDATE rules_qa_video_projects SET video_version = video_version + 1 "
                    "WHERE id = :p"
                ),
                {"p": project},
            )

    # 第 2 次呼叫（涵蓋檢查）之前，專案被別的操作改過
    llm = FakeHookLLM([llm_output(), coverage_output()], hook_at=2, hook=someone_edits)
    row = job_row(rules_db, _run(factory, rules_db, project, llm))
    assert row.status == "failed" and row.error == DRAFT_CONFLICT_MESSAGE
    after = project_row(rules_db, project)
    assert after.video == before.video
    assert after.video_version == before.video_version + 1  # 只有別人那一次


# --- 涵蓋檢查沒做成：草稿照樣存 ---


@pytest.mark.parametrize(
    "coverage, reason",
    [(LLMUnavailable("連不上"), "連不上"), (coverage_output([]), "沒有拆出任何規則")],
    ids=["llm_unavailable", "empty_rules"],
)
def test_coverage_not_done_still_saves_draft(factory, rules_db, project, coverage, reason):
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage])
    row = job_row(rules_db, _run(factory, rules_db, project, llm))
    assert row.status == "succeeded" and row.result["coverage"] == "not_done"
    saved = project_row(rules_db, project)
    assert saved.video is not None and saved.video_version == 1
    assert saved.coverage["status"] == "not_done" and reason in saved.coverage["reason"]
    assert saved.coverage_version == 1


def test_coverage_issues_are_kept(factory, rules_db, project):
    rule = coverage_rule(narration=("incomplete", ["b1"], "同時翻開"))
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage_output([rule])])
    _run(factory, rules_db, project, llm)
    report = project_row(rules_db, project).coverage["report"]
    assert report["rules"][0]["narration"]["missing"] == "同時翻開"


def test_coverage_records_text_hash(factory, rules_db, project):
    # 涵蓋檢查記下旁白與字幕的雜湊，之後用來判斷是否過期（2026-11-21 永傑決定）
    from app.domains.rules_qa.video_draft import narration_text_hash

    _run(
        factory, rules_db, project, FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    )
    saved = project_row(rules_db, project)
    assert saved.coverage["text_hash"] == narration_text_hash(saved.video)


def test_text_hash_ignores_assets_but_not_subtitles() -> None:
    from app.domains.rules_qa.video_draft import narration_text_hash

    video = {"segments": [{"beats": [{"narration": "甲", "subtitle": "乙"}]}], "assets": []}
    same = {**video, "assets": [{"asset_key": "x", "file": "x.jpg"}]}
    changed = {"segments": [{"beats": [{"narration": "甲", "subtitle": "丙"}]}], "assets": []}
    assert narration_text_hash(video) == narration_text_hash(same)
    assert narration_text_hash(video) != narration_text_hash(changed)
