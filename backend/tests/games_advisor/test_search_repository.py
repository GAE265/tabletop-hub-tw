"""「查桌遊」用到的資料庫查詢（spec §11.3、§11.5、§11.8 repository）。連測試用的 PostgreSQL。

篩條件、類別與機制清單在共用桌遊表的 GameRepository；標籤在 TagRepository；心得摘要的相似度與
心得片段在 ReviewRepository（AGENTS.md §4.2：一張表只有一個 repository）。
"""

import math
from typing import TYPE_CHECKING, Any

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from tests.games_advisor.support import make_game, make_tag, seed_game, seed_game_tag, seed_tag

if TYPE_CHECKING:
    from app.core.games.repository import GameRepository
    from app.domains.games_advisor.repository import ReviewRepository, TagRepository


def add_game(session: Session, number: int, **overrides: Any) -> int:
    return seed_game(session.connection(), make_game(number, **overrides))


def vec(dim: int, *leading: float) -> list[float]:
    """前幾個分量照給的值，其餘補 0 的向量。"""
    return [*leading, *([0.0] * (dim - len(leading)))]


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def seed_summary_vector(conn: Connection, game_id: int, vector: list[float], model: str) -> None:
    conn.execute(
        text(
            "INSERT INTO games_advisor_review_summaries "
            "(game_id, summary, embedding, embedding_model) "
            "VALUES (:g, '心得摘要', CAST(:v AS vector), :m)"
        ),
        {"g": game_id, "v": _literal(vector), "m": model},
    )


def seed_excerpt_vector(
    conn: Connection,
    game_id: int,
    excerpt_text: str,
    vector: list[float],
    model: str = "m1",
    language: str = "zh-TW",
) -> str:
    """寫入一段心得片段，回傳它的 id（字串）。"""
    excerpt_id = conn.scalar(
        text(
            "INSERT INTO games_advisor_review_excerpts "
            "(game_id, text, embedding, embedding_model, source_url, site_name, language) "
            "VALUES (:g, :t, CAST(:v AS vector), :m, 'https://example.com/r', '範例網站', :l) "
            "RETURNING id"
        ),
        {"g": game_id, "t": excerpt_text, "v": _literal(vector), "m": model, "l": language},
    )
    return str(excerpt_id)


# --- 篩條件（GameRepository.filter_games） ---


def test_players_filter_includes_both_boundaries(
    session: Session, game_repo: "GameRepository"
) -> None:
    g1 = add_game(session, 1, min_players=2, max_players=4)
    g2 = add_game(session, 2, min_players=3, max_players=5)
    g3 = add_game(session, 3, min_players=5, max_players=8)

    assert [game["id"] for game in game_repo.filter_games(players=4)] == [g1, g2]
    # 剛好等於最少人數、剛好等於最多人數都算符合
    assert [game["id"] for game in game_repo.filter_games(players=2)] == [g1]
    assert [game["id"] for game in game_repo.filter_games(players=5)] == [g2, g3]


def test_max_minutes_compares_with_longest_playtime(
    session: Session, game_repo: "GameRepository"
) -> None:
    g45 = add_game(session, 1, min_playtime=30, max_playtime=45)
    g60 = add_game(session, 2, min_playtime=30, max_playtime=60)
    add_game(session, 3, min_playtime=30, max_playtime=120)

    games = game_repo.filter_games(players=3, max_minutes=60)

    assert [game["id"] for game in games] == [g45, g60]


def test_min_minutes_compares_with_longest_playtime(
    session: Session, game_repo: "GameRepository"
) -> None:
    add_game(session, 1, min_playtime=30, max_playtime=45)
    g60 = add_game(session, 2, min_playtime=30, max_playtime=60)
    g120 = add_game(session, 3, min_playtime=30, max_playtime=120)

    games = game_repo.filter_games(players=3, min_minutes=60)

    assert [game["id"] for game in games] == [g60, g120]


def test_youngest_age_filter(session: Session, game_repo: "GameRepository") -> None:
    g8 = add_game(session, 1, min_age=8)
    g10 = add_game(session, 2, min_age=10)
    add_game(session, 3, min_age=14)

    games = game_repo.filter_games(players=3, youngest_age=10)

    assert [game["id"] for game in games] == [g8, g10]


