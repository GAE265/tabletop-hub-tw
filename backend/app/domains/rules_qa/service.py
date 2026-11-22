"""規則教學與問答的商業規則：教學清單與內容、設定教學影片、建立索引、規則問答、權限。

不 import FastAPI（AGENTS.md 4.2）；錯誤一律拋 AppError，由錯誤處理器轉成統一格式。
"""

import logging
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol

from app.core.auth import CurrentUser, require_role
from app.core.errors import AppError, PermissionDenied
from app.domains.rules_qa import prompts
from app.domains.rules_qa.chunking import split_pages
from app.domains.rules_qa.repository import (
    ActiveJobExists,
    ChunkHit,
    LessonSummary,
    VideoJobRecord,
    VideoProjectRecord,
    VideoRecord,
)
from app.domains.rules_qa.schemas import (
    Citation,
    MessageRequest,
    MessageResponse,
    RulesLessonItem,
    RulesLessonList,
    RulesLessonOut,
    VideoJobList,
    VideoJobOut,
    VideoOut,
    VideoProjectCreate,
    VideoProjectList,
    VideoProjectOut,
    VideoRequest,
)
from app.domains.rules_qa.video_jobs import JOB_TIMEOUT_MINUTES, TIMEOUT_MESSAGE
from app.domains.rules_qa.youtube import parse_youtube_id
from app.integrations.embedding import EmbeddingError, EmbeddingProvider
from app.integrations.llm import LLMProvider
from app.integrations.llm.errors import LLMConversationNotFound, LLMError, LLMUnavailable
from app.integrations.llm.types import LLMResponse

logger = logging.getLogger(__name__)

# 每次問答交給 LLM 的段落數（design.md D6）
SEARCH_LIMIT = 6
# 教學與問答的回答不使用「次」（AGENTS.md §10.2）
FORBIDDEN_WORD = "次"


class RulesQaRepositoryProtocol(Protocol):
    """service 需要的資料存取介面；正式實作是 RulesQaRepository，測試用 FakeRulesQaRepository。"""

    def transaction(self) -> AbstractContextManager[None]: ...
    def game_name(self, game_id: int) -> str | None: ...
    def lesson_summaries(self) -> list[LessonSummary]: ...
    def get_video(self, game_id: int) -> VideoRecord | None: ...
    def upsert_video(self, video: VideoRecord) -> None: ...
    def has_chunks(self, game_id: int) -> bool: ...
    def replace_chunks(
        self, game_id: int, chunks: Sequence[tuple[int, str, list[float]]], embedding_model: str
    ) -> None: ...
    def search_chunks(
        self, game_id: int, vector: Sequence[float], embedding_model: str, limit: int
    ) -> list[ChunkHit]: ...


class NoRulebookPages(Exception):
    """這款遊戲還沒有規則書頁面，無法建立索引。"""


def _game_not_found(game_id: int) -> AppError:
    return AppError(404, "GAME_NOT_FOUND", f"找不到桌遊 {game_id}")


def _unavailable() -> AppError:
    return AppError(503, "RULES_QA_UNAVAILABLE", "規則問答暫時無法使用，請稍後再試")


@contextmanager
def _external_services() -> Iterator[None]:
    """把 LLM、embedding 的錯誤轉成 API 錯誤（比照推薦 Agent）。"""
    try:
        yield
    except LLMConversationNotFound as exc:
        raise AppError(404, "RULES_QA_CONVERSATION_NOT_FOUND", "對話已過期，請開始新對話") from exc
    except (LLMUnavailable, EmbeddingError) as exc:
        logger.warning("規則問答暫時無法使用：%s", exc)
        raise _unavailable() from exc


def build_index(
    repository: RulesQaRepositoryProtocol,
    read_pages: Callable[[int], list[tuple[int, str]] | None],
    embedding: EmbeddingProvider,
    embedding_model: str,
    game_id: int,
) -> int:
    """讀取規則書頁面、切段、轉成向量，取代這款遊戲的所有段落；回傳段落數。

    read_pages 是 rules_ingest 提供的讀取函式（design.md D4）。沒有頁面時拋 NoRulebookPages，
    不動原本的段落。
    """
    pages = read_pages(game_id) or []
    chunks = split_pages(pages)
    if not chunks:
        raise NoRulebookPages(game_id)
    vectors = embedding.embed([chunk.content for chunk in chunks])
    with repository.transaction():
        repository.replace_chunks(
            game_id,
            [(c.page, c.content, v) for c, v in zip(chunks, vectors, strict=True)],
            embedding_model,
        )
    return len(chunks)


