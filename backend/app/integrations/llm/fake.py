from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import LLMConversationNotFound, LLMUnavailable
from app.integrations.llm.types import JsonSchema, LLMResponse, ToolCall, ToolResult, ToolSpec

DEFAULT_REPLY = "這是 FakeLLMProvider 的固定回覆"


@dataclass
class FakeResponse:
    """respond() 腳本的一個項目。fake 不檢查內容，寫什麼就回什麼。"""

    tool_calls: list[ToolCall] = field(default_factory=list)
    output: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class FakeCall:
    """fake 收到的一次呼叫：方法名稱與所有參數。"""

    method: str
    kwargs: dict[str, Any]


class FakeLLMProvider(LLMProvider):
    """測試用：依腳本回傳結果，不發出任何網路請求。

    - generate() 一律回傳 reply。
    - generate_json()、respond() 依序回傳 json_outputs、responses 的項目；
      項目是例外時就拋出它。腳本用完還被呼叫，代表測試本身寫錯，拋 AssertionError。
    - 沒給腳本（None）時拋 LLMUnavailable，讓 LLM_PROVIDER=fake 啟動的後端回 503。
    - 每次呼叫都記在 calls。
    """

    def __init__(
        self,
        reply: str = DEFAULT_REPLY,
        json_outputs: list[dict[str, Any] | Exception] | None = None,
        responses: list[FakeResponse | Exception] | None = None,
    ) -> None:
        self.reply = reply
        self.calls: list[FakeCall] = []
        self._json_outputs = None if json_outputs is None else deque(json_outputs)
        self._responses = None if responses is None else deque(responses)
        self._issued_response_ids: set[str] = set()

    def generate(self, prompt: str) -> str:
        self.calls.append(FakeCall("generate", {"prompt": prompt}))
        return self.reply

    def generate_json(self, *, instructions: str, input: str, schema: JsonSchema) -> dict:
        kwargs = {"instructions": instructions, "input": input, "schema": schema}
        self.calls.append(FakeCall("generate_json", kwargs))
        return _next_item(self._json_outputs, "json_outputs")

    def respond(
        self,
        *,
        instructions: str,
        input: str | list[ToolResult],
        tools: list[ToolSpec],
        output_schema: JsonSchema,
        previous_response_id: str | None,
        allow_tool_calls: bool = True,
    ) -> LLMResponse:
        self.calls.append(
            FakeCall(
                "respond",
                {
                    "instructions": instructions,
                    "input": input,
                    "tools": tools,
                    "output_schema": output_schema,
                    "previous_response_id": previous_response_id,
                    "allow_tool_calls": allow_tool_calls,
                },
            )
        )
        if self._responses is None:
            raise LLMUnavailable("沒有設定模型：FakeLLMProvider 沒有 responses 腳本")
        # 模擬 Azure 找不到對話；不用掉腳本的項目
        if (
            previous_response_id is not None
            and previous_response_id not in self._issued_response_ids
        ):
            raise LLMConversationNotFound(f"找不到 previous_response_id：{previous_response_id}")

        item = _next_item(self._responses, "responses")
        response_id = f"fake_resp_{len(self._issued_response_ids) + 1}"
        self._issued_response_ids.add(response_id)
        return LLMResponse(
            response_id=response_id,
            tool_calls=list(item.tool_calls),
            output=item.output,
            input_tokens=item.input_tokens,
            output_tokens=item.output_tokens,
        )


def _next_item[T](script: deque[T | Exception] | None, name: str) -> T:
    """取出腳本的下一個項目；項目是例外就拋出它。"""
    if script is None:
        raise LLMUnavailable(f"沒有設定模型：FakeLLMProvider 沒有 {name} 腳本")
    if not script:
        raise AssertionError(f"FakeLLMProvider 的 {name} 腳本已經用完，測試多呼叫了一次")
    item = script.popleft()
    if isinstance(item, Exception):
        raise item
    return item
