"""整個遊戲一支影片的測試共用資料（add-rules-video-mobile 整本範圍）。

假規則書四頁都是自行編寫的英文，不含任何真實規則書：
第 1 頁開局、第 2 頁走完一輪（沿用 video_script_support 的假頁面）、第 3 頁獲勝方式、
第 4 頁是變體規則（應該被排除）。
"""

import copy
from typing import Any

from tests.rules_qa.video_script_support import (
    FAKE_PAGE,
    coverage_output,
    coverage_rule,
    llm_output,
)

SETUP_PAGE = """Setup. Each player takes one Red card and one Blue card.
Shuffle the deck face down and place the board in the middle."""
ROUND_PAGE = FAKE_PAGE
WIN_PAGE = """Game end. The game ends when the deck is empty.
The player who placed the most Red cards into Zone A wins."""
VARIANT_PAGE = """Variant. Advanced players may add the Knight expansion.
Designer notes and thanks.
Legend: zone_a is the box on the left of the board."""

WHOLE_GAME_PAGES = [(1, SETUP_PAGE), (2, ROUND_PAGE), (3, WIN_PAGE), (4, VARIANT_PAGE)]

SETUP_QUOTE = "Each player takes one Red card and one Blue card."
ROUND_QUOTE = "Shuffle the played cards face down, then reveal them together."
ROUND_QUOTE_2 = "Case 1: no Blade card. Remove every Blue card; put Red cards into Zone A."
WIN_QUOTE = "The game ends when the deck is empty."
VARIANT_QUOTE = "Advanced players may add the Knight expansion."
# 圖例頁（被排除的頁）才寫出場地名稱：場地清單要掃整本（2026-11-22 永傑決定）
LEGEND_QUOTE = "Legend: zone_a is the box on the left of the board."
ZONE_A_HINT = "盤面左邊的方框"


def classify_output(
    *,
    setup: list[dict[str, Any]] | None = None,
    round_: list[dict[str, Any]] | None = None,
    win: list[dict[str, Any]] | None = None,
    excluded: list[dict[str, Any]] | None = None,
    places: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """分類呼叫的回傳：三格引用原文片段，排除的附原因；場地清單（主板上的格子／桌上的位置）。"""
    return {
        "setup": setup if setup is not None else [{"page": 1, "quote": SETUP_QUOTE}],
        "round": round_
        if round_ is not None
        else [{"page": 2, "quote": ROUND_QUOTE}, {"page": 2, "quote": ROUND_QUOTE_2}],
        "win": win if win is not None else [{"page": 3, "quote": WIN_QUOTE}],
        "excluded": excluded
        if excluded is not None
        else [{"page": 4, "quote": VARIANT_QUOTE, "reason": "變體規則，第一次玩不需要"}],
        "places": places
        if places is not None
        else [
            {
                "name": "zone_a",
                "page": 4,
                "quote": LEGEND_QUOTE,
                "kind": "board",
                "hint": ZONE_A_HINT,
            }
        ],
    }


def whole_game_output() -> dict[str, Any]:
    """產生呼叫的回傳（整本模式）：每段標出屬於哪一格，素材有給店員看的中文名稱。"""
    data = copy.deepcopy(llm_output())
    labels = {"back": "牌背", "red": "紅牌", "blue": "藍牌", "board": "盤面"}
    for asset in data["assets"]:
        asset["label"] = labels[asset["asset_key"]]
    round_1, round_2 = data["segments"]
    for segment in (round_1, round_2):
        segment["chapter"] = "round"
        segment["source_pages"] = [2]
    setup = copy.deepcopy(round_2)
    setup.update(
        segment_key="s_setup",
        chapter="setup",
        source_pages=[1],
        beats=[
            {
                "narration": "每人拿一張紅牌和一張藍牌。",
                "subtitle": "每位玩家拿一張紅牌、一張藍牌。",
                "cues": [],
            }
        ],
    )
    win = copy.deepcopy(round_2)
    win.update(
        segment_key="s_win",
        chapter="win",
        source_pages=[3],
        main={"kind": "asset", "asset_key": "board", "items": []},
        beats=[
            {"narration": "牌庫抽完，遊戲就結束。", "subtitle": "牌庫抽完時遊戲結束。", "cues": []}
        ],
    )
    # 故意把獲勝的段放在前面：程式要依三格的順序排好
    data["segments"] = [win, setup, round_1, round_2]
    return data


def slot_coverage(
    rule_id: str = "R1", beat: str = "1-0", status: str = "complete", missing: str | None = None
) -> dict:
    """某一格的涵蓋檢查回傳（一條規則）。"""
    return coverage_output(
        [
            coverage_rule(
                rule_id,
                narration=(status, [beat], missing),
                subtitle=("complete", [beat], None),
            )
        ]
    )


def slot_output(slot: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """每格各一次呼叫時，這一格的回傳：只有這一格的段；素材列出這一格用到的（含沿用的）。"""
    data = data or whole_game_output()
    return {
        "assets": data["assets"],
        "segments": [s for s in data["segments"] if s["chapter"] == slot],
    }


def whole_game_llm_outputs(*, coverage: list[dict] | None = None) -> list[dict[str, Any]]:
    """草稿工作（整本）依序的 LLM 回傳：分類、三格各產生一次、三格的涵蓋檢查。"""
    return [
        classify_output(),
        slot_output("setup"),
        slot_output("round"),
        slot_output("win"),
        *(coverage or [slot_coverage(), slot_coverage(), slot_coverage()]),
    ]
