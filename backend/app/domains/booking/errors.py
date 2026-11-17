from typing import Any

from app.core.errors import AppError


class BookingRuleError(AppError):
    """訂位時間規則違反（422）。"""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(422, code, message, details)


class NoTableAvailable(AppError):
    """該時段沒有可分配的桌位（409）。"""

    def __init__(
        self, message: str = "該時段沒有足夠的桌位", details: dict[str, Any] | None = None
    ):
        super().__init__(409, "BOOKING_NO_TABLE_AVAILABLE", message, details)


class TableConflict(Exception):
    """寫入桌位時違反 exclusion constraint（同桌時間重疊）。service 會回滾並重試一次。"""
