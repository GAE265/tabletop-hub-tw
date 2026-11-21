"""素材照片、方向、區域與「缺什麼」（add-rules-video-mobile design.md D13 與實作決定）。

段資料（`rules_qa_video_projects.video`）是正本；照片檔放在存放介面，key 是
`rules_videos/<專案>/assets/<file>`，段資料的 `assets[].file` 只記檔名（展開資料夾時放進 assets/）。
"""

import io
import uuid
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

# 每張照片的上限（2026-11-21 永傑決定）；寫在這裡不加設定
MAX_PHOTO_BYTES = 15 * 1024 * 1024

# Pillow 的格式名稱 → 副檔名、Content-Type。只收 JPEG、PNG（HEIC 這一版不收）
PHOTO_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png")}

PHOTO_INVALID_MESSAGE = "只能上傳 JPEG 或 PNG 照片"
PHOTO_TOO_LARGE_MESSAGE = "照片太大，每張最多 15 MB"
DRAWN_UNSUPPORTED_MESSAGE = "本版不支援繪製素材，請改成拍照"

_EXIF_ORIENTATION = 0x0112


class PhotoRejected(ValueError):
    """照片不能用；code 是 API 的錯誤代碼，訊息給店員看。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_photo(data: bytes) -> tuple[bytes, str, str]:
    """檢查格式與大小，依 EXIF 方向轉正；回傳（檔案內容、副檔名、Content-Type）。

    沒有 EXIF 方向（或已經是正的）時原樣保存，不重新壓縮；有的話轉正後重新存，並去掉方向標記，
    之後的區域座標都以轉正後的圖為準。
    """
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoRejected("RULES_VIDEO_PHOTO_TOO_LARGE", PHOTO_TOO_LARGE_MESSAGE)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise PhotoRejected("RULES_VIDEO_PHOTO_INVALID", PHOTO_INVALID_MESSAGE) from exc
    if image.format not in PHOTO_FORMATS:
        raise PhotoRejected("RULES_VIDEO_PHOTO_INVALID", PHOTO_INVALID_MESSAGE)
    ext, content_type = PHOTO_FORMATS[image.format]
    if image.getexif().get(_EXIF_ORIENTATION, 1) in (1, None):
        return data, ext, content_type
    upright = ImageOps.exif_transpose(image)
    exif = upright.getexif()
    exif.pop(_EXIF_ORIENTATION, None)
    out = io.BytesIO()
    if image.format == "JPEG":
        upright.save(out, "JPEG", quality=92, exif=exif)
    else:
        upright.save(out, "PNG")
    return out.getvalue(), ext, content_type


def photo_key(project_id: uuid.UUID, file: str) -> str:
    """存放介面的 key。"""
    return f"rules_videos/{project_id}/assets/{file}"


def new_photo_file(asset_key: str, ext: str) -> str:
    """每次上傳都用新檔名（避免快取到舊照片）；舊檔在寫入段資料後刪除。"""
    return f"{asset_key}-{uuid.uuid4().hex[:8]}.{ext}"


def find_asset(video: dict[str, Any], asset_key: str) -> dict[str, Any] | None:
    for asset in video.get("assets", []):
        if asset.get("asset_key") == asset_key:
            return asset
    return None


def carry_over_assets(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    """重新產生草稿時，把舊段資料同一個 asset_key 的照片、方向、區域座標帶到新草稿。

    只帶新草稿也有的區域名稱；新草稿沒有的素材不處理（照片留在存放介面，之後可能又用到）。
    回傳沿用到照片的 asset_key。
    """
    kept = []
    for asset in new.get("assets", []):
        source = find_asset(old or {}, asset["asset_key"])
        if source is None or not source.get("file"):
            continue
        asset["file"] = source["file"]
        asset["orientation"] = source.get("orientation", 0)
        regions = asset.get("regions") or {}
        old_regions = source.get("regions") or {}
        for name in regions:
            if old_regions.get(name) is not None:
                regions[name] = old_regions[name]
        kept.append(asset["asset_key"])
    return kept


def readiness(video: dict[str, Any]) -> dict[str, Any]:
    """產生影片前還缺什麼：沒有照片的素材（含選拍）、沒有座標的區域、本版不支援的繪製素材。

    第 1 階段的段資料規定每個照片素材都要有檔案才能輸出，所以選拍沒有照片也會擋住（已知限制）。
    """
    missing_photos = []
    missing_regions = []
    unsupported = []
    for asset in video.get("assets", []):
        key = asset["asset_key"]
        if asset.get("kind") == "drawn":
            unsupported.append(
                {"asset_key": key, "kind": "drawn", "message": DRAWN_UNSUPPORTED_MESSAGE}
            )
            continue
        if not asset.get("file"):
            missing_photos.append(
                {
                    "asset_key": key,
                    "priority": asset.get("priority", "must"),
                    "reason": asset.get("reason", ""),
                    "shot": asset.get("shot"),
                }
            )
        for name, box in (asset.get("regions") or {}).items():
            if box is None:
                missing_regions.append({"asset_key": key, "region": name})
    return {
        "ready": not (missing_photos or missing_regions or unsupported),
        "missing_photos": missing_photos,
        "missing_regions": missing_regions,
        "unsupported": unsupported,
    }
