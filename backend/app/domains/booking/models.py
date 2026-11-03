import uuid

from sqlalchemy import Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BookingShop(Base):
    __tablename__ = "booking_shops"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
