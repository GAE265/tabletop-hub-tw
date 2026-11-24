"""開發環境專用 API：測試帳號與錯誤紀錄測試入口。"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import error_response
from app.dev.accounts import get_test_accounts
from app.domains.auth.models import AuthUser

router = APIRouter(prefix="/dev", tags=["dev"])
logger = logging.getLogger(__name__)


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


@router.post("/error-logs/{error_type}")
def trigger_error_log(error_type: Annotated[int, Path(ge=1, le=10)]) -> JSONResponse:
    """開發環境錯誤紀錄測試入口；以固定案例驗證例外與 logger 流程。"""
    messages = {
        number: f"error type {number}: diagnostic test exception" for number in range(1, 11)
    }

    def trigger() -> None:
        message = messages[error_type]
        if error_type == 1:
            raise ValueError(message)
        if error_type == 2:
            raise TypeError(message)
        if error_type == 3:
            raise ZeroDivisionError(message)
        if error_type == 4:
            raise KeyError(message)
        if error_type == 5:
            raise IndexError(message)
        if error_type == 6:
            raise RuntimeError(message)
        if error_type == 7:
            raise OSError(message)
        if error_type == 8:
            raise LookupError(message)
        if error_type == 9:
            raise ArithmeticError(message)
        raise NotImplementedError(message)

    if error_type <= 5:
        trigger()

    try:
        trigger()
    except NotImplementedError:
        logger.warning(messages[error_type])
    except RuntimeError:
        logger.exception(messages[error_type])
    except OSError:
        logger.error(messages[error_type], exc_info=True)
    except LookupError:
        logger.warning(messages[error_type], exc_info=True)
    except ArithmeticError:
        logger.error(messages[error_type])
    return error_response(500, "INTERNAL_ERROR", "伺服器發生未預期的錯誤")
