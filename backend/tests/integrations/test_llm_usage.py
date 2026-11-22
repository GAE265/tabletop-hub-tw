"""每次 LLM／看圖呼叫的實際 token 用量記錄（2026-11-23 永傑要求）。

雲端實作用 FakeAzureTransport（假的 Azure 回應，不連網路）。
"""

import base64
import threading

from app.integrations.llm.cloud import CloudLLMProvider
from app.integrations.llm.types import JsonSchema
from app.integrations.llm.usage import (
    UsageRecord,
    collect_usage,
    in_current_context,
    record_usage,
)
from app.integrations.ocr.vision import CloudVisionProvider
from tests.integrations.fake_azure import FakeAzureTransport, message_item, response_ok

ENDPOINT = "https://example.openai.azure.com/openai/v1/"
SCHEMA = JsonSchema(
    name="reply",
    schema={
        "type": "object",
        "properties": {"reply": {"type": "string"}},
        "required": ["reply"],
        "additionalProperties": False,
    },
)
# 1×1 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
)


def record(name: str, input_tokens: int, output_tokens: int) -> UsageRecord:
    return UsageRecord(
        kind="llm",
        name=name,
        model="m",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=0,
        seconds=1.0,
    )


def test_collect_and_summarize():
    with collect_usage() as usage:
        record_usage(record("a", 10, 5))
        record_usage(record("a", 20, 5))
        record_usage(record("b", 1, 1))
    summary = usage.summary()
    assert summary["calls"] == 3
    assert summary["input_tokens"] == 31 and summary["output_tokens"] == 11
    assert summary["by_name"]["a"] == {"calls": 2, "input_tokens": 30, "output_tokens": 10}
    assert len(summary["records"]) == 3


def test_record_outside_collect_is_ignored():
    record_usage(record("a", 1, 1))  # 不會出錯


def test_threads_record_into_the_same_log():
    with collect_usage() as usage:
        run = in_current_context(lambda: record_usage(record("t", 1, 1)))
        threads = [threading.Thread(target=run) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert usage.summary()["calls"] == 3


def test_cloud_llm_records_usage():
    transport = FakeAzureTransport(
        [response_ok([message_item('{"reply": "ok"}')], input_tokens=120, output_tokens=40)]
    )
    llm = CloudLLMProvider(
        endpoint=ENDPOINT, api_key="k", model="dep", http_client=transport.client()
    )
    with collect_usage() as usage:
        llm.generate_json(instructions="i", input="x", schema=SCHEMA)
    [entry] = usage.summary()["records"]
    assert entry["kind"] == "llm" and entry["name"] == "reply" and entry["model"] == "dep"
    assert entry["input_tokens"] == 120 and entry["output_tokens"] == 40


def test_cloud_vision_records_usage():
    transport = FakeAzureTransport(
        [response_ok([message_item('{"reply": "ok"}')], input_tokens=1415, output_tokens=900)]
    )
    vision = CloudVisionProvider(
        endpoint=ENDPOINT, api_key="k", model="vis", http_client=transport.client()
    )
    with collect_usage() as usage:
        vision.generate_json(instructions="i", input="x", images=[PNG], schema=SCHEMA)
    [entry] = usage.summary()["records"]
    assert entry["kind"] == "vision" and entry["name"] == "reply"
    assert entry["input_tokens"] == 1415 and entry["output_tokens"] == 900
