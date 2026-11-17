"""rules_qa API：打端點、連 `_test` 資料庫，LLM 與 embedding 用 fake。

情境對應 openspec/specs/rules-qa/spec.md。
"""

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.core.auth import CurrentUser
from app.integrations.llm.fake import FakeLLMProvider, FakeResponse

BASE = "/api/v1/rules-lessons"
VIDEO = {"video_url": "https://youtu.be/XE-Sw_FtFFs", "title": "血與刃的白薔薇 規則影片"}

AddGame = Callable[[str], int]
AddPages = Callable[[int, list[tuple[int, str]]], None]
IndexGame = Callable[[int], int]


def error_code(response: Response) -> str:
    return response.json()["error"]["code"]


def ask(client: TestClient, game_id: int, content: str = "一個回合可以做什麼？", previous=None):
    return client.post(
        f"{BASE}/{game_id}/messages",
        json={"content": content, "previous_response_id": previous},
    )


# --- 教學清單與教學內容 ---


def test_list_empty(client: TestClient, as_player: CurrentUser) -> None:
    response = client.get(BASE)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_and_get_lesson(
    client: TestClient,
    as_admin: CurrentUser,
    add_game: AddGame,
    add_pages: AddPages,
    index_game: IndexGame,
) -> None:
    rose = add_game("血與刃的白薔薇")
    marco = add_game("馬可波羅")
    add_game("沒教材的遊戲")
    add_pages(rose, [(1, "每個回合抽兩張牌。")])
    add_pages(marco, [(1, "馬可波羅的規則。")])
    index_game(rose)
    index_game(marco)
    assert client.put(f"{BASE}/{rose}/video", json=VIDEO).status_code == 200

    items = client.get(BASE).json()["items"]
    assert {(i["game_id"], i["has_video"], i["has_rulebook"]) for i in items} == {
        (rose, True, True),
        (marco, False, True),
    }

    lesson = client.get(f"{BASE}/{rose}").json()
    assert lesson["game_name"] == "血與刃的白薔薇"
    assert lesson["video"] == {
        "source": "youtube",
        "video_url": VIDEO["video_url"],
        "youtube_id": "XE-Sw_FtFFs",
        "title": VIDEO["title"],
    }
    assert lesson["has_rulebook"] is True
    assert lesson["suggested_questions"]
    assert client.get(f"{BASE}/{marco}").json()["video"] is None


def test_get_lesson_errors(client: TestClient, as_player: CurrentUser, add_game: AddGame) -> None:
    empty = add_game("沒教材的遊戲")
    missing = client.get(f"{BASE}/999999")
    assert (missing.status_code, error_code(missing)) == (404, "GAME_NOT_FOUND")
    no_material = client.get(f"{BASE}/{empty}")
    assert (no_material.status_code, error_code(no_material)) == (404, "RULES_LESSON_NOT_FOUND")


def test_unauthenticated(jwt_client: TestClient) -> None:
    assert jwt_client.get(BASE).status_code == 401


# --- 設定教學影片 ---


def test_shop_staff_sets_and_replaces_video(
    client: TestClient, as_shop_staff: CurrentUser, add_game: AddGame
) -> None:
    game = add_game("阿瓦隆")
    first = client.put(f"{BASE}/{game}/video", json=VIDEO)
    assert first.status_code == 200
    assert first.json()["youtube_id"] == "XE-Sw_FtFFs"
    replaced = client.put(
        f"{BASE}/{game}/video",
        json={"video_url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "新版"},
    )
    assert replaced.json()["youtube_id"] == "abcdefghijk"
    assert client.get(f"{BASE}/{game}").json()["video"]["title"] == "新版"


def test_player_cannot_set_video(client: TestClient, as_player: CurrentUser, add_game: AddGame):
    game = add_game("阿瓦隆")
    assert client.put(f"{BASE}/{game}/video", json=VIDEO).status_code == 403


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"video_url": "https://vimeo.com/123", "title": "x"}, "RULES_QA_INVALID_VIDEO_URL"),
        ({"video_url": VIDEO["video_url"], "title": ""}, "VALIDATION_ERROR"),
        ({"title": "沒有網址"}, "VALIDATION_ERROR"),
    ],
)
def test_set_video_invalid(
    client: TestClient, as_admin: CurrentUser, add_game: AddGame, body: dict, code: str
) -> None:
    game = add_game("阿瓦隆")
    response = client.put(f"{BASE}/{game}/video", json=body)
    assert (response.status_code, error_code(response)) == (422, code)


def test_set_video_game_not_found(client: TestClient, as_admin: CurrentUser) -> None:
    response = client.put(f"{BASE}/999999/video", json=VIDEO)
    assert (response.status_code, error_code(response)) == (404, "GAME_NOT_FOUND")


# --- 規則問答 ---


def test_ask_and_get_page_citations(
    app: FastAPI,
    client: TestClient,
    as_player: CurrentUser,
    add_game: AddGame,
    add_pages: AddPages,
    index_game: IndexGame,
) -> None:
    game = add_game("血與刃的白薔薇")
    add_pages(game, [(3, "遊戲開始時每人拿五張牌。"), (5, "每個回合可以抽兩張牌。")])
    index_game(game)
    app.state.llm = FakeLLMProvider(
        responses=[
            FakeResponse(
                output={"answer": "每個回合抽兩張牌。", "answerable": True, "citation_ids": [1, 2]}
            )
        ]
    )
    response = ask(client, game)
    assert response.status_code == 201
    body = response.json()
    assert body["answer"] == "每個回合抽兩張牌。"
    assert body["answerable"] is True
    assert body["citations"] == [{"page": 3}, {"page": 5}]
    assert body["response_id"]


def test_ask_without_rulebook_is_409(
    client: TestClient, as_player: CurrentUser, add_game: AddGame
) -> None:
    game = add_game("阿瓦隆")
    response = ask(client, game)
    assert (response.status_code, error_code(response)) == (409, "RULES_QA_NOT_READY")


def test_ask_game_not_found(client: TestClient, as_player: CurrentUser) -> None:
    response = ask(client, 999999)
    assert (response.status_code, error_code(response)) == (404, "GAME_NOT_FOUND")


@pytest.mark.parametrize(
    "body",
    [
        {"content": "   ", "previous_response_id": None},
        {"content": "字" * 501, "previous_response_id": None},
        {"content": "怎麼計分？"},
        {"content": "怎麼計分？", "previous_response_id": ""},
    ],
    ids=["blank", "too-long", "missing-previous", "empty-previous"],
)
def test_ask_invalid_body_is_422(
    client: TestClient, as_player: CurrentUser, add_game: AddGame, body: dict
) -> None:
    game = add_game("阿瓦隆")
    response = client.post(f"{BASE}/{game}/messages", json=body)
    assert response.status_code == 422


def test_ask_when_llm_unavailable_is_503(
    client: TestClient,
    as_player: CurrentUser,
    add_game: AddGame,
    add_pages: AddPages,
    index_game: IndexGame,
) -> None:
    game = add_game("血與刃的白薔薇")
    add_pages(game, [(1, "規則。")])
    index_game(game)
    # app fixture 的 FakeLLMProvider 沒有腳本：respond 會拋 LLMUnavailable
    response = ask(client, game)
    assert (response.status_code, error_code(response)) == (503, "RULES_QA_UNAVAILABLE")
