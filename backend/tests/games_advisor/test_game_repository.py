"""GameRepository：共用桌遊表的讀寫（spec §9 前 6 列）。連測試用的 PostgreSQL。

每個測試都在同一個 session 的交易裡寫入與檢查，結束時不提交。
"""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.games_advisor.support import (
    game_columns,
    make_game,
    read_games,
    seed_summary,
    summary_game_ids,
)

if TYPE_CHECKING:
    from app.core.games.repository import GameRepository


def add_games(game_repo: "GameRepository", *numbers: int) -> list[int]:
    return [game_repo.add_game(game_columns(make_game(number))) for number in numbers]


def type_rows(session: Session) -> list[tuple[int, str]]:
    """game_genres 的每一列：（桌遊 id，類型代碼）。"""
    sql = text(
        "SELECT gg.game_id, t.code FROM game_genres gg "
        "JOIN genres t ON t.id = gg.genre_id ORDER BY gg.game_id, t.code"
    )
    return [tuple(row) for row in session.execute(sql)]


def test_add_game_without_id_gets_automatic_ids(
    game_repo: "GameRepository", session: Session
) -> None:
    assert add_games(game_repo, 1, 2, 3) == [1, 2, 3]

    games = read_games(session.connection())
    assert [game["id"] for game in games] == [1, 2, 3]
    assert [game_columns(game) for game in games] == [
        game_columns(make_game(number)) for number in (1, 2, 3)
    ]


def test_save_game_with_existing_id_updates_fields_and_keeps_summary(
    game_repo: "GameRepository", session: Session
) -> None:
    add_games(game_repo, 1)
    seed_summary(session.connection(), 1)
    changed = game_columns(make_game(1, name="新的名稱", max_players=6, categories=["Dice"]))

    game_repo.save_game(1, changed)

    games = read_games(session.connection())
    assert len(games) == 1
    assert games[0]["id"] == 1
    assert game_columns(games[0]) == changed
    assert summary_game_ids(session.connection()) == [1]


def test_delete_games_except_removes_the_rest_with_their_data(
    game_repo: "GameRepository", session: Session
) -> None:
    add_games(game_repo, 1, 2, 3)
    game_repo.replace_game_genres(3, ["party"])
    for game_id in (1, 3):
        seed_summary(session.connection(), game_id)

    deleted = game_repo.delete_games_except([1, 2])

    assert deleted == 1
    assert [game["id"] for game in read_games(session.connection())] == [1, 2]
    # 第 3 款的心得摘要、類型跟著刪；第 1 款的留著
    assert summary_game_ids(session.connection()) == [1]
    assert type_rows(session) == []


def test_save_game_with_given_ids_then_set_counter(
    game_repo: "GameRepository", session: Session
) -> None:
    game_repo.save_game(1, game_columns(make_game(1)))
    game_repo.save_game(2, game_columns(make_game(2)))
    game_repo.set_next_game_id(4)

    assert add_games(game_repo, 3) == [4]
    assert [game["id"] for game in read_games(session.connection())] == [1, 2, 4]


def test_next_game_id_does_not_shrink_after_delete(
    game_repo: "GameRepository", session: Session
) -> None:
    add_games(game_repo, 1, 2, 3)
    game_repo.delete_games_except([1, 2])

    assert game_repo.next_game_id() == 4


def test_replace_game_genres_only_touches_that_game(
    game_repo: "GameRepository", session: Session
) -> None:
    add_games(game_repo, 1, 2)
    game_repo.replace_game_genres(1, ["party", "family"])
    game_repo.replace_game_genres(2, ["strategy"])

    game_repo.replace_game_genres(1, ["party"])

    assert type_rows(session) == [(1, "party"), (2, "strategy")]
