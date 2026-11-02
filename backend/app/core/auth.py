from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Header, Request

from app.core.errors import AppError, PermissionDenied, Unauthenticated

ROLES = ("player", "shop_staff", "admin")


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    role: str
    shop_id: UUID | None = None


def require_role(user: CurrentUser, *roles: str) -> None:
    """在 service 使用：角色不在允許清單時拋出 PermissionDenied（轉成 403）。"""
    if user.role not in roles:
        raise PermissionDenied(details={"required_roles": list(roles)})


def _invalid_dev_user(value: str) -> AppError:
    return AppError(
        400,
        "INVALID_DEV_USER",
        "X-Dev-User 格式必須是 <user_uuid>:<role>[:<shop_uuid>]，"
        "shop_staff 必須帶 shop_uuid，其他角色不可帶",
        {"value": value, "roles": list(ROLES)},
    )


def parse_dev_user(value: str) -> CurrentUser:
    """只從標頭內容建立 CurrentUser，不查任何資料表。"""
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise _invalid_dev_user(value)
    user_part, role, *shop_part = parts
    if role not in ROLES:
        raise _invalid_dev_user(value)
    # shop_staff 必帶店家；其他角色不可帶
    if (role == "shop_staff") != bool(shop_part):
        raise _invalid_dev_user(value)
    try:
        user_id = UUID(user_part)
        shop_id = UUID(shop_part[0]) if shop_part else None
    except ValueError:
        raise _invalid_dev_user(value) from None
    return CurrentUser(id=user_id, role=role, shop_id=shop_id)


def get_current_user(
    request: Request,
    x_dev_user: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """只在 router 使用。dev 模式讀 X-Dev-User；jwt 模式在 auth 完成前一律 401。"""
    settings = request.app.state.settings
    if settings.auth_mode != "dev":
        raise Unauthenticated()
    if x_dev_user is None:
        return CurrentUser(id=settings.dev_default_user_id, role="player")
    return parse_dev_user(x_dev_user)
