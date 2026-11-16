import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuthUser(Base):
    __tablename__ = "auth_users"
    __table_args__ = (
        CheckConstraint("role IN ('player', 'shop_staff', 'admin')", name="ck_auth_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    # 訂位的「同電話重疊」規則使用，取代舊訂位庫的 customers.phone；由 booking 的 migration 先行加入
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("booking_shops.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
