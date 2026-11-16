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

    def replace_game_tags(self, game_id: int, tags: Sequence[Mapping[str, Any]]) -> None:
        """把一款桌遊的標籤整組換成 tags；每個是 code 與 confidence。"""
        self._require_transaction()
        for code in list(self.game_tags):
            kept = [entry for entry in self.game_tags[code] if entry["game"]["id"] != game_id]
            if kept:
                self.game_tags[code] = kept
            else:
                del self.game_tags[code]
        for tag in tags:
            assert tag["code"] in self.tags, f"沒有標籤 {tag['code']}"
            self.game_tags.setdefault(tag["code"], []).append(
                {"game": {"id": game_id}, "confidence": tag["confidence"]}
            )

    def tags_of(self, game_id: int) -> dict[str, float]:
        """測試用：一款桌遊目前的標籤，代碼 → 信心分數。"""
        return {
            code: entry["confidence"]
            for code, entries in self.game_tags.items()
            for entry in entries
            if entry["game"]["id"] == game_id
        }


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


class FakeSearchRepository:
    """假的「查桌遊」資料來源：同一個物件當作 GameRepository、TagRepository、ReviewRepository。

    - games：桌遊清單，每款是 id 加上 games 的欄位（至少要有篩條件用到的欄位）。
    - game_tags：桌遊 id → {代碼: 信心分數}；tags：詞彙表，每個是 code、name、definition。
    - summary_models：桌遊 id → 心得摘要向量的模型名稱；沒列的桌遊就是沒有心得摘要。
    - similarities：桌遊 id → 帶查詢向量、而且模型相同時回傳的相似度。
    - excerpts：桌遊 id → 心得片段清單，照「由近到遠」的順序寫。
    - excerpt_models：桌遊 id → 這款心得片段用過的模型名稱；沒列的桌遊當作沒有心得片段。
    - filter_calls、excerpt_calls 記下 service 怎麼查的。
    """

    def __init__(
        self,
        games: list[dict[str, Any]],
        *,
        tags: list[dict[str, str]] | None = None,
        game_tags: dict[int, dict[str, float]] | None = None,
        summary_models: dict[int, str] | None = None,
        similarities: dict[int, float] | None = None,
        excerpts: dict[int, list[dict[str, Any]]] | None = None,
        excerpt_models: dict[int, list[str]] | None = None,
    ) -> None:
        self.games = sorted(games, key=lambda game: game["id"])
        self.excerpt_models = dict(excerpt_models or {})
        self.tags = list(tags or [])
        self.game_tags = dict(game_tags or {})
        self.summary_models = dict(summary_models or {})
        self.similarities = dict(similarities or {})
        self.excerpts = dict(excerpts or {})
        self.filter_calls: list[dict[str, Any]] = []
        self.excerpt_calls: list[dict[str, Any]] = []

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    # GameRepository
    def filter_games(
        self,
        *,
        players: int,
        max_minutes: int | None = None,
        min_minutes: int | None = None,
        youngest_age: int | None = None,
        exclude_ids: Collection[int] = (),
    ) -> list[dict[str, Any]]:
        self.filter_calls.append(
            {
                "players": players,
                "max_minutes": max_minutes,
                "min_minutes": min_minutes,
                "youngest_age": youngest_age,
                "exclude_ids": list(exclude_ids),
            }
        )
        return [
            dict(game)
            for game in self.games
            if game["min_players"] <= players <= game["max_players"]
            and (max_minutes is None or game["max_playtime"] <= max_minutes)
            and (min_minutes is None or game["max_playtime"] >= min_minutes)
            and (youngest_age is None or game["min_age"] <= youngest_age)
            and game["id"] not in set(exclude_ids)
        ]

    def list_categories(self) -> list[str]:
        return sorted({value for game in self.games for value in game["categories"]})

    def list_mechanics(self) -> list[str]:
        return sorted({value for game in self.games for value in game["mechanics"]})

    def list_game_ids(self) -> list[int]:
        return [game["id"] for game in self.games]

    # TagRepository
    def list_tags(self) -> list[dict[str, str]]:
        return sorted((dict(tag) for tag in self.tags), key=lambda tag: tag["code"])

    def list_game_tags(self, game_ids: Collection[int]) -> dict[int, dict[str, float]]:
        return {
            game_id: dict(self.game_tags[game_id])
            for game_id in game_ids
            if game_id in self.game_tags
        }

    # ReviewRepository
    def summary_similarities(
        self,
        game_ids: Collection[int],
        *,
        embedding_model: str,
        query_vector: Sequence[float] | None,
    ) -> dict[int, dict[str, Any]]:
        result: dict[int, dict[str, Any]] = {}
        for game_id in game_ids:
            if game_id not in self.summary_models:
                continue
            model = self.summary_models[game_id]
            usable = query_vector is not None and model == embedding_model
            result[game_id] = {
                "embedding_model": model,
                "similarity": self.similarities.get(game_id) if usable else None,
            }
        return result

    def nearest_excerpts(
        self,
        game_id: int,
        *,
        embedding_model: str,
        limit: int,
        query_vector: Sequence[float] | None,
    ) -> list[dict[str, Any]]:
        self.excerpt_calls.append(
            {
                "game_id": game_id,
                "query_vector": None if query_vector is None else list(query_vector),
                "limit": limit,
            }
        )
        return [dict(excerpt) for excerpt in self.excerpts.get(game_id, [])[:limit]]

    def list_excerpt_models(self, game_ids: Collection[int]) -> dict[int, list[str]]:
        return {
            game_id: sorted(self.excerpt_models[game_id])
            for game_id in game_ids
            if game_id in self.excerpt_models
        }
