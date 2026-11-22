"""規則影片的非同步工作（spec rules-video-studio「非同步工作」，add-rules-video-mobile MR 2）。

建立工作測 service；執行測 JobRunner.run_once()（不開執行緒，結果才確定）；
只有「執行緒實際運作」與「啟動時的處理」會真的啟動後端，用輪流檢查、有上限的等待。
處理函式一律用測試裡手寫的 FakeJobHandler（真正的處理函式在 MR 4、MR 8、MR 10）。
"""

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError
from app.domains.rules_qa.repository import VideoJobRepository, VideoProjectRepository
from app.domains.rules_qa.service import VideoJobService
from app.domains.rules_qa.video_jobs import (
    ERROR_DETAIL_MAX_CHARS,
    INTERRUPTED_MESSAGE,
    NO_HANDLER_MESSAGE,
    TIMEOUT_MESSAGE,
    UNEXPECTED_MESSAGE,
    JobContext,
    JobFailed,
    JobRunner,
    recover_interrupted_jobs,
)
from tests.conftest import TEST_PLAYER, TEST_SHOP_STAFF
from tests.rules_qa.video_support import (
    OTHER_STAFF,
    insert_job,
    insert_project,
    job_row,
    seed_people,
)

LOGGER = "app.domains.rules_qa.video_jobs"


class FakeJobHandler:
    """手寫的 fake 處理函式：依設定回報進度、回傳結果或拋出例外，並記下被呼叫的工作。"""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        *,
        error: BaseException | None = None,
        steps: list[tuple[float, str]] | None = None,
        during: Callable[[JobContext], None] | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.steps = steps or []
        self.during = during
        self.calls: list[uuid.UUID] = []

    def __call__(self, ctx: JobContext) -> dict[str, Any] | None:
        self.calls.append(ctx.job_id)
        for progress, message in self.steps:
            ctx.report(progress, message)
        if self.during is not None:
            self.during(ctx)
        if self.error is not None:
            raise self.error
        return self.result


class FakeBrokenJobRepository(VideoJobRepository):
    """手寫的 fake：寫入結束結果時出錯（模擬資料庫斷線），其他照常。"""

    def finish_succeeded(self, job_id: uuid.UUID, result: dict[str, Any] | None) -> None:
        raise RuntimeError("資料庫斷線（測試）")

    def finish_failed(self, job_id: uuid.UUID, error: str, detail: str | None) -> None:
        raise RuntimeError("資料庫斷線（測試）")


@pytest.fixture
def factory(rules_db: Engine) -> sessionmaker[Session]:
    seed_people(rules_db)
    return sessionmaker(rules_db)


@pytest.fixture
def project(rules_db: Engine, factory: sessionmaker[Session], add_game) -> uuid.UUID:
    return insert_project(rules_db, add_game("血與刃的白薔薇"))


def _create(
    factory: sessionmaker[Session],
    project: uuid.UUID,
    kind: str = "draft",
    user: CurrentUser = TEST_SHOP_STAFF,
    notify: Callable[[], None] | None = None,
):
    with factory() as session:
        service = VideoJobService(
            VideoJobRepository(session), VideoProjectRepository(session), notify=notify
        )
        return service.create(user, project, kind)


def _runner(factory: sessionmaker[Session], **handlers: FakeJobHandler) -> JobRunner:
    return JobRunner(factory, handlers)


# --- 建立工作 ---


def test_create_job_is_queued_and_notifies(factory, project):
    notified: list[bool] = []
    job = _create(factory, project, notify=lambda: notified.append(True))
    assert job.status == "queued" and job.progress == 0 and job.kind == "draft"
    assert job.project_id == project
    assert notified == [True]


@pytest.mark.parametrize("active", ["queued", "running"])
def test_second_active_job_is_409(rules_db, factory, project, active):
    first = insert_job(rules_db, project, status=active, started_minutes_ago=1)
    with pytest.raises(AppError) as exc:
        _create(factory, project)
    assert exc.value.status_code == 409 and exc.value.code == "RULES_VIDEO_JOB_RUNNING"
    assert exc.value.details["job_id"] == str(first)


@pytest.mark.parametrize("finished", ["succeeded", "failed"])
def test_after_finished_job_can_create(rules_db, factory, project, finished):
    insert_job(rules_db, project, status=finished)
    assert _create(factory, project).status == "queued"


def test_different_projects_are_independent(rules_db, factory, project, add_game):
    other = insert_project(rules_db, add_game("另一款"))
    _create(factory, project)
    assert _create(factory, other).status == "queued"


