"""每款遊戲一份定義：回合紀錄的內容格式與陣營（design.md D3）。

以 games.bgg_id（有 unique 限制）找定義。沒有定義的遊戲不能記錄回合；新增遊戲時在
GAME_DEFINITIONS 加一筆即可，不用改資料表。
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

# 《血與刃的白薔薇》（Blades & Rose）在 BGG 的編號
WHITE_ROSE_BGG_ID = 400566


class WhiteRoseFaction(StrEnum):
    """《血與刃的白薔薇》的陣營，結果類型為 faction（陣營勝負）時記錄獲勝的一方。"""

    # 薔薇陣營：要找出並保護白薔薇的一方。例：白薔薇揪團中，薔薇陣營完成任務就獲勝
    ROSE = "rose"
    # 血刃陣營：要讓白薔薇凋零的一方。例：白薔薇揪團中，血刃陣營奪得白薔薇就獲勝
    BLOOD_BLADE = "blood_blade"


_Count = Annotated[StrictInt, Field(ge=0)]
_Seat = Annotated[StrictInt, Field(ge=1)]


class WhiteRoseTurnData(BaseModel):
    """白薔薇一個回合的內容。幽魂不記；不接受其他欄位。

    - played_seat_numbers：這回合出牌的座位，必填、不可重複；整桌都不出牌時是空陣列。
      只有這回合什麼都沒發生（四種數量都是 0、白薔薇與司教都沒有）時才可以是空的。
    - 四種數量與 has_white_rose：必填。
    - has_cardinal：這回合有沒有出現司教（一局只有一位司教，所以只記有沒有）。
      選填、預設 False，舊紀錄與舊版前端沒有這個欄位也能通過驗證。
    """

    model_config = ConfigDict(extra="forbid")

    played_seat_numbers: list[_Seat]
    double_blade_count: _Count
    dark_blade_count: _Count
    giant_blade_count: _Count
    faithful_count: _Count
    has_white_rose: StrictBool
    has_cardinal: StrictBool = False

    @model_validator(mode="after")
    def _seats_are_unique(self) -> Self:
        if len(set(self.played_seat_numbers)) != len(self.played_seat_numbers):
            raise ValueError("played_seat_numbers 不可重複")
        return self

    @model_validator(mode="after")
    def _seats_required_when_cards_recorded(self) -> Self:
        counts = (
            self.double_blade_count,
            self.dark_blade_count,
            self.giant_blade_count,
            self.faithful_count,
        )
        happened = any(counts) or self.has_white_rose or self.has_cardinal
        if happened and not self.played_seat_numbers:
            raise ValueError("這回合有記錄到牌，請選出牌的座位")
        return self


@dataclass(frozen=True)
class OncePerMatch:
    """一局只能出現在一個回合的是非欄位，例如白薔薇。跨回合的檢查由 service 負責。"""

    field: str
    label: str
    error_code: str


@dataclass(frozen=True)
class GameDefinition:
    bgg_id: int
    turn_model: type[BaseModel]
    factions: tuple[str, ...]
    once_per_match: tuple[OncePerMatch, ...] = ()

    def played_seats(self, game_data: dict) -> list[int]:
        """這個回合出牌的座位編號；service 用來對照這局有哪些座位。"""
        return list(game_data.get("played_seat_numbers", []))


GAME_DEFINITIONS: dict[int, GameDefinition] = {
    WHITE_ROSE_BGG_ID: GameDefinition(
        bgg_id=WHITE_ROSE_BGG_ID,
        turn_model=WhiteRoseTurnData,
        factions=tuple(faction.value for faction in WhiteRoseFaction),
        # 一局只有一朵白薔薇、一位司教
        once_per_match=(
            OncePerMatch("has_white_rose", "白薔薇", "MATCH_WHITE_ROSE_ALREADY_RECORDED"),
            OncePerMatch("has_cardinal", "司教", "MATCH_CARDINAL_ALREADY_RECORDED"),
        ),
    ),
}


def get_definition(bgg_id: int) -> GameDefinition | None:
    return GAME_DEFINITIONS.get(bgg_id)
