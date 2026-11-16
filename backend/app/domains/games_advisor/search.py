"""「查桌遊」工具 search_games（spec §11）：屬於 service 層，由對話 service 在工具迴圈裡呼叫。

- 工具定義：enum 每則玩家訊息都從資料庫讀一次（load_vocabulary），同步詞彙表或桌遊後不用重啟。
- 參數檢查：Azure strict 模式保證型別與 enum，但 FakeLLMProvider 不檢查，所以這裡再檢查一次；
  不合理就把錯誤回給 LLM，不查詢（§11.2）。
- 排序：SQL 篩條件後，負面分數低的在前，再用 RRF 合併結構化分數與心得摘要相似度（§11.4）。
"""

import logging
from collections.abc import Collection, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from app.domains.games_advisor.constants import (
    EXCERPTS_PER_GAME,
    MAX_RECOMMENDATIONS,
    RRF_K,
    TAG_CONFIDENCE_THRESHOLD,
)
from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.llm.types import ToolSpec

logger = logging.getLogger(__name__)

TOOL_NAME = "search_games"
MIN_PLAYERS = 1
MAX_PLAYERS = 30
MIN_WEIGHT = 1
MAX_WEIGHT = 5

# ⚠️ 回傳給 LLM、也用來組卡片的基本資料（spec §11.7、§13.1）；要和 schemas.AdvisorGame 的欄位一致
GAME_FIELDS = (
    "id",
    "name",
    "min_players",
    "max_players",
    "min_playtime",
    "max_playtime",
    "min_age",
    "weight",
)


class GameSource(Protocol):
    """共用桌遊表的查詢（app/core/games/repository.py 的 GameRepository）。"""

    def transaction(self) -> AbstractContextManager[None]: ...

    def filter_games(
        self,
        *,
        players: int,
        max_minutes: int | None = None,
        min_minutes: int | None = None,
        youngest_age: int | None = None,
        exclude_ids: Collection[int] = (),
    ) -> list[dict[str, Any]]: ...

    def list_categories(self) -> list[str]: ...

    def list_mechanics(self) -> list[str]: ...

    def list_game_ids(self) -> list[int]: ...


class TagSource(Protocol):
    """標籤詞彙表與每款桌遊的標籤（TagRepository）。"""

    def list_tags(self) -> list[dict[str, str]]: ...

    def list_game_tags(self, game_ids: Collection[int]) -> dict[int, dict[str, float]]: ...


class ReviewSource(Protocol):
    """心得摘要的相似度與心得片段（ReviewRepository）。"""

    def summary_similarities(
        self,
        game_ids: Collection[int],
        *,
        embedding_model: str,
        query_vector: Sequence[float] | None,
    ) -> dict[int, dict[str, Any]]: ...

    def nearest_excerpts(
        self,
        game_id: int,
        *,
        embedding_model: str,
        limit: int,
        query_vector: Sequence[float] | None,
    ) -> list[dict[str, Any]]: ...

    def list_excerpt_models(self, game_ids: Collection[int]) -> dict[int, list[str]]: ...


@dataclass(frozen=True)
class SearchVocabulary:
    """組工具定義與檢查參數用的清單；每則玩家訊息讀一次。"""

    tags: list[dict[str, str]]
    categories: list[str]
    mechanics: list[str]
    game_ids: list[int]

    @property
    def tag_codes(self) -> list[str]:
        return [tag["code"] for tag in self.tags]


@dataclass(frozen=True)
class SearchQuery:
    """檢查過的工具參數。清單參數沒帶時是空的 tuple。"""

    players: int
    max_minutes: int | None
    min_minutes: int | None
    youngest_age: int | None
    prefer_tags: tuple[str, ...]
    avoid_tags: tuple[str, ...]
    prefer_categories: tuple[str, ...]
    avoid_categories: tuple[str, ...]
    prefer_mechanics: tuple[str, ...]
    avoid_mechanics: tuple[str, ...]
    weight_min: float | None
    weight_max: float | None
    preference_text: str | None
    exclude_game_ids: tuple[int, ...]

    @property
    def has_structured_preferences(self) -> bool:
        """有沒有正面的結構化偏好（prefer_*、weight_*）。"""
        return bool(
            self.prefer_tags
            or self.prefer_categories
            or self.prefer_mechanics
            or self.weight_min is not None
            or self.weight_max is not None
        )


