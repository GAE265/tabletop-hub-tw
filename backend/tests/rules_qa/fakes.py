"""rules_qa service 單元測試用的手寫 fake（AGENTS.md 7.5）。

照 RulesQaRepository 的介面在記憶體中運作。

只在 fixture 裡 import 這個模組：程式還沒寫的時候，每個測試各自失敗，不會整個資料夾收集失敗。
"""

import math
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from app.domains.rules_qa.repository import ChunkHit, LessonSummary, VideoRecord


@dataclass
class _Chunk:
    id: uuid.UUID
    game_id: int
    page: int
    content: str
    embedding: list[float]
    embedding_model: str


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


class FakeRulesQaRepository:
    def __init__(self) -> None:
        self.games: dict[int, str] = {}
        self.videos: dict[int, VideoRecord] = {}
        self.chunks: list[_Chunk] = []
        self.searches: list[tuple[int, str, int]] = []
        self.committed = 0
        self.rolled_back = 0

    # --- 測試準備資料用 ---

    def add_game(self, game_id: int, name: str) -> int:
        self.games[game_id] = name
        return game_id

    def add_chunk(
        self, game_id: int, page: int, content: str, embedding: list[float], model: str = "fake"
    ) -> uuid.UUID:
        chunk = _Chunk(uuid.uuid4(), game_id, page, content, embedding, model)
        self.chunks.append(chunk)
        return chunk.id

    # --- RulesQaRepository 介面 ---

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.rolled_back += 1
            raise
        self.committed += 1

    def game_name(self, game_id: int) -> str | None:
        return self.games.get(game_id)

    def lesson_summaries(self) -> list[LessonSummary]:
        game_ids = set(self.videos) | {c.game_id for c in self.chunks}
        return [
            LessonSummary(
                game_id=game_id,
                game_name=self.games[game_id],
                has_video=game_id in self.videos,
                has_rulebook=any(c.game_id == game_id for c in self.chunks),
            )
            for game_id in sorted(game_ids, key=lambda g: self.games[g])
        ]

    def get_video(self, game_id: int) -> VideoRecord | None:
        return self.videos.get(game_id)

    def has_chunks(self, game_id: int) -> bool:
        return any(c.game_id == game_id for c in self.chunks)

    def upsert_video(self, video: VideoRecord) -> None:
        self.videos[video.game_id] = video

    def replace_chunks(
        self,
        game_id: int,
        chunks: Sequence[tuple[int, str, list[float]]],
        embedding_model: str,
    ) -> None:
        self.chunks = [c for c in self.chunks if c.game_id != game_id]
        for page, content, embedding in chunks:
            self.add_chunk(game_id, page, content, embedding, embedding_model)

    def search_chunks(
        self, game_id: int, vector: Sequence[float], embedding_model: str, limit: int
    ) -> list[ChunkHit]:
        self.searches.append((game_id, embedding_model, limit))
        candidates = [
            c for c in self.chunks if c.game_id == game_id and c.embedding_model == embedding_model
        ]
        candidates.sort(key=lambda c: _cosine(c.embedding, vector), reverse=True)
        return [ChunkHit(id=c.id, page=c.page, content=c.content) for c in candidates[:limit]]
