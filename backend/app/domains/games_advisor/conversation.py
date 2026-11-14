"""推薦對話的 service（spec §10、§12）：處理玩家的一則訊息。

後端不存對話：用 previous_response_id 接續 Azure 保存的對話（ADR 0001）。追問或推薦由 LLM
依對話規則決定，程式守三道護欄：人數必填、只推薦這則訊息查到的桌遊、每則訊息最多查 2 次
（ADR 0002）。
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.auth import CurrentUser, require_role
from app.core.errors import AppError
from app.domains.games_advisor import prompts
from app.domains.games_advisor.constants import EXCERPTS_PER_GAME, MAX_RECOMMENDATIONS
from app.domains.games_advisor.search import (
    GAME_FIELDS,
    TOOL_NAME,
    GameSearch,
    SearchOutcome,
    SearchQuery,
    build_search_tool,
)
from app.integrations.embedding.errors import EmbeddingError
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import (
    LLMConversationNotFound,
    LLMOutputRejected,
    LLMUnavailable,
)
from app.integrations.llm.types import LLMResponse, ToolCall, ToolResult

logger = logging.getLogger(__name__)

# 每則訊息最多查幾次；查滿之後的那次 respond 不允許再查（護欄 3）
MAX_SEARCHES = 2

# 固定文字（spec §12.6）
REJECTED_REPLY = "這則訊息我沒辦法回答，請換個說法再試一次。"
DROPPED_REPLY = "這次推薦出了問題，請再說一次你的需求。"


@dataclass(frozen=True)
class RecommendationCard:
    """一張推薦卡片。game 是 8 個基本欄位，excerpts 每段是 id、text、language。"""

    game: dict[str, Any]
    reason: str
    excerpts: list[dict[str, Any]]


@dataclass(frozen=True)
class AdvisorReply:
    response_id: str | None
    reply: str
    relaxed_constraint: str | None = None
    recommendations: list[RecommendationCard] = field(default_factory=list)


class _Recommendation(BaseModel):
    game_id: int
    reason: str
    excerpt_ids: list[str]


# ⚠️ 要和 prompts.ADVISOR_REPLY_SCHEMA 一致
class _FinalOutput(BaseModel):
    """最終輸出 advisor_reply（spec §12.3）。多出來的欄位不理會。"""

    reply: str
    recommendations: list[_Recommendation]


class _OffScript(Exception):
    """模型不照約定回應（spec §12.2），當作拒答。"""


class ConversationService:
    def __init__(self, *, search: GameSearch, llm: LLMProvider) -> None:
        self._search = search
        self._llm = llm

    def send_message(
        self, user: CurrentUser, content: str, previous_response_id: str | None
    ) -> AdvisorReply:
        """處理一則玩家訊息。content 由 router 去掉前後空白。

        - 404 GAMES_ADVISOR_CONVERSATION_NOT_FOUND：對話過期或 id 錯。
        - 503 GAMES_ADVISOR_UNAVAILABLE：LLM 或 embedding 暫時連不上、沒設定模型。
        - 其他 LLMError 不攔截（500）。
        """
        require_role(user, "player", "shop_staff", "admin")
        try:
            return self._converse(content, previous_response_id)
        except LLMConversationNotFound as exc:
            raise AppError(
                404, "GAMES_ADVISOR_CONVERSATION_NOT_FOUND", "對話已過期，請重新開始"
            ) from exc
        except (LLMUnavailable, EmbeddingError) as exc:
            logger.warning("推薦服務暫時無法使用：%s", exc)
            raise AppError(
                503, "GAMES_ADVISOR_UNAVAILABLE", "推薦服務暫時無法使用，請稍後再試"
            ) from exc

    def _converse(self, content: str, previous_response_id: str | None) -> AdvisorReply:
        vocabulary = self._search.load_vocabulary()
        tools = [build_search_tool(vocabulary)]
        searches: list[SearchOutcome] = []
        llm_input: str | list[ToolResult] = content
        last_id = previous_response_id

        try:
            # 第 1 次 respond 加上最多 MAX_SEARCHES 次送回工具結果
            for _ in range(MAX_SEARCHES + 1):
                allow_tool_calls = len(searches) < MAX_SEARCHES
                response = self._llm.respond(
                    instructions=prompts.ADVISOR_INSTRUCTIONS,
                    input=llm_input,
                    tools=tools,
                    output_schema=prompts.ADVISOR_REPLY_SCHEMA,
                    previous_response_id=last_id,
                    allow_tool_calls=allow_tool_calls,
                )
                logger.info(
                    "respond token 用量：輸入 %d、輸出 %d",
                    response.input_tokens,
                    response.output_tokens,
                )
                if not response.tool_calls:
                    return self._finish(response, searches, previous_response_id)
                call = _single_search_call(response, allow_tool_calls)
                outcome = self._search.run(call.arguments, vocabulary)
                searches.append(outcome)
                llm_input = [ToolResult(call_id=call.call_id, output=outcome.output)]
                last_id = response.response_id
        except LLMOutputRejected as exc:
            logger.warning("模型拒答或輸出被擋下，回固定文字：%s", exc)
            return AdvisorReply(response_id=previous_response_id, reply=REJECTED_REPLY)
        except _OffScript as exc:
            logger.warning("模型不照約定回應，回固定文字：%s", exc)
            return AdvisorReply(response_id=previous_response_id, reply=REJECTED_REPLY)
        # 迴圈每一輪不是回傳就是查詢；最後一輪不允許查詢，所以走不到這裡
        raise AssertionError("工具迴圈沒有拿到最終輸出")

    def _finish(
        self,
        response: LLMResponse,
        searches: list[SearchOutcome],
        previous_response_id: str | None,
    ) -> AdvisorReply:
        try:
            output = _FinalOutput.model_validate(response.output)
        except ValidationError as exc:
            # 雲端的 strict schema 保證格式；格式不對比照不是合法 JSON，當作拒答
            raise LLMOutputRejected(f"最終輸出不符合 advisor_reply：{exc}") from exc

        if not searches:
            # 這則訊息沒有查詢：service 不知道之前推薦過什麼，只用文字回答（spec §12.4 第 1 點）
            return AdvisorReply(response_id=response.response_id, reply=output.reply)

        cards = _cards(output.recommendations, searches)
        if output.recommendations and not cards:
            logger.warning("推薦的桌遊全部被丟掉，回固定文字")
            return AdvisorReply(response_id=previous_response_id, reply=DROPPED_REPLY)
        return AdvisorReply(
            response_id=response.response_id,
            reply=output.reply,
            relaxed_constraint=_relaxed_constraint(searches) if cards else None,
            recommendations=cards,
        )


def _single_search_call(response: LLMResponse, allow_tool_calls: bool) -> ToolCall:
    if not allow_tool_calls:
        raise _OffScript(f"已經查過 {MAX_SEARCHES} 次，仍然要求查詢")
    if len(response.tool_calls) != 1:
        raise _OffScript(f"一次要求呼叫 {len(response.tool_calls)} 個工具")
    [call] = response.tool_calls
    if call.name != TOOL_NAME:
        raise _OffScript(f"要求的工具不是 {TOOL_NAME}：{call.name}")
    return call


def _cards(
    recommendations: list[_Recommendation], searches: list[SearchOutcome]
) -> list[RecommendationCard]:
    """只認這則訊息查到的桌遊與心得片段；卡片照查詢先後、再照名次排（spec §12.4）。"""
    # 桌遊 id → （順序，桌遊）；同一款兩次都查到時，用第一次的順序
    found: dict[int, tuple[int, dict[str, Any]]] = {}
    excerpts: dict[int, dict[str, dict[str, Any]]] = {}
    for outcome in searches:
        for game in outcome.games:
            found.setdefault(game["id"], (len(found), game))
            for excerpt in game["excerpts"]:
                excerpts.setdefault(game["id"], {})[excerpt["id"]] = excerpt

    kept: dict[int, RecommendationCard] = {}
    for recommendation in recommendations:
        game_id = recommendation.game_id
        if game_id not in found:
            logger.warning("推薦的桌遊 %d 不在這則訊息的查詢結果裡，丟掉", game_id)
            continue
        if game_id in kept:
            continue
        allowed = excerpts.get(game_id, {})
        dropped = [
            excerpt_id for excerpt_id in recommendation.excerpt_ids if excerpt_id not in allowed
        ]
        if dropped:
            logger.warning("桌遊 %d 引用的心得片段不屬於它，丟掉：%s", game_id, "、".join(dropped))
        valid = [excerpt_id for excerpt_id in recommendation.excerpt_ids if excerpt_id in allowed]
        game = found[game_id][1]
        # ⚠️ 心得片段只回 id、text、language，要和 schemas.AdvisorExcerpt 一致
        kept[game_id] = RecommendationCard(
            game={name: game[name] for name in GAME_FIELDS},
            reason=recommendation.reason,
            excerpts=[
                {key: allowed[excerpt_id][key] for key in ("id", "text", "language")}
                for excerpt_id in list(dict.fromkeys(valid))[:EXCERPTS_PER_GAME]
            ],
        )
    ordered = sorted(kept.items(), key=lambda item: found[item[0]][0])
    return [card for _, card in ordered[:MAX_RECOMMENDATIONS]]


def _relaxed_constraint(searches: list[SearchOutcome]) -> str | None:
    """第 1 次查詢 0 款、第 2 次放寬了時長或年齡：回 playtime 或 age（spec §12.5）。"""
    if len(searches) < 2:
        return None
    first, second = searches[0], searches[1]
    if first.query is None or second.query is None or first.games:
        return None
    if _playtime_relaxed(first.query, second.query):
        return "playtime"
    if _loosened_upward(first.query.youngest_age, second.query.youngest_age):
        return "age"
    return None


def _loosened_upward(before: int | None, after: int | None) -> bool:
    """上限類的條件拿掉或變大。"""
    return before is not None and (after is None or after > before)


def _playtime_relaxed(before: SearchQuery, after: SearchQuery) -> bool:
    min_loosened = before.min_minutes is not None and (
        after.min_minutes is None or after.min_minutes < before.min_minutes
    )
    return _loosened_upward(before.max_minutes, after.max_minutes) or min_loosened
