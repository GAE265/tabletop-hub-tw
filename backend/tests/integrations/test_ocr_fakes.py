"""OCR 整合層的假實作與圖片格式判斷。不連網路。"""

import pytest

from app.integrations.llm.types import JsonSchema
from app.integrations.ocr import (
    FakeOCRProvider,
    FakeVisionProvider,
    LayoutLine,
    LayoutResult,
    OCRError,
    OCRUnavailable,
)
from app.integrations.ocr.images import image_mime

JPEG = b"\xff\xd8\xff\xe0 jpeg bytes"
PNG = b"\x89PNG\r\n\x1a\n png bytes"
SCHEMA = JsonSchema(name="reply", schema={"type": "object"})


def layout(text: str = "行") -> LayoutResult:
    return LayoutResult(
        width=100, height=200, unit="pixel", angle=0.0, lines=[LayoutLine(text, [0.0] * 8)]
    )


def test_image_mime_recognizes_jpeg_and_png() -> None:
    assert image_mime(JPEG) == "image/jpeg"
    assert image_mime(PNG) == "image/png"


@pytest.mark.parametrize("data", [b"GIF89a", b"", b"%PDF-1.7"])
def test_image_mime_rejects_other_formats(data: bytes) -> None:
    with pytest.raises(OCRError):
        image_mime(data)


def test_fake_vision_returns_replies_in_order() -> None:
    fake = FakeVisionProvider(replies=[{"n": 1}, {"n": 2}])

    first = fake.generate_json(instructions="a", input="b", images=[JPEG], schema=SCHEMA)
    second = fake.generate_json(instructions="a", input="b", images=[JPEG], schema=SCHEMA)

    assert (first, second) == ({"n": 1}, {"n": 2})


def test_fake_vision_raises_assertion_when_script_is_exhausted() -> None:
    fake = FakeVisionProvider(replies=[{"n": 1}])
    fake.generate_json(instructions="a", input="b", images=[], schema=SCHEMA)

    with pytest.raises(AssertionError, match="沒有預先放入的回覆"):
        fake.generate_json(instructions="a", input="b", images=[], schema=SCHEMA)


def test_fake_vision_raises_scripted_exception() -> None:
    fake = FakeVisionProvider(replies=[OCRUnavailable("逾時")])

    with pytest.raises(OCRUnavailable):
        fake.generate_json(instructions="a", input="b", images=[], schema=SCHEMA)


def test_fake_vision_records_calls_without_image_content() -> None:
    fake = FakeVisionProvider(replies=[{}])

    fake.generate_json(instructions="指令", input="輸入", images=[JPEG, PNG], schema=SCHEMA)

    call = fake.calls[0]
    assert (call.instructions, call.input, call.schema_name) == ("指令", "輸入", "reply")
    assert call.images == [("image/jpeg", len(JPEG)), ("image/png", len(PNG))]


def test_fake_vision_rejects_unknown_image_format() -> None:
    fake = FakeVisionProvider(replies=[{}])

    with pytest.raises(OCRError):
        fake.generate_json(instructions="a", input="b", images=[b"GIF89a"], schema=SCHEMA)


def test_fake_vision_without_script_is_unavailable() -> None:
    with pytest.raises(OCRUnavailable):
        FakeVisionProvider().generate_json(instructions="a", input="b", images=[], schema=SCHEMA)


def test_fake_ocr_returns_layouts_and_angles_in_order_and_records_calls() -> None:
    fake = FakeOCRProvider(layouts=[layout("甲"), layout("乙")], angles=[90.0, None])

    assert fake.analyze_layout(JPEG).lines[0].text == "甲"
    assert fake.analyze_layout(PNG).lines[0].text == "乙"
    assert fake.read_text_angle(JPEG) == 90.0
    assert fake.read_text_angle(JPEG) is None
    assert [(c.method, c.image_size) for c in fake.calls] == [
        ("analyze_layout", len(JPEG)),
        ("analyze_layout", len(PNG)),
        ("read_text_angle", len(JPEG)),
        ("read_text_angle", len(JPEG)),
    ]


def test_fake_ocr_raises_assertion_when_script_is_exhausted() -> None:
    fake = FakeOCRProvider(angles=[])

    with pytest.raises(AssertionError):
        fake.read_text_angle(JPEG)


def test_fake_ocr_without_script_is_unavailable() -> None:
    with pytest.raises(OCRUnavailable):
        FakeOCRProvider().analyze_layout(JPEG)
