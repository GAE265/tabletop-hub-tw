"""雲端實作測試用的 FakeAzureTransport 與假回應（整合層提案 §11.4、§11.5）。

照腳本回傳假的 Azure OpenAI HTTP 回應，不連網路。AGENTS.md 7.5 規定測試替身一律手寫 fake，
所以不用 httpx 的 MockTransport，自己實作 httpx.BaseTransport。
回應格式照 ticket 02 在 Azure 實測的結果。
"""

import base64
import json
import struct
from collections.abc import Callable
from typing import Any

import httpx

ScriptItem = httpx.Response | Exception | Callable[[httpx.Request], httpx.Response]

# SDK 看到這個標頭會等 1 毫秒再重試，測試不用真的等退避時間
FAST_RETRY = {"retry-after-ms": "1"}


class FakeAzureTransport(httpx.BaseTransport):
    """依序回傳腳本的項目，並記下每個收到的請求。

    腳本項目可以是 httpx.Response、要拋出的例外，或「收到請求後產生回應」的函式。
    """

    def __init__(self, script: list[ScriptItem]) -> None:
        self._script = list(script)
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self._script:
            raise AssertionError("FakeAzureTransport 的腳本用完了，測試本身寫錯")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        return item(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=self)

    def json_body(self, index: int = -1) -> dict[str, Any]:
        return json.loads(self.requests[index].content)


# --- Responses API ---


def message_item(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def refusal_item(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "refusal", "refusal": text}],
    }


def function_call_item(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": "fc_1",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments, ensure_ascii=False),
        "status": "completed",
    }


def reasoning_item() -> dict[str, Any]:
    """推理模型會在輸出前面多一個 reasoning 項目（ticket 02 第 5 點）。"""
    return {"type": "reasoning", "id": "rs_1", "summary": []}


def response_ok(
    output: list[dict[str, Any]],
    *,
    response_id: str = "resp_1",
    status: str = "completed",
    incomplete_reason: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": response_id,
            "object": "response",
            "created_at": 1_700_000_000,
            "model": "test-deployment",
            "status": status,
            "incomplete_details": {"reason": incomplete_reason} if incomplete_reason else None,
            "output": output,
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        },
    )


def error_response(
    status: int,
    *,
    code: str | None,
    param: str | None = None,
    message: str = "error",
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> httpx.Response:
    error: dict[str, Any] = {
        "message": message,
        "type": "invalid_request_error",
        "param": param,
        "code": code,
    }
    error.update(extra or {})
    return httpx.Response(status, headers=headers, json={"error": error})


def content_filter_error() -> httpx.Response:
    """擋下輸入：HTTP 400、code 是 content_filter（ticket 02 第 5 點）。"""
    return error_response(
        400,
        code="content_filter",
        param="prompt",
        message="The response was filtered due to the prompt triggering content management policy.",
        extra={
            "content_filters": [{"blocked": True, "source_type": "prompt"}],
            "innererror": {"code": "ContentFiltered"},
        },
    )


def transient_failures(kind: str) -> list[ScriptItem]:
    """SDK 重試 2 次，所以同一種暫時性錯誤要準備 3 個。"""
    if kind == "timeout":
        return [httpx.ReadTimeout("timed out") for _ in range(3)]
    status = {"429": 429, "500": 500, "503": 503}[kind]
    return [
        error_response(status, code=None, message=f"status {status}", headers=FAST_RETRY)
        for _ in range(3)
    ]


# --- Embeddings API ---


def embeddings_response(
    vector_for: Callable[[int, str], list[float]],
    *,
    reverse_order: bool = False,
) -> Callable[[httpx.Request], httpx.Response]:
    """依請求的 input 產生向量。

    SDK 預設要求 base64（encoding_format），所以照請求的格式回傳。reverse_order=True 時
    data 反過來排，用來確認實作是依 index 排序，而不是依回應的順序。
    """

    def _respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        as_base64 = body.get("encoding_format") == "base64"
        data = []
        for index, text in enumerate(body["input"]):
            vector = vector_for(index, text)
            embedding: list[float] | str = vector
            if as_base64:
                packed = struct.pack(f"<{len(vector)}f", *vector)
                embedding = base64.b64encode(packed).decode()
            data.append({"object": "embedding", "index": index, "embedding": embedding})
        if reverse_order:
            data.reverse()
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": body["model"],
                "usage": {"prompt_tokens": len(data), "total_tokens": len(data)},
            },
        )

    return _respond
