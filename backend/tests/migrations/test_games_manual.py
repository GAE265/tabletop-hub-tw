"""0003 migration：games_manual（openspec change games-manual-table 的 spec）。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations

INSERT_GAME = text(
    "INSERT INTO games (id, bgg_id, name, english_name, min_players, max_players, min_playtime, "
    "max_playtime, min_age, weight, categories, mechanics) "
    "VALUES (:id, :id + 900000, '範例桌遊', 'Example Game', 2, 4, 30, 45, 10, 2.0, "
    "ARRAY['Card Game'], ARRAY['Hand Management'])"
)
INSERT_PAGE = text("INSERT INTO games_manual (games_id, page, content) VALUES (:g, :p, :c)")


@pytest.fixture(scope="module")
def migrated() -> Iterator[Engine]:
    url = recreate_database(Settings().database_url, "games_manual")
    run_migrations(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def clean(migrated: Engine) -> Engine:
    with migrated.begin() as conn:
        conn.execute(text("TRUNCATE games, games_manual RESTART IDENTITY CASCADE"))
        conn.execute(INSERT_GAME, {"id": 1})
        conn.execute(INSERT_GAME, {"id": 2})
    return migrated


def pages(engine: Engine, games_id: int = 1) -> dict[int, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT page, content FROM games_manual WHERE games_id = :g"), {"g": games_id}
        )
        return {page: content for page, content in rows}


def test_write_one_page(clean: Engine) -> None:
    with clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 9, "c": "# 標題\n\n內文"})
    assert pages(clean) == {9: "# 標題\n\n內文"}


def test_same_page_twice_is_rejected(clean: Engine) -> None:
    with clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 9, "c": "甲"})
    with pytest.raises(IntegrityError), clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 9, "c": "乙"})
    assert pages(clean) == {9: "甲"}


def test_pages_do_not_have_to_be_consecutive(clean: Engine) -> None:
    with clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 1, "c": "甲"})
        conn.execute(INSERT_PAGE, {"g": 1, "p": 3, "c": "丙"})
    assert pages(clean) == {1: "甲", 3: "丙"}


def test_empty_content_is_allowed(clean: Engine) -> None:
    with clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 2, "c": ""})
    assert pages(clean) == {2: ""}


@pytest.mark.parametrize("page", [0, -1])
def test_page_must_be_at_least_one(clean: Engine, page: int) -> None:
    with pytest.raises(IntegrityError), clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": page, "c": "x"})
    assert pages(clean) == {}


def test_game_must_exist(clean: Engine) -> None:
    with pytest.raises(IntegrityError), clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 999, "p": 1, "c": "x"})


def test_deleting_game_with_manual_is_rejected(clean: Engine) -> None:
    with clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 1, "c": "甲"})
    with pytest.raises(IntegrityError), clean.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE id = 1"))
    assert pages(clean) == {1: "甲"}


def test_deleting_game_without_manual_succeeds(clean: Engine) -> None:
    with clean.begin() as conn:
        conn.execute(INSERT_PAGE, {"g": 1, "p": 1, "c": "甲"})
        conn.execute(text("DELETE FROM games WHERE id = 2"))
    with clean.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM games WHERE id = 2")) == 0


def test_downgrade_removes_only_games_manual() -> None:
    url = recreate_database(Settings().database_url, "games_manual_down")
    run_migrations(url)
    engine = create_engine(url)
    try:
        run_migrations(url, "downgrade", "0002")
        with engine.connect() as conn:
            tables = set(
                conn.scalars(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            )
    finally:
        engine.dispose()
    assert "games_manual" not in tables
    assert {"games", "genres", "game_genres"} <= tables
