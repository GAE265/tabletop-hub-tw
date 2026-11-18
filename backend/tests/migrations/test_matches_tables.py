"""matches 的 migration：matches、match_participants、match_turns 三張表。

情境對應 openspec/changes/add-matches-record/specs/matches-record/spec.md
「資料表與欄位說明」。migration 為 0006，接在 booking 的 0005 之後。
"""

import json
import re
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.core.config import Settings
from tests.db_utils import recreate_database, run_migrations

NEW_TABLES = {"matches", "match_participants", "match_turns"}
CJK = re.compile(r"[一-鿿]")


def migrate(url: str, action: str = "upgrade", revision: str = "head") -> None:
    """不讀本機的 `.env` 檔執行 migration，結果才不受個人設定影響。"""
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(Settings.model_config, "env_file", None)
        mp.setenv("DATABASE_URL", url)
        mp.delenv("GAMES_ADVISOR_EMBEDDING_DIM", raising=False)
        config.get_settings.cache_clear()
        try:
            run_migrations(url, action, revision)
        finally:
            config.get_settings.cache_clear()


@pytest.fixture(scope="module")
def migrated_url() -> str:
    url = recreate_database(Settings().database_url, "matches_tables")
    migrate(url)
    return url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops, games RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def table_names(engine: Engine) -> set[str]:
    sql = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    with engine.connect() as conn:
        return set(conn.scalars(sql).all())


# --- 準備資料 ---


def insert_shop(conn: Connection) -> uuid.UUID:
    return conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('測試店') RETURNING id"))


def insert_user(conn: Connection, name: str = "玩家") -> uuid.UUID:
    return conn.scalar(
        text("INSERT INTO auth_users (display_name, role) VALUES (:n, 'player') RETURNING id"),
        {"n": name},
    )


def insert_game(conn: Connection, bgg_id: int = 400566) -> int:
    return conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics, result_type) "
            "VALUES (:bgg, '血與刃的白薔薇', 'Blades & Rose', 3, 5, 30, 60, 14, 2.0, "
            "ARRAY['Card Game'], ARRAY['Hidden Roles'], 'faction') RETURNING id"
        ),
        {"bgg": bgg_id},
    )


def insert_group(conn: Connection, shop_id: uuid.UUID, organizer_id: uuid.UUID) -> uuid.UUID:
    return conn.scalar(
        text(
            "INSERT INTO groups (shop_id, organizer_id, title, start_at, end_at, capacity) "
            "VALUES (:shop, :org, '週末輕策略', '2030-01-01 11:00+00', '2030-01-01 13:00+00', 4) "
            "RETURNING id"
        ),
        {"shop": shop_id, "org": organizer_id},
    )


def insert_match(conn: Connection, **overrides: object) -> uuid.UUID:
    """預設是在自家玩的進行中的一局；overrides 可覆蓋任何欄位。"""
    user_id = overrides.pop("created_by", None) or insert_user(conn, "開局者")
    values: dict[str, object] = {
        "game_id": insert_game(conn) if "game_id" not in overrides else None,
        "played_on": "2026-11-20",
        "location_type": "home",
        "shop_id": None,
        "group_id": None,
        "created_by": user_id,
        "status": "in_progress",
        "result": None,
    }
    values.update(overrides)
    if isinstance(values["result"], dict):
        values["result"] = json.dumps(values["result"])
    return conn.scalar(
        text(
            "INSERT INTO matches (game_id, played_on, location_type, shop_id, group_id, "
            "created_by, status, result) VALUES (:game_id, :played_on, :location_type, "
            ":shop_id, :group_id, :created_by, :status, CAST(:result AS jsonb)) RETURNING id"
        ),
        values,
    )


def insert_participant(
    conn: Connection,
    match_id: uuid.UUID,
    seat_number: int,
    user_id: uuid.UUID | None = None,
    display_name: str = "Amy",
) -> uuid.UUID:
    return conn.scalar(
        text(
            "INSERT INTO match_participants (match_id, seat_number, user_id, display_name) "
            "VALUES (:m, :s, :u, :n) RETURNING id"
        ),
        {"m": match_id, "s": seat_number, "u": user_id, "n": display_name},
    )


def insert_turn(conn: Connection, match_id: uuid.UUID, turn_number: int, by: uuid.UUID) -> None:
    conn.execute(
        text(
            "INSERT INTO match_turns (match_id, turn_number, seat_number, game_data, recorded_by) "
            "VALUES (:m, :t, 1, CAST(:d AS jsonb), :by)"
        ),
        {"m": match_id, "t": turn_number, "d": json.dumps({"played_seat_numbers": [1]}), "by": by},
    )


