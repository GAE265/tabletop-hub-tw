"""games_advisor service 測試用的手寫 fake（AGENTS.md §7.5）：不連資料庫、不連外部服務。"""

import copy
from collections.abc import Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from app.integrations.embedding.fake import FakeEmbeddingProvider


class FakeGameRepository:
    """假的桌遊查詢：資料放在記憶體，只有 service 讀桌遊用到的方法。"""

    def __init__(self, games: list[dict[str, Any]]) -> None:
        self.games = sorted(games, key=lambda game: game["id"])

    def list_games(self) -> list[dict[str, Any]]:
        return [dict(game) for game in self.games]

    def find_games_by_bgg_ids(self, bgg_ids: Collection[int]) -> list[dict[str, Any]]:
        return [dict(game) for game in self.games if game["bgg_id"] in set(bgg_ids)]


class FakeReviewRepository:
    """假的心得摘要與心得片段資料表。

    - summaries：桌遊 id → 心得摘要那一列；excerpts：桌遊 id → 心得片段的清單。
    - transaction() 和真的一樣：區塊裡拋出例外，這個交易寫的東西全部退回。
    - 不在 transaction() 裡寫入就是測試失敗：真的資料庫不提交就等於沒寫。
    """

    def __init__(self) -> None:
        self.summaries: dict[int, dict[str, Any]] = {}
        self.excerpts: dict[int, list[dict[str, Any]]] = {}
        self._in_transaction = False

    @contextmanager
    def transaction(self) -> Iterator[None]:
        before = copy.deepcopy((self.summaries, self.excerpts))
        self._in_transaction = True
        try:
            yield
        except BaseException:
            self.summaries, self.excerpts = before
            raise
        finally:
            self._in_transaction = False

    def _require_transaction(self) -> None:
        assert self._in_transaction, "寫入要放在 transaction() 裡，否則不會提交"

    def save_review_summary(
        self, game_id: int, summary: str, embedding: Sequence[float], embedding_model: str
    ) -> None:
        self._require_transaction()
        self.summaries[game_id] = {
            "summary": summary,
            "embedding": list(embedding),
            "embedding_model": embedding_model,
        }

    def delete_review_summary(self, game_id: int) -> None:
        self._require_transaction()
        self.summaries.pop(game_id, None)

    def replace_review_excerpts(self, game_id: int, excerpts: Sequence[Mapping[str, Any]]) -> None:
        self._require_transaction()
        self.excerpts[game_id] = [dict(excerpt) for excerpt in excerpts]


class FakeTagRepository:
    """假的標籤詞彙表與每款桌遊的標籤。

    - tags：代碼 → {"name", "definition"}。
    - game_tags：代碼 → 有這個標籤的桌遊清單，每筆是 {"game": 桌遊, "confidence": 信心分數}。
    - transaction() 和寫入的規定同 FakeReviewRepository。
    """

    def __init__(self) -> None:
        self.tags: dict[str, dict[str, str]] = {}
        self.game_tags: dict[str, list[dict[str, Any]]] = {}
        self._in_transaction = False

    @contextmanager
    def transaction(self) -> Iterator[None]:
        before = copy.deepcopy((self.tags, self.game_tags))
        self._in_transaction = True
        try:
            yield
        except BaseException:
            self.tags, self.game_tags = before
            raise
        finally:
            self._in_transaction = False

    def _require_transaction(self) -> None:
        assert self._in_transaction, "寫入要放在 transaction() 裡，否則不會提交"

    def list_tags(self) -> list[dict[str, str]]:
        return [{"code": code, **self.tags[code]} for code in sorted(self.tags)]

    def list_tag_codes(self) -> list[str]:
        return sorted(self.tags)

    def add_tag(self, code: str, name: str, definition: str) -> None:
        self._require_transaction()
        assert code not in self.tags, f"標籤 {code} 已經存在"
        self.tags[code] = {"name": name, "definition": definition}

    def update_tag(self, code: str, name: str, definition: str) -> None:
        self._require_transaction()
        assert code in self.tags, f"沒有標籤 {code}"
        self.tags[code] = {"name": name, "definition": definition}

    def delete_tag(self, code: str) -> list[dict[str, Any]]:
        """刪掉標籤，連帶刪掉各款桌遊上的這個標籤；回傳受影響的桌遊。"""
        self._require_transaction()
        del self.tags[code]
        return [entry["game"] for entry in self.game_tags.pop(code, [])]


class FakeEmbeddingProviderFailingOnCall(FakeEmbeddingProvider):
    """integrations 的 FakeEmbeddingProvider，但只有第 fail_on 次呼叫 embed 會拋出 error。

    用來測「某一款失敗、其他款照寫」：原本的 fake 設了 error 之後每次呼叫都失敗。
    """

    def __init__(self, dim: int, fail_on: int, error: Exception) -> None:
        super().__init__(dim)
        self._fail_on = fail_on
        self._failure = error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if len(self.calls) + 1 == self._fail_on:
            self.calls.append(list(texts))
            raise self._failure
        return super().embed(texts)
