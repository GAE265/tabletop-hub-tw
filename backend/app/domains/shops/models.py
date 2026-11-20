"""店家庫存的資料表：每間店有哪些桌遊。

shop_id、game_id 參照共用資料表 booking_shops、games（AGENTS.md 第 3 節），
shops 只讀不改它們的結構。
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ShopGame(Base):
    __tablename__ = "shops_games"
    __table_args__ = (
        UniqueConstraint("shop_id", "game_id", name="uq_shops_games_shop_game"),
        {"comment": "店家庫存：每間店有哪些桌遊，同一間店同一款桌遊只有一筆，目前不記數量"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="庫存紀錄的識別碼",
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("booking_shops.id", ondelete="CASCADE"),
        comment="哪一間店；店家被刪除時庫存一併刪除",
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        comment="店裡有的桌遊；桌遊被刪除時只刪掉這筆庫存",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="加入庫存的時間（UTC）",
    )
