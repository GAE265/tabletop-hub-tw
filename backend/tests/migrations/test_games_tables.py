"""0002 migration：共用桌遊表與 games_advisor 的 4 張表（spec §3.8）。"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core import config
from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations

NEW_TABLES = {
    "games",
    "game_types",
    "game_game_types",
    "games_advisor_review_summaries",
    "games_advisor_tags",
    "games_advisor_game_tags",
    "games_advisor_review_excerpts",
}
VECTOR_COLUMNS = [
    ("games_advisor_review_summaries", "embedding"),
    ("games_advisor_review_excerpts", "embedding"),
]
GAME_ID_TABLES = [
    "game_game_types",
    "games_advisor_review_summaries",
    "games_advisor_game_tags",
    "games_advisor_review_excerpts",
]
GAME_TYPES = {
    "party": "派對",
    "strategy": "策略",
    "thematic": "主題",
    "war": "戰爭",
    "abstract": "抽象",
    "customizable": "集換",
    "children": "孩童",
    "family": "家庭",
}


def migrate(url: str, embedding_dim: str | None = None, revision: str = "head") -> None:
    """照 `.env` 的讀法執行 migration，但不讀本機的 `.env` 檔，結果才不受個人設定影響。"""
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(Settings.model_config, "env_file", None)
        mp.setenv("DATABASE_URL", url)
        if embedding_dim is None:
            mp.delenv("GAMES_ADVISOR_EMBEDDING_DIM", raising=False)
        else:
            mp.setenv("GAMES_ADVISOR_EMBEDDING_DIM", embedding_dim)
        config.get_settings.cache_clear()
        try:
            run_migrations(url, "upgrade", revision)
        finally:
            config.get_settings.cache_clear()


def fresh_engine(suffix: str, embedding_dim: str | None = None) -> Engine:
    url = recreate_database(Settings().database_url, suffix)
    migrate(url, embedding_dim)
    return create_engine(url)


@pytest.fixture(scope="module")
def migrated() -> Iterator[Engine]:
    engine = fresh_engine("games_tables")
    yield engine
    engine.dispose()


@pytest.fixture
def clean(migrated: Engine) -> Engine:
    # game_types 是 migration 寫入的固定資料，不清；games.id 的計數器從 1 重新開始
    with migrated.begin() as conn:
        conn.execute(text("TRUNCATE games, games_advisor_tags RESTART IDENTITY CASCADE"))
    return migrated


def column_type(engine: Engine, table: str, column: str) -> str:
    sql = text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    with engine.connect() as conn:
        return conn.scalar(sql, {"t": table, "c": column})


def table_names(engine: Engine) -> set[str]:
    sql = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    with engine.connect() as conn:
        return set(conn.scalars(sql).all())


def vector_type(engine: Engine, table: str, column: str) -> str:
    sql = text(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = CAST(:t AS regclass) AND attname = :c"
    )
    with engine.connect() as conn:
        return conn.scalar(sql, {"t": table, "c": column})


def insert_game(conn: Connection, game_id: object = 1, bgg_id: int = 900001) -> int:
    """寫入一款假桌遊並回傳 id；game_id 給 None 時不帶 id，由資料庫自動給號。"""
    columns = "bgg_id, name, english_name, min_players, max_players, " + (
        "min_playtime, max_playtime, min_age, weight, categories, mechanics"
    )
    values = (
        ":bgg_id, '範例桌遊甲', 'Example Game A', 2, 4, 30, 45, 10, 1.85, "
        "ARRAY['Card Game'], ARRAY['Hand Management']"
    )
    params: dict[str, object] = {"bgg_id": bgg_id}
    if game_id is not None:
        columns, values = f"id, {columns}", f":id, {values}"
        params["id"] = game_id
    return conn.scalar(
        text(f"INSERT INTO games ({columns}) VALUES ({values}) RETURNING id"), params
    )


def insert_tag(conn: Connection, code: str = "cooperative") -> str:
    return conn.scalar(
        text(
            "INSERT INTO games_advisor_tags (code, name, definition) "
            "VALUES (:code, :code, '一句定義') RETURNING id"
        ),
        {"code": code},
    )


def zero_vector(engine: Engine) -> str:
    dim = int(vector_type(engine, "games_advisor_review_summaries", "embedding")[7:-1])
    return "[" + ",".join(["0"] * dim) + "]"


def insert_summary(conn: Connection, vector: str, game_id: int = 1) -> None:
    conn.execute(
        text(
            "INSERT INTO games_advisor_review_summaries "
            "(game_id, summary, embedding, embedding_model) "
            "VALUES (:g, '心得摘要', CAST(:v AS vector), 'fake')"
        ),
        {"g": game_id, "v": vector},
    )


def insert_excerpt(conn: Connection, vector: str, game_id: int = 1) -> None:
    conn.execute(
        text(
            "INSERT INTO games_advisor_review_excerpts "
            "(game_id, text, embedding, embedding_model, source_url, site_name, language) "
            "VALUES (:g, '片段原文', CAST(:v AS vector), 'fake', "
            "'https://example.com/review', '範例網站', 'zh-TW')"
        ),
        {"g": game_id, "v": vector},
    )


def add_game_type(conn: Connection, game_id: int = 1, code: str = "party") -> None:
    conn.execute(
        text(
            "INSERT INTO game_game_types (game_id, game_type_id) "
            "SELECT :g, id FROM game_types WHERE code = :c"
        ),
        {"g": game_id, "c": code},
    )


def add_game_tag(conn: Connection, tag_id: str, game_id: int = 1) -> None:
    conn.execute(
        text(
            "INSERT INTO games_advisor_game_tags (game_id, tag_id, confidence) VALUES (:g, :t, 0.8)"
        ),
        {"g": game_id, "t": tag_id},
    )


def count(conn: Connection, table: str) -> int:
    return conn.scalar(text(f"SELECT count(*) FROM {table}"))


# --- spec §3.8 ---


def test_upgrade_creates_tables_with_default_dim(migrated: Engine) -> None:
    assert NEW_TABLES <= table_names(migrated)
    for table, column in VECTOR_COLUMNS:
        assert vector_type(migrated, table, column) == "vector(1536)"
    assert column_type(migrated, "games", "id") == "bigint"
    for table in GAME_ID_TABLES:
        assert column_type(migrated, table, "game_id") == "bigint"


def test_vector_dim_follows_setting() -> None:
    engine = fresh_engine("games_tables_dim8", embedding_dim="8")
    try:
        for table, column in VECTOR_COLUMNS:
            assert vector_type(engine, table, column) == "vector(8)"
    finally:
        engine.dispose()


def test_game_types_are_seeded(migrated: Engine) -> None:
    with migrated.connect() as conn:
        rows = conn.execute(text("SELECT code, name FROM game_types")).all()
    assert dict(rows) == GAME_TYPES


def test_game_id_is_generated_when_omitted(clean: Engine) -> None:
    with clean.begin() as conn:
        first = insert_game(conn, None, bgg_id=900001)
        second = insert_game(conn, None, bgg_id=900002)
    assert (first, second) == (1, 2)


def test_explicit_game_id_is_kept(clean: Engine) -> None:
    with clean.begin() as conn:
        assert insert_game(conn, 5) == 5


def test_game_id_rejects_non_integer(clean: Engine) -> None:
    with pytest.raises(DBAPIError), clean.begin() as conn:
        insert_game(conn, "a")


@pytest.mark.parametrize("game_id", [0, -1])
def test_game_id_must_be_positive(clean: Engine, game_id: int) -> None:
    with pytest.raises(IntegrityError), clean.begin() as conn:
        insert_game(conn, game_id)


def test_downgrade_removes_new_tables_only() -> None:
    url = recreate_database(Settings().database_url, "games_tables_down")
    migrate(url)
    engine = create_engine(url)
    try:
        assert NEW_TABLES <= table_names(engine)
        run_migrations(url, "downgrade", "0001")
        tables = table_names(engine)
    finally:
        engine.dispose()
    assert not NEW_TABLES & tables
    assert {"auth_users", "booking_shops"} <= tables


# --- 補充：spec §3.1–§3.7 的限制 ---


def test_bgg_id_is_unique(clean: Engine) -> None:
    with clean.begin() as conn:
        insert_game(conn, 1, bgg_id=900001)
    with pytest.raises(IntegrityError), clean.begin() as conn:
        insert_game(conn, 2, bgg_id=900001)


def test_same_game_type_twice_is_rejected(clean: Engine) -> None:
    with clean.begin() as conn:
        insert_game(conn)
        add_game_type(conn)
    with pytest.raises(IntegrityError), clean.begin() as conn:
        add_game_type(conn)


def test_same_game_tag_twice_is_rejected(clean: Engine) -> None:
    with clean.begin() as conn:
        insert_game(conn)
        tag_id = insert_tag(conn)
        add_game_tag(conn, tag_id)
    with pytest.raises(IntegrityError), clean.begin() as conn:
        add_game_tag(conn, tag_id)


def test_second_review_summary_is_rejected(clean: Engine) -> None:
    vector = zero_vector(clean)
    with clean.begin() as conn:
        insert_game(conn)
        insert_summary(conn, vector)
    with pytest.raises(IntegrityError), clean.begin() as conn:
        insert_summary(conn, vector)


def test_deleting_game_removes_its_rows(clean: Engine) -> None:
    vector = zero_vector(clean)
    with clean.begin() as conn:
        insert_game(conn, 1, bgg_id=900001)
        insert_game(conn, 2, bgg_id=900002)
        tag_id = insert_tag(conn)
        for game_id in (1, 2):
            add_game_type(conn, game_id)
            add_game_tag(conn, tag_id, game_id)
            insert_summary(conn, vector, game_id)
            insert_excerpt(conn, vector, game_id)
        conn.execute(text("DELETE FROM games WHERE id = 1"))
    with clean.connect() as conn:
        for table in (
            "game_game_types",
            "games_advisor_game_tags",
            "games_advisor_review_summaries",
            "games_advisor_review_excerpts",
        ):
            # 只剩第 2 款的那一列
            assert count(conn, table) == 1
            assert conn.scalar(text(f"SELECT game_id FROM {table}")) == 2
        assert count(conn, "game_types") == len(GAME_TYPES)
        assert count(conn, "games_advisor_tags") == 1


def test_deleting_tag_removes_it_from_games(clean: Engine) -> None:
    with clean.begin() as conn:
        insert_game(conn, 1, bgg_id=900001)
        insert_game(conn, 2, bgg_id=900002)
        kept = insert_tag(conn, "cooperative")
        removed = insert_tag(conn, "bluffing")
        for game_id in (1, 2):
            add_game_tag(conn, kept, game_id)
            add_game_tag(conn, removed, game_id)
        conn.execute(text("DELETE FROM games_advisor_tags WHERE id = :t"), {"t": removed})
    with clean.connect() as conn:
        tag_ids = conn.scalars(text("SELECT DISTINCT tag_id FROM games_advisor_game_tags")).all()
        assert tag_ids == [kept]
        assert count(conn, "games") == 2
