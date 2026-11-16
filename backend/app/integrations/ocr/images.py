"""圖片檔頭判斷。integration 不處理影像，只認得能送給模型的 JPEG 與 PNG。"""

from app.integrations.ocr.errors import OCRError

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"


def image_mime(data: bytes) -> str:
    """回傳 image/jpeg 或 image/png；不認得就拋 OCRError，不猜。"""
    if data.startswith(_JPEG):
        return "image/jpeg"
    if data.startswith(_PNG):
        return "image/png"
    raise OCRError("圖片格式不認得：只支援 JPEG 與 PNG")
