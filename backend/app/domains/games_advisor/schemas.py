"""推薦對話 API 的請求與回應（spec §13.1，在檔案最後）。

批次指令讀寫的檔案格式與檢查：games.json、匯出檔（spec §8.1、§8.10、§8.11）、
reviews.json（spec §8.2）、tag_vocabulary.json（spec §8.6），以及歸納詞彙表時 LLM 的輸出
（spec §8.5）。評估題組的題組檔 eval_cases.json 與評審的輸出（spec §15.2、§15.6）也在檔案最後。

型別一律嚴格比對：整數欄位不接受 "2"、2.0、true。
types 的代碼是否存在，要給 context={"type_codes": 代碼集合} 才檢查；沒給就不檢查。
"""

import re
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.domains.games_advisor.constants import TAG_VOCABULARY_MAX_TAGS


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


def _repeated(entries: list[Any], field: str, unit: str = "款") -> list[str]:
    """同一個欄位值出現第二次時，說明是第幾款和第幾款重複。unit 是量詞。"""
    first_seen: dict[Any, int] = {}
    problems = []
    for position, entry in enumerate(entries, start=1):
        value = getattr(entry, field)
        if value in first_seen:
            problems.append(
                f"第 {position} {unit}的 {field} {value} 和第 {first_seen[value]} {unit}重複"
            )
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


class Review(BaseModel):
    """reviews.json 的一篇心得。後端只讀這 5 個欄位，其他欄位（標題、作者、日期）不管。"""

    model_config = ConfigDict(extra="ignore", strict=True)

    bgg_id: int = Field(gt=0)
    source_url: str
    site_name: str
    language: Literal["zh-TW", "en"]
    text: NonBlank


class ReviewsFile(BaseModel):
    """reviews.json：Codex 收集的心得。shortfalls 等其他欄位後端不讀。"""

    model_config = ConfigDict(extra="ignore", strict=True)

    reviews: list[Review]


_TAG_CODE = re.compile(r"[a-z][a-z0-9_]*")


def _tag_code(value: str) -> str:
    if not _TAG_CODE.fullmatch(value):
        raise ValueError("要用小寫英文字母開頭，只能有小寫英文字母、數字、底線")
    return value


class TagDefinition(BaseModel):
    """tag_vocabulary.json 的一個標籤：英文代碼、繁中名稱、一句繁中定義。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    code: Annotated[str, AfterValidator(_tag_code)]
    name: NonBlank
    definition: NonBlank


class TagVocabularyFile(BaseModel):
    """tag_vocabulary.json：標籤詞彙表的正本，資料表是照它同步出來的副本。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    tags: list[TagDefinition]

    @model_validator(mode="after")
    def _codes_and_names_are_unique_and_within_limit(self) -> Self:
        problems = _repeated(self.tags, "code", "個") + _repeated(self.tags, "name", "個")
        if len(self.tags) > TAG_VOCABULARY_MAX_TAGS:
            problems.append(f"有 {len(self.tags)} 個標籤，最多只能有 {TAG_VOCABULARY_MAX_TAGS} 個")
        if problems:
            raise ValueError("；".join(problems))
        return self


# --- 歸納詞彙表時 LLM 的輸出（spec §8.5）。雲端模型照 strict schema 輸出，這裡再確認一次 ---


class Candidate(BaseModel):
    """LLM 從一款桌遊的心得擷取的候選詞。"""

    term: str
    description: str
    source_urls: list[str]


class CandidatesOutput(BaseModel):
    candidates: list[Candidate]


class MergedTag(BaseModel):
    """LLM 把幾個候選詞合併成的一個標籤。"""

    code: str
    name: str
    definition: str
    candidate_ids: list[str]


class DiscardedCandidate(BaseModel):
    candidate_id: str
    reason: str


class MergeOutput(BaseModel):
    tags: list[MergedTag]
    discarded: list[DiscardedCandidate]


# --- 上標籤時 LLM 的輸出，以及標籤草稿的格式（spec §8.7、§8.8） ---


class JudgedTag(BaseModel):
    """一款桌遊的一個標籤：代碼、信心分數、依據的心得網址。"""

    code: str
    confidence: float
    source_urls: list[str]