@dataclass(frozen=True)
class SearchOutcome:
    """查一次的結果。output 原樣送回給 LLM；query 是 None 代表參數不合理、沒有查詢。"""

    output: dict[str, Any]
    query: SearchQuery | None

    @property
    def is_error(self) -> bool:
        return self.query is None

    @property
    def games(self) -> list[dict[str, Any]]:
        """查到的桌遊，照名次排；每款的格式同 spec §11.7。"""
        return list(self.output.get("games", []))


class InvalidArguments(Exception):
    """工具參數不合理；訊息會原樣回給 LLM。"""


class GameSearch:
    """「查桌遊」工具。repository 由呼叫端傳入，service 測試換成假的。"""

    def __init__(
        self,
        *,
        games: GameSource,
        tags: TagSource,
        reviews: ReviewSource,
        embedding: EmbeddingProvider,
        embedding_model: str,
    ) -> None:
        self._games = games
        self._tags = tags
        self._reviews = reviews
        self._embedding = embedding
        self._embedding_model = embedding_model

    def load_vocabulary(self) -> SearchVocabulary:
        # 讀完就結束交易，不開著交易等模型回應
        with self._games.transaction():
            return SearchVocabulary(
                tags=self._tags.list_tags(),
                categories=self._games.list_categories(),
                mechanics=self._games.list_mechanics(),
                game_ids=self._games.list_game_ids(),
            )

    def run(self, arguments: dict[str, Any], vocabulary: SearchVocabulary) -> SearchOutcome:
        """執行一次工具呼叫。embedding 的例外（EmbeddingError）往上拋，由對話 service 處理。"""
        try:
            query = _parse_arguments(arguments, vocabulary)
        except InvalidArguments as exc:
            return SearchOutcome(output={"error": str(exc)}, query=None)

        # 先算向量再開交易：等 embedding 回應時不佔著交易
        query_vector = None
        if query.preference_text is not None:
            [query_vector] = self._embedding.embed([query.preference_text])

        with self._games.transaction():
            games = self._ranked_games(query, query_vector)
            self._warn_other_excerpt_models(games)
            output_games = [
                _game_output(
                    game,
                    query,
                    vocabulary,
                    self._reviews.nearest_excerpts(
                        game["id"],
                        embedding_model=self._embedding_model,
                        limit=EXCERPTS_PER_GAME,
                        query_vector=query_vector,
                    ),
                )
                for game in games
            ]
        return SearchOutcome(output={"games": output_games}, query=query)

    def _ranked_games(
        self, query: SearchQuery, query_vector: list[float] | None
    ) -> list[dict[str, Any]]:
        candidates = self._games.filter_games(
            players=query.players,
            max_minutes=query.max_minutes,
            min_minutes=query.min_minutes,
            youngest_age=query.youngest_age,
            exclude_ids=query.exclude_game_ids,
        )
        if not candidates:
            return []
        ids = [game["id"] for game in candidates]
        game_tags = self._tags.list_game_tags(ids)
        summaries = self._reviews.summary_similarities(
            ids, embedding_model=self._embedding_model, query_vector=query_vector
        )
        self._warn_other_models(candidates, summaries)

        for game in candidates:
            game["tags"] = game_tags.get(game["id"], {})
        structured = [_preference_score(game, query, avoid=False) for game in candidates]
        negative = [_preference_score(game, query, avoid=True) for game in candidates]
        similarity = [
            summaries.get(game["id"], {}).get("similarity") if query_vector is not None else None
            for game in candidates
        ]

        rank_lists: list[list[int]] = []
        if query.has_structured_preferences:
            rank_lists.append(_competition_ranks(structured))
        if query_vector is not None:
            rank_lists.append(_competition_ranks(similarity))
        rrf = [
            sum(1 / (RRF_K + ranks[index]) for ranks in rank_lists)
            for index in range(len(candidates))
        ]

        order = sorted(
            range(len(candidates)),
            key=lambda index: (
                negative[index],
                -rrf[index],
                candidates[index]["weight"],
                candidates[index]["name"],
            ),
        )
        return [candidates[index] for index in order[:MAX_RECOMMENDATIONS]]

    def _warn_other_models(
        self, candidates: list[dict[str, Any]], summaries: dict[int, dict[str, Any]]
    ) -> None:
        stale = [
            f"{game['id']} 號「{game['name']}」（{summaries[game['id']]['embedding_model']}）"
            for game in candidates
            if game["id"] in summaries
            and summaries[game["id"]]["embedding_model"] != self._embedding_model
        ]
        if stale:
            logger.warning(
                "心得摘要向量的模型和目前設定 %s 不同，當作沒有向量：%s",
                self._embedding_model,
                "、".join(stale),
            )

    def _warn_other_excerpt_models(self, games: list[dict[str, Any]]) -> None:
        """回傳的桌遊有心得片段用的不是目前的模型時寫 log；那些片段查不到（spec §11.6）。"""
        if not games:
            return
        models = self._reviews.list_excerpt_models([game["id"] for game in games])
        stale = [
            f"{game['id']} 號「{game['name']}」（{'、'.join(others)}）"
            for game in games
            if (others := [m for m in models.get(game["id"], []) if m != self._embedding_model])
        ]
        if stale:
            logger.warning(
                "心得片段向量的模型和目前設定 %s 不同，這些片段當作沒有：%s",
                self._embedding_model,
                "、".join(stale),
            )


