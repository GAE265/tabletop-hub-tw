"""換某一段的素材、新增素材（2026-11-25 永傑決定；最小版之後補上完整版）。純函式，不碰資料庫。

- 單一素材的格子（`kind == "asset"`）直接換；放好幾張牌的格子（`items`）指定哪一張（`item_key`）
  與正面或牌背（`face`）。文字、條列的格子不能換。
- 只能換成素材清單裡、可以用的素材：不是繪製素材、沒有被略過。
- 框線、標籤、動作全部保留。單一素材的格子換掉時，這一段指到的區域（`<格子>@<區域>`）沿用到
  新素材：新素材沒有同名區域就加上名稱與白話說明、座標留空，請店員在新照片上重標；有同名區域
  就直接用。回報要重標的區域，以及換完後沒有段在用的素材（「還缺什麼」不再要求它）。
  （最小版是把指向舊區域的東西一律移除；2026-11-25 永傑改成沿用並重標。）
- 新增素材：店員輸入中文名稱與拍攝說明，建立一個照片素材，代號由程式產生。
- 修改紀錄的格式和一句話修改（video_revision）一樣，之後的修改頁可以排在同一份紀錄裡。
"""

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domains.rules_qa.video_assets import (
    _region_refs,
    asset_label,
    is_skipped,
    used_asset_keys,
)

UNSUPPORTED_MESSAGE = "這一段目前不支援換素材"
FACES = ("front", "back")


@dataclass(frozen=True)
class ItemInfo:
    """放牌的格子裡的一張牌。"""

    item_key: str
    asset_key: str
    back_asset_key: str | None


@dataclass(frozen=True)
class SlotInfo:
    """一段裡放素材的格子。asset_keys 依出現順序、不重複（牌的正面與牌背都算）。"""

    slot: str
    kind: str  # asset | items
    asset_keys: list[str]
    swappable: bool
    items: list[ItemInfo] = field(default_factory=list)


