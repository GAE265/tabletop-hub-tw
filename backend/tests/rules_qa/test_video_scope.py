"""整個遊戲一支影片：分類三格與整本模式的段資料（add-rules-video-mobile 整本範圍）。

單元測試：LLM 用 FakeLLMProvider，不連資料庫、不需要金鑰。
"""

from pathlib import Path

import pytest

from app.domains.rules_qa import video_prompts
from app.domains.rules_qa.video_scope import (
    SLOTS,
    ScopeEmpty,
    ScopeIncomplete,
    classify_scope,
    scope_from_dict,
)
from app.domains.rules_qa.video_script import (
    RulebookPage,
    ScriptRejected,
    ScriptRequest,
    build_input,
    check_script,
    generate_script,
    generate_whole_game,
    to_video_data,
)
from app.integrations.llm.fake import FakeLLMProvider
from tests.rules_qa.video_script_support import FAKE_PAGE, llm_output
from tests.rules_qa.whole_game_support import (
    ROUND_QUOTE,
    SETUP_QUOTE,
    VARIANT_QUOTE,
    WHOLE_GAME_PAGES,
    WIN_QUOTE,
    classify_output,
    slot_output,
    whole_game_output,
)

PAGES = [RulebookPage("zh", number, text) for number, text in WHOLE_GAME_PAGES]


def _scope(llm_output=None):
    return classify_scope(FakeLLMProvider(json_outputs=[llm_output or classify_output()]), PAGES)


def _request(scope=None) -> ScriptRequest:
    scope = scope or _scope()
    return ScriptRequest(
        chapter_number=1,
        chapter_title="",
        pages=[p for p in PAGES if p.page in scope.pages],
        terms=[],
        game_key="game-1",
        title="假遊戲 規則教學",
        scope=scope.slots,
    )


# --- 分類 ---


def test_three_slots_in_order():
    assert [(key, title) for key, title in SLOTS] == [
        ("setup", "開局"),
        ("round", "走完一輪"),
        ("win", "獲勝方式"),
    ]


def test_classify_into_three_slots_and_excluded():
    llm = FakeLLMProvider(json_outputs=[classify_output()])
    result = classify_scope(llm, PAGES)
    by_key = {slot.key: slot for slot in result.slots}
    assert [e.text for e in by_key["setup"].excerpts] == [SETUP_QUOTE]
    assert by_key["round"].excerpts[0].text == ROUND_QUOTE
    assert [e.text for e in by_key["win"].excerpts] == [WIN_QUOTE]
    assert result.excluded[0].page == 4 and result.excluded[0].text == VARIANT_QUOTE
    assert result.excluded[0].reason
    assert result.pages == [1, 2, 3]
    # 送給 LLM 的是整本（四頁都在）
    sent = llm.calls[0].kwargs["input"]
    assert all(f"第 {n} 頁" in sent for n in (1, 2, 3, 4))
    assert llm.calls[0].kwargs["schema"].name == "rules_video_scope"


def test_quote_must_appear_on_that_page():
    # 引用的片段不在那一頁（或根本不存在）就不採用，並記下來
    output = classify_output(
        setup=[
            {"page": 1, "quote": SETUP_QUOTE},
            {"page": 3, "quote": SETUP_QUOTE},  # 頁碼錯
            {"page": 1, "quote": "Each player takes ten cards."},  # 原文沒有
        ]
    )
    result = _scope(output)
    setup = next(s for s in result.slots if s.key == "setup")
    assert [(e.page, e.text) for e in setup.excerpts] == [(1, SETUP_QUOTE)]
    assert len(result.dropped) == 2


def test_quote_check_ignores_whitespace_differences():
    output = classify_output(
        setup=[{"page": 1, "quote": "Each player  takes one Red card\nand one Blue card."}]
    )
    setup = next(s for s in _scope(output).slots if s.key == "setup")
    assert len(setup.excerpts) == 1


