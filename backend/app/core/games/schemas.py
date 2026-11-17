from pydantic import BaseModel


class GameSummary(BaseModel):
    id: int
    name: str
    english_name: str


class GameSearchOut(BaseModel):
    items: list[GameSummary]
    total: int