# --- 排序 ---


def _matched_tags(game: dict[str, Any], codes: Sequence[str]) -> list[str]:
    """這款有、而且信心分數到門檻的標籤，照參數的順序。"""
    return [code for code in codes if game["tags"].get(code, 0) >= TAG_CONFIDENCE_THRESHOLD]


def _weight_in_range(game: dict[str, Any], query: SearchQuery) -> bool | None:
    if query.weight_min is None and query.weight_max is None:
        return None
    low = query.weight_min if query.weight_min is not None else MIN_WEIGHT
    high = query.weight_max if query.weight_max is not None else MAX_WEIGHT
    return low <= game["weight"] <= high


def _preference_score(game: dict[str, Any], query: SearchQuery, *, avoid: bool) -> float:
    """命中標籤的信心分數總和＋命中的類別數＋命中的機制數（＋難度在範圍內時 1，只算正面）。"""
    tags = query.avoid_tags if avoid else query.prefer_tags
    categories = query.avoid_categories if avoid else query.prefer_categories
    mechanics = query.avoid_mechanics if avoid else query.prefer_mechanics
    score = sum(game["tags"][code] for code in _matched_tags(game, tags))
    score += len(set(categories) & set(game["categories"]))
    score += len(set(mechanics) & set(game["mechanics"]))
    if not avoid and _weight_in_range(game, query):
        score += 1
    return score


def _competition_ranks(values: Sequence[float | None]) -> list[int]:
    """分數高的名次在前；同分同名次，下一個名次跳過（1、2、2、4）。None 並列最後。"""
    present = [value for value in values if value is not None]
    return [
        len(present) + 1 if value is None else 1 + sum(other > value for other in present)
        for value in values
    ]


# --- 回傳給 LLM 的內容 ---


def _tag_details(codes: Sequence[str], vocabulary: SearchVocabulary) -> list[dict[str, str]]:
    by_code = {tag["code"]: tag for tag in vocabulary.tags}
    return [
        {"name": by_code[code]["name"], "definition": by_code[code]["definition"]} for code in codes
    ]


