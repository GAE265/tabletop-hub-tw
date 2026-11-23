"""VisionProvider 的雲端實作：Azure OpenAI Responses API，帶圖片的結構化輸出。

openai SDK 只在這個檔案與 llm/cloud.py 裡 import（AGENTS.md §4.2）。
"""

import base64
import json
import time
from typing import Any

import httpx
import openai
from openai.types.responses import Response

from app.integrations.llm.types import JsonSchema
from app.integrations.llm.usage import UsageRecord, record_usage, usage_of
from app.integrations.ocr.base import VisionProvider
from app.integrations.ocr.errors import OCRError, OCROutputRejected, OCRUnavailable
from app.integrations.ocr.images import image_mime


class CloudVisionProvider(VisionProvider):
    """一個 provider 只綁一個部署（model）。重試沿用 SDK 預設的 2 次。"""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 120,
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

    def generate_json(
        self, *, instructions: str, input: str, images: list[bytes], schema: JsonSchema
    ) -> dict:
        # 先驗證所有圖片，再發請求：格式不認得時不應該產生任何網路流量
        content: list[dict[str, Any]] = [{"type": "input_text", "text": input}]
        for image in images:
            data_url = f"data:{image_mime(image)};base64,{base64.b64encode(image).decode()}"
            # detail=high：規則書是小字，低解析度模式會讀錯字
            content.append({"type": "input_image", "image_url": data_url, "detail": "high"})
        started = time.monotonic()
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=instructions,
                input=[{"role": "user", "content": content}],
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema.name,
                        "schema": schema.schema,
                        "strict": True,
                    }
                },
            )
        except openai.APIConnectionError as exc:  # 包含逾時（APITimeoutError）
            raise OCRUnavailable(f"連不上 Azure OpenAI：{exc}") from exc
        except openai.APIStatusError as exc:
            raise _convert_status_error(exc) from exc
        except openai.OpenAIError as exc:
            raise OCRError(f"Azure OpenAI 呼叫失敗：{exc}") from exc
        _check_finished(response)
        input_tokens, output_tokens, reasoning_tokens = usage_of(response)
        record_usage(
            UsageRecord(
                kind="vision",
                name=schema.name,
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
                seconds=round(time.monotonic() - started, 1),
            )
        )
        return _parse_json_output(response)


def _convert_status_error(exc: openai.APIStatusError) -> OCRError:
    if exc.status_code == 429 or exc.status_code >= 500:
        return OCRUnavailable(f"Azure OpenAI 暫時無法使用（HTTP {exc.status_code}）：{exc}")
    if exc.code == "content_filter":
        return OCROutputRejected(f"輸入被內容過濾擋下：{exc}")
    return OCRError(f"Azure OpenAI 回傳錯誤（HTTP {exc.status_code}）：{exc}")


def _check_finished(response: Response) -> None:
    """輸出被內容過濾擋下時 Azure 回 200，所以要先檢查 status，再解析輸出。"""
    if response.status == "incomplete":
        details = response.incomplete_details
        reason = details.reason if details else None
        raise OCROutputRejected(f"模型輸出不完整：{reason}")
    if response.status not in (None, "completed"):
        raise OCRError(f"模型回應的狀態是 {response.status}")
    for item in response.output:
        if item.type != "message":
            continue
        for content in item.content:
            if content.type == "refusal":
                raise OCROutputRejected(f"模型拒答：{content.refusal}")


def _parse_json_output(response: Response) -> dict[str, Any]:
    text = response.output_text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OCROutputRejected(f"模型輸出不是合法的 JSON：{text[:200]}") from exc
    if not isinstance(parsed, dict):
        raise OCROutputRejected(f"模型輸出不是 JSON 物件：{text[:200]}")
    return parsed
