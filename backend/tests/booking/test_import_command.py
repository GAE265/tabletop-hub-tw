"""匯入指令：用測試資料庫內臨時建立的來源表（舊結構、整數 id）驗證。"""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.domains.booking import commands

SOURCE_DDL = [
    "CREATE TABLE business_hours (company_id bigint, weekday smallint, open_time time, "
    "close_time time)",
    "CREATE TABLE closing_hours (company_id bigint, closing_date date, start_time time, "
    "end_time time, reason varchar)",
    "CREATE TABLE seating_tables (id bigint, company_id bigint, table_code varchar, "
    "table_name varchar, min_capacity int, max_capacity int, location varchar, is_active boolean)",
    "CREATE TABLE seating_tables_rel (id bigint, seating_tables_id_a bigint, "
    "seating_tables_id_b bigint, company_id bigint, is_combinable boolean)",
    "CREATE TABLE pricing_rules (company_id bigint, rule_code varchar, rule_name varchar, "
    "rule_type varchar, price numeric, unit varchar, description text, is_active boolean, "
    "effective_from date, effective_to date)",
]
SOURCE_DML = [
    "INSERT INTO business_hours VALUES (1, 1, '13:00', '22:00'), (1, 3, '13:00', '22:00')",
    "INSERT INTO closing_hours VALUES (1, '2026-12-02', '15:00', '17:00', '休息')",
    "INSERT INTO seating_tables VALUES (10, 1, 'X', NULL, 1, 6, NULL, true), "
    "(11, 1, 'Y', 'why', 1, 8, '窗邊', true), (99, 2, 'Z', NULL, 1, 4, NULL, true)",
    # 同一對桌位有正向與反向兩筆，另有一筆指向別家公司的桌位
    "INSERT INTO seating_tables_rel VALUES (1, 10, 11, 1, true), (2, 11, 10, 1, true), "
    "(3, 10, 99, 1, false)",
    "INSERT INTO pricing_rules VALUES (1, 'WEEKDAY_HOURLY_FEE', '平日', 'hourly', 60, "
    "'person_hour', NULL, true, NULL, NULL), "
    "(2, 'OTHER', 'x', 'other', 1, 'x', NULL, true, NULL, NULL)",
]


@pytest.fixture
def source(db: Engine):
    with db.begin() as conn:
        for sql in SOURCE_DDL + SOURCE_DML:
            conn.execute(text(sql))
    yield db
    with db.begin() as conn:
        for name in (
            "business_hours",
            "closing_hours",
            "seating_tables",
            "seating_tables_rel",
            "pricing_rules",
        ):
            conn.execute(text(f"DROP TABLE IF EXISTS {name}"))


def run(db: Engine, name: str = "測試店") -> commands.ImportCounts:
    with Session(db) as src, Session(db) as dst, dst.begin():
        return commands.import_shop(src, dst, name, 1)


def count(db: Engine, table: str) -> int:
    with db.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_import_copies_settings_and_dedupes_links(source, seeded):
    counts = run(source)
    assert (counts.business_hours, counts.closing_hours) == (2, 1)
    assert counts.table_links == 1  # 反向重複與跨公司的關係都被略過
    with source.connect() as conn:
        codes = conn.execute(
            text("SELECT table_code FROM booking_tables WHERE table_code IN ('X','Y','Z')")
        ).scalars()
    assert sorted(codes) == ["X", "Y"]


def test_import_can_run_twice(source, seeded):
    run(source)
    before = {t: count(source, t) for t in ("booking_tables", "booking_table_links")}
    before["pricing"] = count(source, "booking_pricing_rules")
    run(source)
    assert before == {
        "booking_tables": count(source, "booking_tables"),
        "booking_table_links": count(source, "booking_table_links"),
        "pricing": count(source, "booking_pricing_rules"),
    }
    assert count(source, "booking_closing_hours") == 1  # 公休以來源為準，整批取代、不累加


def test_unknown_shop_fails(source, seeded):
    with pytest.raises(LookupError):
        run(source, "不存在的店")


def test_missing_source_schema_fails_with_hint(db: Engine):
    with Session(db) as session, pytest.raises(LookupError, match="--source-schema"):
        commands.use_source_schema(session, "no_such_schema")


def test_source_schema_is_used_for_reads(db: Engine, seeded):
    with db.begin() as conn:
        conn.execute(text("CREATE SCHEMA src_test"))
        conn.execute(text("SET LOCAL search_path TO src_test"))
        for sql in SOURCE_DDL + SOURCE_DML:
            conn.execute(text(sql))
    try:
        with Session(db) as src, Session(db) as dst, dst.begin():
            commands.use_source_schema(src, "src_test")
            counts = commands.import_shop(src, dst, "測試店", 1)
        assert counts.tables == 2
    finally:
        with db.begin() as conn:
            conn.execute(text("DROP SCHEMA src_test CASCADE"))