def _game_output(
    game: dict[str, Any],
    query: SearchQuery,
    vocabulary: SearchVocabulary,
    excerpts: list[dict[str, Any]],
) -> dict[str, Any]:
    """spec §11.7：基本資料、命中的偏好與負面偏好、心得片段。不回網址、心得摘要、信心分數。"""

    def matched(values: Sequence[str], game_values: Sequence[str]) -> list[str]:
        return [value for value in values if value in game_values]

    return {
        **{field: game[field] for field in GAME_FIELDS},
        "matched_preferences": {
            "tags": _tag_details(_matched_tags(game, query.prefer_tags), vocabulary),
            "categories": matched(query.prefer_categories, game["categories"]),
            "mechanics": matched(query.prefer_mechanics, game["mechanics"]),
            "weight_in_range": _weight_in_range(game, query),
        },
        "matched_avoids": {
            "tags": _tag_details(_matched_tags(game, query.avoid_tags), vocabulary),
            "categories": matched(query.avoid_categories, game["categories"]),
            "mechanics": matched(query.avoid_mechanics, game["mechanics"]),
        },
        "excerpts": [
            {"id": excerpt["id"], "text": excerpt["text"], "language": excerpt["language"]}
            for excerpt in excerpts
        ],
    }


# --- 參數檢查 ---


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _optional_int(arguments: dict[str, Any], name: str, minimum: int, message: str) -> int | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not _is_int(value) or value < minimum:
        raise InvalidArguments(message)
    return value


def _optional_weight(arguments: dict[str, Any], name: str) -> float | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not _is_number(value) or not MIN_WEIGHT <= value <= MAX_WEIGHT:
        raise InvalidArguments(f"{name} 要是 {MIN_WEIGHT} 到 {MAX_WEIGHT} 之間的數字。")
    return value


def _enum_list(arguments: dict[str, Any], name: str, allowed: Sequence[Any]) -> tuple[Any, ...]:
    value = arguments.get(name)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise InvalidArguments(f"{name} 要是清單。")
    unknown = [item for item in value if item not in allowed or isinstance(item, bool)]
    if unknown:
        listed = "、".join(str(item) for item in unknown)
        raise InvalidArguments(f"{name} 有不在清單裡的值：{listed}，只能用參數說明列出的值。")
    return tuple(dict.fromkeys(value))


def _parse_arguments(arguments: dict[str, Any], vocabulary: SearchVocabulary) -> SearchQuery:
    players = arguments.get("players")
    if not _is_int(players) or not MIN_PLAYERS <= players <= MAX_PLAYERS:
        raise InvalidArguments(f"人數要在 {MIN_PLAYERS} 到 {MAX_PLAYERS} 之間，請向玩家確認人數。")

    max_minutes = _optional_int(arguments, "max_minutes", 1, "max_minutes 要是 1 以上的整數。")
    min_minutes = _optional_int(arguments, "min_minutes", 1, "min_minutes 要是 1 以上的整數。")
    if max_minutes is not None and min_minutes is not None and min_minutes > max_minutes:
        raise InvalidArguments("min_minutes 不能大於 max_minutes。")
    youngest_age = _optional_int(arguments, "youngest_age", 0, "youngest_age 要是 0 以上的整數。")

    weight_min = _optional_weight(arguments, "weight_min")
    weight_max = _optional_weight(arguments, "weight_max")
    if weight_min is not None and weight_max is not None and weight_min > weight_max:
        raise InvalidArguments("weight_min 不能大於 weight_max。")

    preference_text = arguments.get("preference_text")
    if preference_text is not None and not isinstance(preference_text, str):
        raise InvalidArguments("preference_text 要是文字。")
    # 空字串或只有空白當作沒帶：embed 遇到空白會拋 ValueError
    if preference_text is not None and not preference_text.strip():
        preference_text = None

    tag_codes = vocabulary.tag_codes
    return SearchQuery(
        players=players,
        max_minutes=max_minutes,
        min_minutes=min_minutes,
        youngest_age=youngest_age,
        prefer_tags=_enum_list(arguments, "prefer_tags", tag_codes),
        avoid_tags=_enum_list(arguments, "avoid_tags", tag_codes),
        prefer_categories=_enum_list(arguments, "prefer_categories", vocabulary.categories),
        avoid_categories=_enum_list(arguments, "avoid_categories", vocabulary.categories),
        prefer_mechanics=_enum_list(arguments, "prefer_mechanics", vocabulary.mechanics),
        avoid_mechanics=_enum_list(arguments, "avoid_mechanics", vocabulary.mechanics),
        weight_min=weight_min,
        weight_max=weight_max,
        preference_text=preference_text.strip() if preference_text is not None else None,
        exclude_game_ids=_enum_list(arguments, "exclude_game_ids", vocabulary.game_ids),
    )


