"""LLM 的雲端實作：Azure OpenAI Responses API（整合層提案 §3.3、§5）。

openai SDK 只在這個檔案裡 import（AGENTS.md §4.2）。例外轉換照 ticket 02 在 Azure 實測的結果。
"""

import json
from typing import Any

import httpx
import openai
from openai.types.responses import Response

from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import (
    LLMConversationNotFound,
    LLMError,
    LLMOutputRejected,
    LLMUnavailable,
)
from app.integrations.llm.types import JsonSchema, LLMResponse, ToolCall, ToolResult, ToolSpec


class CloudLLMProvider(LLMProvider):
    """一個 provider 只綁一個部署（model）。重試沿用 SDK 預設的 2 次。"""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model: str,
        reasoning_effort: str | None = None,
        timeout_seconds: float = 30,
        http_client: httpx.Client | None = None,
    ) -> None:
        # ⚠️ endpoint 是 Azure 的 v1 端點（.../openai/v1/），不帶 api-version
        self._client = openai.OpenAI(
            base_url=endpoint,
            api_key=api_key,
            timeout=timeout_seconds,
            http_client=http_client,
        )
        self._model = model
        self._reasoning_effort = reasoning_effort

    def generate(self, prompt: str) -> str:
        response = self._create(input=prompt, store=False)
        return response.output_text

    def generate_json(self, *, instructions: str, input: str, schema: JsonSchema) -> dict:
        response = self._create(
            instructions=instructions,
            input=input,
            store=False,
            text={"format": _json_schema_format(schema)},
        )
        return _parse_json_output(response)

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
        params: dict[str, Any] = {
            "instructions": instructions,  # Responses API 不沿用上一次的 instructions，每次都送
            "input": input if isinstance(input, str) else [_tool_output(r) for r in input],
            "store": True,  # ADR 0001：對話狀態交給 Azure 保存
            "text": {"format": _json_schema_format(output_schema)},
        }
        if previous_response_id is not None:
            params["previous_response_id"] = previous_response_id
        if tools:
            params["tools"] = [_tool_definition(tool) for tool in tools]
            # structured outputs 不相容平行工具呼叫，也會打亂呼叫端「先查再放寬」的順序
            params["parallel_tool_calls"] = False
            if not allow_tool_calls:
                params["tool_choice"] = "none"
        response = self._create(**params)

        tool_calls = _tool_calls(response)
        usage = response.usage
        return LLMResponse(
            response_id=response.id,
            tool_calls=tool_calls,
            output=None if tool_calls else _parse_json_output(response),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )

    def _create(self, **params: Any) -> Response:
        if self._reasoning_effort:
            params["reasoning"] = {"effort": self._reasoning_effort}
        try:
            response = self._client.responses.create(model=self._model, **params)
        except openai.APIConnectionError as exc:  # 包含逾時（APITimeoutError）
            raise LLMUnavailable(f"連不上 Azure OpenAI：{exc}") from exc
        except openai.APIStatusError as exc:
            raise _convert_status_error(exc) from exc
        except openai.OpenAIError as exc:
            raise LLMError(f"Azure OpenAI 呼叫失敗：{exc}") from exc
        _check_finished(response)
        return response


def _convert_status_error(exc: openai.APIStatusError) -> LLMError:
    """⚠️ 必須與 Azure 實際回的錯誤同步（ticket 02 第 4 節「給 08 的轉換規則」）。"""
    if exc.status_code == 429 or exc.status_code >= 500:
        return LLMUnavailable(f"Azure OpenAI 暫時無法使用（HTTP {exc.status_code}）：{exc}")
    code = exc.code
    if code == "previous_response_not_found" or (
        code == "invalid_value" and exc.param == "previous_response_id"
    ):
        return LLMConversationNotFound(f"找不到 previous_response_id：{exc}")
    if code == "content_filter":
        return LLMOutputRejected(f"輸入被內容過濾擋下：{exc}")
    return LLMError(f"Azure OpenAI 回傳錯誤（HTTP {exc.status_code}）：{exc}")


def _check_finished(response: Response) -> None:
    """輸出被內容過濾擋下時 Azure 回 200，所以要先檢查 status，再解析輸出。"""
    if response.status == "incomplete":
        details = response.incomplete_details
        reason = details.reason if details else None
        # 原因是 content_filter（被擋下）或 max_output_tokens（被截斷）
        raise LLMOutputRejected(f"模型輸出不完整：{reason}")
    if response.status not in (None, "completed"):
        raise LLMError(f"模型回應的狀態是 {response.status}")
    for item in response.output:
        if item.type != "message":
            continue
        for content in item.content:
            if content.type == "refusal":
                raise LLMOutputRejected(f"模型拒答：{content.refusal}")


def _parse_json_output(response: Response) -> dict[str, Any]:
    text = response.output_text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMOutputRejected(f"模型輸出不是合法的 JSON：{text[:200]}") from exc
    if not isinstance(parsed, dict):
        raise LLMOutputRejected(f"模型輸出不是 JSON 物件：{text[:200]}")
    return parsed


def _tool_calls(response: Response) -> list[ToolCall]:
    calls = []
    for item in response.output:
        if item.type != "function_call":
            continue
        try:
            arguments = json.loads(item.arguments)
        except json.JSONDecodeError as exc:
            raise LLMOutputRejected(f"工具參數不是合法的 JSON：{item.arguments[:200]}") from exc
        calls.append(ToolCall(call_id=item.call_id, name=item.name, arguments=arguments))
    return calls


def _json_schema_format(schema: JsonSchema) -> dict[str, Any]:
    return {"type": "json_schema", "name": schema.name, "schema": schema.schema, "strict": True}


def _tool_definition(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
        "strict": True,
    }


def _tool_output(result: ToolResult) -> dict[str, Any]:
    return {
        "type": "function_call_output",
        "call_id": result.call_id,
        "output": json.dumps(result.output, ensure_ascii=False),
    }
