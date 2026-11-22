"""整個遊戲一支影片：場地清單與區域名稱（add-rules-video-mobile D17，2026-11-22 永傑決定）。

- 分類時同時列出規則書出現過的場地（主板上的格子／桌上的位置），掃整本（含被排除的圖例頁）。
- 名稱要確實出現在引用的那一頁；比對時「區」與「處」視為相同，不做其他寬鬆比對。
- 區域名稱只能用「主板上的格子」；不在清單算檢查失敗，進自動改寫。
- 區域的白話說明（hint）取自場地清單；字幕裡不在清單的「X區」「X處」只記錄、不擋。

單元測試：LLM 用 FakeLLMProvider，不連資料庫、不需要金鑰。
"""

import dataclasses
from pathlib import Path

from app.domains.rules_qa import video_prompts, video_scope
from app.domains.rules_qa.video_scope import (
    Place,
    classify_scope,
    parse_places,
    place_key,
    scope_from_dict,
    unlisted_place_words,
)
from app.domains.rules_qa.video_script import (
    RulebookPage,
    ScriptRequest,
    build_input,
    check_script,
    generate_whole_game,
    to_video_data,
)
from app.integrations.llm.fake import FakeLLMProvider
from tests.rules_qa.whole_game_support import (
    LEGEND_QUOTE,
    WHOLE_GAME_PAGES,
    ZONE_A_HINT,
    classify_output,
    slot_output,
    whole_game_output,
)

PAGES = [RulebookPage("zh", number, text) for number, text in WHOLE_GAME_PAGES]

# 自行編寫的中文圖例頁（不是任何真實規則書）
ZH_LEGEND = RulebookPage("zh", 2, "圖例：A 水晶放置處　B 死亡區\n把計分板放在桌面中央。")

ZONE_A = Place("zone_a", 4, LEGEND_QUOTE, "board", ZONE_A_HINT)
TABLE_CENTER = Place("桌面中央", 2, "把計分板放在桌面中央。", "table", "桌子中間")


def _scope(output=None):
    return classify_scope(FakeLLMProvider(json_outputs=[output or classify_output()]), PAGES)


def _request(places=None) -> ScriptRequest:
    scope = _scope()
    return ScriptRequest(
        chapter_number=1,
        chapter_title="",
        pages=[p for p in PAGES if p.page in scope.pages],
        terms=[],
        game_key="game-1",
        title="假遊戲 規則教學",
        scope=scope.slots,
        places=[ZONE_A] if places is None else places,
    )


# --- 分類時列出場地 ---


def test_places_scan_excluded_legend_page():
    # zone_a 只寫在第 4 頁的圖例（那一頁被排除），仍要列進場地清單
    result = _scope()
    assert result.places == [ZONE_A]
    assert 4 not in result.pages


def test_classify_prompt_asks_for_places():
    text = video_scope.INSTRUCTIONS
    assert "places" in text and "圖例" in text and "被排除" in text
    assert "board" in text and "table" in text and "hint" in text
    schema = video_scope.SCHEMA.schema
    place = schema["properties"]["places"]["items"]
    assert place["properties"]["kind"]["enum"] == ["board", "table"]


def test_place_name_must_appear_in_quote_on_that_page():
    raw = [
        {"name": "死亡區", "page": 2, "quote": "B 死亡區", "kind": "board", "hint": "h"},
        # 名稱不在引用的片段裡
        {"name": "獻祭區", "page": 2, "quote": "B 死亡區", "kind": "board", "hint": "h"},
        # 片段不在那一頁
        {"name": "白薔薇區", "page": 2, "quote": "C 白薔薇區", "kind": "board", "hint": "h"},
        # 頁碼不存在
        {"name": "死亡區", "page": 9, "quote": "B 死亡區", "kind": "board", "hint": "h"},
    ]
    places, dropped = parse_places(raw, [ZH_LEGEND])
    assert [p.name for p in places] == ["死亡區"]
    assert len(dropped) == 3 and all(d["slot"] == "places" for d in dropped)


def test_qu_and_chu_are_the_same_and_name_follows_the_rulebook():
    # AI 寫「水晶放置區」，規則書是「水晶放置處」：視為相同，名稱採用規則書的寫法
    raw = [{"name": "水晶放置區", "page": 2, "quote": "A 水晶放置區", "kind": "board", "hint": "h"}]
    places, dropped = parse_places(raw, [ZH_LEGEND])
    assert dropped == []
    assert places[0].name == "水晶放置處" and places[0].quote == "A 水晶放置處"
    assert place_key("水晶放置區") == place_key("水晶放置處")
    # 只有「區／處」相同，其他字不同就是不同
    assert place_key("水晶放置格") != place_key("水晶放置處")


