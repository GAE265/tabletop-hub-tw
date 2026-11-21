from typing import Literal

from pydantic import BaseModel


class ManualPageOut(BaseModel):
    games_id: int
    page: int
    content: str
    chunk_count: int


class ManualPageItem(BaseModel):
    page: int
    content: str


class ManualPageListOut(BaseModel):
    items: list[ManualPageItem]
    total: int
    ocr_provider: Literal["fake", "cloud"]