def test_exclude_game_ids(session: Session, game_repo: "GameRepository") -> None:
    wide = {"min_players": 1, "max_players": 8}
    g1 = add_game(session, 1, **wide)
    g2 = add_game(session, 2, **wide)
    g3 = add_game(session, 3, **wide)

    games = game_repo.filter_games(players=4, exclude_ids=[g1])

    assert [game["id"] for game in games] == [g2, g3]


def test_only_players_does_not_filter_playtime_or_age(
    session: Session, game_repo: "GameRepository"
) -> None:
    g1 = add_game(session, 1, min_players=1, max_players=8, max_playtime=240, min_age=18)
    g2 = add_game(session, 2, min_players=1, max_players=8, max_playtime=15, min_age=3)

    games = game_repo.filter_games(players=4)

    assert [game["id"] for game in games] == [g1, g2]


def test_filter_games_returns_basic_fields(session: Session, game_repo: "GameRepository") -> None:
    game = make_game(1)
    game_id = add_game(session, 1)

    [found] = game_repo.filter_games(players=game["min_players"])

    assert found["id"] == game_id
    for column in ("name", "min_players", "max_players", "min_playtime", "max_playtime"):
        assert found[column] == game[column]
    assert found["min_age"] == game["min_age"]
    assert found["weight"] == game["weight"]
    assert found["categories"] == game["categories"]
    assert found["mechanics"] == game["mechanics"]


# --- 標籤（TagRepository.list_game_tags） ---


def test_game_tags_include_those_below_threshold(
    session: Session, tag_repo: "TagRepository"
) -> None:
    game_id = add_game(session, 1)
    conn = session.connection()
    seed_tag(conn, make_tag("laughter"))
    seed_tag(conn, make_tag("luck"))
    seed_game_tag(conn, game_id, "laughter", 0.3)
    seed_game_tag(conn, game_id, "luck", 0.8)

    assert tag_repo.list_game_tags([game_id]) == {game_id: {"laughter": 0.3, "luck": 0.8}}


def test_tag_vocabulary_lists_code_name_definition(
    session: Session, tag_repo: "TagRepository"
) -> None:
    conn = session.connection()
    tags = [make_tag(code) for code in ("laughter", "luck", "scheming", "tense")]
    for tag in tags:
        seed_tag(conn, tag)

    assert tag_repo.list_tags() == sorted(tags, key=lambda tag: tag["code"])


# --- 心得摘要的相似度（ReviewRepository.summary_similarities） ---


