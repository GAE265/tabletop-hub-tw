"""TagRepository：標籤詞彙表的讀寫（spec §9）。連測試用的 PostgreSQL。"""

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from tests.games_advisor.support import (
    game_columns,
    make_game,
    make_tag,
    read_game_tags,
    read_tags,
    seed_game_tag,
    seed_tag,
)

if TYPE_CHECKING:
    from app.domains.games_advisor.repository import GameRepository, TagRepository


def test_delete_tag_removes_it_from_every_game_and_returns_those_games(
    game_repo: "GameRepository", tag_repo: "TagRepository", session: Session
) -> None:
    for number in (1, 2, 3):
        game_repo.add_game(game_columns(make_game(number)))
    for code in ("laughter", "scheming"):
        seed_tag(session.connection(), make_tag(code))
    # 第 1、2 款有 laughter；第 3 款只有 scheming
    seed_game_tag(session.connection(), 1, "laughter")
    seed_game_tag(session.connection(), 2, "laughter")
    seed_game_tag(session.connection(), 3, "scheming", confidence=0.4)

    affected = tag_repo.delete_tag("laughter")

    assert [(game["id"], game["name"]) for game in affected] == [
        (1, make_game(1)["name"]),
        (2, make_game(2)["name"]),
    ]
    assert read_tags(session.connection()) == [make_tag("scheming")]
    assert read_game_tags(session.connection()) == [(3, "scheming", 0.4)]


def test_list_tag_codes_returns_every_code(tag_repo: "TagRepository", session: Session) -> None:
    for code in ("scheming", "laughter", "tense", "luck"):
        seed_tag(session.connection(), make_tag(code))

    assert sorted(tag_repo.list_tag_codes()) == ["laughter", "luck", "scheming", "tense"]


def test_add_update_and_list_tags(
    game_repo: "GameRepository", tag_repo: "TagRepository", session: Session
) -> None:
    game_repo.add_game(game_columns(make_game(1)))
    laughter, scheming = make_tag("laughter"), make_tag("scheming")
    tag_repo.add_tag(**laughter)
    tag_repo.add_tag(**scheming)
    seed_game_tag(session.connection(), 1, "laughter", confidence=0.3)

    tag_repo.update_tag("laughter", "新的名稱", "新的定義")

    changed = {"code": "laughter", "name": "新的名稱", "definition": "新的定義"}
    assert tag_repo.list_tags() == [changed, scheming]
    assert read_tags(session.connection()) == [changed, scheming]
    # 原地更新：桌遊上的標籤與信心分數都還在
    assert read_game_tags(session.connection()) == [(1, "laughter", 0.3)]