def test_stale_running_job_is_replaced(rules_db, factory, project):
    stale = insert_job(rules_db, project, status="running", started_minutes_ago=31)
    job = _create(factory, project)
    assert job.status == "queued"
    row = job_row(rules_db, stale)
    assert row.status == "failed" and row.error == TIMEOUT_MESSAGE == "工作逾時，已中止"
    assert row.finished_at is not None


def test_recent_running_job_is_still_409(rules_db, factory, project):
    insert_job(rules_db, project, status="running", started_minutes_ago=29)
    with pytest.raises(AppError) as exc:
        _create(factory, project)
    assert exc.value.status_code == 409


def test_create_for_other_shop_is_404(rules_db, factory, add_game):
    other = insert_project(rules_db, add_game("別家的遊戲"), OTHER_STAFF)
    with pytest.raises(AppError) as exc:
        _create(factory, other)
    assert exc.value.status_code == 404 and exc.value.code == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_player_cannot_create(factory, project):
    with pytest.raises(AppError) as exc:
        _create(factory, project, user=TEST_PLAYER)
    assert exc.value.status_code == 403


# --- 執行（run_once） ---


def test_success_records_result(rules_db, factory, project):
    job = _create(factory, project)
    handler = FakeJobHandler({"segments": 3})
    assert _runner(factory, draft=handler).run_once() is True
    row = job_row(rules_db, job.id)
    assert handler.calls == [job.id]
    assert row.status == "succeeded" and row.result == {"segments": 3} and row.progress == 1
    assert row.started_at is not None and row.finished_at is not None
    assert row.error is None and row.error_detail is None


def test_progress_is_visible_while_running(rules_db, factory, project):
    job = _create(factory, project)
    seen: list[tuple[str, float, str]] = []

    def look(ctx: JobContext) -> None:
        row = job_row(rules_db, ctx.job_id)
        seen.append((row.status, row.progress, row.message))

    handler = FakeJobHandler({}, steps=[(0.5, "段影片 2／3")], during=look)
    _runner(factory, draft=handler).run_once()
    assert seen == [("running", 0.5, "段影片 2／3")]
    assert job_row(rules_db, job.id).status == "succeeded"


def test_job_failed_uses_given_message(rules_db, factory, project):
    job = _create(factory, project)
    _runner(factory, draft=FakeJobHandler(error=JobFailed("找不到第 5 頁"))).run_once()
    row = job_row(rules_db, job.id)
    assert row.status == "failed" and row.error == "找不到第 5 頁"
    assert row.finished_at is not None


def test_unexpected_exception_is_recorded_and_logged(rules_db, factory, project, caplog):
    job = _create(factory, project)
    caplog.set_level(logging.ERROR, logger=LOGGER)
    _runner(factory, draft=FakeJobHandler(error=ValueError("壞掉的段資料"))).run_once()
    row = job_row(rules_db, job.id)
    assert row.status == "failed"
    assert row.error == UNEXPECTED_MESSAGE
    assert row.error_detail.startswith("ValueError") and "壞掉的段資料" in row.error_detail
    records = [r for r in caplog.records if r.name == LOGGER]
    assert records and records[-1].exc_info is not None
    assert str(job.id) in records[-1].getMessage() and "draft" in records[-1].getMessage()


def test_long_error_detail_is_truncated(rules_db, factory, project):
    job = _create(factory, project)
    _runner(factory, draft=FakeJobHandler(error=ValueError("x" * 5000))).run_once()
    assert len(job_row(rules_db, job.id).error_detail) == ERROR_DETAIL_MAX_CHARS == 2000


def test_kind_without_handler_fails(rules_db, factory, project):
    job = _create(factory, project, kind="render")
    _runner(factory, draft=FakeJobHandler({})).run_once()
    row = job_row(rules_db, job.id)
    assert row.status == "failed" and row.error == NO_HANDLER_MESSAGE


def test_oldest_first_one_at_a_time(rules_db, factory, project, add_game):
    other = insert_project(rules_db, add_game("另一款"))
    first = _create(factory, project)
    second = _create(factory, other)
    handler = FakeJobHandler({})
    runner = _runner(factory, draft=handler)
    runner.run_once()
    assert handler.calls == [first.id]
    assert job_row(rules_db, second.id).status == "queued"
    runner.run_once()
    assert handler.calls == [first.id, second.id]