def test_similarity_is_cosine_similarity_when_model_matches(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    game_id = add_game(session, 1)
    seed_summary_vector(session.connection(), game_id, vec(embedding_dim, 1.0), "m1")

    result = review_repo.summary_similarities(
        [game_id], embedding_model="m1", query_vector=vec(embedding_dim, 1.0, 1.0)
    )

    # [1, 0] 與 [1, 1] 夾 45 度
    assert result[game_id]["embedding_model"] == "m1"
    assert math.isclose(result[game_id]["similarity"], 1 / math.sqrt(2), rel_tol=1e-6)


def test_similarity_is_empty_for_other_model_or_missing_vector(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    other_model = add_game(session, 1)
    no_vector = add_game(session, 2)
    seed_summary_vector(session.connection(), other_model, vec(embedding_dim, 1.0), "m0")

    result = review_repo.summary_similarities(
        [other_model, no_vector], embedding_model="m1", query_vector=vec(embedding_dim, 1.0)
    )

    assert result == {other_model: {"embedding_model": "m0", "similarity": None}}


def test_similarity_is_empty_without_query_vector(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    game_id = add_game(session, 1)
    seed_summary_vector(session.connection(), game_id, vec(embedding_dim, 1.0), "m1")

    result = review_repo.summary_similarities([game_id], embedding_model="m1", query_vector=None)

    assert result == {game_id: {"embedding_model": "m1", "similarity": None}}


# --- 心得片段（ReviewRepository.nearest_excerpts） ---


def test_nearest_excerpts_returns_closest_of_this_game(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    game_id = add_game(session, 1)
    other_game = add_game(session, 2)
    conn = session.connection()
    seed_excerpt_vector(conn, game_id, "第三近", vec(embedding_dim, 0.0, 1.0))
    closest = seed_excerpt_vector(conn, game_id, "最近", vec(embedding_dim, 1.0), language="en")
    seed_excerpt_vector(conn, game_id, "最遠", vec(embedding_dim, -1.0))
    second = seed_excerpt_vector(conn, game_id, "第二近", vec(embedding_dim, 1.0, 1.0))
    seed_excerpt_vector(conn, other_game, "別款", vec(embedding_dim, 1.0))

    excerpts = review_repo.nearest_excerpts(
        game_id, embedding_model="m1", limit=2, query_vector=vec(embedding_dim, 1.0)
    )

    assert excerpts == [
        {"id": closest, "text": "最近", "language": "en"},
        {"id": second, "text": "第二近", "language": "zh-TW"},
    ]


def test_nearest_excerpts_with_only_one(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    game_id = add_game(session, 1)
    only = seed_excerpt_vector(session.connection(), game_id, "唯一", vec(embedding_dim, 1.0))

    excerpts = review_repo.nearest_excerpts(
        game_id, embedding_model="m1", limit=2, query_vector=vec(embedding_dim, 1.0)
    )

    assert excerpts == [{"id": only, "text": "唯一", "language": "zh-TW"}]


def test_nearest_excerpts_skips_other_models(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    game_id = add_game(session, 1)
    seed_excerpt_vector(session.connection(), game_id, "舊模型", vec(embedding_dim, 1.0), "m0")

    excerpts = review_repo.nearest_excerpts(
        game_id, embedding_model="m1", limit=2, query_vector=vec(embedding_dim, 1.0)
    )

    assert excerpts == []


def test_nearest_excerpts_use_summary_vector_without_query_vector(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    game_id = add_game(session, 1)
    conn = session.connection()
    seed_summary_vector(conn, game_id, vec(embedding_dim, 0.0, 1.0), "m1")
    near = seed_excerpt_vector(conn, game_id, "接近摘要", vec(embedding_dim, 0.0, 1.0))
    seed_excerpt_vector(conn, game_id, "遠離摘要", vec(embedding_dim, 1.0))

    excerpts = review_repo.nearest_excerpts(
        game_id, embedding_model="m1", limit=1, query_vector=None
    )

    assert excerpts == [{"id": near, "text": "接近摘要", "language": "zh-TW"}]


def test_nearest_excerpts_empty_when_summary_vector_unusable(
    session: Session, review_repo: "ReviewRepository", embedding_dim: int
) -> None:
    other_model = add_game(session, 1)
    no_summary = add_game(session, 2)
    conn = session.connection()
    seed_summary_vector(conn, other_model, vec(embedding_dim, 1.0), "m0")
    seed_excerpt_vector(conn, other_model, "片段", vec(embedding_dim, 1.0))
    seed_excerpt_vector(conn, no_summary, "片段", vec(embedding_dim, 1.0))

    for game_id in (other_model, no_summary):
        assert (
            review_repo.nearest_excerpts(game_id, embedding_model="m1", limit=2, query_vector=None)
            == []
        )


# --- 工具定義用的清單（GameRepository） ---


def test_categories_and_mechanics_are_distinct_union(
    session: Session, game_repo: "GameRepository"
) -> None:
    add_game(session, 1, categories=["Card Game", "Party Game"], mechanics=["Voting"])
    add_game(session, 2, categories=["Card Game", "Bluffing"], mechanics=["Voting", "Drafting"])
    add_game(session, 3, categories=["Party Game"], mechanics=[])

    assert game_repo.list_categories() == ["Bluffing", "Card Game", "Party Game"]
    assert game_repo.list_mechanics() == ["Drafting", "Voting"]


def test_list_game_ids(session: Session, game_repo: "GameRepository") -> None:
    ids = [add_game(session, number) for number in (1, 2, 3)]

    assert game_repo.list_game_ids() == ids
