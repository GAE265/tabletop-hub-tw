"""規則教學與問答的商業規則：教學清單與內容、設定教學影片、建立索引、規則問答、權限。

不 import FastAPI（AGENTS.md 4.2）；錯誤一律拋 AppError，由錯誤處理器轉成統一格式。
"""

import copy
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
    DraftState,
    LessonSummary,
    PagesRecord,
    VideoJobRecord,
    VideoProjectRecord,
    VideoRecord,
    VideoTermsRecord,
)
from app.domains.rules_qa.schemas import (
    ChangedLineOut,
    Citation,
    CoverageHintOut,
    CoverageIssueOut,
    CoverageProblemOut,
    CoverageSlotOut,
    DraftAssetOut,
    DraftBeatOut,
    DraftCoverageOut,
    DraftSegmentOut,
    DraftTermsOut,
    MessageRequest,
    MessageResponse,
    RemovedBlockOut,
    RulesLessonItem,
    RulesLessonList,
    RulesLessonOut,
    VideoAssetOut,
    VideoAssetUpdate,
    VideoDraftOut,
    VideoJobList,
    VideoJobOut,
    VideoOut,
    VideoPageOut,
    VideoPagesIn,
    VideoPagesOut,
    VideoProjectCreate,
    VideoProjectList,
    VideoProjectOut,
    VideoReadinessOut,
    VideoRenderOut,
    VideoRequest,
    VideoTermsIn,
    VideoTermsOut,
)
from app.domains.rules_qa.video_assets import (
    PhotoRejected,
    asset_label,
    find_asset,
    is_skipped,
    new_photo_file,
    normalize_photo,
    photo_key,
    readiness,
    skip_blocked_message,
    skip_impact,
)
from app.domains.rules_qa.video_coverage import report_from_dict
from app.domains.rules_qa.video_draft import (
    DRAFT_NO_RULEBOOK_MESSAGE,
    DRAFT_PAGES_NOT_SET_MESSAGE,
    PAGES_STALE_HINT,
    TERMS_MISSING_HINT,
    narration_text_hash,
    terms_status,
)
from app.domains.rules_qa.video_jobs import JOB_TIMEOUT_MINUTES, TIMEOUT_MESSAGE
from app.domains.rules_qa.video_pages import page_diff, text_hash
from app.domains.rules_qa.video_script import REPRESENTATIVE, term_conflicts
from app.domains.rules_qa.youtube import parse_youtube_id
from app.integrations.embedding import EmbeddingError, EmbeddingProvider
from app.integrations.llm import LLMProvider
from app.integrations.llm.errors import LLMConversationNotFound, LLMError, LLMUnavailable
from app.integrations.llm.types import LLMResponse
from app.integrations.storage.base import FileStorage
from app.integrations.storage.errors import FileNotFound, StorageError

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


class ProjectPagesWriter(Protocol):
    def save(
        self,
        project_id: uuid.UUID,
        *,
        chapter_pages: list[int],
        reference_pages: list[int],
        page_texts: dict[str, Any],
    ) -> None: ...


class DraftStarter(Protocol):
    def create(self, user: CurrentUser, project_id: uuid.UUID, kind: str) -> VideoJobOut: ...


class VideoProjectService:
    """規則影片專案（add-rules-video-mobile design.md D1；整個遊戲一支影片見整本範圍）。

    只給遊戲時：這支影片用到的頁預設是規則書的全部頁，建立後自動開始產生草稿
    （頁面文字那一步不在店員流程裡；OCR 錯字由管理員匯入時處理，2026-11-22 永傑決定）。
    """

    def __init__(
        self,
        projects: VideoProjectStore,
        games: GameNames,
        shops: ShopLookup,
        read_pages: Callable[[int], list[tuple[int, str]]] | None = None,
        pages: ProjectPagesWriter | None = None,
        drafts: DraftStarter | None = None,
    ) -> None:
        self._projects = projects
        self._games = games
        self._shops = shops
        self._read_pages = read_pages
        self._pages = pages
        self._drafts = drafts

    def create(self, user: CurrentUser, body: VideoProjectCreate) -> VideoProjectOut:
        require_role(user, "shop_staff", "admin")
        shop_id = self._shop_for(user, body.shop_id)
        if self._games.game_name(body.game_id) is None:
            raise _game_not_found(body.game_id)
        whole_game = body.chapter_number is None
        manual: list[tuple[int, str]] = []
        if whole_game:
            assert self._read_pages is not None
            manual = sorted((p, t) for p, t in self._read_pages(body.game_id) if t.strip())
            if not manual:
                raise AppError(422, "RULES_VIDEO_NO_RULEBOOK", DRAFT_NO_RULEBOOK_MESSAGE)
        with self._projects.transaction():
            project_id = self._projects.create(
                game_id=body.game_id,
                shop_id=shop_id,
                created_by=user.id,
                chapter_number=body.chapter_number,
                chapter_title=body.chapter_title,
            )
            if whole_game:
                assert self._pages is not None
                self._pages.save(
                    project_id,
                    chapter_pages=[page for page, _ in manual],
                    reference_pages=[],
                    page_texts={
                        str(page): {"text": text, "original_hash": text_hash(text)}
                        for page, text in manual
                    },
                )
        if whole_game:
            assert self._drafts is not None
            self._drafts.create(user, project_id, "draft")
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


