"""0012：match_turns.seat_number 改為可為空（本回合首家選填），並改 comment。"""

import json
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate

NEW_COMMENT = "本回合首家的座位；遊戲沒有這個概念或未填時為空"


@pytest.fixture
def url() -> str:
    return recreate_database(Settings().database_url, "match_turns_seat_nullable")


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    migrate(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


def column_info(engine: Engine) -> tuple[str, str | None]:
    sql = text(
        "SELECT c.is_nullable, col_description('match_turns'::regclass, c.ordinal_position) "
        "FROM information_schema.columns c "
        "WHERE c.table_name = 'match_turns' AND c.column_name = 'seat_number'"
    )
    with engine.connect() as conn:
        row = conn.execute(sql).one()
    return row[0], row[1]


def seed_match(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    user = uuid.uuid4()
    shop = uuid.uuid4()
    conn.execute(text("INSERT INTO booking_shops (id, name) VALUES (:id, '店')"), {"id": shop})
    conn.execute(
        text("INSERT INTO auth_users (id, display_name, role) VALUES (:id, '甲', 'player')"),
        {"id": user},
    )
    game = conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (1, '遊戲', 'Game', 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
        )
    )
    match = conn.scalar(
        text(
            "INSERT INTO matches (game_id, played_on, location_type, shop_id, created_by) "
            "VALUES (:g, '2026-11-20', 'shop', :s, :u) RETURNING id"
        ),
        {"g": game, "s": shop, "u": user},
    )
    return match, user


def insert_turn(conn: Connection, match_id: uuid.UUID, by: uuid.UUID, seat: int | None) -> None:
    conn.execute(
        text(
            "INSERT INTO match_turns (match_id, turn_number, seat_number, game_data, recorded_by) "
            "VALUES (:m, 1, :s, CAST(:d AS jsonb), :by)"
        ),
        {"m": match_id, "s": seat, "d": json.dumps({"played_seat_numbers": [1]}), "by": by},
    )


def test_seat_number_is_nullable_with_new_comment(engine: Engine):
    nullable, comment = column_info(engine)
    assert nullable == "YES"
    assert comment == NEW_COMMENT


def test_turn_without_seat_number_can_be_inserted(engine: Engine):
    with engine.begin() as conn:
        match_id, user = seed_match(conn)
        insert_turn(conn, match_id, user, None)
        assert conn.scalar(text("SELECT count(*) FROM match_turns WHERE seat_number IS NULL")) == 1


def test_downgrade_fills_empty_seat_with_one_and_restores_not_null(url: str, engine: Engine):
    with engine.begin() as conn:
        match_id, user = seed_match(conn)
        insert_turn(conn, match_id, user, None)
    engine.dispose()
    migrate(url, "downgrade", "0011")
    restored = create_engine(url)
    try:
        assert column_info(restored)[0] == "NO"
        with restored.connect() as conn:
            assert conn.scalar(text("SELECT seat_number FROM match_turns")) == 1
        with pytest.raises(IntegrityError), restored.begin() as conn:
            conn.execute(text("UPDATE match_turns SET seat_number = NULL"))
    finally:
        restored.dispose()
