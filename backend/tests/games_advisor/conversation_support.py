"""推薦對話測試（service 與 API）共用的假桌遊、腳本項目與 service 組裝。"""

from typing import TYPE_CHECKING, Any

from app.integrations.embedding import FakeEmbeddingProvider
from app.integrations.llm import FakeLLMProvider, FakeResponse, ToolCall
from tests.games_advisor.fakes import FakeSearchRepository
from tests.games_advisor.support import make_tag

if TYPE_CHECKING:
    from app.domains.games_advisor.conversation import ConversationService

DIM = 4
MODEL = "m1"
REJECTED_REPLY = "這則訊息我沒辦法回答，請換個說法再試一次。"
DROPPED_REPLY = "這次推薦出了問題，請再說一次你的需求。"

# 甲、乙：2–4 人、30 分鐘、8 歲；丙：3–6 人、60 分鐘；丁：5–8 人、60 分鐘
# 4 人查得到甲、乙、丙；2 人查得到甲、乙；6 人查得到丙、丁
GAMES = [
    {"id": 1, "name": "甲", "min_players": 2, "max_players": 4, "max_playtime": 30, "weight": 1.5},
    {"id": 2, "name": "乙", "min_players": 2, "max_players": 4, "max_playtime": 30, "weight": 2.0},
    {"id": 3, "name": "丙", "min_players": 3, "max_players": 6, "max_playtime": 60, "weight": 2.5},
    {"id": 4, "name": "丁", "min_players": 5, "max_players": 8, "max_playtime": 60, "weight": 3.0},
]


def game_row(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "bgg_id": 800000 + values["id"],
        "english_name": f"Game {values['id']}",
        "min_playtime": 20,
        "min_age": 8 if values["id"] <= 2 else 10,
        "categories": [],
        "mechanics": [],
        **values,
    }


def excerpt(game_id: int, letter: str) -> dict[str, Any]:
    return {
        "id": f"e{game_id}{letter}",
        "text": f"第 {game_id} 款的片段 {letter}",
        "language": "zh-TW",
    }


def make_repo() -> FakeSearchRepository:
    return FakeSearchRepository(
        [game_row(values) for values in GAMES],
        tags=[make_tag("laughter")],
        excerpts={
            values["id"]: [excerpt(values["id"], "a"), excerpt(values["id"], "b")]
            for values in GAMES
        },
    )


def search(call_id: str = "call_1", **arguments: Any) -> FakeResponse:
    """腳本項目：要求查詢一次。沒給的參數是 null。"""
    values: dict[str, Any] = {
        "players": None,
        "max_minutes": None,
        "min_minutes": None,
        "youngest_age": None,
        "prefer_tags": None,
        "avoid_tags": None,
        "prefer_categories": None,
        "avoid_categories": None,
        "prefer_mechanics": None,
        "avoid_mechanics": None,
        "weight_min": None,
        "weight_max": None,
        "preference_text": None,
        "exclude_game_ids": None,
    }
    values.update(arguments)
    return FakeResponse(tool_calls=[ToolCall(call_id, "search_games", values)])


def rec(game_id: int, *excerpt_ids: str, reason: str = "推薦理由") -> dict[str, Any]:
    return {"game_id": game_id, "reason": reason, "excerpt_ids": list(excerpt_ids)}


def final(reply: str = "好的", *recommendations: dict[str, Any]) -> FakeResponse:
    """腳本項目：最終輸出。"""
    return FakeResponse(output={"reply": reply, "recommendations": list(recommendations)})


def make_service(
    responses: list[FakeResponse | Exception] | None,
    repo: FakeSearchRepository | None = None,
    embedding: FakeEmbeddingProvider | None = None,
) -> tuple["ConversationService", FakeLLMProvider, FakeSearchRepository]:
    from app.domains.games_advisor.conversation import ConversationService
    from app.domains.games_advisor.search import GameSearch

    repo = repo or make_repo()
    llm = FakeLLMProvider(responses=responses)
    game_search = GameSearch(
        games=repo,
        tags=repo,
        reviews=repo,
        embedding=embedding or FakeEmbeddingProvider(DIM),
        embedding_model=MODEL,
    )
    return ConversationService(search=game_search, llm=llm), llm, repo


def responds(llm: FakeLLMProvider) -> list[dict[str, Any]]:
    return [call.kwargs for call in llm.calls if call.method == "respond"]
