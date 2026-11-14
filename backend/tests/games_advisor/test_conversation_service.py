"""對話 service：工具迴圈、三道護欄、程式檢查、放寬的條件、固定文字與例外（spec §12.7）。

假的 repository、FakeLLMProvider 的腳本、FakeEmbeddingProvider，不連資料庫也不連 Azure。
"""

import logging
from typing import TYPE_CHECKING, Any

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError
from app.integrations.embedding import EmbeddingUnavailable, FakeEmbeddingProvider
from app.integrations.llm import (
    FakeLLMProvider,
    FakeResponse,
    LLMError,
    LLMOutputRejected,
    LLMUnavailable,
    ToolCall,
    ToolResult,
)
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_STAFF
from tests.games_advisor.fakes import FakeSearchRepository
from tests.games_advisor.support import make_tag

if TYPE_CHECKING:
    from app.domains.games_advisor.conversation import AdvisorReply, ConversationService

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


def send(
    service: "ConversationService",
    content: str = "我們 4 個人",
    previous_response_id: str | None = None,
    user: CurrentUser = TEST_PLAYER,
) -> "AdvisorReply":
    return service.send_message(user, content, previous_response_id)


def card_ids(reply: "AdvisorReply") -> list[int]:
    return [card.game["id"] for card in reply.recommendations]


def responds(llm: FakeLLMProvider) -> list[dict[str, Any]]:
    return [call.kwargs for call in llm.calls if call.method == "respond"]


# --- 一般流程 ---


def test_follow_up_question_without_search() -> None:
    service, llm, repo = make_service([final("請問你們有幾個人？")])

    reply = send(service, "想找桌遊")

    assert len(responds(llm)) == 1
    assert repo.filter_calls == []
    assert reply.response_id == "fake_resp_1"
    assert reply.reply == "請問你們有幾個人？"
    assert reply.recommendations == []
    assert reply.relaxed_constraint is None


def test_search_then_recommend() -> None:
    service, llm, _ = make_service(
        [search(players=4), final("幫你找到 3 款", rec(1), rec(2), rec(3))]
    )

    reply = send(service)

    first, second = responds(llm)
    assert first["input"] == "我們 4 個人"
    assert first["previous_response_id"] is None
    [tool_result] = second["input"]
    assert isinstance(tool_result, ToolResult)
    assert tool_result.call_id == "call_1"
    assert [found["id"] for found in tool_result.output["games"]] == [1, 2, 3]
    assert second["previous_response_id"] == "fake_resp_1"
    assert card_ids(reply) == [1, 2, 3]
    assert reply.response_id == "fake_resp_2"
    assert reply.reply == "幫你找到 3 款"


def test_instructions_and_tools_are_sent_every_time() -> None:
    service, llm, _ = make_service([search(players=4), final("好", rec(1))])

    send(service)

    first, second = responds(llm)
    assert first["instructions"]
    assert first["instructions"] == second["instructions"]
    assert [tool.name for tool in first["tools"]] == ["search_games"]
    assert first["tools"] == second["tools"]
    assert first["output_schema"].name == "advisor_reply"
    assert first["output_schema"] == second["output_schema"]


def test_continues_previous_conversation() -> None:
    service, llm, _ = make_service([final("請問幾個人？"), final("請問想玩多久？")])
    first = send(service, "想找桌遊")

    send(service, "4 個人", previous_response_id=first.response_id)

    assert responds(llm)[1]["previous_response_id"] == "fake_resp_1"


# --- 放寬的條件 ---


def test_relaxed_playtime() -> None:
    service, llm, _ = make_service(
        [
            search(players=2, max_minutes=15),
            search("call_2", players=2, max_minutes=30),
            final("沒有 15 分鐘內的，以下是時長稍長的", rec(1)),
        ]
    )

    reply = send(service)

    assert [call["allow_tool_calls"] for call in responds(llm)] == [True, True, False]
    assert card_ids(reply) == [1]
    assert reply.relaxed_constraint == "playtime"


def test_relaxed_age() -> None:
    service, _, _ = make_service(
        [
            search(players=2, youngest_age=6),
            search("call_2", players=2),
            final("以下是適合年紀稍大的", rec(1)),
        ]
    )

    assert send(service).relaxed_constraint == "age"


def test_changing_only_preferences_is_not_relaxing() -> None:
    service, _, _ = make_service(
        [
            search(players=2, max_minutes=15),
            search("call_2", players=2, max_minutes=15, prefer_tags=["laughter"]),
            final("沒有符合的，要調整嗎？"),
        ]
    )

    assert send(service).relaxed_constraint is None


