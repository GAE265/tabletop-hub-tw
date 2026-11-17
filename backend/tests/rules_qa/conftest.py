"""rules_qa API 與指令測試共用的 fixture：連 `_test` 資料庫，LLM 與 embedding 一律用 fake。"""

from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.embedding import FakeEmbeddingProvider
from app.integrations.llm.fake import FakeLLMProvider
from app.main import create_app


@pytest.fixture
def rules_db(db: Engine) -> Iterator[Engine]:
    """每個測試開始時清空桌遊（連帶清掉規則書頁面、段落與影片）。"""
    with db.begin() as conn:
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
    yield db


@pytest.fixture
def embedding_dim(rules_db: Engine) -> int:
    """測試資料庫 rules_qa_chunks.embedding 的實際維度。"""
    with rules_db.connect() as conn:
        return conn.scalar(
            text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'rules_qa_chunks'::regclass AND attname = 'embedding'"
            )
        )


@pytest.fixture
def app(
    make_settings: Callable[..., Settings], test_db_url: str, rules_db: Engine, embedding_dim: int
) -> FastAPI:
    application = create_app(make_settings(database_url=test_db_url))
    application.state.llm = FakeLLMProvider()
    application.state.rules_qa_embedding = FakeEmbeddingProvider(dim=embedding_dim)
    application.state.rules_qa_embedding_model = "fake"
    return application


@pytest.fixture
def add_game(rules_db: Engine) -> Callable[[str], int]:
    counter = iter(range(1, 1000))

    def _add(name: str) -> int:
        with rules_db.begin() as conn:
            return conn.scalar(
                text(
                    "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                    "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
                    "VALUES (:bgg, :name, :name, 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
                ),
                {"bgg": next(counter), "name": name},
            )

    return _add


@pytest.fixture
def add_pages(rules_db: Engine) -> Callable[[int, list[tuple[int, str]]], None]:
    """直接寫入 rules_ingest 的規則書頁面（games_manual）。"""

    def _add(game_id: int, pages: list[tuple[int, str]]) -> None:
        with rules_db.begin() as conn:
            for page, content in pages:
                conn.execute(
                    text("INSERT INTO games_manual (games_id, page, content) VALUES (:g, :p, :c)"),
                    {"g": game_id, "p": page, "c": content},
                )

    return _add


@pytest.fixture
def index_game(rules_db: Engine, embedding_dim: int) -> Callable[[int], int]:
    """用正式的 repository 與 rules_ingest 的讀取函式建立索引，回傳段落數。"""

    def _index(game_id: int) -> int:
        from app.domains.rules_ingest.repository import ManualPageRepository
        from app.domains.rules_ingest.service import read_manual_pages
        from app.domains.rules_qa.repository import RulesQaRepository
        from app.domains.rules_qa.service import build_index

        with Session(rules_db) as session:
            pages = ManualPageRepository(session)
            return build_index(
                RulesQaRepository(session),
                lambda gid: read_manual_pages(pages, gid),
                FakeEmbeddingProvider(dim=embedding_dim),
                "fake",
                game_id,
            )

    return _index
