"""rules_ingest 自己的表：規則書每一頁的 Markdown 文字。

表名與欄位沿用開發資料庫既有的 games_manual（games_id 與其他表的 game_id 不一致，是已知
的小瑕疵）。games_id 參照共用表 games.id（app/core/games/models.py）；依 ADR 0003 不可設定
成「桌遊刪掉就跟著刪」。
"""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GameManualPage(Base):
    __tablename__ = "games_manual"
    __table_args__ = (CheckConstraint("page >= 1", name="ck_games_manual_page_positive"),)

    games_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("games.id", name="games_manual_games_id_fkey"), primary_key=True
    )
    # 頁碼由呼叫端指定，不要求連續；沒有這頁就是沒有列
    page: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    # Markdown；空字串代表整頁沒文字，與「沒有這頁」不同
    content: Mapped[str] = mapped_column(Text)