# --- 工具定義 ---


def _nullable(json_type: str, description: str) -> dict[str, Any]:
    return {"type": [json_type, "null"], "description": description}


def _enum_array(item_type: str, values: Sequence[Any], description: str) -> dict[str, Any]:
    return {
        "type": ["array", "null"],
        "items": {"type": item_type, "enum": list(values)},
        "description": description,
    }


def build_search_tool(vocabulary: SearchVocabulary) -> ToolSpec:
    """組出 search_games 的工具定義（spec §11.1）。

    ⚠️ 照 Azure strict 的規定：所有參數都列為 required、選填的可為 null、additionalProperties
    為 false。某份清單是空的就拿掉對應的參數，不送出空的 enum。
    """
    tag_lines = "\n".join(
        f"{tag['code']}：{tag['name']}——{tag['definition']}" for tag in vocabulary.tags
    )
    properties: dict[str, Any] = {
        "players": {
            "type": "integer",
            "description": f"玩家人數，{MIN_PLAYERS} 到 {MAX_PLAYERS}。唯一的必要條件。",
        },
        "max_minutes": _nullable("integer", "最長能玩幾分鐘：最長的一局也要在這個時間內。"),
        "min_minutes": _nullable("integer", "至少想玩幾分鐘。"),
        "youngest_age": _nullable("integer", "最年輕玩家的年齡。"),
    }
    if vocabulary.tags:
        properties["prefer_tags"] = _enum_array(
            "string",
            vocabulary.tag_codes,
            f"想要的感受。可用的標籤（代碼：名稱——定義）：\n{tag_lines}",
        )
        properties["avoid_tags"] = _enum_array(
            "string", vocabulary.tag_codes, f"不想要的感受，標籤同 prefer_tags：\n{tag_lines}"
        )
    if vocabulary.categories:
        properties["prefer_categories"] = _enum_array(
            "string", vocabulary.categories, "想要的 BGG 類別（英文名稱）。"
        )
        properties["avoid_categories"] = _enum_array(
            "string", vocabulary.categories, "不想要的 BGG 類別（英文名稱）。"
        )
    if vocabulary.mechanics:
        properties["prefer_mechanics"] = _enum_array(
            "string", vocabulary.mechanics, "想要的 BGG 機制（英文名稱）。"
        )
        properties["avoid_mechanics"] = _enum_array(
            "string", vocabulary.mechanics, "不想要的 BGG 機制（英文名稱）。"
        )
    properties["weight_min"] = _nullable("number", "難度下限，1 到 5，可只填一個。")
    properties["weight_max"] = _nullable("number", "難度上限，1 到 5，可只填一個。")
    properties["preference_text"] = _nullable(
        "string", "把玩家所有正面偏好寫成一句繁體中文；玩家沒有偏好時給 null。"
    )
    if vocabulary.game_ids:
        properties["exclude_game_ids"] = _enum_array(
            "integer", vocabulary.game_ids, "已經推薦過、這次不要再出現的桌遊 id。"
        )
    return ToolSpec(
        name=TOOL_NAME,
        description="依人數等條件與玩家偏好查詢桌遊，回傳最適合的至多 3 款與心得片段。",
        parameters={
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    )