def test_empty_slot_fails_with_its_title():
    # 第 3 頁放進了排除清單（每一頁都有去處），獲勝方式的片段又對不上原文：那一格空了
    output = classify_output(
        win=[{"page": 3, "quote": "Nobody ever wins this game."}],
        excluded=[
            {"page": 3, "quote": "The game ends when the deck is empty.", "reason": "r"},
            {"page": 4, "quote": "Advanced players may add the Knight expansion.", "reason": "r"},
        ],
    )
    with pytest.raises(ScopeEmpty) as exc:
        _scope(output)
    assert exc.value.slot_title == "獲勝方式"
    assert exc.value.dropped  # 沒採用的片段留給 error_detail


def test_scope_round_trip_through_json():
    result = _scope()
    restored = scope_from_dict(result.to_dict())
    assert [s.key for s in restored.slots] == ["setup", "round", "win"]
    assert restored.excluded[0].reason == result.excluded[0].reason


# --- 整本模式的段資料 ---


def test_build_input_lists_three_slots_not_chapter():
    text = build_input(_request())
    assert "開局" in text and "走完一輪" in text and "獲勝方式" in text
    assert SETUP_QUOTE in text and WIN_QUOTE in text
    assert "本章內容" not in text
    assert VARIANT_QUOTE not in text  # 排除的內容不送去產生


def test_to_video_data_has_three_chapters_in_slot_order():
    data = to_video_data(whole_game_output(), _request())
    assert [(c["chapter_key"], c["title"]) for c in data["chapters"]] == [
        ("setup", "開局"),
        ("round", "走完一輪"),
        ("win", "獲勝方式"),
    ]
    # 依三格的順序排好；每段記著屬於哪一格
    assert [s["chapter_key"] for s in data["segments"]] == ["setup", "round", "round", "win"]
    assert {a["asset_key"]: a["label"] for a in data["assets"]}["red"] == "紅牌"


def test_whole_game_draft_passes_checks(tmp_path: Path):
    request = _request()
    assert check_script(to_video_data(whole_game_output(), request), request, tmp_path) == []


def test_drawn_asset_is_rejected(tmp_path: Path):
    output = whole_game_output()
    output["assets"][0]["kind"] = "drawn"
    request = _request()
    errors = check_script(to_video_data(output, request), request, tmp_path)
    assert any("繪製" in e and "flat_photo" in e for e in errors)


def test_every_slot_needs_a_segment(tmp_path: Path):
    output = whole_game_output()
    output["segments"] = [s for s in output["segments"] if s["chapter"] != "win"]
    request = _request()
    errors = check_script(to_video_data(output, request), request, tmp_path)
    assert any("獲勝方式" in e for e in errors)


def test_source_page_must_be_in_slots(tmp_path: Path):
    output = whole_game_output()
    output["segments"][0]["source_pages"] = [4]  # 第 4 頁被排除了
    request = _request()
    errors = check_script(to_video_data(output, request), request, tmp_path)
    assert any("source_pages" in e for e in errors)


def test_generate_one_call_per_slot_in_order(tmp_path: Path):
    # 2026-11-22 永傑決定：每格各一次呼叫，依序開局、走完一輪、獲勝方式
    llm = FakeLLMProvider(
        json_outputs=[slot_output("setup"), slot_output("round"), slot_output("win")]
    )
    data = generate_whole_game(llm, _request(), tmp_path)
    assert len(llm.calls) == 3
    for call, (key, title) in zip(llm.calls, SLOTS, strict=True):
        kwargs = call.kwargs
        assert kwargs["instructions"] == video_prompts.WHOLE_GAME_SLOT_INSTRUCTIONS
        assert kwargs["schema"].name == "rules_video_whole_game"
        assert f"這次只產生：{key}（{title}）" in kwargs["input"]
    schema = llm.calls[0].kwargs["schema"].schema
    asset = schema["properties"]["assets"]["items"]["properties"]
    assert asset["kind"]["enum"] == ["flat_photo"]  # 只能實拍
    assert "label" in asset
    # 只送這一格的片段
    assert SETUP_QUOTE in llm.calls[0].kwargs["input"]
    assert WIN_QUOTE not in llm.calls[0].kwargs["input"]
    # 合起來：三個 chapter、段依三格排好
    assert [c["chapter_key"] for c in data["chapters"]] == ["setup", "round", "win"]
    assert [s["chapter_key"] for s in data["segments"]] == ["setup", "round", "round", "win"]
    assert check_script(data, _request(), tmp_path) == []