class RulesQaService:
    def __init__(
        self,
        repository: RulesQaRepositoryProtocol,
        *,
        embedding: EmbeddingProvider,
        embedding_model: str,
        llm: LLMProvider,
    ) -> None:
        self._repo = repository
        self._embedding = embedding
        self._embedding_model = embedding_model
        self._llm = llm

    # --- 教學清單與內容 ---

    def list_lessons(self, user: CurrentUser) -> RulesLessonList:
        require_role(user, "player", "shop_staff", "admin")
        summaries = sorted(self._repo.lesson_summaries(), key=lambda s: (s.game_name, s.game_id))
        items = [
            RulesLessonItem(
                game_id=s.game_id,
                game_name=s.game_name,
                has_video=s.has_video,
                has_rulebook=s.has_rulebook,
            )
            for s in summaries
        ]
        return RulesLessonList(items=items, total=len(items))

    def get_lesson(self, user: CurrentUser, game_id: int) -> RulesLessonOut:
        require_role(user, "player", "shop_staff", "admin")
        name = self._game_name(game_id)
        video = self._repo.get_video(game_id)
        has_rulebook = self._repo.has_chunks(game_id)
        if video is None and not has_rulebook:
            raise AppError(404, "RULES_LESSON_NOT_FOUND", "這款遊戲還沒有規則教學的教材")
        return RulesLessonOut(
            game_id=game_id,
            game_name=name,
            video=None if video is None else _video_out(video),
            has_rulebook=has_rulebook,
            suggested_questions=list(prompts.SUGGESTED_QUESTIONS),
        )

    # --- 設定教學影片 ---

    def set_video(self, user: CurrentUser, game_id: int, data: VideoRequest) -> VideoOut:
        require_role(user, "shop_staff", "admin")
        self._game_name(game_id)
        youtube_id = parse_youtube_id(data.video_url)
        if youtube_id is None:
            raise AppError(
                422,
                "RULES_QA_INVALID_VIDEO_URL",
                "只接受 YouTube 影片網址，例如 https://youtu.be/<影片 ID>",
            )
        video = VideoRecord(
            game_id=game_id,
            source="youtube",
            video_url=data.video_url,
            youtube_id=youtube_id,
            title=data.title,
        )
        with self._repo.transaction():
            self._repo.upsert_video(video)
        return _video_out(video)

    # --- 規則問答 ---

    def send_message(
        self, user: CurrentUser, game_id: int, data: MessageRequest
    ) -> MessageResponse:
        require_role(user, "player", "shop_staff", "admin")
        self._game_name(game_id)
        if not self._repo.has_chunks(game_id):
            raise AppError(409, "RULES_QA_NOT_READY", "這款遊戲的規則書還沒入庫，暫時無法提問")

        with _external_services():
            # 每一則問題都重新檢索：追問的主題可能換了（design.md D6）
            vector = self._embedding.embed([data.content])[0]
            hits = self._repo.search_chunks(game_id, vector, self._embedding_model, SEARCH_LIMIT)
            response = self._respond(
                prompts.build_input(data.content, hits), data.previous_response_id
            )
            output = _output(response)
            if FORBIDDEN_WORD in output["answer"]:
                response = self._respond(prompts.REWRITE_REQUEST, response.response_id)
                output = _output(response)
                if FORBIDDEN_WORD in output["answer"]:
                    raise AppError(
                        503, "RULES_QA_OUTPUT_REJECTED", "規則問答暫時無法回答，請換個說法再問一次"
                    )

        answerable = bool(output["answerable"])
        return MessageResponse(
            response_id=response.response_id,
            answer=str(output["answer"]),
            answerable=answerable,
            citations=_citations(output["citation_ids"], hits) if answerable else [],
        )

    # --- 只檢索（給其他 domain 的 service 用） ---

    def search_rule_chunks(self, game_id: int, question: str) -> list[ChunkHit]:
        """用問題找這款遊戲最像的幾段規則原文，每段有頁碼與原文。不叫 LLM。

        給其他 domain 的 service 用（AI 語音主持）：不檢查使用者，不開成 API。
        這款遊戲沒有索引（或沒有這款遊戲）時回空的清單，不回 409。
        embedding 失敗時和 send_message 一樣丟 503 RULES_QA_UNAVAILABLE，由呼叫端決定怎麼處理。
        """
        if not self._repo.has_chunks(game_id):
            return []
        with _external_services():
            vector = self._embedding.embed([question])[0]
            return self._repo.search_chunks(game_id, vector, self._embedding_model, SEARCH_LIMIT)

    # --- 內部 ---

    def _game_name(self, game_id: int) -> str:
        name = self._repo.game_name(game_id)
        if name is None:
            raise _game_not_found(game_id)
        return name

    def _respond(self, llm_input: str, previous_response_id: str | None) -> LLMResponse:
        return self._llm.respond(
            instructions=prompts.ANSWER_INSTRUCTIONS,
            input=llm_input,
            tools=[],
            output_schema=prompts.ANSWER_SCHEMA,
            previous_response_id=previous_response_id,
            allow_tool_calls=False,
        )