def _step(record: VideoProjectRecord) -> str:
    """由狀態推出（design.md D1、D11、D15 實作決定）：
    pages＝還沒有草稿；draft＝有草稿、還沒拍照也沒略過；assets＝素材還沒齊；
    render＝齊了、還沒有成品；done＝有成功產生的影片。
    """
    video = record.video
    if video is None:
        # 整個遊戲：建立時就開始產生草稿；單章：要先選頁
        return "draft" if record.chapter_number is None else "pages"
    if record.has_render:
        return "done"
    if readiness(video)["ready"]:
        return "render"
    if any(a.get("file") or is_skipped(a) for a in video.get("assets", [])):
        return "assets"
    return "draft"


def _project_out(record: VideoProjectRecord) -> VideoProjectOut:
    return VideoProjectOut(
        id=record.id,
        game_id=record.game_id,
        game_name=record.game_name,
        shop_id=record.shop_id,
        created_by=record.created_by,
        chapter_number=record.chapter_number,
        chapter_title=record.chapter_title,
        title=record.chapter_title or f"{record.game_name} 規則教學",
        step=_step(record),
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

    建立工作的 API 隨各種工作（草稿、產生影片、修改）加上；權限同影片專案。
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


# --------------------------------------------------------------------------- 規則影片的用語對照表


class VideoTermsStore(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...
    def get(self, game_id: int) -> VideoTermsRecord | None: ...
    def replace(self, game_id: int, terms: list[dict[str, Any]], updated_by: uuid.UUID) -> None: ...


class VideoTermsService:
    """每款遊戲一份的用語對照表：管理員上傳、店家人員可看（add-rules-video-mobile D4）。"""

    def __init__(self, terms: VideoTermsStore, games: GameNames) -> None:
        self._terms = terms
        self._games = games

    def replace(self, user: CurrentUser, game_id: int, body: VideoTermsIn) -> VideoTermsOut:
        require_role(user, "admin")
        self._check_game(game_id)
        conflicts = term_conflicts([entry.to_term() for entry in body.terms])
        if conflicts:
            duplicate = any(c.kind == "duplicate_en" for c in conflicts)
            raise AppError(
                422,
                "RULES_VIDEO_TERMS_DUPLICATE"
                if duplicate
                else "RULES_VIDEO_TERMS_CATEGORY_CONFLICT",
                "；".join(c.message for c in conflicts),
                {"problems": [{"kind": c.kind, "message": c.message} for c in conflicts]},
            )
        with self._terms.transaction():
            self._terms.replace(
                game_id, [entry.model_dump() for entry in body.terms], updated_by=user.id
            )
        return self._out(game_id)

    def get(self, user: CurrentUser, game_id: int) -> VideoTermsOut:
        require_role(user, "shop_staff", "admin")
        self._check_game(game_id)
        return self._out(game_id)

    def _check_game(self, game_id: int) -> None:
        if self._games.game_name(game_id) is None:
            raise _game_not_found(game_id)

    def _out(self, game_id: int) -> VideoTermsOut:
        record = self._terms.get(game_id)
        if record is None:
            # 從未上傳 ≠ 上傳了空表（design.md D4）
            raise AppError(404, "RULES_VIDEO_TERMS_NOT_FOUND", "這款遊戲還沒有上傳用語對照表")
        return VideoTermsOut(
            game_id=record.game_id,
            terms=record.terms,
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )


# --------------------------------------------------------------------------- 規則書頁面文字


class VideoPagesStore(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...
    def get(self, project_id: uuid.UUID) -> PagesRecord | None: ...
    def save(
        self,
        project_id: uuid.UUID,
        *,
        chapter_pages: list[int],
        reference_pages: list[int],
        page_texts: dict[str, Any],
    ) -> None: ...


class VideoPagesService:
    """選本章頁與參考頁、編輯文字（add-rules-video-mobile design.md D11）。

    原文從 rules_ingest 的 games_manual 讀（read_pages 是它的 service 函式）；
    編輯後的文字存在專案上，不改 games_manual。
    """

    def __init__(
        self,
        pages: VideoPagesStore,
        projects: VideoProjectStore,
        read_pages: Callable[[int], list[tuple[int, str]]],
    ) -> None:
        self._pages = pages
        self._projects = projects
        self._read_pages = read_pages

    def get(self, user: CurrentUser, project_id: uuid.UUID) -> VideoPagesOut:
        project = self._project(user, project_id)
        record = self._pages.get(project_id)
        assert record is not None
        return _pages_out(record, dict(self._read_pages(project.game_id)))

    def replace(
        self, user: CurrentUser, project_id: uuid.UUID, body: VideoPagesIn
    ) -> VideoPagesOut:
        project = self._project(user, project_id)
        manual = dict(self._read_pages(project.game_id))
        selected = [*body.chapter_pages, *body.reference_pages]
        missing = sorted(set(selected) - set(manual))
        if missing:
            listed = "、".join(str(p) for p in missing)
            raise AppError(
                422,
                "RULES_VIDEO_PAGES_MISSING",
                f"規則書還沒有這幾頁，請先上傳：{listed}",
                {"missing": missing},
            )
        texts = {page: body.texts.get(page, manual[page]) for page in selected}
        if not any(texts[page].strip() for page in body.chapter_pages):
            raise AppError(
                422, "RULES_VIDEO_PAGES_EMPTY", "本章頁的文字全部是空白，沒有東西可以產生草稿"
            )
        page_texts = {
            str(page): {"text": texts[page], "original_hash": text_hash(manual[page])}
            for page in selected
        }
        with self._pages.transaction():
            self._pages.save(
                project_id,
                chapter_pages=body.chapter_pages,
                reference_pages=body.reference_pages,
                page_texts=page_texts,
            )
        return self.get(user, project_id)

    def _project(self, user: CurrentUser, project_id: uuid.UUID) -> VideoProjectRecord:
        require_role(user, "shop_staff", "admin")
        record = self._projects.get(project_id)
        if record is None or not _can_access(user, record):
            raise _project_not_found()
        return record


def _pages_out(record: PagesRecord, manual: dict[int, str]) -> VideoPagesOut:
    roles = [(p, "chapter") for p in record.chapter_pages]
    roles += [(p, "reference") for p in record.reference_pages]
    pages = []
    for page, role in roles:
        saved = record.page_texts.get(str(page), {})
        original = manual.get(page)
        edited = saved.get("text", original or "")
        diff = page_diff(original or "", edited)
        changed_original = original is None or text_hash(original) != saved.get("original_hash")
        pages.append(
            VideoPageOut(
                page=page,
                role=role,
                original=original,
                text=edited,
                original_changed=changed_original,
                removed=[RemovedBlockOut(lines=b.lines) for b in diff.removed],
                changed=[
                    ChangedLineOut(original=c.original, edited=c.edited, similarity=c.similarity)
                    for c in diff.changed
                ],
            )
        )
    return VideoPagesOut(
        available_pages=sorted(manual),
        chapter_pages=record.chapter_pages,
        reference_pages=record.reference_pages,
        pages_version=record.pages_version,
        pages=pages,
    )


# --------------------------------------------------------------------------- 草稿


class VideoDraftStore(Protocol):
    def get_state(self, project_id: uuid.UUID) -> DraftState | None: ...


class TermsReader(Protocol):
    def get(self, game_id: int) -> VideoTermsRecord | None: ...


class VideoDraftService:
    """建立草稿工作、查看草稿（add-rules-video-mobile design.md D11）。"""

    def __init__(
        self,
        drafts: VideoDraftStore,
        projects: VideoProjectStore,
        terms: TermsReader,
        jobs: VideoJobService,
    ) -> None:
        self._drafts = drafts
        self._projects = projects
        self._terms = terms
        self._jobs = jobs

    def start(self, user: CurrentUser, project_id: uuid.UUID, kind: str = "draft") -> VideoJobOut:
        state = self._state(user, project_id)
        if kind == "render":
            # 產生影片：要有草稿、素材齊了（MR 9）
            if state.video is None:
                raise AppError(404, "RULES_VIDEO_DRAFT_NOT_FOUND", "這個專案還沒有草稿")
            report = readiness(state.video)
            if not report["ready"]:
                raise AppError(
                    422,
                    "RULES_VIDEO_NOT_READY",
                    "還不能產生影片，請先補齊素材",
                    {k: v for k, v in report.items() if k != "ready"},
                )
            return self._jobs.create(user, project_id, "render")
        if not state.chapter_pages:
            raise AppError(422, "RULES_VIDEO_PAGES_NOT_SET", DRAFT_PAGES_NOT_SET_MESSAGE)
        return self._jobs.create(user, project_id, "draft")

    def get(self, user: CurrentUser, project_id: uuid.UUID) -> VideoDraftOut:
        state = self._state(user, project_id)
        if state.video is None:
            raise AppError(404, "RULES_VIDEO_DRAFT_NOT_FOUND", "這個專案還沒有草稿")
        stored = self._terms.get(state.game_id)
        status = terms_status(None if stored is None else stored.terms)
        stale = state.draft_pages_version is not None and (
            state.draft_pages_version != state.pages_version
        )
        return VideoDraftOut(
            video_version=state.video_version,
            segments=[_draft_segment(s) for s in state.video.get("segments", [])],
            assets=[_draft_asset(a) for a in state.video.get("assets", [])],
            coverage=_draft_coverage(state),
            terms=DraftTermsOut(
                status=status, message=TERMS_MISSING_HINT if status == "missing" else None
            ),
            pages_stale=stale,
            pages_stale_message=PAGES_STALE_HINT if stale else None,
        )

    def _state(self, user: CurrentUser, project_id: uuid.UUID) -> DraftState:
        require_role(user, "shop_staff", "admin")
        record = self._projects.get(project_id)
        if record is None or not _can_access(user, record):
            raise _project_not_found()
        state = self._drafts.get_state(project_id)
        assert state is not None
        return state


def _draft_segment(segment: dict[str, Any]) -> DraftSegmentOut:
    return DraftSegmentOut(
        segment_key=segment["segment_key"],
        chapter=segment.get("chapter_key", ""),
        source_pages=[p["page"] for p in segment.get("source_pages", [])],
        beats=[
            DraftBeatOut(
                beat_key=b.get("beat_key", ""),
                narration=b.get("narration", ""),
                subtitle=b.get("subtitle", ""),
            )
            for b in segment.get("beats", [])
        ],
    )


def _draft_asset(asset: dict[str, Any]) -> DraftAssetOut:
    reason = asset.get("reason", "")
    return DraftAssetOut(
        asset_key=asset["asset_key"],
        label=asset.get("label"),
        kind=asset.get("kind", "flat_photo"),
        priority=asset.get("priority", "must"),
        reason=reason,
        shot=asset.get("shot"),
        representative=REPRESENTATIVE in reason,
        regions=list((asset.get("regions") or {}).keys()),
        has_photo=bool(asset.get("file")),
        skipped=is_skipped(asset),
    )


def _draft_coverage(state: DraftState) -> DraftCoverageOut:
    coverage = state.coverage or {"status": "not_done", "reason": "還沒有做規則涵蓋檢查"}
    if "slots" in coverage:
        return _slot_coverage(coverage, state)
    if coverage.get("status") != "done":
        return DraftCoverageOut(
            status="not_done",
            reason=coverage.get("reason"),
            total_rules=0,
            issues=[],
            problems=[],
            hints=[],
        )
    report = report_from_dict(coverage["report"])
    issues, problems, hints = _report_parts(report)
    # 只有旁白或字幕變了才算過期；只改素材（照片、區域）不算
    stale = coverage.get("text_hash") != narration_text_hash(state.video or {})
    return DraftCoverageOut(
        status="stale" if stale else "done",
        reason=STALE_COVERAGE_REASON if stale else None,
        total_rules=len(report.rules),
        issues=issues,
        problems=problems,
        hints=hints,
    )


STALE_COVERAGE_REASON = "旁白或字幕在涵蓋檢查之後改過，結果可能過期"


def _report_parts(
    report: Any, prefix: str = ""
) -> tuple[list[CoverageIssueOut], list[CoverageProblemOut], list[CoverageHintOut]]:
    issues = [
        CoverageIssueOut(
            rule_id=prefix + r.rule_id,
            category=r.category,
            source=r.source,
            narration_status=r.narration.status,
            narration_missing=r.narration.missing,
            subtitle_status=r.subtitle.status,
            subtitle_missing=r.subtitle.missing,
            narration_shorter=r.narration_shorter,
        )
        for r in report.rules
        if not r.is_hint and r.has_issue
    ]
    problems = [
        CoverageProblemOut(
            beat_key=p.beat_key, track=p.track, kind=p.kind, text=p.text, reason=p.reason
        )
        for p in report.problems
    ]
    hints = [
        CoverageHintOut(rule_id=prefix + r.rule_id, source=r.source)
        for r in report.rules
        if r.is_hint
    ]
    return issues, problems, hints


def _slot_coverage(coverage: dict[str, Any], state: DraftState) -> DraftCoverageOut:
    """整個遊戲：每一格一份涵蓋檢查；合計把三格加起來（rule_id 前面加格的 key）。"""
    slots: list[CoverageSlotOut] = []
    for slot in coverage["slots"]:
        if slot.get("status") != "done":
            slots.append(
                CoverageSlotOut(
                    slot=slot["key"],
                    title=slot["title"],
                    status="not_done",
                    reason=slot.get("reason"),
                    total_rules=0,
                    issues=[],
                    problems=[],
                    hints=[],
                )
            )
            continue
        report = report_from_dict(slot["report"])
        issues, problems, hints = _report_parts(report, prefix=f"{slot['key']}-")
        slots.append(
            CoverageSlotOut(
                slot=slot["key"],
                title=slot["title"],
                status="done",
                reason=None,
                total_rules=len(report.rules),
                issues=issues,
                problems=problems,
                hints=hints,
            )
        )
    stale = coverage.get("text_hash") != narration_text_hash(state.video or {})
    not_done = [s.title for s in slots if s.status == "not_done"]
    if stale:
        status, reason = "stale", STALE_COVERAGE_REASON
    elif not_done:
        status, reason = "not_done", f"「{'、'.join(not_done)}」的涵蓋檢查沒有完成"
    else:
        status, reason = "done", None
    return DraftCoverageOut(
        status=status,
        reason=reason,
        total_rules=sum(s.total_rules for s in slots),
        issues=[i for s in slots for i in s.issues],
        problems=[p for s in slots for p in s.problems],
        hints=[h for s in slots for h in s.hints],
        slots=slots,
    )


# --------------------------------------------------------------------------- 素材（MR 7）


class VideoAssetStore(VideoDraftStore, Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...
    def save_video(
        self, project_id: uuid.UUID, *, expected_version: int, video: dict[str, Any]
    ) -> bool: ...


ASSET_CONFLICT_MESSAGE = "專案剛被修改（例如草稿重新產生），請重新整理後再試一次"


class VideoAssetsService:
    """素材照片、方向、區域、缺什麼（add-rules-video-mobile design.md D13）。

    照片檔放在存放介面；段資料記檔名。寫入段資料的條件是 video_version 沒變（和草稿工作一樣），
    所以草稿工作進行中上傳照片時，是草稿工作寫入失敗，照片保留。
    """

    def __init__(
        self, drafts: VideoAssetStore, projects: VideoProjectStore, storage: FileStorage
    ) -> None:
        self._drafts = drafts
        self._projects = projects
        self._storage = storage

    def upload_photo(
        self, user: CurrentUser, project_id: uuid.UUID, asset_key: str, data: bytes
    ) -> VideoAssetOut:
        state = self._state(user, project_id)
        video, asset = self._asset(state, asset_key)
        try:
            content, ext, content_type = normalize_photo(data)
        except PhotoRejected as exc:
            raise AppError(422, exc.code, f"「{asset_label(asset)}」：{exc.message}") from exc
        old_file = asset.get("file")
        file = new_photo_file(asset_key, ext)
        self._put(photo_key(project_id, file), content, content_type)
        asset["file"] = file
        # 新照片已經轉正；區域座標保留（同一張牌的版面通常相同），由手機頁提示重新確認
        asset["orientation"] = 0
        if not self._save(project_id, state.video_version, video):
            self._storage.delete(photo_key(project_id, file))
            raise AppError(409, "RULES_VIDEO_CONFLICT", ASSET_CONFLICT_MESSAGE)
        if old_file and old_file != file:
            self._delete(photo_key(project_id, old_file))
        return _asset_out(asset, state.video_version + 1, video)

    def read_photo(
        self, user: CurrentUser, project_id: uuid.UUID, asset_key: str
    ) -> tuple[bytes, str]:
        state = self._state(user, project_id)
        _, asset = self._asset(state, asset_key)
        file = asset.get("file")
        if not file:
            raise AppError(
                404, "RULES_VIDEO_PHOTO_NOT_FOUND", f"「{asset_label(asset)}」還沒有照片"
            )
        try:
            data = self._storage.get(photo_key(project_id, file))
        except FileNotFound as exc:
            raise AppError(404, "RULES_VIDEO_PHOTO_NOT_FOUND", "找不到這個素材的照片") from exc
        except StorageError as exc:
            raise AppError(503, "RULES_VIDEO_STORAGE_UNAVAILABLE", STORAGE_DOWN_MESSAGE) from exc
        ext = file.rsplit(".", 1)[-1].lower()
        return data, "image/png" if ext == "png" else "image/jpeg"

    def get_asset(self, user: CurrentUser, project_id: uuid.UUID, asset_key: str) -> VideoAssetOut:
        state = self._state(user, project_id)
        video, asset = self._asset(state, asset_key)
        return _asset_out(asset, state.video_version, video)

    def update_asset(
        self, user: CurrentUser, project_id: uuid.UUID, asset_key: str, body: VideoAssetUpdate
    ) -> VideoAssetOut:
        state = self._state(user, project_id)
        video, asset = self._asset(state, asset_key)
        regions = asset.setdefault("regions", {})
        if body.regions is not None:
            unknown = sorted(set(body.regions) - set(regions))
            if unknown:
                raise AppError(
                    422,
                    "RULES_VIDEO_REGION_UNKNOWN",
                    f"「{asset_label(asset)}」沒有這些區域：{'、'.join(unknown)}",
                    {"unknown": unknown},
                )
        if body.orientation is not None and body.orientation != asset.get("orientation", 0):
            asset["orientation"] = body.orientation
            # 座標以套用方向之後的圖為準，方向變了舊座標就不對
            if body.regions is None:
                for name in regions:
                    regions[name] = None
        for name, box in (body.regions or {}).items():
            regions[name] = box
        if body.skipped is True:
            self._check_skip(video, asset)
            asset["usable"] = False
        elif body.skipped is False:
            asset.pop("usable", None)
        if not self._save(project_id, state.video_version, video):
            raise AppError(409, "RULES_VIDEO_CONFLICT", ASSET_CONFLICT_MESSAGE)
        return _asset_out(asset, state.video_version + 1, video)

    @staticmethod
    def _check_skip(video: dict[str, Any], asset: dict[str, Any]) -> None:
        """只有選拍可以略過；略過後某段的主畫面會空掉就不能略過（2026-11-22 永傑決定）。"""
        label = asset_label(asset)
        if asset.get("priority") != "optional":
            raise AppError(
                422, "RULES_VIDEO_SKIP_NOT_OPTIONAL", f"「{label}」是必拍的素材，不能略過"
            )
        _, blocked = skip_impact(video, asset["asset_key"])
        if blocked:
            raise AppError(
                422,
                "RULES_VIDEO_SKIP_BLOCKED",
                f"「{label}」：{skip_blocked_message(blocked)}",
                {"segments": blocked},
            )

    def readiness(self, user: CurrentUser, project_id: uuid.UUID) -> VideoReadinessOut:
        state = self._state(user, project_id)
        return VideoReadinessOut.model_validate(readiness(state.video or {}))

    def _state(self, user: CurrentUser, project_id: uuid.UUID) -> DraftState:
        require_role(user, "shop_staff", "admin")
        record = self._projects.get(project_id)
        if record is None or not _can_access(user, record):
            raise _project_not_found()
        state = self._drafts.get_state(project_id)
        assert state is not None
        if state.video is None:
            raise AppError(404, "RULES_VIDEO_DRAFT_NOT_FOUND", "這個專案還沒有草稿")
        return state

    @staticmethod
    def _asset(state: DraftState, asset_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """回傳（段資料的複本、其中的這個素材）；改複本再寫回，失敗時原本的不受影響。"""
        video = copy.deepcopy(state.video or {})
        asset = find_asset(video, asset_key)
        if asset is None:
            raise AppError(
                404, "RULES_VIDEO_ASSET_NOT_FOUND", "草稿沒有這個素材，請重新整理素材清單"
            )
        return video, asset

    def _save(self, project_id: uuid.UUID, version: int, video: dict[str, Any]) -> bool:
        with self._drafts.transaction():
            return self._drafts.save_video(project_id, expected_version=version, video=video)

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._storage.put(key, data, content_type)
        except StorageError as exc:
            raise AppError(503, "RULES_VIDEO_STORAGE_UNAVAILABLE", STORAGE_DOWN_MESSAGE) from exc

    def _delete(self, key: str) -> None:
        """刪舊照片失敗不影響這次上傳（只留下用不到的檔案），記 log。"""
        try:
            self._storage.delete(key)
        except StorageError:
            logger.warning("刪除舊的素材照片失敗：%s", key, exc_info=True)


STORAGE_DOWN_MESSAGE = "照片存放空間暫時無法使用，請稍後再試"


def _asset_out(asset: dict[str, Any], version: int, video: dict[str, Any]) -> VideoAssetOut:
    optional = asset.get("priority") == "optional"
    affected, blocked = skip_impact(video, asset["asset_key"]) if optional else ([], [])
    return VideoAssetOut(
        asset_key=asset["asset_key"],
        label=asset.get("label"),
        kind=asset.get("kind", "flat_photo"),
        priority=asset.get("priority", "must"),
        reason=asset.get("reason", ""),
        shot=asset.get("shot"),
        has_photo=bool(asset.get("file")),
        orientation=asset.get("orientation", 0),
        regions=dict(asset.get("regions") or {}),
        video_version=version,
        skipped=is_skipped(asset),
        skip_affected_segments=affected,
        skip_blocked_segments=blocked,
    )


# --------------------------------------------------------------------------- 成品影片（MR 9）


class RenderJobsReader(Protocol):
    def latest_succeeded(self, project_id: uuid.UUID, kind: str) -> VideoJobRecord | None: ...


class VideoRenderService:
    """最近一次成功產生的影片與影片檔（design.md D15）。"""

    def __init__(
        self, projects: VideoProjectStore, jobs: RenderJobsReader, storage: FileStorage
    ) -> None:
        self._projects = projects
        self._jobs = jobs
        self._storage = storage

    def get(self, user: CurrentUser, project_id: uuid.UUID) -> VideoRenderOut:
        job = self._latest(user, project_id)
        result = job.result or {}
        return VideoRenderOut(
            job_id=job.id,
            video_path=f"/api/v1/rules-videos/{project_id}/render/video",
            total_seconds=result.get("total_seconds", 0),
            reencoded=result.get("reencoded", []),
            reused=result.get("reused", []),
            skipped_assets=result.get("skipped_assets", []),
            estimated=result.get("estimated", False),
            warnings=result.get("warnings", []),
            segments=result.get("segments", []),
            finished_at=job.finished_at,
        )

    def video(self, user: CurrentUser, project_id: uuid.UUID) -> bytes:
        job = self._latest(user, project_id)
        try:
            return self._storage.get((job.result or {})["video_key"])
        except (KeyError, FileNotFound) as exc:
            raise AppError(404, "RULES_VIDEO_RENDER_NOT_FOUND", "找不到影片檔") from exc
        except StorageError as exc:
            raise AppError(503, "RULES_VIDEO_STORAGE_UNAVAILABLE", STORAGE_DOWN_MESSAGE) from exc

    def _latest(self, user: CurrentUser, project_id: uuid.UUID) -> VideoJobRecord:
        require_role(user, "shop_staff", "admin")
        record = self._projects.get(project_id)
        if record is None or not _can_access(user, record):
            raise _project_not_found()
        job = self._jobs.latest_succeeded(project_id, "render")
        if job is None:
            raise AppError(404, "RULES_VIDEO_RENDER_NOT_FOUND", "這個專案還沒有產生影片")
        return job
