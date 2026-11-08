"""LLMProvider 的輸入輸出型別（整合層提案 §3.1）。"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonSchema:
    """要求模型輸出符合的 JSON Schema。

    呼叫端負責寫成 Azure strict 規定的格式：所有欄位都列為 required、
    additionalProperties 為 false、選填欄位寫成可為 null。整合層不轉換、不驗證。
    """

    name: str  # Azure 規定只能用英數字、底線、連字號
    schema: dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    """送給模型的工具定義。parameters 的規定同 JsonSchema.schema。"""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """模型要求呼叫工具。"""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """呼叫端執行工具後送回的結果；整合層負責轉成 JSON 字串（ensure_ascii=False）。"""

    call_id: str
    output: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    """respond() 一次呼叫的結果。tool_calls 與 output 一定剛好只有一個有值。

    不叫 Turn，因為 turn 是 AGENTS.md §10.2 的「回合」。
    """

    response_id: str
    tool_calls: list[ToolCall]
    output: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
