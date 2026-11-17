"""開發用 seed：匯入真實店家「靠過來桌遊咖啡廳」的設定資料（可重複執行）。

執行方式：uv run python -m app.dev.seed_shop
"""

import sys

from sqlalchemy import text
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
    BookingTableLink,
)

SHOP_ID = "550e8400-e29b-41d4-a716-446655440000"
SHOP_NAME = "靠過來桌遊咖啡廳"


def main() -> int:
    settings = get_settings()
    if settings.auth_mode != "dev":
        print("拒絕執行：seed_shop 只能在 AUTH_MODE=dev 時使用。", file=sys.stderr)
        return 1

    engine = create_db_engine(settings.database_url)
    with Session(engine) as session, session.begin():
        # ── 店家 ──
        session.execute(
            insert(BookingShop)
            .values(
                id=SHOP_ID,
                name=SHOP_NAME,
                timezone="Asia/Taipei",
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

        # ── 營業時間（週二公休） ──
        for weekday in (0, 1, 3, 4, 5, 6):
            session.execute(
                insert(BookingBusinessHours)
                .values(
                    shop_id=SHOP_ID,
                    weekday=weekday,
                    open_time="13:00",
                    close_time="22:00",
                )
                .on_conflict_do_nothing(
                    index_elements=["shop_id", "weekday"]
                )
            )

        # ── 公休時段 ──
        session.execute(
            text(
                "INSERT INTO closing_hours (shop_id, closing_date, start_time, end_time, reason) "
                "SELECT :sid, :d, :st, :et, :r "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM closing_hours "
                "  WHERE shop_id = :sid2 AND closing_date = :d2 "
                "    AND start_time = :st2 AND end_time = :et2"
                ")"
            ),
            {
                "sid": SHOP_ID, "d": "2026-11-18", "st": "12:00", "et": "14:00",
                "r": "take a break",
                "sid2": SHOP_ID, "d2": "2026-11-18", "st2": "12:00", "et2": "14:00",
            },
        )

        # ── 桌子 ──
        table_codes = {
            "D": 10, "A": 6, "B": 6, "C": 10, "E": 10, "F": 8, "G": 10, "H": 12, "I": 12,
        }
        for code, cap in table_codes.items():
            session.execute(
                text(
                    "INSERT INTO seating_tables "
                    "(shop_id, table_code, min_capacity, max_capacity, is_active) "
                    "SELECT :sid, :c, 1, :m, true "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM seating_tables "
                    "  WHERE shop_id = :sid2 AND table_code = :c2"
                    ")"
                ),
                {"sid": SHOP_ID, "c": code, "m": cap, "sid2": SHOP_ID, "c2": code},
            )

        # ── 桌子關係 ──
        links = [
            ("B", "C", True),
            ("C", "E", True),
            ("D", "E", True),
            ("H", "I", True),
            ("A", "B", False),
            ("A", "C", False),
            ("A", "D", False),
        ]
        for a, b, combinable in links:
            session.execute(
                text(
                    "INSERT INTO seating_tables_rel "
                    "(shop_id, seating_tables_id_a, seating_tables_id_b, is_combinable) "
                    "SELECT :sid, ta.id, tb.id, :comb "
                    "FROM seating_tables ta, seating_tables tb "
                    "WHERE ta.shop_id = :sid2 AND ta.table_code = :ca "
                    "  AND tb.shop_id = :sid3 AND tb.table_code = :cb "
                    "  AND NOT EXISTS ("
                    "    SELECT 1 FROM seating_tables_rel r "
                    "    WHERE r.shop_id = :sid4 "
                    "      AND r.seating_tables_id_a = ta.id "
                    "      AND r.seating_tables_id_b = tb.id"
                    "  )"
                ),
                {
                    "sid": SHOP_ID, "sid2": SHOP_ID, "sid3": SHOP_ID, "sid4": SHOP_ID,
                    "ca": a, "cb": b, "comb": combinable,
                },
            )

        # ── 定價規則 ──
        rules = [
            ("WEEKDAY_HOURLY_FEE", "平日場地費", "hourly", 60.00, "person_hour",
             "適用星期一至星期五。依每位客人計費；不足一小時以一小時計算；超過 5 小時以 5 小時計算。"),
            ("WEEKEND_HOURLY_FEE", "假日場地費", "hourly", 80.00, "person_hour",
             "適用星期六及星期日。依每位客人計費；不足一小時以一小時計算；超過 5 小時以 5 小時計算。"),
            ("WEEKEND_MINIMUM_DRINK_PER_PERSON", "假日每人最低飲料", "minimum_charge", 0.00,
             "drink_per_person",
             "僅適用星期六及星期日；星期一至五無低消。每位客人至少須消費一杯飲料。"),
            ("BILLING_ROUNDING_UNIT_HOURS", "計費取整單位", "other", 1.00, "hour",
             "計費時數以此單位無條件進位。"),
            ("BILLING_MAX_HOURS", "計費時數上限", "other", 5.00, "hour",
             "計費時數上限；超過以 5 小時計算。"),
            ("BOOKING_MIN_HOURS", "最短訂位時數", "other", 1.00, "hour",
             "單筆訂位最短時間。"),
        ]
        for code, name, rtype, price, unit, desc in rules:
            session.execute(
                insert(BookingPricingRule)
                .values(
                    shop_id=SHOP_ID,
                    rule_code=code,
                    rule_name=name,
                    rule_type=rtype,
                    price=price,
                    unit=unit,
                    description=desc,
                    is_active=True,
                )
                .on_conflict_do_nothing(index_elements=["shop_id", "rule_code"])
            )

        # ── FAQ（raw SQL，尚無 ORM model） ──
        faqs = [
            ("場地費如何計算？",
             "場地費依照每位客人及使用時數計算。每位客人都需要支付場地費，使用時間不足一小時時，以一小時計算。實際費率依平日或週末的收費規則為準。",
             "pricing", "{場地費,收費,計算方式,每人,每小時}", 1),
            ("平日與假日的場地費有什麼不同？",
             "店家的平日與假日採用不同的場地費率。平日為星期一至星期五，假日為星期六及星期日。實際收費金額依目前設定的場地費規則為準。",
             "pricing", "{平日,假日,週末,星期六,星期日,價格,費率}", 2),
            ("使用時間不滿一小時也要付一小時的費用嗎？",
             "是的。場地費以一小時為計費單位，不足一小時的部分會進位至下一個完整小時。例如使用一小時十分鐘，會以兩小時計算。",
             "pricing", "{不足一小時,進位,計費單位,使用時間,場地費}", 3),
            ("每個人都有最低消費嗎？",
             "是的，每位客人都必須至少消費一個品項，可以選擇飲料或點心。這項規則是以品項數量計算，不是固定金額的最低消費。",
             "consumption", "{最低消費,低消,每人低消,飲料,點心,消費規則}", 1),
        ]
        for q, a, cat, kw, so in faqs:
            session.execute(
                text(
                    "INSERT INTO faqs (shop_id, question, answer, category, keywords, "
                    "is_active, sort_order) "
                    "SELECT :sid, :q, :a, :cat, :kw::text[], true, :so "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM faqs "
                    "  WHERE shop_id = :sid2 AND question = :q2"
                    ")"
                ),
                {"sid": SHOP_ID, "q": q, "a": a, "cat": cat, "kw": kw, "so": so,
                 "sid2": SHOP_ID, "q2": q},
            )

        # ── 菜單分類 ──
        cat_names = ["飲料", "點心", "輕食"]
        for idx, name in enumerate(cat_names, start=1):
            session.execute(
                text(
                    "INSERT INTO menu_categories (shop_id, name, sort_order, is_active) "
                    "SELECT :sid, :n, :so, true "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM menu_categories "
                    "  WHERE shop_id = :sid2 AND name = :n2"
                    ")"
                ),
                {"sid": SHOP_ID, "n": name, "so": idx, "sid2": SHOP_ID, "n2": name},
            )

        # ── 菜單品項（以分類名稱參照 category_id） ──
        items = [
            ("飲料", "美式咖啡", "測試品項：經典美式咖啡（冰／熱）", 90.00, 1),
            ("飲料", "拿鐵", "測試品項：濃縮咖啡搭配牛奶（冰／熱）", 100.00, 2),
            ("飲料", "檸檬紅茶", "測試品項：檸檬風味紅茶（冰）", 60.00, 3),
            ("飲料", "無糖綠茶", "測試品項：無糖綠茶（冰）", 50.00, 4),
            ("飲料", "可樂", "測試品項：罐裝可樂", 45.00, 5),
            ("點心", "薯條", "測試品項：炸薯條一份", 70.00, 1),
            ("點心", "布朗尼", "測試品項：巧克力布朗尼一份", 90.00, 2),
            ("點心", "爆米花", "測試品項：分享用爆米花一份", 60.00, 3),
            ("點心", "雞塊", "測試品項：炸雞塊一份", 85.00, 4),
            ("輕食", "火腿起司吐司", "測試品項：火腿起司吐司一份", 80.00, 1),
        ]
        for cat_name, name, desc, price, so in items:
            session.execute(
                text(
                    "INSERT INTO menu_items (shop_id, category_id, name, description, price, "
                    "is_active, sort_order, is_available) "
                    "SELECT :sid, c.id, :n, :d, :p, true, :so, true "
                    "FROM menu_categories c "
                    "WHERE c.shop_id = :sid2 AND c.name = :cn "
                    "  AND NOT EXISTS ("
                    "    SELECT 1 FROM menu_items "
                    "    WHERE shop_id = :sid3 AND name = :n2"
                    "  )"
                ),
                {
                    "sid": SHOP_ID, "sid2": SHOP_ID, "sid3": SHOP_ID,
                    "cn": cat_name, "n": name, "n2": name, "d": desc, "p": price, "so": so,
                },
            )

    engine.dispose()
    print(f"已建立（或確認存在）店家「{SHOP_NAME}」的設定資料。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