def test_later_slots_get_existing_assets(tmp_path: Path):
    llm = FakeLLMProvider(
        json_outputs=[slot_output("setup"), slot_output("round"), slot_output("win")]
    )
    data = generate_whole_game(llm, _request(), tmp_path)
    first, second = llm.calls[0].kwargs["input"], llm.calls[1].kwargs["input"]
    assert "已有的素材" not in first
    assert "已有的素材" in second and "red（紅牌）" in second
    # 後面的格沿用同一個 asset_key，不會重複
    keys = [a["asset_key"] for a in data["assets"]]
    assert sorted(keys) == ["back", "blue", "board", "red"] and len(keys) == len(set(keys))


def test_new_regions_are_added_to_existing_asset(tmp_path: Path):
    setup, round_, win = slot_output("setup"), slot_output("round"), slot_output("win")
    board = next(a for a in win["assets"] if a["asset_key"] == "board")
    board["regions"] = ["zone_a", "zone_b"]
    # 獲勝方式的段框選 zone_b（沒有被指到的區域會被刪掉，見下一個測試）
    win["segments"][0]["highlights"] = [
        {"key": "h_b", "target": "main@zone_b", "shape": "box", "style": "gold"}
    ]
    llm = FakeLLMProvider(json_outputs=[setup, round_, win])
    data = generate_whole_game(llm, _request(), tmp_path)
    merged = next(a for a in data["assets"] if a["asset_key"] == "board")
    assert set(merged["regions"]) == {"zone_a", "zone_b"}


def test_unused_regions_are_removed(tmp_path: Path):
    # 2026-11-22 永傑決定：沒被任何高亮、標籤、移動指到的區域，程式固定刪掉，店員不用標
    setup, round_, win = slot_output("setup"), slot_output("round"), slot_output("win")
    for output in (setup, round_, win):
        for asset in output["assets"]:
            if asset["asset_key"] == "red":
                asset["regions"] = ["牌面"]
            if asset["asset_key"] == "board":
                asset["regions"] = ["zone_a", "血刃區"]
    llm = FakeLLMProvider(json_outputs=[setup, round_, win])
    data = generate_whole_game(llm, _request(), tmp_path)
    assets = {a["asset_key"]: a for a in data["assets"]}
    assert assets["red"]["regions"] == {}
    # zone_a 有 highlight 與 move 指到，留下
    assert list(assets["board"]["regions"]) == ["zone_a"]
    assert check_script(data, _request(), tmp_path) == []


def test_label_target_keeps_region(tmp_path: Path):
    setup, round_, win = slot_output("setup"), slot_output("round"), slot_output("win")
    for output in (setup, round_, win):
        board = next(a for a in output["assets"] if a["asset_key"] == "board")
        board["regions"] = ["zone_a", "zone_c"]
    win["segments"][0]["labels"] = [
        {
            "key": "l_c",
            "text": "這裡",
            "target": "main@zone_c",
            "position": "below",
            "style": "plain",
        }
    ]
    llm = FakeLLMProvider(json_outputs=[setup, round_, win])
    data = generate_whole_game(llm, _request(), tmp_path)
    board = next(a for a in data["assets"] if a["asset_key"] == "board")
    assert set(board["regions"]) == {"zone_a", "zone_c"}


