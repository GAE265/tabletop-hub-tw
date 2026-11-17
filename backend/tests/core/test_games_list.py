"""遊戲清單 API：打端點、連 `_test` 資料庫。

情境對應 openspec/changes/update-groups-shop-game-pickers/specs/games-list/spec.md。
"""

from collections.abc import Callable
from itertools import count

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, text

from app.core.auth import CurrentUser
from app.core.config import Settings
from app.main import create_app

URL = "/api/v1/games"


@pytest.fixture
def app(make_settings: Callable[..., Settings], test_db_url: str, db: Engine) -> FastAPI:
    """連 `_test` 資料庫；每個測試開始時清空 games。"""
    with db.begin() as conn:
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
    return create_app(make_settings(database_url=test_db_url))


@pytest.fixture
def jwt_app(make_settings: Callable[..., Settings], test_db_url: str) -> FastAPI:
    return create_app(make_settings(database_url=test_db_url, auth_mode="jwt"))


@pytest.fixture
def add_game(db: Engine) -> Callable[[str, str], int]:
    """寫入一款桌遊（只填必填欄位），回傳 id。"""
    bgg_ids = count(1)

    def _add(name: str, english_name: str) -> int:
        with db.begin() as conn:
            return conn.scalar(
                text(
                    "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                    "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
                    "VALUES (:bgg, :name, :en, 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
                ),
                {"bgg": next(bgg_ids), "name": name, "en": english_name},
            )

    return _add


def names(response: Response) -> list[str]:
    return [item["name"] for item in response.json()["items"]]


def test_list_games_sorted_by_name(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    add_game("馬可波羅", "The Voyages of Marco Polo")
    add_game("阿瓦隆", "The Resistance: Avalon")
    add_game("卡坦島", "CATAN")
    response = client.get(URL)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert names(response) == sorted(["馬可波羅", "阿瓦隆", "卡坦島"])
    assert set(body["items"][0]) == {"id", "name", "english_name"}


def test_search_by_chinese_name(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    add_game("阿瓦隆", "The Resistance: Avalon")
    add_game("卡坦島", "CATAN")
    response = client.get(URL, params={"q": "阿瓦"})
    assert response.status_code == 200
    assert names(response) == ["阿瓦隆"]
    assert response.json()["total"] == 1


def test_search_by_english_name_ignores_case(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    add_game("阿瓦隆", "The Resistance: Avalon")
    add_game("卡坦島", "CATAN")
    response = client.get(URL, params={"q": "  AVALON  "})
    assert names(response) == ["阿瓦隆"]


def test_wildcards_in_query_are_plain_characters(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    add_game("阿瓦隆", "The Resistance: Avalon")
    for q in ["%", "_"]:
        response = client.get(URL, params={"q": q})
        assert response.json()["items"] == [], q


def test_no_match_returns_empty(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    add_game("阿瓦隆", "The Resistance: Avalon")
    response = client.get(URL, params={"q": "不存在的遊戲"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_pagination(
    client: TestClient, as_player: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    for number in range(25):
        add_game(f"遊戲{number:02d}", f"Game {number:02d}")
    response = client.get(URL, params={"page": 2, "page_size": 20})
    body = response.json()
    assert body["total"] == 25
    assert len(body["items"]) == 5
    assert names(response)[0] == "遊戲20"


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_invalid_pagination_is_422(
    client: TestClient, as_player: CurrentUser, params: dict[str, int]
) -> None:
    assert client.get(URL, params=params).status_code == 422


def test_every_role_can_list(
    client: TestClient, as_shop_staff: CurrentUser, add_game: Callable[[str, str], int]
) -> None:
    add_game("阿瓦隆", "The Resistance: Avalon")
    assert client.get(URL).status_code == 200


def test_jwt_without_token_is_401(jwt_client: TestClient) -> None:
    assert jwt_client.get(URL).status_code == 401
