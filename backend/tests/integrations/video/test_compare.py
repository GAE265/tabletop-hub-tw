"""逐項比對兩份段資料（spec rules-video-script「逐項比對」）。

a 是 AI 草稿、b 是手寫版本：只有 b 有的叫「缺少」，只有 a 有的叫「多出」。
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from app.integrations.video import load_video
from app.integrations.video.compare import CATEGORIES, compare_videos
from tests.integrations.video.support import base_data, segment, write_game


def _load(folder: Path, data: dict[str, Any]):
    return load_video(write_game(folder, data), draft=True)


def _pair(tmp_path: Path, ai: dict[str, Any], hand: dict[str, Any]):
    return compare_videos(_load(tmp_path / "ai", ai), _load(tmp_path / "hand", hand))


def test_identical(tmp_path: Path) -> None:
    report = _pair(tmp_path, base_data(), base_data())
    assert set(report.summary) == set(CATEGORIES)
    for counts in report.summary.values():
        assert counts.different == counts.missing == counts.extra == 0
    assert report.summary["旁白與字幕"].same == 3
    assert all(pair.narration_similarity == pytest.approx(1.0) for pair in report.beats)
    markdown = report.markdown()
    assert "摘要" in markdown and "AI 草稿" in markdown and "手寫" in markdown


def test_asset_list_differences(tmp_path: Path) -> None:
    hand = base_data()
    hand["assets"].append(
        {
            "asset_key": "spare",
            "kind": "flat_photo",
            "priority": "optional",
            "reason": "x",
            "file": None,
        }
    )
    ai = base_data()
    ai["assets"].append(
        {"asset_key": "die", "kind": "drawn", "priority": "optional", "reason": "y"}
    )
    ai["assets"][1]["priority"] = "optional"  # red：手寫版是 must
    report = _pair(tmp_path, ai, hand)
    assets = report.summary["素材"]
    assert (assets.missing, assets.extra, assets.different) == (1, 1, 1)
    markdown = report.markdown()
    for key in ("spare", "die", "red"):
        assert key in markdown


def test_cues_aligned_by_asset(tmp_path: Path) -> None:
    hand = base_data()
    ai = copy.deepcopy(hand)
    s1 = segment(ai, "s1")
    # AI 的項目命名不同：c1/c2/c3 → card1/card2/card3，但指向同樣的素材
    for item in s1["slots"]["main"]["items"]:
        item["item_key"] = item["item_key"].replace("c", "card")
    s1["labels"][0]["target"] = "main.card2"
    s1["beats"][1]["cues"] = [
        {"at": 0.9, "do": "hide", "target": "main.card2"},
        {"at": 1.0, "do": "move", "target": "main.card1", "to": "sidebar@zone_a"},
    ]
    report = _pair(tmp_path, ai, hand)
    cues = report.summary["句內動作"]
    assert cues.missing == 0 and cues.extra == 0 and cues.different == 0
    # hide 藍牌的時間差 0.4 秒要列出來
    assert any(abs(diff.at_delta - 0.4) < 1e-6 for diff in report.cues if diff.at_delta)
    assert "+0.40" in report.markdown()


def test_segment_split_differs(tmp_path: Path) -> None:
    hand = base_data()
    ai = copy.deepcopy(hand)
    # AI 把第 3 句併進第 1 段
    s1, s2 = segment(ai, "s1"), segment(ai, "s2")
    s1["beats"].append(s2["beats"][0])
    ai["segments"] = [s1]
    report = _pair(tmp_path, ai, hand)
    assert report.summary["分段"].different > 0
    assert report.segment_counts == ((1, [3]), (2, [2, 1]))
    assert [pair.narration_similarity for pair in report.beats] == [1.0, 1.0, 1.0]
