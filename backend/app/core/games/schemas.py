"""遊戲清單 API 的回應格式。"""

from pydantic import BaseModel


class GameListItem(BaseModel):
    id: int
    name: str
    english_name: str


class GameListResponse(BaseModel):
    items: list[GameListItem]
    total: int