# --- 資料表 ---


def test_upgrade_creates_three_tables(engine: Engine):
    assert NEW_TABLES <= table_names(engine)


def test_primary_keys_are_uuid_and_game_id_is_bigint(engine: Engine):
    sql = text(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY(:tables)"
    )
    with engine.connect() as conn:
        types = {(t, c): d for t, c, d in conn.execute(sql, {"tables": list(NEW_TABLES)})}
    for table in NEW_TABLES:
        assert types[(table, "id")] == "uuid"
    assert types[("matches", "game_id")] == "bigint"
    assert types[("matches", "created_by")] == "uuid"
    assert types[("matches", "group_id")] == "uuid"


def test_every_table_and_column_has_a_chinese_comment(engine: Engine):
    columns = text(
        "SELECT c.relname, a.attname, d.description FROM pg_class c "
        "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped "
        "LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = a.attnum "
        "WHERE c.relkind = 'r' AND c.relname = ANY(:tables)"
    )
    tables = text(
        "SELECT c.relname, obj_description(c.oid, 'pg_class') FROM pg_class c "
        "WHERE c.relkind = 'r' AND c.relname = ANY(:tables)"
    )
    with engine.connect() as conn:
        column_rows = conn.execute(columns, {"tables": list(NEW_TABLES)}).all()
        table_rows = conn.execute(tables, {"tables": list(NEW_TABLES)}).all()
    assert {name for name, _ in table_rows} == NEW_TABLES
    for name, comment in table_rows:
        assert comment and CJK.search(comment), f"資料表 {name} 缺少中文說明"
    assert column_rows
    for table, column, comment in column_rows:
        assert comment and CJK.search(comment), f"{table}.{column} 缺少中文說明"


# --- group_id 的外鍵 ---


def test_group_id_foreign_key_is_set_null_to_groups(engine: Engine):
    sql = text(
        "SELECT a.attname, con.confrelid::regclass::text, con.confdeltype "
        "FROM pg_constraint con JOIN pg_attribute a "
        "ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey) "
        "WHERE con.conrelid = 'matches'::regclass AND con.contype = 'f'"
    )
    with engine.connect() as conn:
        foreign_keys = {name: (target, rule) for name, target, rule in conn.execute(sql)}
    assert foreign_keys["group_id"] == ("groups", "n")  # n＝SET NULL
    assert foreign_keys["game_id"][0] == "games"
    assert foreign_keys["shop_id"][0] == "booking_shops"
    assert foreign_keys["created_by"][0] == "auth_users"


def test_group_id_comment(engine: Engine):
    sql = text(
        "SELECT col_description('matches'::regclass, a.attnum) FROM pg_attribute a "
        "WHERE a.attrelid = 'matches'::regclass AND a.attname = 'group_id'"
    )
    with engine.connect() as conn:
        assert conn.scalar(sql) == "所屬揪團；不一定屬於揪團"


def test_group_id_rejects_unknown_group(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_match(conn, group_id=uuid.uuid4())


def test_deleting_group_keeps_match_with_null_group_id(engine: Engine):
    with engine.begin() as conn:
        shop = insert_shop(conn)
        organizer = insert_user(conn, "開團主")
        group_id = insert_group(conn, shop, organizer)
        match_id = insert_match(conn, group_id=group_id, created_by=organizer)
        insert_participant(conn, match_id, 1, organizer, "開團主")
        insert_turn(conn, match_id, 1, organizer)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group_id})
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT group_id, location_type, status FROM matches WHERE id = :id"),
            {"id": match_id},
        ).one()
        participants = conn.scalar(
            text("SELECT count(*) FROM match_participants WHERE match_id = :id"), {"id": match_id}
        )
        turns = conn.scalar(
            text("SELECT count(*) FROM match_turns WHERE match_id = :id"), {"id": match_id}
        )
    assert row.group_id is None
    assert (row.location_type, row.status) == ("home", "in_progress")
    assert (participants, turns) == (1, 1)


# --- 約束 ---


