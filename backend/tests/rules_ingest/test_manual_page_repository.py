"""ManualPageRepository：依 (games_id, page) 覆蓋寫入（openspec change games-manual-table）。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.rules_ingest.repository import GameNotFoundError, ManualPageRepository
from tests.db_utils import recreate_database, run_migrations
from tests.migrations.test_games_manual import INSERT_GAME


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    url = recreate_database(Settings().database_url, "rules_ingest")
    run_migrations(url)
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(INSERT_GAME, {"id": 1})
        conn.execute(INSERT_GAME, {"id": 2})
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        s.execute(text("TRUNCATE games_manual"))
        s.commit()
        yield s


@pytest.fixture
def repo(session: Session) -> ManualPageRepository:
    return ManualPageRepository(session)


def content_of(session: Session, games_id: int, page: int) -> list[str]:
    return list(
        session.scalars(
            text("SELECT content FROM games_manual WHERE games_id = :g AND page = :p"),
            {"g": games_id, "p": page},
        )
    )


def test_upsert_inserts_new_page(repo: ManualPageRepository, session: Session) -> None:
    repo.upsert_page(1, 9, "# 新內容")
    assert content_of(session, 1, 9) == ["# 新內容"]


def test_upsert_overwrites_existing_page(repo: ManualPageRepository, session: Session) -> None:
    repo.upsert_page(1, 9, "舊")
    repo.upsert_page(1, 9, "新")
    assert content_of(session, 1, 9) == ["新"]


def test_upsert_overwrites_with_empty_string(repo: ManualPageRepository, session: Session) -> None:
    repo.upsert_page(1, 9, "有字")
    repo.upsert_page(1, 9, "")
    assert content_of(session, 1, 9) == [""]


def test_upsert_does_not_touch_other_pages(repo: ManualPageRepository, session: Session) -> None:
    repo.upsert_page(1, 8, "八")
    repo.upsert_page(2, 9, "二的九")
    repo.upsert_page(1, 9, "一的九")
    assert content_of(session, 1, 8) == ["八"]
    assert content_of(session, 2, 9) == ["二的九"]
    assert content_of(session, 1, 9) == ["一的九"]


def test_upsert_allows_gaps(repo: ManualPageRepository, session: Session) -> None:
    repo.upsert_page(1, 1, "一")
    repo.upsert_page(1, 3, "三")
    assert content_of(session, 1, 2) == []


def test_upsert_unknown_game_raises_and_writes_nothing(
    repo: ManualPageRepository, session: Session
) -> None:
    with pytest.raises(GameNotFoundError) as info:
        repo.upsert_page(999, 1, "x")
    assert info.value.games_id == 999
    assert session.scalar(text("SELECT count(*) FROM games_manual")) == 0
