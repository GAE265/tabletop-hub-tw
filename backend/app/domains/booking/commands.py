"""booking 的匯入指令。在本機手動執行，沒有登入者。

執行方式：uv run python -m app.domains.booking.commands import-shop --shop-name <店家名稱>

只使用 DATABASE_URL 一個連線：從同一個資料庫的來源 schema（預設 booking_source，唯讀）
讀舊訂位系統的營業時間、公休、桌位、桌位關係與費率規則，寫入目標店家
（以 booking_shops 的名稱找）。可重複執行。真實店家資料只留在資料庫，不寫進 repo。
"""

import argparse
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import create_db_engine
from app.domains.booking.models import (
    BookingBusinessHours,
    BookingClosingHours,
    BookingPricingRule,
    BookingShop,
    BookingTable,
)

EXIT_OK = 0
EXIT_FAILED = 1
DEFAULT_SOURCE_SCHEMA = "booking_source"


@dataclass
class ImportCounts:
    business_hours: int = 0
    closing_hours: int = 0
    tables: int = 0
    table_links: int = 0
    pricing_rules: int = 0


def import_shop(
    source: Session, target: Session, shop_name: str, source_company_id: int
) -> ImportCounts:
    shop_id = target.scalar(select(BookingShop.id).where(BookingShop.name == shop_name))
    if shop_id is None:
        raise LookupError(f"找不到店家：{shop_name}（請先在 booking_shops 建立）")
    cid = {"c": source_company_id}
    counts = ImportCounts()

    for row in source.execute(
        text("SELECT weekday, open_time, close_time FROM business_hours WHERE company_id = :c"), cid
    ):
        target.execute(
            insert(BookingBusinessHours)
            .values(
                shop_id=shop_id,
                weekday=row.weekday,
                open_time=row.open_time,
                close_time=row.close_time,
            )
            .on_conflict_do_update(
                constraint="uq_booking_business_hours_shop_weekday",
                set_={"open_time": row.open_time, "close_time": row.close_time},
            )
        )
        counts.business_hours += 1

    target.execute(delete(BookingClosingHours).where(BookingClosingHours.shop_id == shop_id))
    for row in source.execute(
        text(
            "SELECT closing_date, start_time, end_time, reason FROM closing_hours "
            "WHERE company_id = :c"
        ),
        cid,
    ):
        target.add(
            BookingClosingHours(
                shop_id=shop_id,
                closing_date=row.closing_date,
                start_time=row.start_time,
                end_time=row.end_time,
                reason=row.reason,
            )
        )
        counts.closing_hours += 1

    code_by_source_id: dict[int, str] = {}
    for row in source.execute(
        text(
            "SELECT id, table_code, table_name, min_capacity, max_capacity, location, is_active "
            "FROM seating_tables WHERE company_id = :c"
        ),
        cid,
    ):
        code_by_source_id[row.id] = row.table_code
        values = dict(
            name=row.table_name,
            min_capacity=row.min_capacity,
            max_capacity=row.max_capacity,
            location=row.location,
            is_active=row.is_active,
        )
        target.execute(
            insert(BookingTable)
            .values(shop_id=shop_id, table_code=row.table_code, **values)
            .on_conflict_do_update(constraint="uq_booking_tables_shop_code", set_=values)
        )
        counts.tables += 1
    target.flush()
    table_ids = {
        code: tid
        for code, tid in target.execute(
            select(BookingTable.table_code, BookingTable.id).where(BookingTable.shop_id == shop_id)
        )
    }

    seen: set[frozenset[uuid.UUID]] = set()
    for row in source.execute(
        text(
            "SELECT seating_tables_id_a AS a, seating_tables_id_b AS b, is_combinable "
            "FROM seating_tables_rel WHERE company_id = :c"
        ),
        cid,
    ):
        if row.a not in code_by_source_id or row.b not in code_by_source_id or row.a == row.b:
            continue
        a, b = table_ids[code_by_source_id[row.a]], table_ids[code_by_source_id[row.b]]
        pair = frozenset((a, b))
        if pair in seen:  # 來源庫有重複與反向重複的紀錄
            continue
        seen.add(pair)
        target.execute(
            text(
                "INSERT INTO booking_table_links (shop_id, table_a_id, table_b_id, is_combinable) "
                "VALUES (:s, :a, :b, :i) ON CONFLICT (shop_id, LEAST(table_a_id, table_b_id), "
                "GREATEST(table_a_id, table_b_id)) "
                "DO UPDATE SET is_combinable = EXCLUDED.is_combinable"
            ),
            {"s": shop_id, "a": a, "b": b, "i": row.is_combinable},
        )
        counts.table_links += 1

    for row in source.execute(
        text(
            "SELECT rule_code, rule_name, rule_type, price, unit, description, is_active, "
            "effective_from, effective_to FROM pricing_rules WHERE company_id = :c"
        ),
        cid,
    ):
        values = row._asdict()
        code = values.pop("rule_code")
        target.execute(
            insert(BookingPricingRule)
            .values(shop_id=shop_id, rule_code=code, **values)
            .on_conflict_do_update(constraint="uq_booking_pricing_rules_shop_code", set_=values)
        )
        counts.pricing_rules += 1
    return counts


def use_source_schema(source: Session, schema: str) -> None:
    """讓來源 session 只讀指定 schema 的舊訂位表（business_hours、seating_tables…）。"""
    exists = source.scalar(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"), {"s": schema}
    )
    if not exists:
        raise LookupError(
            f"找不到來源 schema：{schema}（請先把舊訂位資料表放進同一個資料庫的該 schema，"
            "或用 --source-schema 指定）"
        )
    quoted = source.get_bind().dialect.identifier_preparer.quote_schema(schema)
    source.execute(text(f"SET LOCAL search_path TO {quoted}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="booking.commands")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("import-shop", help="從來源 schema 匯入店家的訂位設定")
    cmd.add_argument("--shop-name", required=True, help="目標店家在 booking_shops 的名稱")
    cmd.add_argument("--source-company-id", type=int, default=1)
    cmd.add_argument(
        "--source-schema",
        default=DEFAULT_SOURCE_SCHEMA,
        help=f"舊訂位資料表所在的 schema，同一個資料庫（預設 {DEFAULT_SOURCE_SCHEMA}）",
    )
    args = parser.parse_args(argv)

    engine = create_db_engine(get_settings().database_url)
    try:
        with Session(engine) as source, Session(engine) as target:
            source.connection(execution_options={"postgresql_readonly": True})
            use_source_schema(source, args.source_schema)
            with target.begin():
                counts = import_shop(source, target, args.shop_name, args.source_company_id)
    except LookupError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILED
    finally:
        engine.dispose()
    print(
        f"已匯入：營業時間 {counts.business_hours}、公休 {counts.closing_hours}、"
        f"桌位 {counts.tables}、桌位關係 {counts.table_links}、費率規則 {counts.pricing_rules}"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
