"""OCRProvider 的雲端實作：Azure AI Document Intelligence。

azure SDK 只在這個檔案裡 import（AGENTS.md §4.2）。prebuilt-layout 取逐行文字與位置，
prebuilt-read 只取文字角度（比 layout 便宜，轉正用）。
"""

import io
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult, DocumentPage
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import (
    HttpResponseError,
    ServiceRequestError,
    ServiceResponseError,
)

from app.integrations.ocr.base import OCRProvider
from app.integrations.ocr.errors import OCRError, OCRUnavailable
from app.integrations.ocr.types import LayoutLine, LayoutResult


class AzureDocumentIntelligenceProvider(OCRProvider):
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        polling_interval: float = 1.0,
        **client_kwargs: Any,
    ) -> None:
        """client_kwargs 直接交給 SDK 的 client，測試用來換 transport 與重試設定。"""
        client_kwargs.setdefault("connection_timeout", 10)
        client_kwargs.setdefault("read_timeout", 60)
        self._client = DocumentIntelligenceClient(
            endpoint=endpoint, credential=AzureKeyCredential(api_key), **client_kwargs
        )
        self._polling_interval = polling_interval

    def analyze_layout(self, image: bytes) -> LayoutResult:
        page = self._first_page(self._analyze("prebuilt-layout", image))
        if page is None:
            raise OCRError("版面分析沒有回傳任何頁面")
        return LayoutResult(
            width=float(page.width or 0),
            height=float(page.height or 0),
            # SDK 的 unit 是 enum（LengthUnit.PIXEL），轉成它的值 "pixel"
            unit=str(getattr(page.unit, "value", page.unit) or ""),
            angle=float(page.angle or 0.0),
            lines=[
                LayoutLine(text=line.content, polygon=[float(v) for v in line.polygon or []])
                for line in page.lines or []
            ],
        )

    def read_text_angle(self, image: bytes) -> float | None:
        page = self._first_page(self._analyze("prebuilt-read", image))
        if page is None or not (page.lines or page.words):
            return None
        return float(page.angle or 0.0)

    def _analyze(self, model_id: str, image: bytes) -> AnalyzeResult:
        try:
            poller = self._client.begin_analyze_document(
                model_id,
                body=io.BytesIO(image),
                content_type="application/octet-stream",
                polling_interval=self._polling_interval,
            )
            return poller.result()
        except (ServiceRequestError, ServiceResponseError) as exc:  # 連線失敗、逾時
            raise OCRUnavailable(f"連不上 Azure Document Intelligence：{exc}") from exc
        except HttpResponseError as exc:
            raise _convert_status_error(exc) from exc

    @staticmethod
    def _first_page(result: AnalyzeResult) -> DocumentPage | None:
        pages = list(result.pages or [])
        return pages[0] if pages else None


def _convert_status_error(exc: HttpResponseError) -> OCRError:
    status = exc.status_code
    if status == 429 or (status is not None and status >= 500):
        return OCRUnavailable(f"Azure Document Intelligence 暫時無法使用（HTTP {status}）：{exc}")
    return OCRError(f"Azure Document Intelligence 回傳錯誤（HTTP {status}）：{exc.message}")
