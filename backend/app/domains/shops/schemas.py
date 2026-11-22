"""店家與庫存 API 的請求與回應格式。"""

import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# 前後空白先去掉，所以只有空白的店名會因為長度不足而被擋下
ShopName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ShopCreate(BaseModel):
    name: ShopName
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)


class ShopCreatedOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    address: str | None


class ShopGameAdd(BaseModel):
    game_id: int


class ShopGameOut(BaseModel):
    game_id: int
    name: str


class ShopGameList(BaseModel):
    items: list[ShopGameOut]
    total: int
