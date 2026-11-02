"""開發用 seed：建立固定 UUID 的測試帳號。可重複執行；AUTH_MODE 不是 dev 時拒絕執行。

執行方式：uv run python -m app.dev.seed
"""

import sys

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import create_db_engine
from app.dev.accounts import TEST_SHOP_ID, TEST_SHOP_NAME, get_test_accounts
from app.domains.auth.models import AuthUser
from app.domains.booking.models import BookingShop


def main() -> int:
    settings = get_settings()
    if settings.auth_mode != "dev":
        print("拒絕執行：seed 只能在 AUTH_MODE=dev 時使用。", file=sys.stderr)
        return 1

    engine = create_db_engine(settings.database_url)
    with Session(engine) as session, session.begin():
        session.execute(
            insert(BookingShop)
            .values(id=TEST_SHOP_ID, name=TEST_SHOP_NAME)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        for account in get_test_accounts(settings):
            session.execute(
                insert(AuthUser)
                .values(
                    id=account.id,
                    display_name=account.display_name,
                    role=account.role,
                    shop_id=account.shop_id,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
    engine.dispose()
    print("已建立（或確認存在）3 個測試帳號與 1 間測試店家。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
