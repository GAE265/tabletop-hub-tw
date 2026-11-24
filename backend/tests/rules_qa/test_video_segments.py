"""換素材的純函式（2026-11-25 永傑決定，最小版）。

- 每一段列出放素材的格子：單一素材的格子可以換；放好幾張牌的格子不能換。
- 換素材：只能換成素材清單裡、可以用的素材（不是繪製、沒有略過）。指向這一格舊素材區域
  （`<格子>@<區域>`）的框線、標籤、動作一律移除，指向被移除的框線、標籤的動作也一起移除；
  指向整個格子的動作保留。回報移除了什麼與換完後沒有段在用的素材。
- 沒有段在用的素材：「還缺什麼」不再要求照片與區域；產生影片前拿掉。沒有被指到的區域也不要求。

測試資料都是自編的段資料，不連資料庫。
"""

import copy

import pytest

from app.domains.rules_qa.video_assets import (
    asset_segments,
    readiness,
    strip_unused,
    used_asset_keys,
)
from app.domains.rules_qa.video_segments import (
    SwapRejected,
    segment_slots,
    swap_segment_asset,
)


def _asset(key, *, kind="flat_photo", regions=None, file="x.jpg", usable=None):
    asset = {
        "asset_key": key,
        "label": f"素材{key}",
        "kind": kind,
        "priority": "must",
        "reason": "r",
        "regions": regions or {},
    }
    if file:
        asset["file"] = file
    if usable is not None:
        asset["usable"] = usable
    return asset


def sample_video() -> dict:
    """s1：主畫面放兩張牌（items）、側欄是圖板（單一素材）、主標題文字；s2：主畫面是紅牌。"""
    return {
        "assets": [
            _asset("board", regions={"zone_a": [0.1, 0.1, 0.3, 0.3], "zone_b": None}),
            _asset("red"),
            _asset("blue"),
            _asset("back"),
            _asset("map", kind="drawn", file=None),
            _asset("gone", usable=False),
        ],
        "segments": [
            {
                "segment_key": "s1",
                "slots": {
                    "main_title": {"kind": "text", "text": "情況一"},
                    "main": {
                        "kind": "items",
                        "items": [
                            {"item_key": "c1", "asset_key": "red", "back_asset_key": "back"},
                            {"item_key": "c2", "asset_key": "blue", "back_asset_key": "back"},
                        ],
                    },
                    "sidebar": {"kind": "asset", "asset_key": "board"},
                },
                "highlights": [{"key": "h1", "target": "sidebar@zone_a"}],
                "labels": [
                    {"key": "l1", "text": "乙區", "target": "sidebar@zone_b"},
                    {"key": "l2", "text": "移除", "target": "main.c2"},
                ],
                "beats": [
                    {
                        "beat_key": "b1",
                        "narration": "把紅牌放進甲區。",
                        "subtitle": "紅牌放進甲區。",
                        "cues": [
                            {"at": 0.5, "do": "show", "target": "sidebar"},
                            {"at": 1.0, "do": "move", "target": "main.c1", "to": "sidebar@zone_a"},
                            {"at": 1.5, "do": "show", "target": "h1"},
                            {"at": 2.0, "do": "show", "target": "l2"},
                        ],
                    }
                ],
            },
            {
                "segment_key": "s2",
                "slots": {"main": {"kind": "asset", "asset_key": "red"}},
                "beats": [
                    {"beat_key": "b2", "narration": "再看紅牌。", "subtitle": "紅牌。", "cues": []}
                ],
            },
        ],
    }


# --- 每一段的格子 ---


def test_segment_slots_lists_asset_slots_only():
    s1, s2 = sample_video()["segments"]
    assert [(s.slot, s.kind, s.asset_keys, s.swappable) for s in segment_slots(s1)] == [
        ("main", "items", ["red", "back", "blue"], False),
        ("sidebar", "asset", ["board"], True),
    ]
    assert [(s.slot, s.kind, s.asset_keys, s.swappable) for s in segment_slots(s2)] == [
        ("main", "asset", ["red"], True),
    ]


# --- 換素材 ---


def test_swap_changes_only_that_slot():
    video = sample_video()
    original = copy.deepcopy(video)
    result = swap_segment_asset(video, "s1", "sidebar", "blue")
    s1, s2 = result.video["segments"]
    assert s1["slots"]["sidebar"] == {"kind": "asset", "asset_key": "blue"}
    assert s1["slots"]["main"] == original["segments"][0]["slots"]["main"]
    assert s1["beats"][0]["narration"] == "把紅牌放進甲區。"
    assert s2 == original["segments"][1]
    assert result.old_asset_key == "board"
    assert video == original  # 不改傳入的段資料


