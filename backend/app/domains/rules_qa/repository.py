"""規則教學與問答的資料存取。交易範圍由 service 用 transaction() 決定。

遊戲名稱讀取共用表 games（只讀，AGENTS.md §4.2 的共用資料表例外）。
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, exists, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import SessionRepository
from app.core.games.models import Game
from app.domains.rules_qa.models import RulesQaChunk, RulesQaVideo, RulesQaVideoProject


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
