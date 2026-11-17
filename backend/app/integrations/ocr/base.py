from abc import ABC, abstractmethod

from app.integrations.llm.types import JsonSchema
from app.integrations.ocr.types import LayoutResult


class OCRProvider(ABC):
    """版面分析：取得逐行文字、位置與文字角度。domain 不得直接 import 廠商 SDK。"""

    @abstractmethod
    def analyze_layout(self, image: bytes) -> LayoutResult:
        """第一頁的逐行文字與 polygon、頁面尺寸與單位、文字角度。"""

    @abstractmethod
    def read_text_angle(self, image: bytes) -> float | None:
        """第一頁的文字角度（度）；整頁沒有任何文字時回傳 None。"""


class VisionProvider(ABC):
    """帶圖片的模型呼叫。prompt 與 schema 由呼叫端提供，這裡不內建任何 domain 的內容。"""

    @abstractmethod
    def generate_json(
        self, *, instructions: str, input: str, images: list[bytes], schema: JsonSchema
    ) -> dict:
        """無狀態；輸出符合 schema 的 JSON。images 照傳入順序送給模型。"""
