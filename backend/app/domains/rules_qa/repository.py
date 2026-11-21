"""規則教學與問答的資料存取。交易範圍由 service 用 transaction() 決定。

遊戲名稱讀取共用表 games（只讀，AGENTS.md §4.2 的共用資料表例外）。
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionRepository
from app.core.games.models import Game
from app.domains.rules_qa.models import (
    ACTIVE_JOB_INDEX,
    RulesQaChunk,
    RulesQaVideo,
    RulesQaVideoJob,
    RulesQaVideoProject,
    RulesQaVideoTerms,
)


@dataclass(frozen=True)
class LessonSummary:
    game_id: int
    game_name: str
    has_video: bool
    has_rulebook: bool


@dataclass(frozen=True)
class VideoRecord:
    game_id: int
    source: str
    video_url: str
    youtube_id: str | None
    title: str


@dataclass(frozen=True)
class ChunkHit:
    id: uuid.UUID
    page: int
    content: str


class RulesQaRepository(SessionRepository):
    # --- 共用資料表（只讀） ---

    def game_name(self, game_id: int) -> str | None:
        return self.session.scalar(select(Game.name).where(Game.id == game_id))

    # --- 教學清單與影片 ---

    def lesson_summaries(self) -> list[LessonSummary]:
        """有影片或有段落的遊戲。排序由 service 決定。"""
        has_rulebook = exists().where(RulesQaChunk.game_id == Game.id)
        has_video = exists().where(RulesQaVideo.game_id == Game.id)
        rows = self.session.execute(
            select(
                Game.id,
                Game.name,
                has_video.label("has_video"),
                has_rulebook.label("has_rulebook"),
            ).where(has_video | has_rulebook)
        )
        return [
            LessonSummary(
                game_id=r.id, game_name=r.name, has_video=r.has_video, has_rulebook=r.has_rulebook
            )
            for r in rows
        ]

    def get_video(self, game_id: int) -> VideoRecord | None:
        row = self.session.execute(
            select(
                RulesQaVideo.game_id,
                RulesQaVideo.source,
                RulesQaVideo.video_url,
                RulesQaVideo.youtube_id,
                RulesQaVideo.title,
            ).where(RulesQaVideo.game_id == game_id)
        ).one_or_none()
        return None if row is None else VideoRecord(**row._mapping)

    def upsert_video(self, video: VideoRecord) -> None:
        """一款遊戲最多一支影片：已經有就整筆取代。"""
        values = {
            "game_id": video.game_id,
            "source": video.source,
            "video_url": video.video_url,
            "youtube_id": video.youtube_id,
            "title": video.title,
        }
        statement = pg_insert(RulesQaVideo).values(**values)
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[RulesQaVideo.game_id],
                set_={
                    **{k: statement.excluded[k] for k in values if k != "game_id"},
                    "updated_at": func.now(),
                },
            )
        )

    # --- 檢索段落 ---

    def has_chunks(self, game_id: int) -> bool:
        return bool(self.session.scalar(select(exists().where(RulesQaChunk.game_id == game_id))))

    def replace_chunks(
        self,
        game_id: int,
        chunks: Sequence[tuple[int, str, list[float]]],
        embedding_model: str,
    ) -> None:
        """取代這款遊戲所有的段落（頁碼、文字、向量）。"""
        self.session.execute(delete(RulesQaChunk).where(RulesQaChunk.game_id == game_id))
        if chunks:
            self.session.execute(
                insert(RulesQaChunk),
                [
                    {
                        "game_id": game_id,
                        "page": page,
                        "content": content,
                        "embedding": embedding,
                        "embedding_model": embedding_model,
                    }
                    for page, content, embedding in chunks
                ],
            )

    def search_chunks(
        self, game_id: int, vector: Sequence[float], embedding_model: str, limit: int
    ) -> list[ChunkHit]:
        """這款遊戲中和 vector 最相近（cosine 距離最小）的段落；只看同一個 embedding 模型的段落。"""
        rows = self.session.execute(
            select(RulesQaChunk.id, RulesQaChunk.page, RulesQaChunk.content)
            .where(
                RulesQaChunk.game_id == game_id,
                RulesQaChunk.embedding_model == embedding_model,
            )
            .order_by(RulesQaChunk.embedding.cosine_distance(list(vector)), RulesQaChunk.id)
            .limit(limit)
        )
        return [ChunkHit(id=r.id, page=r.page, content=r.content) for r in rows]


# --------------------------------------------------------------------------- 規則影片專案


@dataclass(frozen=True)
class VideoProjectRecord:
    id: uuid.UUID
    game_id: int
    game_name: str
    shop_id: uuid.UUID
    created_by: uuid.UUID
    chapter_number: int
    chapter_title: str
    created_at: datetime
    updated_at: datetime
    has_draft: bool = False


class VideoProjectRepository(SessionRepository):
    """rules_qa_video_projects（add-rules-video-mobile design.md D1）。遊戲名稱讀共用表 games。"""

    def _select(self):
        return select(RulesQaVideoProject, Game.name).join(
            Game, Game.id == RulesQaVideoProject.game_id
        )

    @staticmethod
    def _record(project: RulesQaVideoProject, game_name: str) -> VideoProjectRecord:
        return VideoProjectRecord(
            id=project.id,
            game_id=project.game_id,
            game_name=game_name,
            shop_id=project.shop_id,
            created_by=project.created_by,
            chapter_number=project.chapter_number,
            chapter_title=project.chapter_title,
            created_at=project.created_at,
            updated_at=project.updated_at,
            has_draft=project.video is not None,
        )

    def create(
        self,
        *,
        game_id: int,
        shop_id: uuid.UUID,
        created_by: uuid.UUID,
        chapter_number: int,
        chapter_title: str,
    ) -> uuid.UUID:
        project = RulesQaVideoProject(
            game_id=game_id,
            shop_id=shop_id,
            created_by=created_by,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
        )
        self.session.add(project)
        self.session.flush()
        return project.id

    def get(self, project_id: uuid.UUID) -> VideoProjectRecord | None:
        row = self.session.execute(
            self._select().where(RulesQaVideoProject.id == project_id)
        ).one_or_none()
        return None if row is None else self._record(*row)

    def list_projects(
        self, shop_id: uuid.UUID | None, offset: int, limit: int
    ) -> tuple[list[VideoProjectRecord], int]:
        """shop_id 為 None 時列出全部（管理員）；依 updated_at 由新到舊。"""
        query = self._select()
        count = select(func.count()).select_from(RulesQaVideoProject)
        if shop_id is not None:
            query = query.where(RulesQaVideoProject.shop_id == shop_id)
            count = count.where(RulesQaVideoProject.shop_id == shop_id)
        rows = self.session.execute(
            query.order_by(
                RulesQaVideoProject.updated_at.desc(),
                RulesQaVideoProject.created_at.desc(),
                RulesQaVideoProject.id,
            )
            .offset(offset)
            .limit(limit)
        ).all()
        return [self._record(*row) for row in rows], self.session.scalar(count) or 0


# --------------------------------------------------------------------------- 規則影片的非同步工作


class ActiveJobExists(Exception):
    """這個專案已經有等待中或處理中的工作（部分唯一索引擋下）。"""


@dataclass(frozen=True)
class VideoJobRecord:
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    status: str
    progress: float
    message: str | None
    error: str | None
    result: dict[str, Any] | None
    created_by: uuid.UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str


class VideoJobRepository(SessionRepository):
    """rules_qa_video_jobs（add-rules-video-mobile design.md D2）。

    結束與回報進度都只更新 running 的工作：逾時被中止後，原本的執行緒才做完也不會改寫狀態。
    """

    @staticmethod
    def _record(job: RulesQaVideoJob) -> VideoJobRecord:
        return VideoJobRecord(
            id=job.id,
            project_id=job.project_id,
            kind=job.kind,
            status=job.status,
            progress=job.progress,
            message=job.message,
            error=job.error,
            result=job.result,
            created_by=job.created_by,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )

    def create(self, *, project_id: uuid.UUID, kind: str, created_by: uuid.UUID) -> uuid.UUID:
        job = RulesQaVideoJob(project_id=project_id, kind=kind, created_by=created_by)
        self.session.add(job)
        try:
            self.session.flush()
        except IntegrityError as exc:
            if ACTIVE_JOB_INDEX in str(exc.orig):
                raise ActiveJobExists from exc
            raise
        return job.id

    def active_job_id(self, project_id: uuid.UUID) -> uuid.UUID | None:
        return self.session.scalar(
            select(RulesQaVideoJob.id).where(
                RulesQaVideoJob.project_id == project_id,
                RulesQaVideoJob.status.in_(("queued", "running")),
            )
        )

    def expire_stale(self, project_id: uuid.UUID, minutes: int, error: str) -> int:
        """同專案 running 超過 minutes 分鐘的工作標為失敗；回傳筆數。"""
        result = self.session.execute(
            update(RulesQaVideoJob)
            .where(
                RulesQaVideoJob.project_id == project_id,
                RulesQaVideoJob.status == "running",
                RulesQaVideoJob.started_at < func.now() - timedelta(minutes=minutes),
            )
            .values(status="failed", error=error, finished_at=func.now())
        )
        return result.rowcount

    def get(self, job_id: uuid.UUID) -> VideoJobRecord | None:
        job = self.session.get(RulesQaVideoJob, job_id, populate_existing=True)
        return None if job is None else self._record(job)

    def list_for_project(
        self, project_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[VideoJobRecord], int]:
        jobs = self.session.scalars(
            select(RulesQaVideoJob)
            .where(RulesQaVideoJob.project_id == project_id)
            .order_by(RulesQaVideoJob.created_at.desc(), RulesQaVideoJob.id)
            .offset(offset)
            .limit(limit)
        ).all()
        total = self.session.scalar(
            select(func.count())
            .select_from(RulesQaVideoJob)
            .where(RulesQaVideoJob.project_id == project_id)
        )
        return [self._record(j) for j in jobs], total or 0

    def claim_next(self) -> ClaimedJob | None:
        """取最早建立的等待中工作並改成 running；多個執行緒同時取也不會取到同一筆。"""
        next_id = (
            select(RulesQaVideoJob.id)
            .where(RulesQaVideoJob.status == "queued")
            .order_by(RulesQaVideoJob.created_at, RulesQaVideoJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        row = self.session.execute(
            update(RulesQaVideoJob)
            .where(RulesQaVideoJob.id == next_id)
            .values(status="running", started_at=func.now(), progress=0)
            .returning(RulesQaVideoJob.id, RulesQaVideoJob.project_id, RulesQaVideoJob.kind)
        ).one_or_none()
        return None if row is None else ClaimedJob(*row)

    def _update_running(self, job_id: uuid.UUID, **values: Any) -> None:
        self.session.execute(
            update(RulesQaVideoJob)
            .where(RulesQaVideoJob.id == job_id, RulesQaVideoJob.status == "running")
            .values(**values)
        )

    def report(self, job_id: uuid.UUID, progress: float, message: str | None) -> None:
        self._update_running(job_id, progress=progress, message=message)

    def finish_succeeded(self, job_id: uuid.UUID, result: dict[str, Any] | None) -> None:
        self._update_running(
            job_id, status="succeeded", progress=1, result=result, finished_at=func.now()
        )

    def finish_failed(self, job_id: uuid.UUID, error: str, detail: str | None) -> None:
        self._update_running(
            job_id, status="failed", error=error, error_detail=detail, finished_at=func.now()
        )

    def fail_running(self, error: str) -> int:
        """伺服器重新啟動時：所有 running 的工作標為失敗；回傳筆數。"""
        result = self.session.execute(
            update(RulesQaVideoJob)
            .where(RulesQaVideoJob.status == "running")
            .values(status="failed", error=error, finished_at=func.now())
        )
        return result.rowcount


# --------------------------------------------------------------------------- 規則影片的用語對照表


@dataclass(frozen=True)
class VideoTermsRecord:
    game_id: int
    terms: list[dict[str, Any]]
    updated_by: uuid.UUID
    updated_at: datetime


class VideoTermsRepository(SessionRepository):
    """rules_qa_video_terms（add-rules-video-mobile design.md D4）。"""

    def get(self, game_id: int) -> VideoTermsRecord | None:
        row = self.session.get(RulesQaVideoTerms, game_id, populate_existing=True)
        if row is None:
            return None
        return VideoTermsRecord(row.game_id, row.terms, row.updated_by, row.updated_at)

    def replace(self, game_id: int, terms: list[dict[str, Any]], updated_by: uuid.UUID) -> None:
        """整份取代；沒有就新增。"""
        statement = pg_insert(RulesQaVideoTerms).values(
            game_id=game_id, terms=terms, updated_by=updated_by
        )
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[RulesQaVideoTerms.game_id],
                set_={"terms": terms, "updated_by": updated_by, "updated_at": func.now()},
            )
        )


# --------------------------------------------------------------------------- 規則書頁面文字


@dataclass(frozen=True)
class PagesRecord:
    chapter_pages: list[int]
    reference_pages: list[int]
    page_texts: dict[str, Any]
    pages_version: int


class VideoPagesRepository(SessionRepository):
    """rules_qa_video_projects 的頁面文字欄位（add-rules-video-mobile design.md D11）。"""

    def get(self, project_id: uuid.UUID) -> PagesRecord | None:
        row = self.session.execute(
            select(
                RulesQaVideoProject.chapter_pages,
                RulesQaVideoProject.reference_pages,
                RulesQaVideoProject.page_texts,
                RulesQaVideoProject.pages_version,
            ).where(RulesQaVideoProject.id == project_id)
        ).one_or_none()
        return None if row is None else PagesRecord(list(row[0]), list(row[1]), row[2], row[3])

    def save(
        self,
        project_id: uuid.UUID,
        *,
        chapter_pages: list[int],
        reference_pages: list[int],
        page_texts: dict[str, Any],
    ) -> None:
        """整份取代；版本加 1、更新專案的修改時間。"""
        self.session.execute(
            update(RulesQaVideoProject)
            .where(RulesQaVideoProject.id == project_id)
            .values(
                chapter_pages=chapter_pages,
                reference_pages=reference_pages,
                page_texts=page_texts,
                pages_version=RulesQaVideoProject.pages_version + 1,
                updated_at=func.now(),
            )
        )


# --------------------------------------------------------------------------- 草稿


@dataclass(frozen=True)
class DraftState:
    game_id: int
    chapter_number: int
    chapter_title: str
    chapter_pages: list[int]
    reference_pages: list[int]
    page_texts: dict[str, Any]
    pages_version: int
    video: dict[str, Any] | None
    video_version: int
    coverage: dict[str, Any] | None
    coverage_version: int | None
    draft_pages_version: int | None


class VideoDraftRepository(SessionRepository):
    """rules_qa_video_projects 的草稿欄位（add-rules-video-mobile design.md D11）。"""

    def get_state(self, project_id: uuid.UUID) -> DraftState | None:
        project = self.session.get(RulesQaVideoProject, project_id, populate_existing=True)
        if project is None:
            return None
        return DraftState(
            game_id=project.game_id,
            chapter_number=project.chapter_number,
            chapter_title=project.chapter_title,
            chapter_pages=list(project.chapter_pages),
            reference_pages=list(project.reference_pages),
            page_texts=project.page_texts,
            pages_version=project.pages_version,
            video=project.video,
            video_version=project.video_version,
            coverage=project.coverage,
            coverage_version=project.coverage_version,
            draft_pages_version=project.draft_pages_version,
        )

    def save_draft(
        self,
        project_id: uuid.UUID,
        *,
        expected_version: int,
        video: dict[str, Any],
        coverage: dict[str, Any],
        pages_version: int,
    ) -> bool:
        """video_version 還是 expected_version 才寫入；回傳是否寫入（沒寫入代表專案被改過）。"""
        result = self.session.execute(
            update(RulesQaVideoProject)
            .where(
                RulesQaVideoProject.id == project_id,
                RulesQaVideoProject.video_version == expected_version,
            )
            .values(
                video=video,
                video_version=expected_version + 1,
                coverage=coverage,
                coverage_version=expected_version + 1,
                draft_pages_version=pages_version,
                updated_at=func.now(),
            )
        )
        return result.rowcount == 1

    def save_video(
        self, project_id: uuid.UUID, *, expected_version: int, video: dict[str, Any]
    ) -> bool:
        """只改段資料（例如素材照片、方向、區域；涵蓋檢查不動）。條件同 save_draft。"""
        result = self.session.execute(
            update(RulesQaVideoProject)
            .where(
                RulesQaVideoProject.id == project_id,
                RulesQaVideoProject.video_version == expected_version,
            )
            .values(video=video, video_version=expected_version + 1, updated_at=func.now())
        )
        return result.rowcount == 1
