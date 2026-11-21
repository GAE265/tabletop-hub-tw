"""0018：rules_qa_video_projects 加上頁面文字（add-rules-video-mobile MR 4，design.md D11）。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, inspect, text

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate

TABLE = "rules_qa_video_projects"
NEW_COLUMNS = {"chapter_pages", "reference_pages", "page_texts", "pages_version"}


@pytest.fixture(scope="module")
def url() -> str:
    url = recreate_database(Settings().database_url, "rules_qa_video_pages")
    migrate(url, "upgrade", "0018")
    return url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE games, auth_users, booking_shops RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def test_new_columns_have_chinese_comments(engine: Engine):
    columns = {c["name"]: c for c in inspect(engine).get_columns(TABLE)}
    assert NEW_COLUMNS <= set(columns)
    for name in NEW_COLUMNS:
        assert columns[name]["comment"], name
        assert not columns[name]["nullable"], name


def test_existing_project_gets_defaults(engine: Engine):
    with engine.begin() as conn:
        game = conn.scalar(
            text(
                "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
                "VALUES (1, '假遊戲', 'Fake', 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
            )
        )
        shop = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
        user = conn.scalar(
            text(
                "INSERT INTO auth_users (display_name, role, shop_id) "
                "VALUES ('店員', 'shop_staff', :s) RETURNING id"
            ),
            {"s": shop},
        )
        project = conn.scalar(
            text(
                f"INSERT INTO {TABLE} (game_id, shop_id, created_by, chapter_number, "
                "chapter_title) VALUES (:g, :s, :u, 11, '步驟三') RETURNING id"
            ),
            {"g": game, "s": shop, "u": user},
        )
        row = conn.execute(
            text(
                "SELECT chapter_pages, reference_pages, page_texts, pages_version "
                f"FROM {TABLE} WHERE id = :i"
            ),
            {"i": project},
        ).one()
    assert row.chapter_pages == [] and row.reference_pages == []
    assert row.page_texts == {} and row.pages_version == 0


def test_downgrade_removes_columns(url: str):
    try:
        migrate(url, "downgrade", "0017")
        engine = create_engine(url)
        try:
            columns = {c["name"] for c in inspect(engine).get_columns(TABLE)}
            assert not (NEW_COLUMNS & columns)
        finally:
            engine.dispose()
    finally:
        migrate(url, "upgrade", "0018")
