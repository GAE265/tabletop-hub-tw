"""規則影片的非同步工作：背景執行緒依序處理（add-rules-video-mobile design.md D2）。

- 後端啟動時（lifespan）先把中斷的 running 工作標為失敗，再開一個執行緒；關閉時停止。
- 執行緒每次取一個最早建立的 queued 工作，依 kind 找處理函式執行。有新工作時立刻被通知，
  平常每 POLL_SECONDS 秒檢查一次。
- 處理函式拋出例外不會讓執行緒停下：log 記下堆疊，工作標為失敗（error 給店員、
  error_detail 給開發者）。寫入結果本身又出錯時只記 log，那個工作留在 running，
  JOB_TIMEOUT_MINUTES 分鐘後建立新工作時被釋放。
- 處理函式（MR 4、MR 8、MR 10）呼叫 LLM、TTS、ffmpeg 都必須自己設逾時，不能依賴
  JOB_TIMEOUT_MINUTES 的出口。
- 已知限制：假設後端只有一個程序；伺服器重新啟動會中斷進行中的工作。
"""

import logging
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.domains.rules_qa.repository import ClaimedJob, VideoJobRepository

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
JOB_TIMEOUT_MINUTES = 30
ERROR_DETAIL_MAX_CHARS = 2000

TIMEOUT_MESSAGE = "工作逾時，已中止"
INTERRUPTED_MESSAGE = "伺服器重新啟動，工作中斷，請重新開始"
UNEXPECTED_MESSAGE = "發生未預期的錯誤，請重試；若持續發生請通知管理員"
NO_HANDLER_MESSAGE = "這種工作還沒有實作"


class JobFailed(Exception):
    """處理函式用來回報「店員看得懂的失敗原因」；訊息直接寫進工作的 error。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class JobContext:
    """交給處理函式的工作資訊。report() 用獨立的短交易寫入進度，店員查詢時看得到。"""

    job_id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    session_factory: sessionmaker[Session]
    _report: Callable[[uuid.UUID, float, str | None], None]

    def report(self, progress: float, message: str | None = None) -> None:
        self._report(self.job_id, min(max(progress, 0.0), 1.0), message)


JobHandler = Callable[[JobContext], dict[str, Any] | None]
RepositoryFactory = Callable[[Session], VideoJobRepository]


def recover_interrupted_jobs(
    session_factory: sessionmaker[Session],
    repository: RepositoryFactory = VideoJobRepository,
) -> int:
    """伺服器重新啟動時：所有 running 的工作標為失敗；queued 保留，之後照常處理。"""
    with session_factory() as session:
        repo = repository(session)
        with repo.transaction():
            count = repo.fail_running(INTERRUPTED_MESSAGE)
    if count:
        logger.warning("伺服器重新啟動：%d 個進行中的規則影片工作標為失敗", count)
    return count


class JobRunner:
    """一個背景執行緒，依序處理規則影片的工作。測試可以不開執行緒，直接呼叫 run_once()。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        handlers: Mapping[str, JobHandler],
        repository: RepositoryFactory = VideoJobRepository,
    ) -> None:
        self._session_factory = session_factory
        # 不複製：之後註冊的處理函式（MR 4 起）也看得到
        self._handlers = handlers
        self._repository = repository
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- 執行緒 ---

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="rules-video-jobs", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def notify(self) -> None:
        """有新工作：叫醒執行緒立刻取，不用等下一次檢查。"""
        self._wake.set()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self.run_once()
            except Exception:  # run_once 自己會接住；這裡是最後一道防線，執行緒不能停
                logger.exception("規則影片工作的執行緒發生未預期的錯誤")
                worked = False
            if not worked:
                self._wake.wait(POLL_SECONDS)
                self._wake.clear()

    # --- 處理一個工作 ---

    def run_once(self) -> bool:
        """處理一個等待中的工作；沒有工作回 False。任何例外都不會傳出去。"""
        try:
            job = self._write(lambda repo: repo.claim_next())
        except Exception:
            logger.exception("取規則影片工作時出錯")
            return False
        if job is None:
            return False
        try:
            handler = self._handlers.get(job.kind)
            if handler is None:
                raise JobFailed(NO_HANDLER_MESSAGE)
            context = JobContext(
                job.id, job.project_id, job.kind, self._session_factory, self._report
            )
            result = handler(context)
        except JobFailed as exc:
            logger.info("規則影片工作 %s（%s）失敗：%s", job.id, job.kind, exc.message)
            self._finish(job, error=exc.message, detail=None)
        except Exception as exc:
            logger.exception("規則影片工作 %s（%s）發生未預期的錯誤", job.id, job.kind)
            detail = f"{type(exc).__name__}: {exc}"[:ERROR_DETAIL_MAX_CHARS]
            self._finish(job, error=UNEXPECTED_MESSAGE, detail=detail)
        else:
            self._finish(job, result=result)
        return True

    def _write(self, action: Callable[[VideoJobRepository], Any]) -> Any:
        with self._session_factory() as session:
            repo = self._repository(session)
            with repo.transaction():
                return action(repo)

    def _report(self, job_id: uuid.UUID, progress: float, message: str | None) -> None:
        self._write(lambda repo: repo.report(job_id, progress, message))

    def _finish(
        self,
        job: ClaimedJob,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        detail: str | None = None,
    ) -> None:
        """寫入結束結果；寫入本身出錯只記 log，工作留在 running，逾時後建立新工作時釋放。"""
        try:
            if error is None:
                self._write(lambda repo: repo.finish_succeeded(job.id, result))
            else:
                self._write(lambda repo: repo.finish_failed(job.id, error, detail))
        except Exception:
            logger.exception(
                "記錄規則影片工作 %s（%s）的結果時出錯；工作留在 running，"
                "%d 分鐘後建立新工作時釋放",
                job.id,
                job.kind,
                JOB_TIMEOUT_MINUTES,
            )