class SwapRejected(Exception):
    """不能換：status 是 HTTP 狀態碼，code 是錯誤代碼，message 給店員看。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class AssetRejected(SwapRejected):
    """不能新增這個素材。"""


@dataclass
class SwapResult:
    video: dict[str, Any]
    old_asset_key: str
    new_asset_key: str
    item_key: str | None = None
    face: str = "front"
    # 新素材上要重標的區域（沿用自舊素材、還沒有座標）
    regions_to_mark: list[str] = field(default_factory=list)
    unused_assets: list[str] = field(default_factory=list)

    @property
    def changed(self) -> list[str]:
        """修改紀錄的欄位分類（和 video_revision.CATEGORIES 一樣的名稱）。"""
        return ["slots"]


@dataclass
class CreatedAsset:
    video: dict[str, Any]
    asset_key: str


def segment_slots(segment: dict[str, Any]) -> list[SlotInfo]:
    """這一段放素材的格子（依段資料的順序）；文字、條列的格子不列。"""
    result = []
    for name, slot in (segment.get("slots") or {}).items():
        kind = slot.get("kind")
        if kind == "asset" and slot.get("asset_key"):
            result.append(SlotInfo(name, "asset", [slot["asset_key"]], True))
        elif kind == "items":
            keys: list[str] = []
            items = []
            for item in slot.get("items") or []:
                items.append(
                    ItemInfo(
                        item.get("item_key", ""),
                        item.get("asset_key", ""),
                        item.get("back_asset_key"),
                    )
                )
                for key in (item.get("asset_key"), item.get("back_asset_key")):
                    if key and key not in keys:
                        keys.append(key)
            result.append(SlotInfo(name, "items", keys, True, items))
    return result


def swap_segment_asset(
    video: dict[str, Any],
    segment_key: str,
    slot_name: str,
    asset_key: str,
    *,
    item_key: str | None = None,
    face: str = "front",
) -> SwapResult:
    """把 segment_key 這一段的 slot_name 格子（放牌的格子是其中一張的正面或牌背）換成 asset_key。

    不改傳入的段資料。
    """
    data = copy.deepcopy(video)
    segment = next(
        (s for s in data.get("segments", []) if s.get("segment_key") == segment_key), None
    )
    if segment is None:
        raise SwapRejected(404, "RULES_VIDEO_SEGMENT_NOT_FOUND", "草稿沒有這一段，請重新整理")
    slots = segment.get("slots") or {}
    slot = slots.get(slot_name)
    if slot is None:
        raise SwapRejected(422, "RULES_VIDEO_SLOT_NOT_FOUND", "這一段沒有這個格子，請重新整理")
    kind = slot.get("kind")
    if kind == "items":
        holder, field_name = _item_target(slot, item_key, face)
    elif kind == "asset" and slot.get("asset_key"):
        holder, field_name = slot, "asset_key"
    else:
        raise SwapRejected(422, "RULES_VIDEO_SWAP_UNSUPPORTED", UNSUPPORTED_MESSAGE)
    new_asset = _usable_asset(data, asset_key)
    old_key = holder[field_name]
    if old_key == asset_key:
        raise SwapRejected(422, "RULES_VIDEO_SWAP_SAME_ASSET", "這裡已經是這個素材")

    before = used_asset_keys(data)
    holder[field_name] = asset_key
    result = SwapResult(
        data,
        old_key,
        asset_key,
        item_key=item_key if kind == "items" else None,
        face=face if kind == "items" else "front",
    )
    if kind == "asset":
        result.regions_to_mark = _carry_regions(data, segment, slot_name, old_key, new_asset)
    after = used_asset_keys(data)
    result.unused_assets = [
        a["asset_key"]
        for a in data.get("assets", [])
        if a["asset_key"] in before and a["asset_key"] not in after
    ]
    return result


def _item_target(
    slot: dict[str, Any], item_key: str | None, face: str
) -> tuple[dict[str, Any], str]:
    """放牌的格子裡要換的那一張與欄位（asset_key 或 back_asset_key）。"""
    if not item_key:
        raise SwapRejected(422, "RULES_VIDEO_ITEM_REQUIRED", "請指定要換哪一張牌")
    item = next((i for i in slot.get("items") or [] if i.get("item_key") == item_key), None)
    if item is None:
        raise SwapRejected(422, "RULES_VIDEO_ITEM_NOT_FOUND", "這一格沒有這張牌，請重新整理")
    if face == "back":
        if not item.get("back_asset_key"):
            raise SwapRejected(422, "RULES_VIDEO_ITEM_NO_BACK", "這張牌沒有牌背，不能換牌背")
        return item, "back_asset_key"
    return item, "asset_key"


def _usable_asset(data: dict[str, Any], asset_key: str) -> dict[str, Any]:
    asset = next((a for a in data.get("assets", []) if a["asset_key"] == asset_key), None)
    if asset is None:
        raise SwapRejected(422, "RULES_VIDEO_SWAP_ASSET_INVALID", "素材清單沒有這個素材")
    if asset.get("kind") == "drawn":
        raise SwapRejected(
            422, "RULES_VIDEO_SWAP_ASSET_INVALID", "本版不支援繪製素材，請改選要拍照的素材"
        )
    if is_skipped(asset):
        raise SwapRejected(
            422,
            "RULES_VIDEO_SWAP_ASSET_INVALID",
            f"「{asset_label(asset)}」已略過，請先取消略過再換",
        )
    return asset


def _carry_regions(
    data: dict[str, Any],
    segment: dict[str, Any],
    slot_name: str,
    old_key: str,
    new_asset: dict[str, Any],
) -> list[str]:
    """這一段指到這一格的區域沿用到新素材；回傳新素材上還沒有座標、要重標的區域。"""
    names: list[str] = []
    for ref_slot, region in _region_refs(segment):
        if ref_slot == slot_name and region not in names:
            names.append(region)
    if not names:
        return []
    old_asset = next((a for a in data.get("assets", []) if a["asset_key"] == old_key), {})
    old_hints = old_asset.get("region_hints") or {}
    regions = new_asset.setdefault("regions", {})
    hints = new_asset.get("region_hints") or {}
    for name in names:
        if name not in regions:
            regions[name] = None
            if old_hints.get(name):
                hints.setdefault(name, old_hints[name])
    if hints:
        new_asset["region_hints"] = hints
    return [name for name in names if regions.get(name) is None]


def create_asset(video: dict[str, Any], label: str, shot: str | None) -> CreatedAsset:
    """新增一個照片素材（店員在換素材時新增）；代號由程式產生，不改傳入的段資料。

    名稱去掉前後空白後不可和既有素材的名稱相同。名稱長度等格式由 API 的 schema 檢查。
    """
    data = copy.deepcopy(video)
    name = label.strip()
    taken = {asset_label(a).strip() for a in data.get("assets", [])}
    if name in taken:
        raise AssetRejected(
            422, "RULES_VIDEO_ASSET_LABEL_TAKEN", f"已經有叫「{name}」的素材，請換一個名稱"
        )
    keys = {a["asset_key"] for a in data.get("assets", [])}
    number = 1
    while f"custom_{number}" in keys:
        number += 1
    key = f"custom_{number}"
    asset: dict[str, Any] = {
        "asset_key": key,
        "label": name,
        "kind": "flat_photo",
        "priority": "must",
        "reason": f"店員新增：{name}",
        "regions": {},
    }
    if shot and shot.strip():
        asset["shot"] = shot.strip()
    data.setdefault("assets", []).append(asset)
    return CreatedAsset(data, key)


def record_swap(
    result: SwapResult, segment_key: str, *, by: str, now: datetime | None = None
) -> None:
    """在這一段加一筆修改紀錄，並標示需要重新產生（格式同 video_revision.apply_entries）。

    編號接在所有段既有紀錄的最大值之後。直接改 result.video。
    """
    segments = result.video.get("segments", [])
    number = 1 + max(
        (r.get("number", 0) for s in segments for r in s.get("revisions") or []), default=0
    )
    labels = {a["asset_key"]: asset_label(a) for a in result.video.get("assets", [])}
    old, new = labels.get(result.old_asset_key), labels.get(result.new_asset_key)
    where = ""
    if result.item_key:
        where = f"（{result.item_key} 的{'牌背' if result.face == 'back' else '正面'}）"
    segment = next(s for s in segments if s.get("segment_key") == segment_key)
    segment["state"] = {
        k: v for k, v in (segment.get("state") or {}).items() if k != "content_hash"
    } | {"status": "stale"}
    segment["revisions"] = [
        *(segment.get("revisions") or []),
        {
            "number": number,
            "at": (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "by": by,
            "kind": "asset_swap",
            "request": f"換素材{where}：{old} → {new}",
            "changed": result.changed,
            "unrequested": [],
            "summary": f"這一段改用「{new}」",
        },
    ]
