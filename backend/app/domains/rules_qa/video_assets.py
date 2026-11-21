"""素材照片、方向、區域與「缺什麼」（add-rules-video-mobile design.md D13 與實作決定）。

段資料（`rules_qa_video_projects.video`）是正本；照片檔放在存放介面，key 是
`rules_videos/<專案>/assets/<file>`，段資料的 `assets[].file` 只記檔名（展開資料夾時放進 assets/）。
"""

import copy
import io
import uuid
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.integrations.video.templates import DEFAULT_TEMPLATE, TEMPLATES

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


def is_skipped(asset: dict[str, Any]) -> bool:
    """店員略過的選拍素材（記在 usable=false；段資料原本就有的預留欄位）。"""
    return asset.get("usable") is False


def skip_blocked_message(segments: list[int]) -> str:
    return f"第 {'、'.join(str(n) for n in segments)} 段只靠這張，不能略過"


@dataclass(frozen=True)
class StripResult:
    """拿掉略過的素材之後的段資料。affected／blocked 是段號（從 1 開始）。"""

    video: dict[str, Any]
    # 少了東西的段（略過後第 N 段會少一張圖）
    affected: list[int]
    # 必填槽位空了的段（第 N 段只靠這些素材，不能略過）
    blocked: list[int]


def strip_skipped(video: dict[str, Any], skipped: set[str]) -> StripResult:
    """把略過的素材，以及用到它的槽位、卡牌項目、highlight、label、cue 從段資料拿掉。

    卡牌項目的正面或牌背是略過的素材，整個項目都拿掉；項目全拿掉的 items 槽位也拿掉。
    之後指向被拿掉的槽位、項目或區域的 highlight、label、cue（含 move 的目的地）都拿掉。
    不改傳入的段資料。
    """
    result = copy.deepcopy(video)
    result["assets"] = [a for a in result.get("assets", []) if a.get("asset_key") not in skipped]
    affected: list[int] = []
    blocked: list[int] = []
    for number, segment in enumerate(result.get("segments", []), start=1):
        slots = segment.get("slots") or {}
        removed_slots: set[str] = set()
        removed_items: set[tuple[str, str]] = set()
        for name, slot in list(slots.items()):
            kind = slot.get("kind")
            if kind == "asset" and slot.get("asset_key") in skipped:
                del slots[name]
                removed_slots.add(name)
            elif kind == "items":
                kept = []
                for item in slot.get("items") or []:
                    if item.get("asset_key") in skipped or item.get("back_asset_key") in skipped:
                        removed_items.add((name, item.get("item_key", "")))
                    else:
                        kept.append(item)
                if not kept:
                    del slots[name]
                    removed_slots.add(name)
                else:
                    slot["items"] = kept
        if not removed_slots and not removed_items:
            continue
        affected.append(number)
        spec = TEMPLATES.get(segment.get("template", DEFAULT_TEMPLATE))
        if spec is not None and any(
            name in removed_slots for name, slot_spec in spec.slots.items() if slot_spec.required
        ):
            blocked.append(number)
        removed = _Removed(removed_slots, removed_items, set())
        for field in ("highlights", "labels"):
            if field not in segment:
                continue
            kept_overlays = []
            for overlay in segment[field]:
                if removed.covers(overlay.get("target")):
                    removed.overlays.add(overlay.get("key", ""))
                else:
                    kept_overlays.append(overlay)
            segment[field] = kept_overlays
        for beat in segment.get("beats", []):
            if "cues" in beat:
                beat["cues"] = [
                    cue
                    for cue in beat["cues"]
                    if not removed.covers(cue.get("target")) and not removed.covers(cue.get("to"))
                ]
    return StripResult(result, affected, blocked)


@dataclass(frozen=True)
class _Removed:
    """一段裡被拿掉的東西：槽位、卡牌項目（槽位, item_key）、highlight／label 的 key。"""

    slots: set[str]
    items: set[tuple[str, str]]
    overlays: set[str]

    def covers(self, target: str | None) -> bool:
        """target（`main`、`main.c2`、`sidebar@zone`、highlight／label 的 key）指向被拿掉的東西。"""
        if not target:
            return False
        if "@" in target:
            return target.partition("@")[0] in self.slots
        if "." in target:
            slot_name, _, item_key = target.partition(".")
            return slot_name in self.slots or (slot_name, item_key) in self.items
        return target in self.slots or target in self.overlays


def skip_impact(video: dict[str, Any], asset_key: str) -> tuple[list[int], list[int]]:
    """略過這個素材（加上已經略過的）會影響哪些段：（會少一張圖的段, 只靠它而不能略過的段）。"""
    affected = strip_skipped(video, {asset_key}).affected
    # 和已經略過的素材一起看：兩張都略過才讓某段空掉，也算不能略過
    skipped = {a["asset_key"] for a in video.get("assets", []) if is_skipped(a)} - {asset_key}
    before = strip_skipped(video, skipped).blocked
    blocked = [n for n in strip_skipped(video, skipped | {asset_key}).blocked if n not in before]
    return affected, blocked


def readiness(video: dict[str, Any]) -> dict[str, Any]:
    """產生影片前還缺什麼：沒有照片的素材、沒有座標的區域、本版不支援的繪製素材。

    略過的選拍素材不列。選拍沒有照片也會擋住（第 1 階段的段資料要求每個照片素材都有檔案），
    但選拍附上略過的影響，讓店員可以選擇略過（MR 9）。
    """
    missing_photos = []
    missing_regions = []
    unsupported = []
    for asset in video.get("assets", []):
        key = asset["asset_key"]
        if is_skipped(asset):
            continue
        if asset.get("kind") == "drawn":
            unsupported.append(
                {"asset_key": key, "kind": "drawn", "message": DRAWN_UNSUPPORTED_MESSAGE}
            )
            continue
        if not asset.get("file"):
            priority = asset.get("priority", "must")
            affected, blocked = skip_impact(video, key) if priority == "optional" else ([], [])
            missing_photos.append(
                {
                    "asset_key": key,
                    "priority": priority,
                    "reason": asset.get("reason", ""),
                    "shot": asset.get("shot"),
                    "skip_affected_segments": affected,
                    "skip_blocked_segments": blocked,
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