def test_beat_and_segment_keys_unique_across_slots(tmp_path: Path):
    setup, round_, win = slot_output("setup"), slot_output("round"), slot_output("win")
    for output in (setup, win):
        output["segments"][0]["segment_key"] = "s1"  # 和走完一輪的 s1 撞名
    llm = FakeLLMProvider(json_outputs=[setup, round_, win])
    data = generate_whole_game(llm, _request(), tmp_path)
    segment_keys = [s["segment_key"] for s in data["segments"]]
    beat_keys = [b["beat_key"] for s in data["segments"] for b in s["beats"]]
    assert len(segment_keys) == len(set(segment_keys))
    assert len(beat_keys) == len(set(beat_keys))
    assert check_script(data, _request(), tmp_path) == []


def test_each_slot_rewrites_once(tmp_path: Path):
    bad = slot_output("round")
    bad["segments"][0]["beats"][0]["narration"] = "每人只有一次機會。"
    llm = FakeLLMProvider(
        json_outputs=[slot_output("setup"), bad, slot_output("round"), slot_output("win")]
    )
    generate_whole_game(llm, _request(), tmp_path)
    assert len(llm.calls) == 4
    rewrite = llm.calls[2].kwargs["input"]
    assert "上一次的輸出有以下問題" in rewrite and "次" in rewrite
    assert "這次只產生：round（走完一輪）" in rewrite


def test_slot_rejected_twice_names_the_slot(tmp_path: Path):
    bad = slot_output("win")
    bad["segments"][0]["beats"][0]["narration"] = "每人只有一次機會。"
    llm = FakeLLMProvider(json_outputs=[slot_output("setup"), slot_output("round"), bad, bad])
    with pytest.raises(ScriptRejected) as exc:
        generate_whole_game(llm, _request(), tmp_path)
    assert any(e.startswith("「獲勝方式」") for e in exc.value.errors)


def test_whole_game_prompt_rules():
    text = video_prompts.WHOLE_GAME_SLOT_INSTRUCTIONS
    assert "「一次機會」" in text and "「一個機會」" in text
    assert "只能用素材 regions 列出的名稱" in text
    assert "優先沿用" in text
    assert "不限" in text  # 段數依這一格的規則量決定
    assert "輔助" in text and "optional" in text
    assert "代表牌" in text
    assert "drawn" not in text
    # 2026-11-22 永傑決定：牌類不需要區域，高亮直接框整張牌
    assert "牌類不需要區域" in text


# --- 分類的完整性：每一頁都要有去處 ---


def test_page_without_place_triggers_rewrite():
    # 第一次漏了第 4 頁（既不在三格、也不在排除清單），改寫一次後補上
    first = classify_output(excluded=[])
    llm = FakeLLMProvider(json_outputs=[first, classify_output()])
    result = classify_scope(llm, PAGES)
    assert len(llm.calls) == 2
    rewrite = llm.calls[1].kwargs["input"]
    assert "第 4 頁" in rewrite and "每一頁" in rewrite
    assert result.excluded[0].page == 4


def test_page_still_without_place_fails():
    first = classify_output(excluded=[])
    llm = FakeLLMProvider(json_outputs=[first, first])
    with pytest.raises(ScopeIncomplete) as exc:
        classify_scope(llm, PAGES)
    assert exc.value.pages == [4]
    assert "4" in exc.value.detail


def test_dropped_quote_does_not_count_as_place():
    # 引用對不上原文的片段不算有去處
    first = classify_output(excluded=[{"page": 4, "quote": "不存在的文字", "reason": "r"}])
    llm = FakeLLMProvider(json_outputs=[first, classify_output()])
    classify_scope(llm, PAGES)
    assert len(llm.calls) == 2


def test_chapter_mode_unchanged(tmp_path: Path):
    # 沒有 scope 時照舊（命令列工具與既有的單章專案）
    request = ScriptRequest(
        chapter_number=11,
        chapter_title="步驟三",
        pages=[RulebookPage("en", 5, FAKE_PAGE)],
        terms=[],
        game_key="game-1",
        title="t",
    )
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    data = generate_script(llm, request, tmp_path)
    assert llm.calls[0].kwargs["instructions"] == video_prompts.INSTRUCTIONS
    assert llm.calls[0].kwargs["schema"].name == "rules_video_script"
    assert [c["chapter_key"] for c in data["chapters"]] == ["c11"]
