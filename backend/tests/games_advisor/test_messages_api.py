"""POST /api/v1/advisor/messages（spec §13.4）。

TestClient；LLM 用 FakeLLMProvider 的腳本、embedding 用 FakeEmbeddingProvider、repository 換成
假的；角色用 as_player、as_shop_staff、as_admin（AGENTS.md §4.5）。
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.config import Settings
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
from tests.games_advisor.fakes import FakeShopStock
from tests.games_advisor.support import make_game, seed_game

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
    app: FastAPI,
    responses: Script,
    embedding: FakeEmbeddingProvider | None = None,
    stock: FakeShopStock | None = None,
) -> FakeLLMProvider:
    """把對話 service 換成用假的 repository 與腳本組出來的。"""
    from app.domains.games_advisor.router import get_conversation_service

    service, llm, _ = make_service(responses, embedding=embedding, stock=stock)
    app.dependency_overrides[get_conversation_service] = lambda: service
    return llm


@pytest.fixture
def use_script(app: FastAPI) -> UseScript:
    def _use(
        responses: Script,
        embedding: FakeEmbeddingProvider | None = None,
        stock: FakeShopStock | None = None,
    ) -> FakeLLMProvider:
        return install(app, responses, embedding, stock)

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
    assert set(card) == {"game", "reason", "excerpts", "in_stock"}
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


def test_missing_previous_response_id_is_422(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    llm = use_script([final("好")])

    response = client.post(URL, json={"content": "我們 4 個人"})

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
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


# --- 店家有沒有這款桌遊（spec §19） ---

SHOP = uuid.UUID("c0000000-0000-4000-8000-000000000001")
MISSING_SHOP = uuid.UUID("c0000000-0000-4000-8000-0000000000ff")


def stock_of(*game_ids: int) -> FakeShopStock:
    """只有 SHOP 這一間店，店裡有 game_ids 這幾款。"""
    return FakeShopStock({SHOP: set(game_ids)})


def in_stock(response: Any) -> dict[int, bool | None]:
    return {card["game"]["id"]: card["in_stock"] for card in response.json()["recommendations"]}


def test_shop_has_the_game(client: TestClient, as_player: Any, use_script: UseScript) -> None:
    use_script([search(players=4), final("幫你找到 1 款", rec(1))], stock=stock_of(1))

    response = post(client, shop_id=str(SHOP))

    assert response.status_code == 201
    assert in_stock(response) == {1: True}


def test_shop_does_not_have_the_game(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([search(players=4), final("幫你找到 1 款", rec(1))], stock=stock_of(2))

    response = post(client, shop_id=str(SHOP))

    assert response.status_code == 201
    assert in_stock(response) == {1: False}


def test_each_card_is_marked_separately(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script(
        [search(players=4), final("幫你找到 3 款", rec(1), rec(2), rec(3))], stock=stock_of(1, 3)
    )

    response = post(client, shop_id=str(SHOP))

    assert response.status_code == 201
    assert in_stock(response) == {1: True, 2: False, 3: True}


@pytest.mark.parametrize("body", [{}, {"shop_id": None}], ids=["不帶 shop_id", "shop_id 是 null"])
def test_without_shop_in_stock_is_null(
    client: TestClient, as_player: Any, use_script: UseScript, body: dict[str, Any]
) -> None:
    stock = stock_of(1)
    use_script([search(players=4), final("幫你找到 2 款", rec(1, "e1a"), rec(2))], stock=stock)

    response = post(client, **body)

    assert response.status_code == 201
    assert in_stock(response) == {1: None, 2: None}
    assert stock.calls == []
    # 其他欄位和沒有這個功能時一樣
    first = response.json()["recommendations"][0]
    assert set(first["game"]) == GAME_KEYS
    assert first["reason"] == "推薦理由"
    assert first["excerpts"] == [{"id": "e1a", "text": "第 1 款的片段 a", "language": "zh-TW"}]


def test_unknown_shop_is_404_without_calling_llm(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    llm = use_script([search(players=4), final("好", rec(1))], stock=stock_of(1))

    response = post(client, shop_id=str(MISSING_SHOP))

    assert response.status_code == 404
    assert error_code(response) == "SHOP_NOT_FOUND"
    assert llm.calls == []


def test_malformed_shop_id_is_422(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    llm = use_script([final("好")], stock=stock_of(1))

    response = post(client, shop_id="不是 UUID")

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
    assert llm.calls == []


def test_follow_up_with_shop_has_no_cards(
    client: TestClient, as_player: Any, use_script: UseScript
) -> None:
    use_script([final("請問想玩多久？")], stock=stock_of(1))

    response = post(client, shop_id=str(SHOP))

    assert response.status_code == 201
    assert response.json()["recommendations"] == []


@pytest.mark.parametrize("role", ["as_player", "as_shop_staff", "as_admin"])
def test_every_role_can_ask_about_any_shop(
    client: TestClient, use_script: UseScript, role: str, request: pytest.FixtureRequest
) -> None:
    """as_shop_staff 的店是 TEST_SHOP_ID，不是 SHOP：不屬於那間店的店家人員也查得到。"""
    request.getfixturevalue(role)
    use_script([search(players=4), final("幫你找到 2 款", rec(1), rec(2))], stock=stock_of(1))

    response = post(client, shop_id=str(SHOP))

    assert response.status_code == 201
    assert in_stock(response) == {1: True, 2: False}


def test_shop_stock_comes_from_the_database(
    make_settings: Callable[..., Settings], test_db_url: str, db: Engine, games_db: Engine
) -> None:
    """不換掉對話 service：確認 router 真的把 shops 的庫存接上（資料來自 `_test` 資料庫）。"""
    from app.core.auth import get_current_user
    from app.main import create_app
    from tests.conftest import TEST_PLAYER

    # 範例桌遊甲 1–3 人、乙 2–4 人：2 人兩款都查得到
    stocked = seed_game(games_db, make_game(1))
    missing = seed_game(games_db, make_game(2))
    with db.begin() as conn:
        conn.execute(
            text("INSERT INTO booking_shops (id, name) VALUES (:id, '測試桌遊店')"), {"id": SHOP}
        )
        conn.execute(
            text("INSERT INTO shop_games (shop_id, game_id) VALUES (:s, :g)"),
            {"s": SHOP, "g": stocked},
        )
    app = create_app(make_settings(database_url=test_db_url))
    app.dependency_overrides[get_current_user] = lambda: TEST_PLAYER
    app.state.llm = FakeLLMProvider(
        responses=[search(players=2), final("幫你找到 2 款", rec(stocked), rec(missing))]
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = post(client, shop_id=str(SHOP))

    assert response.status_code == 201
    assert in_stock(response) == {stocked: True, missing: False}
    assert error_code(post(client, shop_id=str(MISSING_SHOP))) == "SHOP_NOT_FOUND"