class TagsOutput(BaseModel):
    tags: list[JudgedTag]


class TagDraftGame(BaseModel):
    """標籤草稿裡的一款桌遊。name 只是給人看的，匯入時用 bgg_id 認桌遊。"""

    bgg_id: int
    name: str = ""
    tags: list[JudgedTag]


class TagDraftFile(BaseModel):
    """標籤草稿與它的原始檔。"""

    games: list[TagDraftGame]


def _reason(error: Any) -> str:
    """把 pydantic 的錯誤換成中文說明；沒列到的類型就用 pydantic 原本的訊息。"""
    context = error.get("ctx") or {}
    reasons = {
        "literal_error": f"只能是 {str(context.get('expected')).replace(' or ', ' 或 ')}",
        "missing": "缺少這個欄位",
        "extra_forbidden": "不認得的欄位",
        "int_type": "要是整數",
        "float_type": "要是數字",
        "bool_type": "要是 true 或 false",
        "string_type": "要是文字",
        "string_too_short": f"至少要 {context.get('min_length')} 個字",
        "string_too_long": f"不能超過 {context.get('max_length')} 個字",
        "list_type": "要是陣列",
        "too_short": f"至少要有 {context.get('min_length')} 個",
        "model_type": "要是物件",
        "greater_than": f"要大於 {context.get('gt')}",
        "greater_than_equal": f"不能小於 {context.get('ge')}",
        "less_than_equal": f"不能大於 {context.get('le')}",
        "value_error": str(context.get("error")),
    }
    return reasons.get(error["type"], error["msg"])


def describe_problems(
    exc: ValidationError, data: object, *, id_field: str, items: str = "games", unit: str = "款"
) -> list[str]:
    """把檢查不通過的地方寫成一行一個問題：第幾款（id_field 的值）的哪個欄位、為什麼。

    items 是檔案裡放清單的欄位名稱，unit 是量詞：桌遊用「款」，心得用「篇」。
    """
    entries = data.get(items) if isinstance(data, dict) else None
    lines = []
    for error in exc.errors():
        location = error["loc"]
        if len(location) >= 2 and location[0] == items and isinstance(location[1], int):
            entry = entries[location[1]] if isinstance(entries, list) else None
            value = entry.get(id_field, "？") if isinstance(entry, dict) else "？"
            where = f"第 {location[1] + 1} {unit}（{id_field} {value}）"
            if len(location) >= 3:
                where += f"的 {location[2]}"
        else:
            where = ".".join(str(part) for part in location) or "檔案內容"
        lines.append(f"{where}：{_reason(error)}")
    return lines


def describe_eval_problems(exc: ValidationError, data: object) -> list[str]:
    """題組檔檢查不通過的地方，一行一個問題：第幾題（id）第幾輪的哪個欄位、為什麼。

    expect 有好幾層，所以寫出完整的欄位路徑，例如 expect.tool_args.players。
    """
    cases = data.get("cases") if isinstance(data, dict) else None
    lines = []
    for error in exc.errors():
        location = list(error["loc"])
        if len(location) >= 2 and location[0] == "cases" and isinstance(location[1], int):
            index = location[1]
            entry = cases[index] if isinstance(cases, list) and index < len(cases) else None
            case_id = entry.get("id", "？") if isinstance(entry, dict) else "？"
            where = f"第 {index + 1} 題（id {case_id}）"
            rest = location[2:]
            if len(rest) >= 2 and rest[0] == "turns" and isinstance(rest[1], int):
                where += f"第 {rest[1] + 1} 輪"
                rest = rest[2:]
            if rest:
                where += "的 " + ".".join(str(part) for part in rest)
        else:
            where = ".".join(str(part) for part in location) or "題組檔"
        lines.append(f"{where}：{_reason(error)}")
    return lines


# --- 推薦對話 API（spec §13.1）。⚠️ 改這裡等於改前後端的契約 ---

# 欄位超過上限的訊息不送給 LLM
MESSAGE_MAX_CHARS = 500


