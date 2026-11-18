"""使用者帳號（auth_users）的資料存取。

目前只提供其他 domain 需要的讀取方法，不寫入（AGENTS.md 4.2：共用表由擁有者提供 repository）。
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select

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
