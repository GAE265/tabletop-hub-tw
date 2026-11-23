"""demo 店家設定與規則教學影片種子資料

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHOP_ID = "44444444-4444-4444-8444-444444444444"


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO booking_shops (id, name, timezone, is_active)
        VALUES ('44444444-4444-4444-8444-444444444444', '測試桌遊店', 'Asia/Taipei', true)
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO business_hours (shop_id, weekday, open_time, close_time)
        VALUES {", ".join(f"('{SHOP_ID}', {weekday}, '13:00', '22:00')" for weekday in (0, 1, 3, 4, 5, 6))}
        ON CONFLICT (shop_id, weekday) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO closing_hours (shop_id, closing_date, start_time, end_time, reason)
        SELECT '{SHOP_ID}', DATE '2026-11-18', TIME '12:00', TIME '14:00', 'take a break'
        WHERE NOT EXISTS (
            SELECT 1 FROM closing_hours
            WHERE shop_id = '{SHOP_ID}' AND closing_date = DATE '2026-11-18'
              AND start_time = TIME '12:00' AND end_time = TIME '14:00'
        )
        """
    )
    tables = [
        ("A", 6, 1, 0, 0, 80, 80),
        ("B", 6, 1, 120, 0, 80, 40),
        ("C", 10, 1, 120, 40, 80, 40),
        ("D", 10, 1, 120, 80, 80, 80),
        ("E", 10, 1, 0, 80, 80, 80),
        ("F", 8, 1, 0, 200, 80, 40),
        ("G", 10, 1, 120, 240, 120, 120),
        ("H", 12, -1, 0, 0, 120, 80),
        ("I", 12, -1, 40, 160, 160, 160),
    ]
    values = ", ".join(
        f"('{SHOP_ID}', '{code}', 1, {capacity}, true, {floor}, {x}, {y}, {width}, {height}, 'rectangle')"
        for code, capacity, floor, x, y, width, height in tables
    )
    op.execute(
        f"""
        INSERT INTO seating_tables
            (shop_id, table_code, min_capacity, max_capacity, is_active, floor, x, y, width, height, shape)
        VALUES {values}
        ON CONFLICT (shop_id, table_code) DO NOTHING
        """
    )
    links = [
        ("B", "C", True),
        ("C", "D", True),
        ("D", "E", True),
        ("H", "I", True),
        ("A", "B", False),
        ("A", "C", False),
        ("A", "D", False),
    ]
    values = ", ".join(f"('{a}', '{b}', {str(combinable).lower()})" for a, b, combinable in links)
    op.execute(
        f"""
        INSERT INTO seating_tables_rel
            (shop_id, seating_tables_id_a, seating_tables_id_b, is_combinable)
        SELECT '{SHOP_ID}', ta.id, tb.id, links.is_combinable
        FROM (VALUES {values}) AS links(code_a, code_b, is_combinable)
        JOIN seating_tables ta ON ta.shop_id = '{SHOP_ID}' AND ta.table_code = links.code_a
        JOIN seating_tables tb ON tb.shop_id = '{SHOP_ID}' AND tb.table_code = links.code_b
        WHERE NOT EXISTS (
            SELECT 1 FROM seating_tables_rel r
            WHERE r.shop_id = '{SHOP_ID}'
              AND r.seating_tables_id_a = ta.id AND r.seating_tables_id_b = tb.id
        )
        """
    )
    pricing_rules = [
        (
            "WEEKDAY_HOURLY_FEE",
            "平日場地費",
            "hourly",
            60.00,
            "person_hour",
            "適用星期一至星期五。依每位客人計費；不足一小時以一小時計算；超過 5 小時以 5 小時計算。",
        ),
        (
            "WEEKEND_HOURLY_FEE",
            "假日場地費",
            "hourly",
            80.00,
            "person_hour",
            "適用星期六及星期日。依每位客人計費；不足一小時以一小時計算；超過 5 小時以 5 小時計算。",
        ),
        (
            "WEEKEND_MINIMUM_DRINK_PER_PERSON",
            "假日每人最低飲料",
            "minimum_charge",
            0.00,
            "drink_per_person",
            "僅適用星期六及星期日；星期一至五無低消。每位客人至少須消費一杯飲料。",
        ),
        (
            "BILLING_ROUNDING_UNIT_HOURS",
            "計費取整單位",
            "other",
            1.00,
            "hour",
            "計費時數以此單位無條件進位。",
        ),
        (
            "BILLING_MAX_HOURS",
            "計費時數上限",
            "other",
            5.00,
            "hour",
            "計費時數上限；超過以 5 小時計算。",
        ),
        ("BOOKING_MIN_HOURS", "最短訂位時數", "other", 1.00, "hour", "單筆訂位最短時間。"),
    ]
    values = ", ".join(
        "("
        + ", ".join(
            (
                f"'{SHOP_ID}'",
                f"'{code}'",
                f"'{name}'",
                f"'{kind}'",
                str(price),
                f"'{unit}'",
                f"'{description}'",
                "true",
            )
        )
        + ")"
        for code, name, kind, price, unit, description in pricing_rules
    )
    op.execute(
        f"""
        INSERT INTO pricing_rules
            (shop_id, rule_code, rule_name, rule_type, price, unit, description, is_active)
        VALUES {values}
        ON CONFLICT (shop_id, rule_code) DO NOTHING
        """
    )
    faqs = [
        (
            "場地費如何計算？",
            "場地費依照每位客人及使用時數計算。每位客人都需要支付場地費，使用時間不足一小時時，以一小時計算。實際費率依平日或週末的收費規則為準。",
            "pricing",
            ["場地費", "收費", "計算方式", "每人", "每小時"],
            1,
        ),
        (
            "平日與假日的場地費有什麼不同？",
            "店家的平日與假日採用不同的場地費率。平日為星期一至星期五，假日為星期六及星期日。實際收費金額依目前設定的場地費規則為準。",
            "pricing",
            ["平日", "假日", "週末", "星期六", "星期日", "價格", "費率"],
            2,
        ),
        (
            "使用時間不滿一小時也要付一小時的費用嗎？",
            "是的。場地費以一小時為計費單位，不足一小時的部分會進位至下一個完整小時。例如使用一小時十分鐘，會以兩小時計算。",
            "pricing",
            ["不足一小時", "進位", "計費單位", "使用時間", "場地費"],
            3,
        ),
        (
            "每個人都有最低消費嗎？",
            "是的，每位客人都必須至少消費一個品項，可以選擇飲料或點心。這項規則是以品項數量計算，不是固定金額的最低消費。",
            "consumption",
            ["最低消費", "低消", "每人低消", "飲料", "點心", "消費規則"],
            1,
        ),
    ]
    for question, answer, category, keywords, sort_order in faqs:
        keywords_sql = "{" + ",".join(keywords) + "}"
        op.execute(
            f"""
            INSERT INTO faqs (shop_id, question, answer, category, keywords, is_active, sort_order)
            SELECT '{SHOP_ID}', '{question}', '{answer}', '{category}', '{keywords_sql}', true, {sort_order}
            WHERE NOT EXISTS (
                SELECT 1 FROM faqs WHERE shop_id = '{SHOP_ID}' AND question = '{question}'
            )
            """
        )
    categories = [("飲料", 1), ("點心", 2), ("輕食", 3)]
    values = ", ".join(f"('{name}', {sort_order})" for name, sort_order in categories)
    op.execute(
        f"""
        INSERT INTO menu_categories (shop_id, name, sort_order, is_active)
        SELECT '{SHOP_ID}', data.name, data.sort_order, true
        FROM (VALUES {values}) AS data(name, sort_order)
        WHERE NOT EXISTS (
            SELECT 1 FROM menu_categories c WHERE c.shop_id = '{SHOP_ID}' AND c.name = data.name
        )
        """
    )
    items = [
        ("飲料", "美式咖啡", "測試品項：經典美式咖啡（冰／熱）", 90, 1),
        ("飲料", "拿鐵", "測試品項：濃縮咖啡搭配牛奶（冰／熱）", 100, 2),
        ("飲料", "檸檬紅茶", "測試品項：檸檬風味紅茶（冰）", 60, 3),
        ("飲料", "無糖綠茶", "測試品項：無糖綠茶（冰）", 50, 4),
        ("飲料", "可樂", "測試品項：罐裝可樂", 45, 5),
        ("點心", "薯條", "測試品項：炸薯條一份", 70, 1),
        ("點心", "布朗尼", "測試品項：巧克力布朗尼一份", 90, 2),
        ("點心", "爆米花", "測試品項：分享用爆米花一份", 60, 3),
        ("點心", "雞塊", "測試品項：炸雞塊一份", 85, 4),
        ("輕食", "火腿起司吐司", "測試品項：火腿起司吐司一份", 80, 1),
    ]
    values = ", ".join(
        f"('{category}', '{name}', '{description}', {price}, {sort_order})"
        for category, name, description, price, sort_order in items
    )
    op.execute(
        f"""
        INSERT INTO menu_items (shop_id, category_id, name, description, price, sort_order, is_available)
        SELECT '{SHOP_ID}', c.id, data.name, data.description, data.price, data.sort_order, true
        FROM (VALUES {values}) AS data(category_name, name, description, price, sort_order)
        JOIN menu_categories c ON c.shop_id = '{SHOP_ID}' AND c.name = data.category_name
        WHERE NOT EXISTS (
            SELECT 1 FROM menu_items i WHERE i.shop_id = '{SHOP_ID}' AND i.name = data.name
        )
        """
    )
    op.execute(
        """
        INSERT INTO rules_qa_videos (game_id, source, video_url, youtube_id, title)
        SELECT games.id, 'youtube', urls.video_url, videos.youtube_id, videos.title
        FROM (VALUES
            (400566, 'XE-Sw_FtFFs', '血與刃的白薔薇 規則影片'),
            (144734, '5nIdNY056Gw', '阿不思學院 規則影片'),
            (171623, 'F5abxTqoEH8', '馬可波羅 規則影片')
        ) AS videos(bgg_id, youtube_id, title)
        JOIN games ON games.bgg_id = videos.bgg_id
        CROSS JOIN LATERAL (SELECT 'https://youtu.be/' || videos.youtube_id AS video_url) urls
        ON CONFLICT (game_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM rules_qa_videos
        WHERE youtube_id IN ('XE-Sw_FtFFs', '5nIdNY056Gw', 'F5abxTqoEH8')
        """
    )
    op.execute(
        f"DELETE FROM menu_items WHERE shop_id = '{SHOP_ID}' AND name IN ('美式咖啡', '拿鐵', '檸檬紅茶', '無糖綠茶', '可樂', '薯條', '布朗尼', '爆米花', '雞塊', '火腿起司吐司')"
    )
    op.execute(
        f"DELETE FROM menu_categories WHERE shop_id = '{SHOP_ID}' AND name IN ('飲料', '點心', '輕食')"
    )
    op.execute(
        f"DELETE FROM faqs WHERE shop_id = '{SHOP_ID}' AND question IN ('場地費如何計算？', '平日與假日的場地費有什麼不同？', '使用時間不滿一小時也要付一小時的費用嗎？', '每個人都有最低消費嗎？')"
    )
    op.execute(
        f"DELETE FROM pricing_rules WHERE shop_id = '{SHOP_ID}' AND rule_code IN ('WEEKDAY_HOURLY_FEE', 'WEEKEND_HOURLY_FEE', 'WEEKEND_MINIMUM_DRINK_PER_PERSON', 'BILLING_ROUNDING_UNIT_HOURS', 'BILLING_MAX_HOURS', 'BOOKING_MIN_HOURS')"
    )
    op.execute(f"DELETE FROM seating_tables_rel WHERE shop_id = '{SHOP_ID}'")
    op.execute(
        f"DELETE FROM seating_tables WHERE shop_id = '{SHOP_ID}' AND table_code IN ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I')"
    )
    op.execute(
        f"DELETE FROM closing_hours WHERE shop_id = '{SHOP_ID}' AND closing_date = DATE '2026-11-18' AND start_time = TIME '12:00' AND end_time = TIME '14:00' AND reason = 'take a break'"
    )
    op.execute(
        f"DELETE FROM business_hours WHERE shop_id = '{SHOP_ID}' AND weekday IN (0, 1, 3, 4, 5, 6) AND open_time = TIME '13:00' AND close_time = TIME '22:00'"
    )
    # 測試帳號的 shop_id 會參照此店家，因此保留店家列供 seed 指令建立帳號使用。