def test_results_on_first_search_are_not_relaxing() -> None:
    service, _, _ = make_service([search(players=2), final("好", rec(1))])

    assert send(service).relaxed_constraint is None


def test_both_searches_empty() -> None:
    service, _, _ = make_service(
        [
            search(players=2, max_minutes=15),
            search("call_2", players=2, max_minutes=20),
            final("沒有符合的桌遊，要怎麼調整？"),
        ]
    )

    reply = send(service)

    assert reply.recommendations == []
    assert reply.relaxed_constraint is None


# --- 護欄 ---


def test_third_search_request_is_rejected(caplog: pytest.LogCaptureFixture) -> None:
    service, llm, repo = make_service(
        [
            final("請問幾個人？"),
            search(players=4),
            search("call_2", players=2),
            search("call_3", players=6),
        ]
    )
    first = send(service, "想找桌遊")

    with caplog.at_level(logging.WARNING):
        reply = send(service, previous_response_id=first.response_id)

    assert len(repo.filter_calls) == 2
    assert responds(llm)[-1]["allow_tool_calls"] is False
    assert reply.reply == REJECTED_REPLY
    assert reply.response_id == "fake_resp_1"
    assert reply.recommendations == []
    assert caplog.records


def test_unknown_tool_is_rejected() -> None:
    other_tool = FakeResponse(tool_calls=[ToolCall("call_1", "delete_games", {})])
    service, _, repo = make_service([other_tool])

    reply = send(service)

    assert reply.reply == REJECTED_REPLY
    assert repo.filter_calls == []


def test_two_tool_calls_at_once_are_rejected() -> None:
    both = FakeResponse(
        tool_calls=[
            search(players=4).tool_calls[0],
            search("call_2", players=2).tool_calls[0],
        ]
    )
    service, _, repo = make_service([both])

    reply = send(service)

    assert reply.reply == REJECTED_REPLY
    assert repo.filter_calls == []


def test_invalid_players_returns_error_to_llm() -> None:
    service, llm, repo = make_service([search(players=50), final("請問到底幾個人呢？")])

    reply = send(service)

    assert repo.filter_calls == []
    [tool_result] = responds(llm)[1]["input"]
    assert set(tool_result.output) == {"error"}
    assert reply.reply == "請問到底幾個人呢？"
    assert reply.recommendations == []


# --- 程式檢查 ---


def test_game_not_in_results_is_dropped(caplog: pytest.LogCaptureFixture) -> None:
    service, _, _ = make_service([search(players=2), final("好", rec(1), rec(99))])

    with caplog.at_level(logging.WARNING):
        reply = send(service)

    assert card_ids(reply) == [1]
    assert any("99" in record.getMessage() for record in caplog.records)


def test_excerpt_of_other_game_is_dropped(caplog: pytest.LogCaptureFixture) -> None:
    service, _, _ = make_service([search(players=2), final("好", rec(1, "e1a", "e2a"))])

    with caplog.at_level(logging.WARNING):
        reply = send(service)

    [card] = reply.recommendations
    assert [found["id"] for found in card.excerpts] == ["e1a"]
    assert any("e2a" in record.getMessage() for record in caplog.records)


def test_all_recommendations_dropped_returns_fixed_reply(caplog: pytest.LogCaptureFixture) -> None:
    service, _, _ = make_service([final("請問幾個人？"), search(players=2), final("好", rec(99))])
    first = send(service, "想找桌遊")

    with caplog.at_level(logging.WARNING):
        reply = send(service, previous_response_id=first.response_id)

    assert reply.reply == DROPPED_REPLY
    assert reply.response_id == "fake_resp_1"
    assert reply.recommendations == []
    assert reply.relaxed_constraint is None
    assert any("99" in record.getMessage() for record in caplog.records)


def test_recommendations_without_search_are_ignored() -> None:
    service, _, _ = make_service([final("剛剛那款很適合小孩", rec(1))])

    reply = send(service, "剛剛第一款適合小孩嗎？")

    assert reply.recommendations == []
    assert reply.reply == "剛剛那款很適合小孩"
    assert reply.response_id == "fake_resp_1"


def test_cards_follow_search_order() -> None:
    service, _, _ = make_service([search(players=4), final("好", rec(3), rec(1), rec(2))])

    assert card_ids(send(service)) == [1, 2, 3]