def test_empty_queue(factory, project):
    assert _runner(factory, draft=FakeJobHandler({})).run_once() is False


def test_recording_failure_is_logged_and_released_after_timeout(rules_db, factory, project, caplog):
    job = _create(factory, project)
    caplog.set_level(logging.ERROR, logger=LOGGER)
    runner = JobRunner(factory, {"draft": FakeJobHandler({})}, FakeBrokenJobRepository)
    assert runner.run_once() is True  # 不讓例外跑出執行緒
    assert job_row(rules_db, job.id).status == "running"
    assert any(str(job.id) in r.getMessage() for r in caplog.records if r.name == LOGGER)
    # 30 分鐘後，建立新工作時被釋放
    with rules_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE rules_qa_video_jobs SET started_at = now() - interval '31 minutes' "
                "WHERE id = :i"
            ),
            {"i": job.id},
        )
    assert _create(factory, project).status == "queued"
    assert job_row(rules_db, job.id).error == TIMEOUT_MESSAGE


def test_late_finish_does_not_overwrite_timeout(rules_db, factory, project):
    job = _create(factory, project)

    def expire_meanwhile(ctx: JobContext) -> None:
        # 處理中途被判逾時、另一個工作已經建立
        with rules_db.begin() as conn:
            conn.execute(
                text(
                    "UPDATE rules_qa_video_jobs SET started_at = now() - interval '31 minutes' "
                    "WHERE id = :i"
                ),
                {"i": ctx.job_id},
            )
        _create(factory, project)
        ctx.report(0.9, "快做完了")

    _runner(factory, draft=FakeJobHandler({"late": True}, during=expire_meanwhile)).run_once()
    row = job_row(rules_db, job.id)
    assert row.status == "failed" and row.error == TIMEOUT_MESSAGE
    assert row.result is None and row.progress != 0.9


# --- 伺服器重新啟動 ---


def test_recover_marks_running_failed_keeps_queued(rules_db, factory, project, add_game):
    running = insert_job(rules_db, project, status="running", started_minutes_ago=1)
    other = insert_project(rules_db, add_game("另一款"))
    queued = insert_job(rules_db, other)
    done = insert_job(rules_db, insert_project(rules_db, add_game("第三款")), status="succeeded")
    assert recover_interrupted_jobs(factory) == 1
    row = job_row(rules_db, running)
    assert row.status == "failed" and row.error == INTERRUPTED_MESSAGE
    assert row.finished_at is not None
    assert job_row(rules_db, queued).status == "queued"
    assert job_row(rules_db, done).status == "succeeded"


# --- 真的啟動後端：執行緒與啟動時的處理 ---


def _wait_until(check: Callable[[], bool], timeout: float = 10.0) -> bool:
    """輪流檢查，最多等 timeout 秒。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return check()


def _app(make_settings, test_db_url: str, **settings: object):
    from app.main import create_app

    app = create_app(make_settings(database_url=test_db_url, **settings))
    app.dependency_overrides[get_current_user] = lambda: TEST_SHOP_STAFF
    return app


def test_worker_thread_processes_job(rules_db, factory, project, make_settings, test_db_url):
    app = _app(make_settings, test_db_url, rules_video_worker=True)
    handler = FakeJobHandler({"ok": True})
    app.state.rules_video_job_handlers["draft"] = handler
    with TestClient(app) as client:
        runner = app.state.rules_video_runner
        assert runner is not None and runner.is_alive()
        job = _create(factory, project, notify=runner.notify)
        url = f"/api/v1/rules-videos/{project}/jobs/{job.id}"
        assert _wait_until(lambda: client.get(url).json()["status"] == "succeeded")
        assert client.get(url).json()["result"] == {"ok": True}
    assert not runner.is_alive()  # 關閉後端時執行緒停止


def test_startup_marks_running_failed(rules_db, factory, project, make_settings, test_db_url):
    running = insert_job(rules_db, project, status="running", started_minutes_ago=1)
    app = _app(make_settings, test_db_url, rules_video_worker=True)
    with TestClient(app):
        row = job_row(rules_db, running)
        assert row.status == "failed" and row.error == INTERRUPTED_MESSAGE


def test_worker_disabled(rules_db, factory, project, make_settings, test_db_url):
    running = insert_job(rules_db, project, status="running", started_minutes_ago=1)
    app = _app(make_settings, test_db_url, rules_video_worker=False)
    with TestClient(app):
        assert app.state.rules_video_runner is None
        assert job_row(rules_db, running).status == "running"
