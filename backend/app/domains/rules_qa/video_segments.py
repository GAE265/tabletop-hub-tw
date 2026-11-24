"""換某一段的素材（2026-11-25 永傑決定，最小版）。純函式，不碰資料庫。

- 只支援單一素材的格子（`kind == "asset"`）；放好幾張牌的格子（`items`）與文字格子不能換。
- 只能換成素材清單裡、可以用的素材：不是繪製素材、沒有被略過。
- 指向這一格舊素材區域（`<格子>@<區域>`）的框線、標籤、動作一律移除，不重新對應；
  指向被移除的框線、標籤的動作也一起移除。指向整個格子的動作保留。
- 回報移除了什麼，以及換完後沒有段在用的素材（「還缺什麼」不再要求它）。
- 修改紀錄的格式和一句話修改（video_revision）一樣，之後的修改頁可以排在同一份紀錄裡。
"""

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domains.rules_qa.video_assets import asset_label, is_skipped, used_asset_keys

UNSUPPORTED_MESSAGE = "這一段目前不支援換素材"


@dataclass(frozen=True)
class SlotInfo:
    """一段裡放素材的格子。asset_keys 依出現順序、不重複（牌的正面與牌背都算）。"""

    slot: str
    kind: str  # asset | items
    asset_keys: list[str]
    swappable: bool


class SwapRejected(Exception):
    """不能換：status 是 HTTP 狀態碼，code 是錯誤代碼，message 給店員看。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class SwapResult:
    video: dict[str, Any]
    old_asset_key: str
    new_asset_key: str
    removed_highlights: list[str] = field(default_factory=list)
    removed_labels: list[str] = field(default_factory=list)
    # 每個移除的動作：{"beat_key", "do", "target"}
    removed_cues: list[dict[str, str]] = field(default_factory=list)
    unused_assets: list[str] = field(default_factory=list)

    @property
    def changed(self) -> list[str]:
        """修改紀錄的欄位分類（和 video_revision.CATEGORIES 一樣的名稱）。"""
        changed = ["slots"]
        if self.removed_highlights:
            changed.append("highlights")
        if self.removed_labels:
            changed.append("labels")
        if self.removed_cues:
            changed.append("cues")
        return changed


def segment_slots(segment: dict[str, Any]) -> list[SlotInfo]:
    """這一段放素材的格子（依段資料的順序）；文字、條列的格子不列。"""
    result = []
    for name, slot in (segment.get("slots") or {}).items():
        kind = slot.get("kind")
        if kind == "asset" and slot.get("asset_key"):
            result.append(SlotInfo(name, "asset", [slot["asset_key"]], True))
        elif kind == "items":
            keys: list[str] = []
            for item in slot.get("items") or []:
                for key in (item.get("asset_key"), item.get("back_asset_key")):
                    if key and key not in keys:
                        keys.append(key)
            result.append(SlotInfo(name, "items", keys, False))
    return result


def swap_segment_asset(
    video: dict[str, Any], segment_key: str, slot_name: str, asset_key: str
) -> SwapResult:
    """把 segment_key 這一段的 slot_name 格子換成 asset_key；不改傳入的段資料。"""
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
    if slot.get("kind") != "asset" or not slot.get("asset_key"):
        raise SwapRejected(422, "RULES_VIDEO_SWAP_UNSUPPORTED", UNSUPPORTED_MESSAGE)
    new_asset = next((a for a in data.get("assets", []) if a["asset_key"] == asset_key), None)
    if new_asset is None:
        raise SwapRejected(422, "RULES_VIDEO_SWAP_ASSET_INVALID", "素材清單沒有這個素材")
    if new_asset.get("kind") == "drawn":
        raise SwapRejected(
            422, "RULES_VIDEO_SWAP_ASSET_INVALID", "本版不支援繪製素材，請改選要拍照的素材"
        )
    if is_skipped(new_asset):
        raise SwapRejected(
            422,
            "RULES_VIDEO_SWAP_ASSET_INVALID",
            f"「{asset_label(new_asset)}」已略過，請先取消略過再換",
        )
    old_key = slot["asset_key"]
    if old_key == asset_key:
        raise SwapRejected(422, "RULES_VIDEO_SWAP_SAME_ASSET", "這一格已經是這個素材")

    before = used_asset_keys(data)
    slot["asset_key"] = asset_key
    result = SwapResult(data, old_key, asset_key)
    prefix = f"{slot_name}@"

    def on_old_region(target: str | None) -> bool:
        return bool(target) and target.startswith(prefix)

    removed_overlays: set[str] = set()
    for field_name, removed in (
        ("highlights", result.removed_highlights),
        ("labels", result.removed_labels),
    ):
        if field_name not in segment:
            continue
        kept = []
        for overlay in segment[field_name]:
            if on_old_region(overlay.get("target")):
                removed.append(overlay.get("key", ""))
                removed_overlays.add(overlay.get("key", ""))
            else:
                kept.append(overlay)
        segment[field_name] = kept
    for beat in segment.get("beats", []):
        if "cues" not in beat:
            continue
        kept_cues = []
        for cue in beat["cues"]:
            gone = (
                on_old_region(cue.get("target"))
                or on_old_region(cue.get("to"))
                or cue.get("target") in removed_overlays
            )
            if gone:
                result.removed_cues.append(
                    {
                        "beat_key": beat.get("beat_key", ""),
                        "do": cue.get("do", ""),
                        "target": cue.get("target", ""),
                    }
                )
            else:
                kept_cues.append(cue)
        beat["cues"] = kept_cues
    after = used_asset_keys(data)
    result.unused_assets = [
        a["asset_key"]
        for a in data.get("assets", [])
        if a["asset_key"] in before and a["asset_key"] not in after
    ]
    return result


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
            "request": f"換素材：{old} → {new}",
            "changed": result.changed,
            "unrequested": [c for c in result.changed if c != "slots"],
            "summary": f"這一段改用「{new}」",
        },
    ]
