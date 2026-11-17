from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_session
from tests.db_utils import recreate_database, run_migrations
from tests.migrations.test_games_manual import INSERT_GAME

URL = "/api/v1/games"

INSERT_TWO = text(
    "INSERT INTO games (id, bgg_id, name, english_name, min_players, max_players, min_playtime, "
    "max_playtime, min_age, weight, categories, mechanics) "
    "VALUES (:id, :id + 900000, :name, :english, 2, 4, 30, 45, 10, 2.0, "
    "ARRAY['Card Game'], ARRAY['Hand Management'])"
)


@pytest.fixture(scope="module")
def api_engine() -> Iterator[Engine]:
    url = recreate_database(Settings().database_url, "games_search_api")
    run_migrations(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(app, api_engine):
    with api_engine.begin() as connection:
        connection.execute(text("TRUNCATE games CASCADE"))
        connection.execute(INSERT_GAME, {"id": 1})
        connection.execute(
            INSERT_TWO, {"id": 2, "name": "璀璨寶石", "english": "Splendor"}
        )

    def session():
        with Session(api_engine) as value:
            yield value

    app.dependency_overrides[get_session] = session
    return api_engine


def test_search_by_chinese_name(client, seeded):
    response = client.get(URL, params={"name": "範例"})
    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": 1, "name": "範例桌遊", "english_name": "Example Game"}],
        "total": 1,
    }


def test_search_by_english_name_case_insensitive(client, seeded):
    response = client.get(URL, params={"name": "splend"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [2]


def test_search_no_match_returns_empty(client, seeded):
    response = client.get(URL, params={"name": "不存在的遊戲"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_search_missing_name_is_validation_error(client, seeded):
    response = client.get(URL)
    assert response.status_code == 422
