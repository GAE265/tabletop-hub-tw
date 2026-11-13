"""games.json 與匯出檔的格式與檢查（spec §8.1、§8.10、§8.11）。

型別一律嚴格比對：整數欄位不接受 "2"、2.0、true。
types 的代碼是否存在，要給 context={"type_codes": 代碼集合} 才檢查；沒給就不檢查。
"""

from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("不能是空白")
    return value


def _unique(values: list[str]) -> list[str]:
    repeated = sorted({value for value in values if values.count(value) > 1})
    if repeated:
        raise ValueError(f"有重複的值：{'、'.join(repeated)}")
    return values


NonBlank = Annotated[str, AfterValidator(_not_blank)]
UniqueNames = Annotated[list[NonBlank], AfterValidator(_unique)]


class GameData(BaseModel):
    """games.json 的一款桌遊：12 個欄位都必填，不接受其他欄位。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    bgg_id: int = Field(gt=0)
    name: NonBlank
    english_name: NonBlank
    min_players: int = Field(ge=1)
    max_players: int = Field(ge=1)
    min_playtime: int = Field(ge=1)
    max_playtime: int = Field(ge=1)
    min_age: int = Field(ge=0)
    weight: float = Field(ge=1, le=5)
    categories: UniqueNames
    mechanics: UniqueNames
    types: Annotated[list[str], AfterValidator(_unique)]

    @field_validator("types")
    @classmethod
    def _types_are_known(cls, codes: list[str], info: ValidationInfo) -> list[str]:
        known = (info.context or {}).get("type_codes")
        unknown = [code for code in codes if known is not None and code not in known]
        if unknown:
            raise ValueError(f"不認得的類型代碼：{'、'.join(unknown)}")
        return codes

    @model_validator(mode="after")
    def _min_not_above_max(self) -> Self:
        if self.min_players > self.max_players:
            raise ValueError("min_players 不能大於 max_players")
        if self.min_playtime > self.max_playtime:
            raise ValueError("min_playtime 不能大於 max_playtime")
        return self

    def columns(self) -> dict[str, Any]:
        """games 資料表的 11 個欄位值（不含 id、types）。"""
        return self.model_dump(exclude={"id", "types"})


class ExportedGame(GameData):
    """匯出檔的一款桌遊：games.json 的 12 個欄位加上 id。"""

    id: int = Field(gt=0)


def _repeated(games: list[Any], field: str) -> list[str]:
    """同一個欄位值出現第二次時，說明是第幾款和第幾款重複。"""
    first_seen: dict[int, int] = {}
    problems = []
    for position, game in enumerate(games, start=1):
        value = getattr(game, field)
        if value in first_seen:
            problems.append(f"第 {position} 款的 {field} {value} 和第 {first_seen[value]} 款重複")
        else:
            first_seen[value] = position
    return problems


class GamesFile(BaseModel):
    """games.json：Codex 整理的桌遊資料，沒有編號。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    games: list[GameData]

    @model_validator(mode="after")
    def _bgg_ids_are_unique(self) -> Self:
        if problems := _repeated(self.games, "bgg_id"):
            raise ValueError("；".join(problems))
        return self


class GamesExport(BaseModel):
    """匯出檔：每款帶編號，加上計數器的下一個號碼。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    next_id: int = Field(gt=0)
    games: list[ExportedGame]

    @model_validator(mode="after")
    def _ids_are_consistent(self) -> Self:
        problems = _repeated(self.games, "id") + _repeated(self.games, "bgg_id")
        largest = max((game.id for game in self.games), default=0)
        if self.next_id <= largest:
            problems.append(f"next_id 是 {self.next_id}，要大於所有 id（最大的 id 是 {largest}）")
        if problems:
            raise ValueError("；".join(problems))
        return self

    def to_json(self) -> dict[str, Any]:
        """寫進匯出檔的內容：每款的 id 排在最前面。"""
        games = [{"id": game.id, **game.model_dump(exclude={"id"})} for game in self.games]
        return {"next_id": self.next_id, "games": games}


def _reason(error: Any) -> str:
    """把 pydantic 的錯誤換成中文說明；沒列到的類型就用 pydantic 原本的訊息。"""
    context = error.get("ctx") or {}
    reasons = {
        "missing": "缺少這個欄位",
        "extra_forbidden": "不認得的欄位",
        "int_type": "要是整數",
        "float_type": "要是數字",
        "string_type": "要是文字",
        "list_type": "要是陣列",
        "model_type": "要是物件",
        "greater_than": f"要大於 {context.get('gt')}",
        "greater_than_equal": f"不能小於 {context.get('ge')}",
        "less_than_equal": f"不能大於 {context.get('le')}",
        "value_error": str(context.get("error")),
    }
    return reasons.get(error["type"], error["msg"])


def describe_problems(exc: ValidationError, data: object, id_field: str) -> list[str]:
    """把檢查不通過的地方寫成一行一個問題：哪一款（id_field 的值）的哪個欄位、為什麼。"""
    games = data.get("games") if isinstance(data, dict) else None
    lines = []
    for error in exc.errors():
        location = error["loc"]
        if len(location) >= 2 and location[0] == "games" and isinstance(location[1], int):
            game = games[location[1]] if isinstance(games, list) else None
            value = game.get(id_field, "？") if isinstance(game, dict) else "？"
            where = f"第 {location[1] + 1} 款（{id_field} {value}）"
            if len(location) >= 3:
                where += f"的 {location[2]}"
        else:
            where = ".".join(str(part) for part in location) or "檔案內容"
        lines.append(f"{where}：{_reason(error)}")
    return lines
