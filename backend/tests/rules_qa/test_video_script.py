"""AI 產生段資料草稿、檢查與改寫一次（spec rules-video-script）。

一律用 FakeLLMProvider，不連真正的 LLM（AGENTS.md 7.6）。
"""

from pathlib import Path

import pytest

from app.domains.rules_qa.video_script import (
    ScriptInputError,
    ScriptRejected,
    ScriptRequest,
    generate_script,
    load_pages,
    load_terms,
)
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.video import parse_video
from tests.rules_qa.video_script_support import FAKE_PAGE, llm_output, write_inputs


def _request(folder: Path) -> ScriptRequest:
    write_inputs(folder)
    return ScriptRequest(
        chapter_number=11,
        chapter_title="步驟三",
        pages=load_pages(folder, ["rulebook/en-005.txt"]),
        terms=load_terms(folder / "terms.json"),
        game_key="fake_game",
        title="假遊戲 規則教學",
    )


def test_generate_draft(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    data = generate_script(llm, _request(tmp_path), tmp_path / "draft")
    video = parse_video(data, tmp_path / "draft", draft=True)
    assert [b.beat_key for s in video.segments for b in s.beats] == ["11-0", "11-1", "11-2"]
    assert video.chapters[0].number == 11 and video.chapters[0].title == "步驟三"
    # 有 show cue 的主體標題自動設為隱藏
    assert video.segments[0].slots["main_title"].hidden is True
    # 照片檔待拍、區域待量測
    assert video.assets["board"].file is None
    assert video.assets["board"].regions == {"zone_a": None}
    assert video.segments[0].source_pages[0].lang == "en"
    assert video.segments[0].source_pages[0].page == 5
    assert len(llm.calls) == 1


def test_llm_input_and_instructions(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    generate_script(llm, _request(tmp_path), tmp_path / "draft")
    call = llm.calls[0].kwargs
    assert "第 5 頁" in call["input"] and FAKE_PAGE.splitlines()[0] in call["input"]
    assert "11" in call["input"] and "步驟三" in call["input"]
    assert "Zone A" in call["input"] and "甲區" in call["input"] and "A區" in call["input"]
    instructions = call["instructions"]
    assert "只根據" in instructions and "必須讀到" in instructions and "「次」" in instructions


def test_rewrite_once_then_pass(tmp_path: Path) -> None:
    bad = llm_output()
    bad["segments"][0]["beats"][0]["narration"] = "每次都把牌蓋著洗勻。"
    llm = FakeLLMProvider(json_outputs=[bad, llm_output()])
    generate_script(llm, _request(tmp_path), tmp_path / "draft")
    assert len(llm.calls) == 2
    second = llm.calls[1].kwargs["input"]
    assert "「次」" in second and "每次都把牌蓋著洗勻" in second


def test_rejected_after_rewrite(tmp_path: Path) -> None:
    bad = llm_output()
    bad["segments"][0]["beats"][0]["subtitle"] = "這次翻開。"
    llm = FakeLLMProvider(json_outputs=[bad, bad])
    with pytest.raises(ScriptRejected) as exc:
        generate_script(llm, _request(tmp_path), tmp_path / "draft")
    assert any("次" in e for e in exc.value.errors)
    assert len(exc.value.outputs) == 2


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (
            lambda o: o["segments"][0]["beats"][1]["cues"][0].__setitem__("target", "main.c9"),
            "main.c9",
        ),
        (lambda o: o["segments"][0]["beats"][1].__setitem__("subtitle", "紅牌放進A區。"), "甲區"),
        (lambda o: o["segments"][1].__setitem__("source_pages", [9]), "9"),
    ],
    ids=["bad-target", "avoid-word", "source-page"],
)
def test_check_failures_trigger_rewrite(tmp_path: Path, mutate, expected: str) -> None:
    bad = llm_output()
    mutate(bad)
    llm = FakeLLMProvider(json_outputs=[bad, bad])
    with pytest.raises(ScriptRejected) as exc:
        generate_script(llm, _request(tmp_path), tmp_path / "draft")
    assert any(expected in e for e in exc.value.errors)
    assert expected in llm.calls[1].kwargs["input"]


def test_avoid_word_message_names_replacement(tmp_path: Path) -> None:
    bad = llm_output()
    bad["segments"][0]["labels"][0]["text"] = "放進A區"
    llm = FakeLLMProvider(json_outputs=[bad, bad])
    with pytest.raises(ScriptRejected) as exc:
        generate_script(llm, _request(tmp_path), tmp_path / "draft")
    message = " ".join(exc.value.errors)
    assert "A區" in message and "甲區" in message


@pytest.mark.parametrize("name", ["rulebook/page5.txt", "rulebook/en-five.txt"])
def test_bad_page_file_name(tmp_path: Path, name: str) -> None:
    write_inputs(tmp_path)
    (tmp_path / name).write_text("x", encoding="utf-8")
    with pytest.raises(ScriptInputError) as exc:
        load_pages(tmp_path, [name])
    assert "<語言>-<頁碼>.txt" in str(exc.value)


def test_missing_input_files(tmp_path: Path) -> None:
    with pytest.raises(ScriptInputError) as exc:
        load_pages(tmp_path, ["rulebook/en-005.txt"])
    assert "en-005.txt" in str(exc.value)
    with pytest.raises(ScriptInputError) as exc:
        load_terms(tmp_path / "terms.json")
    assert "terms.json" in str(exc.value)


def test_instructions_ask_for_representative_card(tmp_path: Path) -> None:
    # 規則寫泛稱（例如「血刃牌」）時，選一張具體的代表牌，素材說明寫明店員可以替換
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    generate_script(llm, _request(tmp_path), tmp_path / "draft")
    instructions = llm.calls[0].kwargs["instructions"]
    assert "泛稱" in instructions and "代表牌" in instructions and "店員可以替換" in instructions


def test_instructions_explain_how_to_target_highlights_and_labels(tmp_path: Path) -> None:
    # 實際產生時，AI 曾把 cue 的 target 寫成 highlight:<key>、label:<key>（2026-11-21）
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    generate_script(llm, _request(tmp_path), tmp_path / "draft")
    instructions = llm.calls[0].kwargs["instructions"]
    assert "直接寫它的 key" in instructions and "不加" in instructions
