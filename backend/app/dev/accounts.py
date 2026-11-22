"""開發用測試帳號的唯一定義處。前端不存這些 UUID，身分切換器從 GET /api/v1/dev/users 讀取。"""

from dataclasses import dataclass
from uuid import UUID

from app.core.config import Settings

TEST_SHOP_ID = UUID("44444444-4444-4444-8444-444444444444")
TEST_SHOP_NAME = "測試桌遊店"

SHOP_STAFF_ID = UUID("22222222-2222-4222-8222-222222222222")
ADMIN_ID = UUID("33333333-3333-4333-8333-333333333333")
# 還沒有店的店員：示範「店員新增店家」用（add-shops-management）
NEW_SHOP_STAFF_ID = UUID("55555555-5555-4555-8555-555555555555")


@dataclass(frozen=True)
class TestAccount:
    __test__ = False  # 避免 pytest 把它當成測試類別

    id: UUID
    display_name: str
    role: str
    shop_id: UUID | None
    # 假電話：訂位要求使用者有電話（BOOKING_PHONE_REQUIRED）；每個帳號不同，避免觸發同電話重疊規則
    phone: str


def get_test_accounts(settings: Settings) -> list[TestAccount]:
    """player 的 UUID 取自設定 DEV_DEFAULT_USER_ID，其餘固定在這裡。"""
    return [
        TestAccount(settings.dev_default_user_id, "測試玩家", "player", None, "0900000001"),
        TestAccount(SHOP_STAFF_ID, "測試店家人員", "shop_staff", TEST_SHOP_ID, "0900000002"),
        TestAccount(ADMIN_ID, "測試管理員", "admin", None, "0900000003"),
        TestAccount(
            NEW_SHOP_STAFF_ID, "測試店家人員（還沒有店）", "shop_staff", None, "0900000004"
        ),
    ]
