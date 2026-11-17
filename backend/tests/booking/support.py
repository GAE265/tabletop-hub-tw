"""測試用的虛構桌位配置：結構（容量、相鄰、可併桌）與真實店家相同，但不是真實資料。"""

from datetime import UTC, datetime

from app.domains.booking.allocation import TableInfo, TableLink
from app.domains.booking.rules import COMPANY_TZ

CAPACITY = {"A": 6, "B": 6, "C": 10, "D": 8, "E": 10, "F": 8, "G": 4, "H": 12, "I": 12}
TABLES = {
    code: TableInfo(index, code, 1, cap)
    for index, (code, cap) in enumerate(CAPACITY.items(), start=1)
}


def tid(code: str) -> int:
    return TABLES[code].id


LINK_SPECS = [
    ("B", "C", True),
    ("C", "E", True),
    ("D", "E", True),
    ("H", "I", True),
    ("A", "B", False),
    ("A", "C", False),
    ("A", "D", False),
]
LINKS = [TableLink(tid(a), tid(b), combinable) for a, b, combinable in LINK_SPECS]


def tables(*codes: str) -> list[TableInfo]:
    return [TABLES[c] for c in codes]


def local(day: str, hhmm: str) -> datetime:
    """公司時區的時間，例如 local('2026-11-20', '14:00')。"""
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=COMPANY_TZ).astimezone(UTC)