def test_swap_removes_highlights_and_labels_on_old_regions():
    result = swap_segment_asset(sample_video(), "s1", "sidebar", "blue")
    s1 = result.video["segments"][0]
    assert result.removed_highlights == ["h1"]
    assert result.removed_labels == ["l1"]
    assert s1["highlights"] == []
    assert [lab["key"] for lab in s1["labels"]] == ["l2"]  # 指向牌的標籤保留


def test_swap_removes_cues_on_old_regions_and_removed_overlays():
    result = swap_segment_asset(sample_video(), "s1", "sidebar", "blue")
    cues = result.video["segments"][0]["beats"][0]["cues"]
    # 指向整個側欄的 show、指向保留標籤 l2 的 show 留著；移到 sidebar@zone_a、顯示 h1 的移除
    assert [(c["do"], c["target"]) for c in cues] == [("show", "sidebar"), ("show", "l2")]
    assert result.removed_cues == [
        {"beat_key": "b1", "do": "move", "target": "main.c1"},
        {"beat_key": "b1", "do": "show", "target": "h1"},
    ]


def test_swap_without_region_references_removes_nothing():
    result = swap_segment_asset(sample_video(), "s2", "main", "blue")
    assert (result.removed_highlights, result.removed_labels, result.removed_cues) == ([], [], [])
    assert result.video["segments"][1]["slots"]["main"]["asset_key"] == "blue"


def test_swap_reports_assets_no_longer_used():
    result = swap_segment_asset(sample_video(), "s1", "sidebar", "blue")
    assert result.unused_assets == ["board"]
    back = swap_segment_asset(result.video, "s1", "sidebar", "board")
    assert back.unused_assets == []


@pytest.mark.parametrize(
    ("segment", "slot", "asset", "status", "code"),
    [
        ("s9", "main", "blue", 404, "RULES_VIDEO_SEGMENT_NOT_FOUND"),
        ("s1", "side", "blue", 422, "RULES_VIDEO_SLOT_NOT_FOUND"),
        ("s1", "main", "blue", 422, "RULES_VIDEO_SWAP_UNSUPPORTED"),
        ("s1", "main_title", "blue", 422, "RULES_VIDEO_SWAP_UNSUPPORTED"),
        ("s1", "sidebar", "nope", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "map", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "gone", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "board", 422, "RULES_VIDEO_SWAP_SAME_ASSET"),
    ],
    ids=[
        "segment-missing",
        "slot-missing",
        "items-slot",
        "text-slot",
        "asset-missing",
        "drawn-asset",
        "skipped-asset",
        "same-asset",
    ],
)
def test_swap_rejected(segment, slot, asset, status, code):
    video = sample_video()
    with pytest.raises(SwapRejected) as exc:
        swap_segment_asset(video, segment, slot, asset)
    assert (exc.value.status, exc.value.code) == (status, code)
    assert exc.value.message


def test_unsupported_slot_message():
    with pytest.raises(SwapRejected) as exc:
        swap_segment_asset(sample_video(), "s1", "main", "blue")
    assert exc.value.message == "這一段目前不支援換素材"


# --- 沒有段在用的素材 ---


def test_used_asset_keys_include_items_and_backs():
    assert used_asset_keys(sample_video()) == {"board", "red", "blue", "back"}


def test_asset_segments_numbers():
    video = sample_video()
    assert asset_segments(video, "red") == [1, 2]
    assert asset_segments(video, "board") == [1]
    assert asset_segments(video, "map") == []


def test_readiness_skips_unused_assets():
    video = swap_segment_asset(sample_video(), "s1", "sidebar", "blue").video
    for asset in video["assets"]:
        if asset["asset_key"] == "board":
            asset.pop("file")
    report = readiness(video)
    assert "board" not in [m["asset_key"] for m in report["missing_photos"]]
    assert "board" not in [m["asset_key"] for m in report["missing_regions"]]
    # 沒有段在用的繪製素材也不擋
    assert report["unsupported"] == []


def test_readiness_only_requires_referenced_regions():
    video = sample_video()
    report = readiness(video)
    assert report["missing_regions"] == [{"asset_key": "board", "region": "zone_b"}]
    video["segments"][0]["labels"] = [
        lab for lab in video["segments"][0]["labels"] if lab["key"] != "l1"
    ]
    assert readiness(video)["missing_regions"] == []


def test_strip_unused_removes_unused_assets_and_unreferenced_regions():
    video = swap_segment_asset(sample_video(), "s2", "main", "blue").video
    video["segments"][0]["labels"] = [
        lab for lab in video["segments"][0]["labels"] if lab["key"] != "l1"
    ]
    stripped = strip_unused(video)
    keys = [a["asset_key"] for a in stripped["assets"]]
    assert keys == ["board", "red", "blue", "back"]
    board = stripped["assets"][0]
    assert board["regions"] == {"zone_a": [0.1, 0.1, 0.3, 0.3]}
    assert [a["asset_key"] for a in video["assets"]][-2:] == ["map", "gone"]  # 不改傳入的
