"""AI 產生段資料的測試共用資料（spec rules-video-script）。

假規則書頁面、用語對照表與 LLM 的回傳內容都是自行編寫的，不含任何真實規則書。
"""

import copy
import json
from pathlib import Path
from typing import Any

FAKE_PAGE = """Step 3. Shuffle the played cards face down, then reveal them together.
Case 1: no Blade card. Remove every Blue card; put Red cards into Zone A.
Case 2: any Blade card. Remove every Blue card."""

FAKE_REFERENCE_PAGE = """Card list. Red cards: Red Knight, Red Queen. Blue cards: Blue Pawn.
FAQ: A player may skip playing a card."""

TERMS: list[dict[str, Any]] = [
    {"en": "Red card", "zh": "紅牌", "key": "red"},
    {"en": "Blue card", "zh": "藍牌", "key": "blue"},
    {"en": "Card back", "zh": "牌背", "key": "back"},
    {"en": "Board", "zh": "盤面", "key": "board"},
    {"en": "Zone A", "zh": "甲區", "key": "zone_a", "avoid": ["A區"]},
]

# LLM 依 schema 回傳的內容（對應 tests/integrations/video/support.py 的假遊戲）
_LLM_OUTPUT: dict[str, Any] = {
    "assets": [
        {
            "asset_key": "back",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "觀眾要知道牌是蓋著洗",
            "shot": "牌背一張，正面朝下平放",
            "regions": [],
        },
        {
            "asset_key": "red",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "要認得紅牌",
            "shot": None,
            "regions": [],
        },
        {
            "asset_key": "blue",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "要認得藍牌",
            "shot": None,
            "regions": [],
        },
        {
            "asset_key": "board",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "要知道牌放進哪一區",
            "shot": "從正上方拍整個盤面",
            "regions": ["zone_a"],
        },
    ],
    "segments": [
        {
            "segment_key": "s1",
            "source_pages": [5],
            "main_title": "情況一",
            "main": {
                "kind": "items",
                "asset_key": None,
                "items": [
                    {"item_key": "c1", "asset_key": "red", "back_asset_key": "back"},
                    {"item_key": "c2", "asset_key": "blue", "back_asset_key": "back"},
                    {"item_key": "c3", "asset_key": "red", "back_asset_key": "back"},
                ],
            },
            "sidebar": {
                "kind": "asset",
                "asset_key": "board",
                "text": None,
                "title": None,
                "items": [],
            },
            "highlights": [
                {"key": "h1", "target": "sidebar@zone_a", "shape": "box", "style": "gold"}
            ],
            "labels": [
                {
                    "key": "l1",
                    "text": "移除",
                    "target": "main.c2",
                    "position": "below",
                    "style": "plain",
                }
            ],
            "beats": [
                {
                    "narration": "把打出的牌蓋著洗勻，同時翻開。",
                    "subtitle": "把打出的牌蓋著洗在一起，然後同時翻開。",
                    "cues": [
                        {"at": 0.5, "do": "flip", "target": "main", "to": None},
                        {"at": 1.6, "do": "show", "target": "main_title", "to": None},
                    ],
                },
                {
                    "narration": "情況一：移除藍牌，紅牌放進甲區。",
                    "subtitle": "情況一：移除所有藍牌，紅牌放進甲區。",
                    "cues": [
                        {"at": 0.5, "do": "hide", "target": "main.c2", "to": None},
                        {"at": 1.0, "do": "move", "target": "main.c1", "to": "sidebar@zone_a"},
                    ],
                },
            ],
        },
        {
            "segment_key": "s2",
            "source_pages": [5],
            "main_title": None,
            "main": {"kind": "asset", "asset_key": "red", "items": []},
            "sidebar": {
                "kind": "none",
                "asset_key": None,
                "text": None,
                "title": None,
                "items": [],
            },
            "highlights": [],
            "labels": [],
            "beats": [
                {
                    "narration": "情況二：移除藍牌。",
                    "subtitle": "情況二：移除所有藍牌。",
                    "cues": [],
                }
            ],
        },
    ],
}


def llm_output() -> dict[str, Any]:
    return copy.deepcopy(_LLM_OUTPUT)


def write_inputs(folder: Path) -> Path:
    """寫出 rulebook/en-005.txt（本章）、en-003.txt（參考頁）與 terms.json，回傳 folder。"""
    (folder / "rulebook").mkdir(parents=True, exist_ok=True)
    (folder / "rulebook" / "en-005.txt").write_text(FAKE_PAGE, encoding="utf-8")
    (folder / "rulebook" / "en-003.txt").write_text(FAKE_REFERENCE_PAGE, encoding="utf-8")
    (folder / "terms.json").write_text(json.dumps(TERMS, ensure_ascii=False), encoding="utf-8")
    return folder
