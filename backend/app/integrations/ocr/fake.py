from collections import deque
from dataclasses import dataclass
from typing import Any

from app.integrations.llm.types import JsonSchema
from app.integrations.ocr.base import OCRProvider, VisionProvider
from app.integrations.ocr.errors import OCRUnavailable
from app.integrations.ocr.images import image_mime
from app.integrations.ocr.types import LayoutResult


@dataclass(frozen=True)
class FakeOCRCall:
    """fake 收到的一次呼叫。只記圖片大小，不保存圖片內容。"""

    method: str
    image_size: int


@dataclass(frozen=True)
class FakeVisionCall:
    instructions: str
    input: str
    schema_name: str
    # 每張圖的（MIME，大小）
    images: list[tuple[str, int]]


def _next(script: "deque[Any] | None", what: str) -> Any:
    if script is None:
        # LLM_PROVIDER=fake 一樣的做法：沒給腳本就讓後端回 503，不編造結果
        raise OCRUnavailable(f"fake 實作沒有設定{what}，請改用 OCR_PROVIDER=cloud")
    if not script:
        raise AssertionError(f"沒有預先放入的{what}，測試本身寫錯")
    item = script.popleft()
    if isinstance(item, Exception):
        raise item
    return item


class FakeOCRProvider(OCRProvider):
    """測試用：依序回傳放入的 layouts、angles；項目是例外就拋出它。不發出任何網路請求。"""

    def __init__(
        self,
        layouts: list[LayoutResult | Exception] | None = None,
        angles: list[float | None | Exception] | None = None,
    ) -> None:
        self.calls: list[FakeOCRCall] = []
        self._layouts = None if layouts is None else deque(layouts)
        self._angles = None if angles is None else deque(angles)

    def analyze_layout(self, image: bytes) -> LayoutResult:
        self.calls.append(FakeOCRCall("analyze_layout", len(image)))
        return _next(self._layouts, "版面分析結果")

    def read_text_angle(self, image: bytes) -> float | None:
        self.calls.append(FakeOCRCall("read_text_angle", len(image)))
        return _next(self._angles, "文字角度")


class FakeVisionProvider(VisionProvider):
    """測試用：依序回傳放入的 replies；項目是例外就拋出它。不發出任何網路請求。"""

    def __init__(self, replies: list[dict[str, Any] | Exception] | None = None) -> None:
        self.calls: list[FakeVisionCall] = []
        self._replies = None if replies is None else deque(replies)

    def generate_json(
        self, *, instructions: str, input: str, images: list[bytes], schema: JsonSchema
    ) -> dict:
        described = [(image_mime(image), len(image)) for image in images]
        self.calls.append(FakeVisionCall(instructions, input, schema.name, described))
        return _next(self._replies, "回覆")
