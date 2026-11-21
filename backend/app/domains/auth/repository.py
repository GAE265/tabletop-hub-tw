"""使用者帳號（auth_users）的資料存取。

只提供其他 domain 需要的方法（AGENTS.md 4.2：共用表由擁有者提供 repository）。
唯一的寫入是 set_shop_id：新增店家時把店員綁到新店（shops domain 使用）。
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, update

from app.core.db import SessionRepository
from app.domains.auth.models import AuthUser


@dataclass(frozen=True)
class AuthUserInfo:
    id: uuid.UUID
    display_name: str


class AuthUserRepository(SessionRepository):
    def get_user(self, user_id: uuid.UUID) -> AuthUserInfo | None:
        """依 id 讀使用者的顯示名稱（只讀）；不存在回 None。"""
        row = self.session.execute(
            select(AuthUser.id, AuthUser.display_name).where(AuthUser.id == user_id)
        ).one_or_none()
        return None if row is None else AuthUserInfo(**row._mapping)

    def get_shop_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """帳號所屬的店家；沒有店或沒有這個帳號回 None。"""
        return self.session.scalar(select(AuthUser.shop_id).where(AuthUser.id == user_id))

    def set_shop_id(self, user_id: uuid.UUID, shop_id: uuid.UUID) -> bool:
        """只在帳號還沒有店時綁定；已經有店（或沒有這個帳號）回 False。呼叫端要用 transaction()。"""
        result = self.session.execute(
            update(AuthUser)
            .where(AuthUser.id == user_id, AuthUser.shop_id.is_(None))
            .values(shop_id=shop_id)
        )
        return result.rowcount > 0