def test_cards_from_both_searches_follow_search_then_rank_order() -> None:
    service, _, _ = make_service(
        [
            search(players=2),
            search("call_2", players=6),
            final("好", rec(4), rec(1)),
        ]
    )

    assert card_ids(send(service)) == [1, 4]


def test_duplicate_recommendation_kept_once() -> None:
    service, _, _ = make_service([search(players=2), final("好", rec(1), rec(1))])

    assert card_ids(send(service)) == [1]


def test_card_content_comes_from_database() -> None:
    llm_rec = {**rec(1, "e1b", "e1a", reason="很熱鬧"), "min_players": 99}
    service, _, _ = make_service([search(players=2), final("好", llm_rec)])

    [card] = send(service).recommendations

    assert card.game == {
        "id": 1,
        "name": "甲",
        "min_players": 2,
        "max_players": 4,
        "min_playtime": 20,
        "max_playtime": 30,
        "min_age": 8,
        "weight": 1.5,
    }
    assert card.reason == "很熱鬧"
    assert card.excerpts == [excerpt(1, "b"), excerpt(1, "a")]


def test_more_than_two_excerpts_keeps_first_two_valid() -> None:
    service, _, _ = make_service([search(players=2), final("好", rec(1, "e2a", "e1b", "e1a"))])

    [card] = send(service).recommendations

    assert [found["id"] for found in card.excerpts] == ["e1b", "e1a"]


def test_malformed_final_output_is_rejected() -> None:
    service, _, _ = make_service([FakeResponse(output={"recommendations": []})])

    reply = send(service)

    assert reply.reply == REJECTED_REPLY
    assert reply.response_id is None


# --- 固定文字與例外 ---


def test_output_rejected_on_first_respond_returns_previous_id() -> None:
    service, _, _ = make_service([final("請問幾個人？"), LLMOutputRejected("內容過濾")])
    first = send(service, "想找桌遊")

    reply = send(service, previous_response_id=first.response_id)

    assert reply.reply == REJECTED_REPLY
    assert reply.response_id == "fake_resp_1"
    assert reply.recommendations == []
    assert reply.relaxed_constraint is None


def test_output_rejected_after_search_returns_previous_id() -> None:
    service, _, _ = make_service(
        [final("請問幾個人？"), search(players=2), LLMOutputRejected("截斷")]
    )
    first = send(service, "想找桌遊")

    reply = send(service, previous_response_id=first.response_id)

    assert reply.reply == REJECTED_REPLY
    assert reply.response_id == "fake_resp_1"
    assert reply.recommendations == []


def test_fixed_reply_on_first_message_has_no_id() -> None:
    service, _, _ = make_service([LLMOutputRejected("拒答")])

    reply = send(service)

    assert reply.reply == REJECTED_REPLY
    assert reply.response_id is None


def expect_app_error(service: "ConversationService", status: int, code: str, **kwargs: Any) -> None:
    with pytest.raises(AppError) as caught:
        send(service, **kwargs)
    assert caught.value.status_code == status
    assert caught.value.code == code


def test_expired_conversation_is_404() -> None:
    service, _, _ = make_service([final("好")])

    expect_app_error(
        service,
        404,
        "GAMES_ADVISOR_CONVERSATION_NOT_FOUND",
        previous_response_id="resp_unknown",
    )


def test_llm_unavailable_is_503() -> None:
    service, _, _ = make_service([LLMUnavailable("逾時")])

    expect_app_error(service, 503, "GAMES_ADVISOR_UNAVAILABLE")


def test_fake_without_script_is_503() -> None:
    service, _, _ = make_service(None)

    expect_app_error(service, 503, "GAMES_ADVISOR_UNAVAILABLE")


def test_embedding_unavailable_is_503() -> None:
    embedding = FakeEmbeddingProvider(DIM, error=EmbeddingUnavailable("連不上"))
    service, _, _ = make_service(
        [search(players=2, preference_text="熱鬧"), final("好")], embedding=embedding
    )

    expect_app_error(service, 503, "GAMES_ADVISOR_UNAVAILABLE")


def test_other_llm_error_propagates() -> None:
    service, _, _ = make_service([LLMError("金鑰錯誤")])

    with pytest.raises(LLMError):
        send(service)


@pytest.mark.parametrize("user", [TEST_PLAYER, TEST_SHOP_STAFF, TEST_ADMIN])
def test_every_role_can_chat(user: CurrentUser) -> None:
    service, _, _ = make_service([final("請問幾個人？")])

    reply = send(service, user=user)

    assert reply.reply == "請問幾個人？"
