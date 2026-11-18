"""建立規則書索引的指令（spec rules-qa「建立規則書索引」）。"""

from collections.abc import Callable

import pytest
from sqlalchemy import Engine, text

from app.core import config
from app.core.config import Settings


@pytest.fixture
def run_index(
    test_db_url: str,
    embedding_dim: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Callable[..., tuple[int, str, str]]:
    def _run(*args: str) -> tuple[int, str, str]:
        from app.domains.rules_qa.commands import main

        monkeypatch.setitem(Settings.model_config, "env_file", None)
        monkeypatch.setenv("DATABASE_URL", test_db_url)
        monkeypatch.setenv("RULES_QA_EMBEDDING_PROVIDER", "fake")
        monkeypatch.setenv("RULES_QA_EMBEDDING_DIM", str(embedding_dim))
        config.get_settings.cache_clear()
        try:
            code = main(list(args))
        finally:
            config.get_settings.cache_clear()
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def chunk_pages(db: Engine, game_id: int) -> list[int]:
    with db.connect() as conn:
        return list(
            conn.scalars(
                text("SELECT page FROM rules_qa_chunks WHERE game_id = :g ORDER BY page"),
                {"g": game_id},
            )
        )


def test_index_builds_chunks(rules_db: Engine, add_game, add_pages, run_index) -> None:
    game = add_game("血與刃的白薔薇")
    add_pages(game, [(1, "第一頁。"), (2, ""), (3, "第三頁。")])
    code, out, _ = run_index("index", "--game-id", str(game))
    assert code == 0
    assert "2" in out
    assert chunk_pages(rules_db, game) == [1, 3]


def test_index_again_replaces(rules_db: Engine, add_game, add_pages, run_index) -> None:
    game = add_game("血與刃的白薔薇")
    add_pages(game, [(1, "第一頁。")])
    run_index("index", "--game-id", str(game))
    assert run_index("index", "--game-id", str(game))[0] == 0
    assert chunk_pages(rules_db, game) == [1]


def test_index_without_pages_fails(rules_db: Engine, add_game, run_index) -> None:
    game = add_game("阿瓦隆")
    code, _, err = run_index("index", "--game-id", str(game))
    assert code != 0
    assert "這款遊戲還沒有規則書頁面" in err
    assert chunk_pages(rules_db, game) == []


def test_index_unknown_game_fails(run_index) -> None:
    code, _, err = run_index("index", "--game-id", "999999")
    assert code != 0
    assert "找不到" in err
