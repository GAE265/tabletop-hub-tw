"""整個遊戲一支影片：分類三格與整本模式的段資料（add-rules-video-mobile 整本範圍）。

單元測試：LLM 用 FakeLLMProvider，不連資料庫、不需要金鑰。
"""

from pathlib import Path

import pytest

from app.domains.rules_qa import video_prompts
from app.domains.rules_qa.video_scope import (
    SLOTS,
    ScopeEmpty,
    classify_scope,
    scope_from_dict,
)
from app.domains.rules_qa.video_script import (
    RulebookPage,
    ScriptRequest,
    build_input,
    check_script,
    generate_script,
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
    output = classify_output(win=[{"page": 3, "quote": "Nobody ever wins this game."}])
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


def test_generate_uses_whole_game_prompt_and_schema(tmp_path: Path):
    llm = FakeLLMProvider(json_outputs=[whole_game_output()])
    generate_script(llm, _request(), tmp_path)
    call = llm.calls[0].kwargs
    assert call["instructions"] == video_prompts.WHOLE_GAME_INSTRUCTIONS
    assert call["schema"].name == "rules_video_whole_game"
    schema = call["schema"].schema
    asset = schema["properties"]["assets"]["items"]["properties"]
    assert asset["kind"]["enum"] == ["flat_photo"]  # 只能實拍
    assert "label" in asset


def test_whole_game_prompt_rules():
    text = video_prompts.WHOLE_GAME_INSTRUCTIONS
    assert "「一次機會」" in text and "「一個機會」" in text
    assert "只能用素材 regions 列出的名稱" in text
    assert "輔助" in text and "optional" in text
    assert "代表牌" in text
    assert "drawn" not in text


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
