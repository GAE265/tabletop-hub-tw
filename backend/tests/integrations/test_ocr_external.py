"""OCR 整合層的外部服務測試：直連真的 Azure Document Intelligence 與 Azure OpenAI（AGENTS.md 7.6）。

預設不執行，CI 也不跑。本機執行：在 backend/ 跑 `uv run pytest -m external`。
圖片全部用 Pillow 現場畫的英文字，不使用任何規則書內容。每次跑會呼叫 Document Intelligence
約 6 次、視覺模型 3 次。
"""

import io
import re

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings
from app.integrations.llm.types import JsonSchema
from app.integrations.ocr import (
    OCRError,
    OCRUnavailable,
    get_ocr_provider,
    get_vision_provider,
)
from app.integrations.ocr.azure_di import AzureDocumentIntelligenceProvider
from app.integrations.ocr.vision import CloudVisionProvider

pytestmark = pytest.mark.external


def draw_png(lines: list[str], *, rotate: int = 0, size: tuple[int, int] = (1400, 700)) -> bytes:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=72)
    for index, line in enumerate(lines):
        draw.text((60, 60 + index * 140), line, fill="black", font=font)
    if rotate:
        image = image.rotate(rotate, expand=True)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def blank_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# --- Azure Document Intelligence ---


def test_analyze_layout_returns_lines_with_polygon(ocr_external_settings: Settings) -> None:
    provider = get_ocr_provider("cloud", ocr_external_settings)

    result = provider.analyze_layout(draw_png(["HELLO RULEBOOK", "SECOND LINE 2026"]))

    assert result.unit == "pixel"
    assert (result.width, result.height) == (1400, 700)
    assert abs(result.angle) < 5
    joined = normalize(" ".join(line.text for line in result.lines))
    assert "hellorulebook" in joined
    assert "secondline2026" in joined
    assert all(len(line.polygon) == 8 for line in result.lines)


def test_read_text_angle_of_upright_page(ocr_external_settings: Settings) -> None:
    provider = get_ocr_provider("cloud", ocr_external_settings)

    angle = provider.read_text_angle(draw_png(["UPRIGHT PAGE TEXT"]))

    assert angle is not None
    assert abs(angle) < 5


@pytest.mark.parametrize("rotate", [90, -90])
def test_read_text_angle_of_sideways_page(ocr_external_settings: Settings, rotate: int) -> None:
    provider = get_ocr_provider("cloud", ocr_external_settings)

    angle = provider.read_text_angle(draw_png(["SIDEWAYS PAGE TEXT"], rotate=rotate))

    assert angle is not None
    assert 80 < abs(angle) < 100


def test_read_text_angle_is_none_without_text(ocr_external_settings: Settings) -> None:
    provider = get_ocr_provider("cloud", ocr_external_settings)

    assert provider.read_text_angle(blank_png()) is None


def test_wrong_di_key_is_ocr_error_not_unavailable(ocr_external_settings: Settings) -> None:
    provider = AzureDocumentIntelligenceProvider(
        endpoint=ocr_external_settings.ocr_di_endpoint,  # type: ignore[arg-type]
        api_key="wrong-key-for-test",
        retry_total=0,
    )

    with pytest.raises(OCRError) as info:
        provider.read_text_angle(draw_png(["X"]))

    assert not isinstance(info.value, OCRUnavailable)
    assert "wrong-key-for-test" not in str(info.value)


def test_unreachable_di_endpoint_is_unavailable() -> None:
    provider = AzureDocumentIntelligenceProvider(
        endpoint="https://no-such-resource-for-test.invalid/",
        api_key="any",
        retry_total=0,
        connection_timeout=3,
    )

    with pytest.raises(OCRUnavailable):
        provider.read_text_angle(draw_png(["X"]))


# --- Azure OpenAI 視覺模型 ---

TEXT_SCHEMA = JsonSchema(
    name="read_text",
    schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)
TEXTS_SCHEMA = JsonSchema(
    name="read_texts",
    schema={
        "type": "object",
        "properties": {"texts": {"type": "array", "items": {"type": "string"}}},
        "required": ["texts"],
        "additionalProperties": False,
    },
)


def test_vision_reads_text_from_one_image(ocr_external_settings: Settings) -> None:
    provider = get_vision_provider("cloud", ocr_external_settings)

    reply = provider.generate_json(
        instructions="你是逐字轉錄器。只輸出圖片上的文字，不要加任何說明。",
        input="請轉錄這張圖。",
        images=[draw_png(["PURPLE GIRAFFE"])],
        schema=TEXT_SCHEMA,
    )

    assert "purplegiraffe" in normalize(reply["text"])


def test_vision_keeps_image_order(ocr_external_settings: Settings) -> None:
    provider = get_vision_provider("cloud", ocr_external_settings)

    reply = provider.generate_json(
        instructions="你是逐字轉錄器。依圖片順序，各輸出一個字串，只含圖上的文字。",
        input="共有兩張圖，請依序轉錄。",
        images=[draw_png(["ALPHA ONE"]), draw_png(["BRAVO TWO"])],
        schema=TEXTS_SCHEMA,
    )

    assert [normalize(text) for text in reply["texts"]] == ["alphaone", "bravotwo"]


def test_vision_rejects_unknown_image_format_before_any_request() -> None:
    # endpoint 指向不存在的主機：若真的發出請求，會得到 OCRUnavailable 而不是 OCRError
    provider = CloudVisionProvider(
        endpoint="https://no-such-resource-for-test.invalid/openai/v1/",
        api_key="any",
        model="any",
        timeout_seconds=3,
    )

    with pytest.raises(OCRError) as info:
        provider.generate_json(
            instructions="x", input="x", images=[b"GIF89a not supported"], schema=TEXT_SCHEMA
        )

    assert not isinstance(info.value, OCRUnavailable)


def test_wrong_vision_key_is_ocr_error_not_unavailable(ocr_external_settings: Settings) -> None:
    provider = CloudVisionProvider(
        endpoint=ocr_external_settings.ocr_vision_endpoint or ocr_external_settings.llm_endpoint,  # type: ignore[arg-type]
        api_key="wrong-key-for-test",
        model=ocr_external_settings.llm_model,  # type: ignore[arg-type]
        timeout_seconds=30,
    )

    with pytest.raises(OCRError) as info:
        provider.generate_json(
            instructions="x", input="x", images=[draw_png(["X"])], schema=TEXT_SCHEMA
        )

    assert not isinstance(info.value, OCRUnavailable)
    assert "wrong-key-for-test" not in str(info.value)


def test_unreachable_vision_endpoint_is_unavailable() -> None:
    provider = CloudVisionProvider(
        endpoint="https://no-such-resource-for-test.invalid/openai/v1/",
        api_key="any",
        model="any",
        timeout_seconds=3,
    )

    with pytest.raises(OCRUnavailable):
        provider.generate_json(
            instructions="x", input="x", images=[draw_png(["X"])], schema=TEXT_SCHEMA
        )
