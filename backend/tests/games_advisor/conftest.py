"""games_advisor 測試共用的 fixture。

要測的程式都在 fixture 裡才 import：程式還沒寫的時候，每個情境各自失敗，
不會讓整個測試資料夾收不到測試。
"""

from collections.abc import Callable, Iterator
from types import ModuleType
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core import config
from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations
from tests.games_advisor import support
from tests.games_advisor.support import CommandResult

if TYPE_CHECKING:
    from app.domains.games_advisor.repository import (
        GameRepository,
        ReviewRepository,
        TagRepository,
    )

RunCommand = Callable[..., CommandResult]

# game_types 是 migration 寫入的固定資料，不清；games.id 的計數器從 1 重新開始
_CLEAN = "TRUNCATE games, games_advisor_tags RESTART IDENTITY CASCADE"


@pytest.fixture
def games_db(test_db_url: str) -> Iterator[Engine]:
    """測試用的資料庫：每個測試開始前清空桌遊與標籤。"""
    engine = create_engine(test_db_url)
    with engine.begin() as conn:
        conn.execute(text(_CLEAN))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def other_db_url() -> str:
    """第二個空的資料庫，用來模擬「另一位組員的資料庫」。"""
    url = recreate_database(Settings().database_url, "test_other")
    run_migrations(url)
    return url


@pytest.fixture
def other_db(other_db_url: str) -> Iterator[Engine]:
    engine = create_engine(other_db_url)
    with engine.begin() as conn:
        conn.execute(text(_CLEAN))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def embedding_dim(test_db_url: str) -> int:
    """測試資料庫向量欄位的維度。"""
    engine = create_engine(test_db_url)
    try:
        return support.embedding_dim(engine)
    finally:
        engine.dispose()


@pytest.fixture
def run_command(
    test_db_url: str,
    embedding_dim: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> RunCommand:
    """在同一個行程裡執行批次指令的 main()，回傳結束碼與印出的文字。

    一律設 LLM_PROVIDER=fake，所以不用 LLM 的指令在 fake 之下照常執行（spec §7.2）。
    embedding 也用 fake，維度照測試資料庫的欄位。database_url 沒給就連 games_db 的資料庫。
    """

    def _run(*args: str, database_url: str | None = None) -> CommandResult:
        from app.domains.games_advisor.commands import main

        # 不讀本機的 .env，結果才不受個人設定影響
        monkeypatch.setitem(Settings.model_config, "env_file", None)
        monkeypatch.setenv("DATABASE_URL", database_url or test_db_url)
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("GAMES_ADVISOR_EMBEDDING_PROVIDER", "fake")
        monkeypatch.setenv("GAMES_ADVISOR_EMBEDDING_DIM", str(embedding_dim))
        config.get_settings.cache_clear()
        try:
            code = main(list(args))
        finally:
            config.get_settings.cache_clear()
        captured = capsys.readouterr()
        return CommandResult(code=code, out=captured.out, err=captured.err)

    return _run


@pytest.fixture
def session(games_db: Engine) -> Iterator[Session]:
    """repository 測試用的 session。測試結束時不提交，資料由下一個測試的 games_db 清掉。"""
    with Session(games_db) as db_session:
        yield db_session


@pytest.fixture
def game_repo(session: Session) -> "GameRepository":
    from app.domains.games_advisor.repository import GameRepository

    return GameRepository(session)


@pytest.fixture
def review_repo(session: Session) -> "ReviewRepository":
    from app.domains.games_advisor.repository import ReviewRepository

    return ReviewRepository(session)


@pytest.fixture
def tag_repo(session: Session) -> "TagRepository":
    from app.domains.games_advisor.repository import TagRepository

    return TagRepository(session)


@pytest.fixture
def excerpts() -> ModuleType:
    """切段函式所在的模組 app.domains.games_advisor.excerpts。"""
    from app.domains.games_advisor import excerpts as module

    return module