def _output(response: LLMResponse) -> dict[str, Any]:
    output = response.output
    if not isinstance(output, dict) or not {"answer", "answerable", "citation_ids"} <= set(output):
        raise LLMError("規則問答的輸出不符合格式")
    return output


def _citations(citation_ids: Any, hits: Sequence[ChunkHit]) -> list[Citation]:
    """把段落編號換成頁碼：只保留這次檢索到的段落，同一頁只列一次，依頁碼排序。"""
    pages = {
        hits[number - 1].page
        for number in citation_ids or []
        if isinstance(number, int) and 1 <= number <= len(hits)
    }
    return [Citation(page=page) for page in sorted(pages)]


def _video_out(video: VideoRecord) -> VideoOut:
    return VideoOut(
        source=video.source,  # type: ignore[arg-type]
        video_url=video.video_url,
        youtube_id=video.youtube_id,
        title=video.title,
    )


# --------------------------------------------------------------------------- 規則影片專案


class VideoProjectStore(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...
    def create(
        self,
        *,
        game_id: int,
        shop_id: uuid.UUID,
        created_by: uuid.UUID,
        chapter_number: int,
        chapter_title: str,
    ) -> uuid.UUID: ...
    def get(self, project_id: uuid.UUID) -> VideoProjectRecord | None: ...
    def list_projects(
        self, shop_id: uuid.UUID | None, offset: int, limit: int
    ) -> tuple[list[VideoProjectRecord], int]: ...


class GameNames(Protocol):
    def game_name(self, game_id: int) -> str | None: ...


class ShopLookup(Protocol):
    """共用表 booking_shops 的 repository（擁有者瑋鋐，AGENTS.md 4.2 共用資料表例外）。"""

    def shop_exists(self, shop_id: uuid.UUID) -> bool: ...


def _project_not_found() -> AppError:
    return AppError(404, "RULES_VIDEO_PROJECT_NOT_FOUND", "找不到這個影片專案")


class VideoProjectService:
    """規則影片專案（add-rules-video-mobile design.md D1）。"""

    def __init__(self, projects: VideoProjectStore, games: GameNames, shops: ShopLookup) -> None:
        self._projects = projects
        self._games = games
        self._shops = shops

    def create(self, user: CurrentUser, body: VideoProjectCreate) -> VideoProjectOut:
        require_role(user, "shop_staff", "admin")
        shop_id = self._shop_for(user, body.shop_id)
        if self._games.game_name(body.game_id) is None:
            raise _game_not_found(body.game_id)
        with self._projects.transaction():
            project_id = self._projects.create(
                game_id=body.game_id,
                shop_id=shop_id,
                created_by=user.id,
                chapter_number=body.chapter_number,
                chapter_title=body.chapter_title,
            )
            record = self._projects.get(project_id)
        assert record is not None
        return _project_out(record)

    def get(self, user: CurrentUser, project_id: uuid.UUID) -> VideoProjectOut:
        require_role(user, "shop_staff", "admin")
        record = self._projects.get(project_id)
        # 別家店的專案回 404，不透露專案存在
        if record is None or not _can_access(user, record):
            raise _project_not_found()
        return _project_out(record)

    def list(self, user: CurrentUser, page: int, page_size: int) -> VideoProjectList:
        require_role(user, "shop_staff", "admin")
        shop_id = None if user.role == "admin" else user.shop_id
        if user.role != "admin" and shop_id is None:
            raise PermissionDenied("這個店家人員帳號沒有所屬店家")
        records, total = self._projects.list_projects(shop_id, (page - 1) * page_size, page_size)
        return VideoProjectList(items=[_project_out(r) for r in records], total=total)

    def _shop_for(self, user: CurrentUser, requested: uuid.UUID | None) -> uuid.UUID:
        """店家人員用登入身分的店家；管理員必須指定店家。"""
        if user.role == "admin":
            if requested is None:
                raise AppError(
                    422, "RULES_VIDEO_SHOP_REQUIRED", "管理員建立專案時要指定店家（shop_id）"
                )
            if not self._shops.shop_exists(requested):
                raise AppError(404, "BOOKING_SHOP_NOT_FOUND", "找不到店家")
            return requested
        if user.shop_id is None:
            raise PermissionDenied("這個店家人員帳號沒有所屬店家")
        if requested is not None and requested != user.shop_id:
            raise PermissionDenied("只能為自己的店建立影片專案")
        return user.shop_id


def _can_access(user: CurrentUser, record: VideoProjectRecord) -> bool:
    return user.role == "admin" or record.shop_id == user.shop_id


def _project_out(record: VideoProjectRecord) -> VideoProjectOut:
    return VideoProjectOut(
        id=record.id,
        game_id=record.game_id,
        game_name=record.game_name,
        shop_id=record.shop_id,
        created_by=record.created_by,
        chapter_number=record.chapter_number,
        chapter_title=record.chapter_title,
        step="pages",  # MR 1 沒有其他狀態（design.md D1）
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# --------------------------------------------------------------------------- 規則影片的非同步工作


class VideoJobStore(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...
    def create(self, *, project_id: uuid.UUID, kind: str, created_by: uuid.UUID) -> uuid.UUID: ...
    def active_job_id(self, project_id: uuid.UUID) -> uuid.UUID | None: ...
    def expire_stale(self, project_id: uuid.UUID, minutes: int, error: str) -> int: ...
    def get(self, job_id: uuid.UUID) -> VideoJobRecord | None: ...
    def list_for_project(
        self, project_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[VideoJobRecord], int]: ...


class VideoJobService:
    """建立與查詢規則影片的工作（add-rules-video-mobile design.md D2）。

    建立工作的 API 在 MR 4（草稿）、MR 8（影片）、MR 10（修改）；權限同影片專案。
    """

    def __init__(
        self,
        jobs: VideoJobStore,
        projects: VideoProjectStore,
        *,
        notify: Callable[[], None] | None = None,
    ) -> None:
        self._jobs = jobs
        self._projects = projects
        self._notify = notify

    def create(self, user: CurrentUser, project_id: uuid.UUID, kind: str) -> VideoJobOut:
        require_role(user, "shop_staff", "admin")
        self._project(user, project_id)
        # 卡死的工作的出口：running 超過上限的先標為逾時，才不會一直擋住新工作
        with self._jobs.transaction():
            self._jobs.expire_stale(project_id, JOB_TIMEOUT_MINUTES, TIMEOUT_MESSAGE)
        try:
            with self._jobs.transaction():
                job_id = self._jobs.create(project_id=project_id, kind=kind, created_by=user.id)
        except ActiveJobExists:
            active = self._jobs.active_job_id(project_id)
            raise AppError(
                409,
                "RULES_VIDEO_JOB_RUNNING",
                "這個專案已經有進行中的工作，請等它完成",
                {"job_id": str(active) if active else None},
            ) from None
        if self._notify is not None:
            self._notify()
        record = self._jobs.get(job_id)
        assert record is not None
        return _job_out(record)

    def get(self, user: CurrentUser, project_id: uuid.UUID, job_id: uuid.UUID) -> VideoJobOut:
        require_role(user, "shop_staff", "admin")
        self._project(user, project_id)
        record = self._jobs.get(job_id)
        if record is None or record.project_id != project_id:
            raise AppError(404, "RULES_VIDEO_JOB_NOT_FOUND", "找不到這個工作")
        return _job_out(record)

    def list(
        self, user: CurrentUser, project_id: uuid.UUID, page: int, page_size: int
    ) -> VideoJobList:
        require_role(user, "shop_staff", "admin")
        self._project(user, project_id)
        records, total = self._jobs.list_for_project(project_id, (page - 1) * page_size, page_size)
        return VideoJobList(items=[_job_out(r) for r in records], total=total)

    def _project(self, user: CurrentUser, project_id: uuid.UUID) -> VideoProjectRecord:
        record = self._projects.get(project_id)
        if record is None or not _can_access(user, record):
            raise _project_not_found()
        return record


def _job_out(record: VideoJobRecord) -> VideoJobOut:
    return VideoJobOut.model_validate(record, from_attributes=True)
