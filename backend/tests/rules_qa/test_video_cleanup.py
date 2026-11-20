"""LLM 輸出的格式小錯自動清理（2026-11-21 永傑同意的 C1–C4）。

只清這四種；清理後仍要通過所有檢查，其他錯誤照舊走改寫。每次清了什麼都記錄下來。
"""

from pathlib import Path

import pytest

from app.domains.rules_qa.video_script import (
    CleanupRecord,
    ScriptRejected,
    ScriptRequest,
    clean_format,
    generate_script,
    load_pages,
    load_terms,
)
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.video import parse_video
from tests.rules_qa.video_script_support import llm_output, write_inputs


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


def _move_cue(raw: dict) -> dict:
    return raw["segments"][0]["beats"][1]["cues"][1]


def test_c1_spaces_around_separators() -> None:
    raw = llm_output()
    _move_cue(raw)["to"] = "sidebar@ zone_a"
    _move_cue(raw)["target"] = "main .c1"
    cleaned, records = clean_format(raw)
    assert _move_cue(cleaned)["to"] == "sidebar@zone_a"
    assert _move_cue(cleaned)["target"] == "main.c1"
    assert {r.rule for r in records} == {"C1"}
    assert any(r.before == "sidebar@ zone_a" and r.after == "sidebar@zone_a" for r in records)


def test_c2_leading_trailing_spaces() -> None:
    raw = llm_output()
    raw["segments"][0]["highlights"][0]["key"] = " h1 "
    raw["assets"][0]["asset_key"] = "back "
    cleaned, records = clean_format(raw)
    assert cleaned["segments"][0]["highlights"][0]["key"] == "h1"
    assert cleaned["assets"][0]["asset_key"] == "back"
    assert {r.rule for r in records} == {"C2"}


def test_c3_full_width_separators() -> None:
    raw = llm_output()
    _move_cue(raw)["to"] = "sidebar＠zone_a"
    _move_cue(raw)["target"] = "main．c1"
    cleaned, records = clean_format(raw)
    assert _move_cue(cleaned)["to"] == "sidebar@zone_a"
    assert _move_cue(cleaned)["target"] == "main.c1"
    assert {r.rule for r in records} == {"C3"}


def test_c4_highlight_prefix_only_when_key_exists() -> None:
    raw = llm_output()
    cues = raw["segments"][0]["beats"][1]["cues"]
    cues.append({"at": 1.5, "do": "show", "target": "highlight:h1", "to": None})
    cues.append({"at": 1.6, "do": "show", "target": "label:nope", "to": None})
    cleaned, records = clean_format(raw)
    new_cues = cleaned["segments"][0]["beats"][1]["cues"]
    assert new_cues[2]["target"] == "h1"
    assert new_cues[3]["target"] == "label:nope"  # 這一段沒有 nope，不清
    assert [r.rule for r in records] == ["C4"]


def test_nothing_to_clean() -> None:
    raw = llm_output()
    cleaned, records = clean_format(raw)
    assert cleaned == raw and records == []


def test_cleaned_output_still_checked_and_logged(tmp_path: Path) -> None:
    raw = llm_output()
    _move_cue(raw)["to"] = "sidebar@ zone_a"
    llm = FakeLLMProvider(json_outputs=[raw])
    log: list[CleanupRecord] = []
    data = generate_script(llm, _request(tmp_path), tmp_path / "draft", cleanup_log=log)
    parse_video(data, tmp_path / "draft", draft=True)
    assert len(llm.calls) == 1  # 清理後通過，不需要改寫
    assert [r.rule for r in log] == ["C1"] and log[0].attempt == 1


def test_other_errors_still_rewrite(tmp_path: Path) -> None:
    raw = llm_output()
    _move_cue(raw)["to"] = "sidebar@ zone_a"  # 會被清
    _move_cue(raw)["target"] = "main.c9"  # 不在清單內，照舊要改寫
    llm = FakeLLMProvider(json_outputs=[raw, raw])
    with pytest.raises(ScriptRejected) as exc:
        generate_script(llm, _request(tmp_path), tmp_path / "draft")
    assert any("main.c9" in e for e in exc.value.errors)
    assert len(llm.calls) == 2
