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
    VideoRequest,
    VideoTermsIn,
    VideoTermsOut,
)
from app.domains.rules_qa.video_coverage import report_from_dict
from app.domains.rules_qa.video_draft import (
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
        step="draft" if record.has_draft else "pages",  # 由狀態推出（design.md D1、D11）
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

    def start(self, user: CurrentUser, project_id: uuid.UUID) -> VideoJobOut:
        state = self._state(user, project_id)
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
        kind=asset.get("kind", "flat_photo"),
        priority=asset.get("priority", "must"),
        reason=reason,
        shot=asset.get("shot"),
        representative=REPRESENTATIVE in reason,
        regions=list((asset.get("regions") or {}).keys()),
        has_photo=bool(asset.get("file")),
    )


def _draft_coverage(state: DraftState) -> DraftCoverageOut:
    coverage = state.coverage or {"status": "not_done", "reason": "還沒有做規則涵蓋檢查"}
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
    # 只有旁白或字幕變了才算過期；只改素材（照片、區域）不算
    stale = coverage.get("text_hash") != narration_text_hash(state.video or {})
    return DraftCoverageOut(
        status="stale" if stale else "done",
        reason="旁白或字幕在涵蓋檢查之後改過，結果可能過期" if stale else None,
        total_rules=len(report.rules),
        issues=[
            CoverageIssueOut(
                rule_id=r.rule_id,
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
        ],
        problems=[
            CoverageProblemOut(
                beat_key=p.beat_key, track=p.track, kind=p.kind, text=p.text, reason=p.reason
            )
            for p in report.problems
        ],
        hints=[
            CoverageHintOut(rule_id=r.rule_id, source=r.source) for r in report.rules if r.is_hint
        ],
    )