def test_duplicate_seat_number_in_same_match_is_rejected(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        insert_participant(conn, match_id, 1, display_name="Amy")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_participant(conn, match_id, 1, display_name="Bob")


def test_same_seat_number_in_different_matches_is_allowed(engine: Engine):
    with engine.begin() as conn:
        first = insert_match(conn)
        second = insert_match(conn, game_id=conn.scalar(text("SELECT id FROM games")))
        insert_participant(conn, first, 1)
        insert_participant(conn, second, 1)


def test_duplicate_user_in_same_match_is_rejected(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        user_id = insert_user(conn, "玩家甲")
        insert_participant(conn, match_id, 1, user_id, "玩家甲")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_participant(conn, match_id, 2, user_id, "玩家甲")


def test_many_participants_without_account_can_coexist(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        insert_participant(conn, match_id, 1, None, "Amy")
        insert_participant(conn, match_id, 2, None, "Bob")
    with engine.connect() as conn:
        count = conn.scalar(text("SELECT count(*) FROM match_participants"))
    assert count == 2


def test_duplicate_turn_number_in_same_match_is_rejected(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        user_id = insert_user(conn, "記錄的人")
        insert_turn(conn, match_id, 1, user_id)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_turn(conn, match_id, 1, user_id)


@pytest.mark.parametrize(
    "overrides",
    [
        {"location_type": "shop", "shop_id": None},  # 桌遊店一定要有店家
        {"location_type": "home", "shop_id": "SHOP"},  # 自家不能有店家
        {"location_type": "office"},
        {"location_type": "Shop"},
        {"status": "done"},
        {"status": "in_progress", "result": {"type": "faction"}},  # 還沒結束不能有結果
        {"status": "finished", "result": None},  # 結束了一定要有結果
    ],
)
def test_matches_check_constraints(engine: Engine, overrides: dict[str, object]):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        if overrides.get("shop_id") == "SHOP":
            overrides = {**overrides, "shop_id": insert_shop(conn)}
        insert_match(conn, **overrides)


def test_shop_match_with_shop_and_finished_match_with_result_are_accepted(engine: Engine):
    with engine.begin() as conn:
        shop = insert_shop(conn)
        insert_match(conn, location_type="shop", shop_id=shop)
        insert_match(
            conn,
            game_id=conn.scalar(text("SELECT id FROM games")),
            status="finished",
            result={"type": "faction", "winning_faction": "rose"},
        )


@pytest.mark.parametrize("column, value", [("seat_number", 0), ("placement", 0)])
def test_participant_numbers_must_be_positive(engine: Engine, column: str, value: int):
    with engine.begin() as conn:
        match_id = insert_match(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        values = {"m": match_id, "s": 1, "p": None, "v": value}
        if column == "seat_number":
            values["s"] = value
        else:
            values["p"] = value
        conn.execute(
            text(
                "INSERT INTO match_participants (match_id, seat_number, display_name, placement) "
                "VALUES (:m, :s, 'Amy', :p)"
            ),
            values,
        )


def test_turn_number_must_be_positive(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        user_id = insert_user(conn, "記錄的人")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        insert_turn(conn, match_id, 0, user_id)


# --- 空值與預設值 ---


def test_faction_match_stores_null_score_and_placement_not_zero(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        participant_id = insert_participant(conn, match_id, 1)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT score, placement, faction, is_winner, is_confirmed, confirmed_at "
                "FROM match_participants WHERE id = :id"
            ),
            {"id": participant_id},
        ).one()
    assert row.score is None and row.placement is None  # NULL，不是 0
    assert row.faction is None and row.is_winner is None  # 結果還沒記錄
    assert row.is_confirmed is False and row.confirmed_at is None


def test_deleting_match_removes_its_participants_and_turns(engine: Engine):
    with engine.begin() as conn:
        match_id = insert_match(conn)
        user_id = insert_user(conn, "記錄的人")
        insert_participant(conn, match_id, 1)
        insert_turn(conn, match_id, 1, user_id)
        conn.execute(text("DELETE FROM matches WHERE id = :id"), {"id": match_id})
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM match_participants")) == 0
        assert conn.scalar(text("SELECT count(*) FROM match_turns")) == 0


def test_game_with_matches_cannot_be_deleted(engine: Engine):
    with engine.begin() as conn:
        insert_match(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM games"))


# --- 升級與降版 ---


def test_downgrade_removes_only_the_three_tables_and_upgrade_restores_them():
    url = recreate_database(Settings().database_url, "matches_downgrade")
    migrate(url)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            insert_game(conn)
        migrate(url, "downgrade", "0005")
        remaining = table_names(engine)
        assert not (NEW_TABLES & remaining)
        assert {"groups", "group_members", "games", "auth_users", "booking_shops"} <= remaining
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM games")) == 1
        migrate(url)
        assert NEW_TABLES <= table_names(engine)
    finally:
        engine.dispose()


def test_migration_chain_has_single_head_after_0005():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from tests.db_utils import BACKEND_DIR

    config_ = Config(str(BACKEND_DIR / "alembic.ini"))
    config_.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config_)
    assert len(script.get_heads()) == 1
    head = script.get_revision(script.get_heads()[0])
    assert head.down_revision == "0005"
