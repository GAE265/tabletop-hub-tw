"""規則教學與問答的資料存取。交易範圍由 service 用 transaction() 決定。

遊戲名稱讀取共用表 games（只讀，AGENTS.md §4.2 的共用資料表例外）。
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, exists, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import SessionRepository
from app.core.games.models import Game
from app.domains.rules_qa.models import RulesQaChunk, RulesQaVideo


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

    def replace_page_chunks(
        self,
        game_id: int,
        page: int,
        chunks: Sequence[tuple[str, list[float]]],
        embedding_model: str,
    ) -> None:
        """取代這款遊戲某一頁的段落（文字、向量）。空清單代表這一頁已無內容，只刪除舊段落。"""
        self.session.execute(
            delete(RulesQaChunk).where(RulesQaChunk.game_id == game_id, RulesQaChunk.page == page)
        )
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
                    for content, embedding in chunks
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