def test_empty_hint_falls_back_to_the_page():
    raw = [{"name": "死亡區", "page": 2, "quote": "B 死亡區", "kind": "board", "hint": " "}]
    places, _ = parse_places(raw, [ZH_LEGEND])
    assert places[0].hint == "對照規則書第 2 頁的圖"


def test_duplicate_places_keep_first():
    raw = [
        {"name": "死亡區", "page": 2, "quote": "B 死亡區", "kind": "board", "hint": "第一筆"},
        {"name": "死亡區", "page": 2, "quote": "B 死亡區", "kind": "board", "hint": "第二筆"},
    ]
    places, _ = parse_places(raw, [ZH_LEGEND])
    assert [p.hint for p in places] == ["第一筆"]


def test_places_round_trip_through_json():
    restored = scope_from_dict(_scope().to_dict())
    assert restored.places == [ZONE_A]


# --- 產生：區域名稱只能用主板上的格子 ---


def test_slot_input_lists_board_and_table_places():
    text = build_input(_request(places=[ZONE_A, TABLE_CENTER]))
    assert "可以當區域的名稱" in text and "zone_a" in text
    assert "不能當區域" in text and "桌面中央" in text


def test_slot_prompt_says_table_places_are_not_regions():
    text = video_prompts.WHOLE_GAME_SLOT_INSTRUCTIONS
    assert "桌上的位置" in text and "整張素材" in text
    assert "可以當區域的名稱" in text


def _with_board_regions(*names: str) -> dict:
    output = whole_game_output()
    for asset in output["assets"]:
        if asset["asset_key"] == "board":
            asset["regions"] = ["zone_a", *names]
    return output


def test_region_not_in_places_is_rejected(tmp_path: Path):
    request = _request(places=[ZONE_A, TABLE_CENTER])
    data = to_video_data(_with_board_regions("桌面中央", "圓版中央"), request)
    errors = check_script(data, request, tmp_path)
    table = [e for e in errors if "「桌面中央」" in e]
    assert table and "桌上的位置" in table[0] and "整張素材" in table[0]
    unknown = [e for e in errors if "「圓版中央」" in e]
    assert unknown and "zone_a" in unknown[0]  # 列出可以用的名稱
    assert not any("「zone_a」" in e for e in errors)


def test_region_matches_place_with_qu_or_chu(tmp_path: Path):
    crystal = Place("水晶放置處", 2, "A 水晶放置處", "board", "h")
    request = _request(places=[ZONE_A, crystal])
    data = to_video_data(_with_board_regions("水晶放置區"), request)
    assert check_script(data, request, tmp_path) == []


def test_no_place_check_without_places(tmp_path: Path):
    # 舊的單章模式（沒有場地清單）照舊，不檢查區域名稱
    request = dataclasses.replace(_request(), places=None)
    data = to_video_data(_with_board_regions("圓版中央"), request)
    assert check_script(data, request, tmp_path) == []


def test_bad_region_name_triggers_rewrite(tmp_path: Path):
    bad = slot_output("round")
    board = next(a for a in bad["assets"] if a["asset_key"] == "board")
    board["regions"] = ["zone_a", "圓版中央"]
    llm = FakeLLMProvider(
        json_outputs=[slot_output("setup"), bad, slot_output("round"), slot_output("win")]
    )
    generate_whole_game(llm, _request(), tmp_path)
    assert len(llm.calls) == 4
    assert "「圓版中央」" in llm.calls[2].kwargs["input"]


def test_region_hints_come_from_places(tmp_path: Path):
    llm = FakeLLMProvider(
        json_outputs=[slot_output("setup"), slot_output("round"), slot_output("win")]
    )
    data = generate_whole_game(llm, _request(), tmp_path)
    board = next(a for a in data["assets"] if a["asset_key"] == "board")
    assert board["region_hints"] == {"zone_a": ZONE_A_HINT}
    # 沒有區域的素材不加 hint
    assert "region_hints" not in next(a for a in data["assets"] if a["asset_key"] == "red")


# --- 字幕裡不在清單的「X區」「X處」：只記錄 ---


def _beats(*subtitles: str) -> dict:
    return {
        "segments": [
            {"beats": [{"narration": "", "subtitle": text} for text in subtitles]},
        ]
    }


def test_unlisted_place_words_are_recorded():
    places = [Place("死亡區", 2, "B 死亡區", "board", "h"), TABLE_CENTER]
    data = _beats("蓋牌放進死亡區。", "水晶放進中央區。", "這張牌留在此處。")
    assert unlisted_place_words(data, places, []) == ["中央區"]


def test_unlisted_words_treat_qu_and_chu_the_same():
    places = [Place("水晶放置處", 2, "A 水晶放置處", "board", "h")]
    assert unlisted_place_words(_beats("白水晶放進水晶放置區。"), places, []) == []
