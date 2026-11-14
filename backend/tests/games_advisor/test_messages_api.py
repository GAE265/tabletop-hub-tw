"""POST /api/v1/advisor/messages（spec §13.4）。

TestClient；LLM 用 FakeLLMProvider 的腳本、embedding 用 FakeEmbeddingProvider、repository 換成
假的；角色用 as_player、as_shop_staff、as_admin（AGENTS.md §4.5）。
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.embedding import EmbeddingUnavailable, FakeEmbeddingProvider
from app.integrations.llm import (
    FakeLLMProvider,
    FakeResponse,
    LLMError,
    LLMOutputRejected,
    LLMUnavailable,
)
from tests.games_advisor.conversation_support import (
    DIM,
    DROPPED_REPLY,
    REJECTED_REPLY,
    final,
    make_service,
    rec,
    responds,
    search,
)

URL = "/api/v1/advisor/messages"
GAME_KEYS = {
    "id",
    "name",
    "min_players",
    "max_players",
    "min_playtime",
    "max_playtime",
    "min_age",
    "weight",
}

Script = list[FakeResponse | Exception] | None
UseScript = Callable[..., FakeLLMProvider]


def install(
    app: FastAPI, responses: Script, embedding: FakeEmbeddingProvider | None = None
) -> FakeLLMProvider:
    """把對話 service 換成用假的 repository 與腳本組出來的。"""
    from app.domains.games_advisor.router import get_conversation_service

    service, llm, _ = make_service(responses, embedding=embedding)
    app.dependency_overrides[get_conversation_service] = lambda: service
    return llm


@pytest.fixture
def use_script(app: FastAPI) -> UseScript:
    def _use(responses: Script, embedding: FakeEmbeddingProvider | None = None) -> FakeLLMProvider:
        return install(app, responses, embedding)

    return _use


def post(client: TestClient, content: Any = "我們 4 個人，想輕鬆聊天", **body: Any) -> Any:
    payload = {"content": content, "previous_response_id": None, **body}
    if content is None:
        del payload["content"]
    return client.post(URL, json=payload)


def error_code(response: Any) -> str:
    return response.json()["error"]["code"]


# --- 成功 ---


def test_recommend(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    use_script([search(players=4), final("幫你找到 1 款", rec(1, "e1a"))])

    response = post(client)

    assert response.status_code == 201
    body = response.json()
    assert body["response_id"] == "fake_resp_2"
    assert body["reply"] == "幫你找到 1 款"
    assert body["relaxed_constraint"] is None
    [card] = body["recommendations"]
    assert set(card) == {"game", "reason", "excerpts"}
    assert set(card["game"]) == GAME_KEYS
    assert card["game"]["id"] == 1
    assert card["reason"] == "推薦理由"
    assert card["excerpts"] == [{"id": "e1a", "text": "第 1 款的片段 a", "language": "zh-TW"}]


def test_follow_up_question(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    use_script([final("請問想玩多久？")])

    response = post(client)

    assert response.status_code == 201
    assert response.json()["recommendations"] == []


def test_relaxed_playtime(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    use_script(
        [
            search(players=2, max_minutes=15),
            search("call_2", players=2, max_minutes=30),
            final("沒有 15 分鐘內的，以下是時長稍長的", rec(1)),
        ]
    )

    response = post(client)

    assert response.status_code == 201
    assert response.json()["relaxed_constraint"] == "playtime"


def test_continue_conversation(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    llm = use_script([final("請問幾個人？"), final("請問想玩多久？")])
    first = post(client, "想找桌遊").json()

    response = post(client, "4 個人", previous_response_id=first["response_id"])

    assert response.status_code == 201
    assert responds(llm)[-1]["previous_response_id"] == "fake_resp_1"


def test_content_is_trimmed(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    llm = use_script([final("好")])

    response = post(client, "  4 人  ")

    assert response.status_code == 201
    assert responds(llm)[0]["input"] == "4 人"


def test_content_of_exactly_500_chars(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([final("好")])

    assert post(client, "桌" * 500).status_code == 201


# --- 欄位錯誤 ---


@pytest.mark.parametrize(
    "content",
    ["   ", "桌" * 501, None],
    ids=["只有空白", "501 字", "沒有 content"],
)
def test_invalid_content_is_422(
    client: TestClient, as_player: Any, use_script: UseScript, content: Any
) -> None:
    llm = use_script([final("好")])

    response = post(client, content)

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
    assert llm.calls == []


def test_empty_previous_response_id_is_422(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    llm = use_script([final("好")])

    response = post(client, previous_response_id="")

    assert response.status_code == 422
    assert llm.calls == []


# --- 權限 ---


def test_unauthenticated_is_401(jwt_app: FastAPI, jwt_client: TestClient) -> None:
    llm = install(jwt_app, [final("好")])

    response = post(jwt_client)

    assert response.status_code == 401
    assert error_code(response) == "UNAUTHENTICATED"
    assert llm.calls == []


@pytest.mark.parametrize("role", ["as_player", "as_shop_staff", "as_admin"])
def test_every_role_gets_201(
    client: TestClient, use_script: UseScript, role: str, request: pytest.FixtureRequest
) -> None:
    request.getfixturevalue(role)
    use_script([final("請問幾個人？")])

    assert post(client).status_code == 201


# --- 錯誤 ---


def test_expired_conversation_is_404(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([final("好")])

    response = post(client, previous_response_id="resp_unknown")

    assert response.status_code == 404
    assert error_code(response) == "GAMES_ADVISOR_CONVERSATION_NOT_FOUND"


def test_llm_unavailable_is_503(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    use_script([LLMUnavailable("逾時")])

    response = post(client)

    assert response.status_code == 503
    assert error_code(response) == "GAMES_ADVISOR_UNAVAILABLE"


def test_no_model_configured_is_503(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script(None)

    response = post(client)

    assert response.status_code == 503
    assert error_code(response) == "GAMES_ADVISOR_UNAVAILABLE"


def test_embedding_unavailable_is_503(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    embedding = FakeEmbeddingProvider(DIM, error=EmbeddingUnavailable("連不上"))
    use_script([search(players=2, preference_text="熱鬧"), final("好")], embedding)

    response = post(client)

    assert response.status_code == 503
    assert error_code(response) == "GAMES_ADVISOR_UNAVAILABLE"


def test_other_llm_error_is_500(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    use_script([LLMError("金鑰錯誤")])

    response = post(client)

    assert response.status_code == 500
    assert error_code(response) == "INTERNAL_ERROR"


# --- 固定文字 ---


def test_output_rejected_returns_fixed_reply_and_previous_id(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([final("請問幾個人？"), LLMOutputRejected("拒答")])
    first = post(client, "想找桌遊").json()

    response = post(client, previous_response_id=first["response_id"])

    assert response.status_code == 201
    body = response.json()
    assert body["reply"] == REJECTED_REPLY
    assert body["response_id"] == "fake_resp_1"
    assert body["recommendations"] == []


def test_all_recommendations_dropped_returns_fixed_reply(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([final("請問幾個人？"), search(players=2), final("好", rec(99))])
    first = post(client, "想找桌遊").json()

    response = post(client, previous_response_id=first["response_id"])

    assert response.status_code == 201
    body = response.json()
    assert body["reply"] == DROPPED_REPLY
    assert body["response_id"] == "fake_resp_1"
    assert body["recommendations"] == []


def test_fixed_reply_on_first_message_has_null_id(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([LLMOutputRejected("拒答")])

    response = post(client)

    assert response.status_code == 201
    assert response.json()["response_id"] is None
    assert response.json()["reply"] == REJECTED_REPLY