class MessageRequest(BaseModel):
    # 去掉前後空白後 1–500 字；送給 LLM 的是去掉空白後的文字
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_MAX_CHARS)
    ]
    # 上一則回應的 response_id；必填，新對話給 null。漏了這個欄位或給空字串回 422：
    # 漏送會讓 Agent 默默忘記前面的對話，寧可讓前端在開發時就看到錯誤
    previous_response_id: Annotated[str, StringConstraints(min_length=1)] | None


class AdvisorGame(BaseModel):
    id: int
    name: str
    min_players: int
    max_players: int
    min_playtime: int
    max_playtime: int
    min_age: int
    weight: float


class AdvisorExcerpt(BaseModel):
    id: str
    text: str
    language: str


class AdvisorRecommendation(BaseModel):
    game: AdvisorGame
    reason: str
    excerpts: list[AdvisorExcerpt]


class MessageResponse(BaseModel):
    # 固定文字時是請求帶來的舊 id；第一則訊息就固定文字時是 null
    response_id: str | None
    reply: str
    relaxed_constraint: Literal["playtime", "age"] | None
    recommendations: list[AdvisorRecommendation]


# --- 評估題組的題組檔 eval_cases.json（spec §15.2） ---


class EvalToolArgs(BaseModel):
    """一輪預期的工具參數：只寫要檢查的參數，寫 null 代表模型必須沒帶。

    model_fields_set 分得出「沒寫」和「寫 null」。排除清單用 BGG ID 寫（exclude_bgg_ids），
    比對前換成桌遊 id。preference_text 是自由文字，沒辦法比對，所以不能寫。
    ⚠️ 欄位要和「查桌遊」工具的參數（search.build_search_tool）一致
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    players: int | None = None
    max_minutes: int | None = None
    min_minutes: int | None = None
    youngest_age: int | None = None
    weight_min: float | None = None
    weight_max: float | None = None
    prefer_tags: list[str] | None = None
    avoid_tags: list[str] | None = None
    prefer_categories: list[str] | None = None
    avoid_categories: list[str] | None = None
    prefer_mechanics: list[str] | None = None
    avoid_mechanics: list[str] | None = None
    exclude_bgg_ids: list[int] | None = None


class EvalExpect(BaseModel):
    """一輪的預期結果：只寫這一輪要檢查的欄位。桌遊用 BGG ID 寫。

    只有 relaxed_constraint 可以寫 null（代表必須沒有放寬）；其他欄位不檢查就不要寫。
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["follow_up", "recommend", "off_topic"] | None = None
    tool_args: EvalToolArgs | None = None
    relaxed_constraint: Literal["playtime", "age"] | None = None
    expect_any: list[int] | None = None
    forbid: list[int] | None = None
    manual: list[NonBlank] = Field(default_factory=list)

    @model_validator(mode="after")
    def _only_relaxed_constraint_can_be_null(self) -> Self:
        nulls = [
            name
            for name in ("action", "tool_args", "expect_any", "forbid")
            if name in self.model_fields_set and getattr(self, name) is None
        ]
        if nulls:
            raise ValueError(f"{'、'.join(nulls)} 不能是 null：這一輪不檢查就不要寫")
        return self


class EvalTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    # 同 MessageRequest.content：API 收得下的訊息才放得進題組
    player: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_MAX_CHARS)
    ]
    expect: EvalExpect


class EvalCase(BaseModel):
    """一題評估題：一段對話腳本。demo 標 true 的是 Demo 題，固定跑 3 次。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonBlank
    demo: bool = False
    turns: list[EvalTurn] = Field(min_length=1)


class EvalCasesFile(BaseModel):
    """eval_cases.json：立倫寫的玩家訊息與預期結果，進 repo。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    cases: list[EvalCase]

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Self:
        if problems := _repeated(self.cases, "id", "題"):
            raise ValueError("；".join(problems))
        return self


class ReasonCheckOutput(BaseModel):
    """評審的輸出（spec §15.6）：推薦理由裡找不到依據的說法，空的就是「有依據」。

    ⚠️ 要和 prompts.REASON_CHECK_SCHEMA 一致
    """

    unsupported: list[str]
