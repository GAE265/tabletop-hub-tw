"""讀 reviews.json 的指令經過 main() 的行為：共用規則（spec §7.2）與 reviews.json 的格式檢查
（spec §8.2）。連測試用的 PostgreSQL；LLM 與 embedding 都是 fake。
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine

from app.core.config import Settings
from app.domains.games_advisor import commands
from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    make_game,
    make_review,
    read_excerpts,
    read_summaries,
    review_paragraphs,
    seed_excerpt,
    seed_game,
    seed_summary,
    write_reviews_file,
)

Reviews = list[dict[str, Any]]


def seed_two_games(db: Engine) -> None:
    for number in (1, 2):
        seed_game(db, make_game(number))


def three_reviews() -> Reviews:
    return [make_review(1, 1), make_review(1, 2), make_review(2, 1)]


# --- 需要 LLM 的指令遇到 LLM_PROVIDER=fake 就拒絕執行（規則 3） ---


def test_summarize_reviews_refuses_fake_llm(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_two_games(games_db)
    seed_summary(games_db, 1, summary="舊的心得摘要")
    before = read_summaries(games_db)

    result = run_command("summarize-reviews", str(write_reviews_file(tmp_path, three_reviews())))

    assert result.code == 1
    assert "需要真的模型，請設定 LLM_*" in result.err
    assert read_summaries(games_db) == before


def test_build_excerpts_runs_with_fake_llm(
    games_db: Engine, run_command: RunCommand, tmp_path: Path, embedding_dim: int
) -> None:
    seed_two_games(games_db)
    seed_excerpt(games_db, 1, "舊的心得片段")

    result = run_command("build-excerpts", str(write_reviews_file(tmp_path, three_reviews())))

    assert result.code == 0, result.err
    # 每篇心得兩段；舊的心得片段被換掉
    expected = [
        {
            "game_id": number,
            "text": paragraph,
            "embedding_model": "fake",
            "source_url": make_review(number, index)["source_url"],
            "site_name": make_review(number, index)["site_name"],
            "language": "zh-TW",
            "dims": embedding_dim,
        }
        for number, index in ((1, 1), (1, 2), (2, 1))
        for paragraph in review_paragraphs(number, index)
    ]
    expected.sort(key=lambda row: (row["game_id"], row["text"]))
    assert read_excerpts(games_db) == expected
    assert "2 款" in result.out


# --- 批次用的 LLM 設定（規則 4） ---


def test_batch_llm_settings_swap_model_effort_and_timeout(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(
        llm_model="a", llm_batch_model="b", llm_reasoning_effort="low", llm_timeout_seconds=30
    )

    batch = commands.batch_llm_settings(settings)

    assert batch.llm_model == "b"
    assert batch.llm_reasoning_effort is None
    assert batch.llm_timeout_seconds == 300
    # 原本的 settings 不變
    assert settings.llm_model == "a"
    assert settings.llm_reasoning_effort == "low"
    assert settings.llm_timeout_seconds == 30


def test_batch_llm_settings_fall_back_to_llm_model(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(llm_model="a", llm_batch_model=None)

    assert commands.batch_llm_settings(settings).llm_model == "a"


# --- reviews.json 格式不對：整份拒絕（spec §8.2） ---


def _without_source_url(reviews: Reviews) -> None:
    del reviews[1]["source_url"]


def _unknown_language(reviews: Reviews) -> None:
    reviews[1]["language"] = "ja"


def _blank_text(reviews: Reviews) -> None:
    reviews[1]["text"] = "  \n\n  "


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        pytest.param(_without_source_url, "source_url", id="缺欄位 source_url"),
        pytest.param(_unknown_language, "language", id="language 不是 zh-TW 或 en"),
        pytest.param(_blank_text, "text", id="text 是空白"),
    ],
)
def test_refuses_whole_file_when_one_review_is_invalid(
    games_db: Engine,
    run_command: RunCommand,
    tmp_path: Path,
    mutate: Callable[[Reviews], None],
    field: str,
) -> None:
    seed_two_games(games_db)
    seed_excerpt(games_db, 1, "舊的心得片段")
    before = read_excerpts(games_db)
    reviews = three_reviews()
    mutate(reviews)

    result = run_command("build-excerpts", str(write_reviews_file(tmp_path, reviews)))

    assert result.code == 1
    # 印出第幾篇的哪個欄位
    assert "第 2 篇" in result.err
    assert field in result.err
    assert read_excerpts(games_db) == before


def test_refuses_when_reviews_file_does_not_exist(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_two_games(games_db)
    seed_excerpt(games_db, 1, "舊的心得片段")
    before = read_excerpts(games_db)

    result = run_command("build-excerpts", str(tmp_path / "no-such-file.json"))

    assert result.code == 1
    assert "no-such-file.json" in result.err
    assert "usage" not in result.err
    assert read_excerpts(games_db) == before


def test_refuses_when_reviews_file_is_not_valid_json(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_two_games(games_db)
    seed_excerpt(games_db, 1, "舊的心得片段")
    before = read_excerpts(games_db)
    path = tmp_path / "reviews.json"
    path.write_text('{"reviews": [', encoding="utf-8")

    result = run_command("build-excerpts", str(path))

    assert result.code == 1
    assert "JSON" in result.err
    assert "usage" not in result.err
    assert read_excerpts(games_db) == before
