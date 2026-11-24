"""換素材的純函式（2026-11-25 永傑決定；最小版之後補上完整版）。

- 每一段列出放素材的格子：單一素材的格子、放好幾張牌的格子（逐張換正面或牌背）都可以換；
  文字格子不能換。
- 換素材：只能換成素材清單裡、可以用的素材（不是繪製、沒有略過）。
- 完整版：指向這一格區域的框線、標籤、動作全部保留；這一段指到的區域沿用到新素材
  （新素材沒有同名區域時加上名稱與白話說明、座標留空，請店員重標），回報要重標的區域。
  （最小版是一律移除；2026-11-25 永傑改成沿用並重標。）
- 新增素材：店員在換素材時新增一個照片素材（中文名稱、拍攝說明），代號由程式產生。
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
    AssetRejected,
    SwapRejected,
    create_asset,
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
            {
                **_asset("board", regions={"zone_a": [0.1, 0.1, 0.3, 0.3], "zone_b": None}),
                "region_hints": {"zone_a": "左上的甲區", "zone_b": "右下的乙區"},
            },
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
                            {"item_key": "c3", "asset_key": "red"},
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
        ("main", "items", ["red", "back", "blue"], True),
        ("sidebar", "asset", ["board"], True),
    ]
    assert [(s.slot, s.kind, s.asset_keys, s.swappable) for s in segment_slots(s2)] == [
        ("main", "asset", ["red"], True),
    ]


def test_segment_slots_list_each_item():
    s1 = sample_video()["segments"][0]
    main = segment_slots(s1)[0]
    assert [(i.item_key, i.asset_key, i.back_asset_key) for i in main.items] == [
        ("c1", "red", "back"),
        ("c2", "blue", "back"),
        ("c3", "red", None),
    ]
    assert segment_slots(s1)[1].items == []


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


def test_swap_keeps_highlights_labels_and_cues():
    # 完整版：框線、標籤、動作全部保留（最小版是移除）
    original = sample_video()["segments"][0]
    s1 = swap_segment_asset(sample_video(), "s1", "sidebar", "blue").video["segments"][0]
    assert s1["highlights"] == original["highlights"]
    assert s1["labels"] == original["labels"]
    assert s1["beats"] == original["beats"]


def test_swap_copies_regions_to_new_asset_for_remarking():
    result = swap_segment_asset(sample_video(), "s1", "sidebar", "blue")
    blue = next(a for a in result.video["assets"] if a["asset_key"] == "blue")
    assert blue["regions"] == {"zone_a": None, "zone_b": None}
    assert blue["region_hints"] == {"zone_a": "左上的甲區", "zone_b": "右下的乙區"}
    assert result.regions_to_mark == ["zone_a", "zone_b"]
    board = next(a for a in result.video["assets"] if a["asset_key"] == "board")
    assert board["regions"]["zone_a"] == [0.1, 0.1, 0.3, 0.3]  # 舊素材不動


def test_swap_reuses_same_name_region_on_new_asset():
    video = sample_video()
    red = next(a for a in video["assets"] if a["asset_key"] == "red")
    red["regions"] = {"zone_a": [0.2, 0.2, 0.3, 0.3]}
    result = swap_segment_asset(video, "s1", "sidebar", "red")
    red = next(a for a in result.video["assets"] if a["asset_key"] == "red")
    assert red["regions"] == {"zone_a": [0.2, 0.2, 0.3, 0.3], "zone_b": None}
    assert result.regions_to_mark == ["zone_b"]


def test_swap_without_region_references_needs_no_marking():
    result = swap_segment_asset(sample_video(), "s2", "main", "blue")
    assert result.regions_to_mark == []
    assert result.video["segments"][1]["slots"]["main"]["asset_key"] == "blue"
    blue = next(a for a in result.video["assets"] if a["asset_key"] == "blue")
    assert blue["regions"] == {}


def test_readiness_asks_to_mark_copied_regions():
    video = swap_segment_asset(sample_video(), "s1", "sidebar", "blue").video
    missing = readiness(video)["missing_regions"]
    assert {"asset_key": "blue", "region": "zone_a"} in missing
    assert {"asset_key": "blue", "region": "zone_b"} in missing
    assert all(m["asset_key"] != "board" for m in missing)


# --- 放好幾張牌的格子：逐張換正面或牌背 ---


def test_swap_item_front():
    original = sample_video()["segments"][0]
    result = swap_segment_asset(sample_video(), "s1", "main", "red", item_key="c2")
    s1 = result.video["segments"][0]
    items = s1["slots"]["main"]["items"]
    assert items[1] == {"item_key": "c2", "asset_key": "red", "back_asset_key": "back"}
    assert items[0] == original["slots"]["main"]["items"][0]
    # 指向這張牌的標籤與動作保留
    assert s1["labels"] == original["labels"]
    assert s1["beats"] == original["beats"]
    assert (result.old_asset_key, result.new_asset_key) == ("blue", "red")
    assert result.regions_to_mark == []
    assert result.unused_assets == ["blue"]  # 藍牌只用在 c2 的正面


def test_swap_item_back():
    result = swap_segment_asset(sample_video(), "s1", "main", "blue", item_key="c1", face="back")
    items = result.video["segments"][0]["slots"]["main"]["items"]
    assert items[0] == {"item_key": "c1", "asset_key": "red", "back_asset_key": "blue"}
    assert result.old_asset_key == "back"


def test_swap_reports_assets_no_longer_used():
    result = swap_segment_asset(sample_video(), "s1", "sidebar", "blue")
    assert result.unused_assets == ["board"]
    back = swap_segment_asset(result.video, "s1", "sidebar", "board")
    assert back.unused_assets == []


@pytest.mark.parametrize(
    ("segment", "slot", "asset", "status", "code"),
    [
        ("s9", "main", "blue", None, "front", 404, "RULES_VIDEO_SEGMENT_NOT_FOUND"),
        ("s1", "side", "blue", None, "front", 422, "RULES_VIDEO_SLOT_NOT_FOUND"),
        ("s1", "main_title", "blue", None, "front", 422, "RULES_VIDEO_SWAP_UNSUPPORTED"),
        ("s1", "main", "blue", None, "front", 422, "RULES_VIDEO_ITEM_REQUIRED"),
        ("s1", "main", "blue", "c9", "front", 422, "RULES_VIDEO_ITEM_NOT_FOUND"),
        ("s1", "main", "blue", "c3", "back", 422, "RULES_VIDEO_ITEM_NO_BACK"),
        ("s1", "main", "red", "c1", "front", 422, "RULES_VIDEO_SWAP_SAME_ASSET"),
        ("s1", "sidebar", "nope", None, "front", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "map", None, "front", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "gone", None, "front", 422, "RULES_VIDEO_SWAP_ASSET_INVALID"),
        ("s1", "sidebar", "board", None, "front", 422, "RULES_VIDEO_SWAP_SAME_ASSET"),
    ],
    ids=[
        "segment-missing",
        "slot-missing",
        "text-slot",
        "item-required",
        "item-missing",
        "item-no-back",
        "item-same-asset",
        "asset-missing",
        "drawn-asset",
        "skipped-asset",
        "same-asset",
    ],
)
def test_swap_rejected(segment, slot, asset, item, face, status, code):
    video = sample_video()
    with pytest.raises(SwapRejected) as exc:
        swap_segment_asset(video, segment, slot, asset, item_key=item, face=face)
    assert (exc.value.status, exc.value.code) == (status, code)
    assert exc.value.message


def test_unsupported_slot_message():
    with pytest.raises(SwapRejected) as exc:
        swap_segment_asset(sample_video(), "s1", "main_title", "blue")
    assert exc.value.message == "這一段目前不支援換素材"


# --- 新增素材 ---


def test_create_asset():
    video = sample_video()
    original = copy.deepcopy(video)
    result = create_asset(video, "白薔薇", "整張牌正面朝上，從正上方拍")
    asset = result.video["assets"][-1]
    assert asset["asset_key"] == result.asset_key
    assert result.asset_key not in {a["asset_key"] for a in original["assets"]}
    assert asset["label"] == "白薔薇"
    assert asset["shot"] == "整張牌正面朝上，從正上方拍"
    assert (asset["kind"], asset["priority"], asset["regions"]) == ("flat_photo", "must", {})
    assert asset["reason"]
    assert video == original  # 不改傳入的段資料
    # 剛新增還沒有段在用
    assert asset_segments(result.video, result.asset_key) == []


def test_create_asset_keys_are_unique():
    first = create_asset(sample_video(), "白薔薇", None)
    second = create_asset(first.video, "黑薔薇", None)
    assert first.asset_key != second.asset_key


def test_create_asset_trims_label_and_allows_no_shot():
    result = create_asset(sample_video(), "  白薔薇  ", None)
    asset = result.video["assets"][-1]
    assert asset["label"] == "白薔薇" and asset.get("shot") is None


@pytest.mark.parametrize("label", ["素材red", "  素材red "], ids=["same", "same-with-spaces"])
def test_create_asset_label_taken(label):
    with pytest.raises(AssetRejected) as exc:
        create_asset(sample_video(), label, None)
    assert (exc.value.status, exc.value.code) == (422, "RULES_VIDEO_ASSET_LABEL_TAKEN")


def test_create_then_swap():
    created = create_asset(sample_video(), "白薔薇", None)
    result = swap_segment_asset(created.video, "s2", "main", created.asset_key)
    assert result.video["segments"][1]["slots"]["main"]["asset_key"] == created.asset_key


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
