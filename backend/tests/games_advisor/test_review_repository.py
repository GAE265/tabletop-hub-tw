"""心得摘要、心得片段的讀寫，以及用 bgg_id 查桌遊（spec §9）。連測試用的 PostgreSQL。"""

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.games_advisor.support import (
    game_columns,
    make_game,
    read_excerpts,
    read_summaries,
)

if TYPE_CHECKING:
    from app.domains.games_advisor.repository import GameRepository, ReviewRepository


def add_games(game_repo: "GameRepository", *numbers: int) -> None:
    for number in numbers:
        game_repo.add_game(game_columns(make_game(number)))


def excerpt(text: str, dim: int, **overrides: Any) -> dict[str, Any]:
    """要寫入的一段心得片段。"""
    values = {
        "text": text,
        "embedding": [0.5] * dim,
        "embedding_model": "m1",
        "source_url": "https://example.com/review",
        "site_name": "範例網站",
        "language": "zh-TW",
    }
    values.update(overrides)
    return values


def stored_excerpt(game_id: int, values: dict[str, Any]) -> dict[str, Any]:
    """這段心得片段寫進資料庫後，read_excerpts 應該讀到的樣子。"""
    row = {"game_id": game_id, **values, "dims": len(values["embedding"])}
    del row["embedding"]
    return row


def test_save_review_summary_writes_one_row(
    game_repo: "GameRepository",
    review_repo: "ReviewRepository",
    session: Session,
    embedding_dim: int,
) -> None:
    add_games(game_repo, 1)

    review_repo.save_review_summary(1, "心得摘要", [0.5] * embedding_dim, "m1")

    assert read_summaries(session.connection()) == [
        {"game_id": 1, "summary": "心得摘要", "embedding_model": "m1", "dims": embedding_dim}
    ]


def test_save_review_summary_again_replaces_the_old_one(
    game_repo: "GameRepository",
    review_repo: "ReviewRepository",
    session: Session,
    embedding_dim: int,
) -> None:
    add_games(game_repo, 1)
    review_repo.save_review_summary(1, "舊的心得摘要", [0.5] * embedding_dim, "m1")

    review_repo.save_review_summary(1, "新的心得摘要", [0.25] * embedding_dim, "m2")

    assert read_summaries(session.connection()) == [
        {"game_id": 1, "summary": "新的心得摘要", "embedding_model": "m2", "dims": embedding_dim}
    ]


def test_wrong_vector_length_is_rejected_and_rolled_back(
    game_repo: "GameRepository",
    review_repo: "ReviewRepository",
    session: Session,
    embedding_dim: int,
) -> None:
    with review_repo.transaction():
        add_games(game_repo, 1)
        review_repo.save_review_summary(1, "舊的心得摘要", [0.5] * embedding_dim, "m1")

    with pytest.raises(DBAPIError), review_repo.transaction():
        review_repo.save_review_summary(1, "新的心得摘要", [0.5] * (embedding_dim + 1), "m1")

    # 交易退回：舊的心得摘要還在，session 也還能繼續用
    assert read_summaries(session.connection()) == [
        {"game_id": 1, "summary": "舊的心得摘要", "embedding_model": "m1", "dims": embedding_dim}
    ]


def test_delete_review_summary_removes_only_that_game(
    game_repo: "GameRepository",
    review_repo: "ReviewRepository",
    session: Session,
    embedding_dim: int,
) -> None:
    add_games(game_repo, 1, 2)
    for game_id in (1, 2):
        review_repo.save_review_summary(game_id, "心得摘要", [0.5] * embedding_dim, "m1")

    review_repo.delete_review_summary(1)

    assert [row["game_id"] for row in read_summaries(session.connection())] == [2]


def test_replace_review_excerpts_only_touches_that_game(
    game_repo: "GameRepository",
    review_repo: "ReviewRepository",
    session: Session,
    embedding_dim: int,
) -> None:
    add_games(game_repo, 1, 2)
    other = excerpt("第 2 款的心得片段", embedding_dim)
    review_repo.replace_review_excerpts(
        1, [excerpt("舊的心得片段甲", embedding_dim), excerpt("舊的心得片段乙", embedding_dim)]
    )
    review_repo.replace_review_excerpts(2, [other])
    new = excerpt(
        "新的心得片段", embedding_dim, source_url="https://example.com/new", language="en"
    )

    review_repo.replace_review_excerpts(1, [new])

    assert read_excerpts(session.connection()) == [stored_excerpt(1, new), stored_excerpt(2, other)]


def test_find_games_by_bgg_ids_returns_only_existing_games(
    game_repo: "GameRepository",
) -> None:
    add_games(game_repo, 1, 2)

    found = game_repo.find_games_by_bgg_ids([900001, 900002, 900009])

    assert [(game["id"], game["bgg_id"], game["name"]) for game in found] == [
        (1, 900001, make_game(1)["name"]),
        (2, 900002, make_game(2)["name"]),
    ]
