"""GET /api/v1/dev/users：列出測試帳號，供前端身分切換器使用。只在 AUTH_MODE=dev 掛載。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.dev.accounts import get_test_accounts
from app.domains.auth.models import AuthUser

router = APIRouter(prefix="/dev", tags=["dev"])


class DevUser(BaseModel):
    id: UUID
    display_name: str
    role: str
    shop_id: UUID | None


class DevUserList(BaseModel):
    items: list[DevUser]
    total: int


@router.get("/users", response_model=DevUserList)
def list_dev_users(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> DevUserList:
    order = [account.id for account in get_test_accounts(request.app.state.settings)]
    rows = session.scalars(select(AuthUser).where(AuthUser.id.in_(order))).all()
    rows = sorted(rows, key=lambda row: order.index(row.id))
    items = [
        DevUser(id=r.id, display_name=r.display_name, role=r.role, shop_id=r.shop_id) for r in rows
    ]
    return DevUserList(items=items, total=len(items))
