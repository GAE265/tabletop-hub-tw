"""規則涵蓋檢查（spec rules-video-script「規則涵蓋檢查」）。

一律用 FakeLLMProvider，不連真正的 LLM（AGENTS.md 7.6）。
"""

from pathlib import Path

from app.domains.rules_qa.video_coverage import check_coverage
from app.domains.rules_qa.video_script import load_pages
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.video import load_video
from tests.integrations.video.support import base_data, write_game
from tests.rules_qa.video_script_support import (
    FAKE_PAGE,
    FAKE_REFERENCE_PAGE,
    coverage_output,
    coverage_rule,
    write_inputs,
)


def _run(tmp_path: Path, output: dict):
    folder = write_inputs(write_game(tmp_path, base_data()))
    llm = FakeLLMProvider(json_outputs=[output])
    report = check_coverage(
        llm, load_video(folder, draft=True), load_pages(folder, ["rulebook/en-005.txt"])
    )
    return llm, report


def test_narration_shorter_than_subtitle(tmp_path: Path) -> None:
    rule = coverage_rule(
        narration=("incomplete", ["b2"], "或所有輪都結束"),
        subtitle=("complete", ["b2"], None),
    )
    _, report = _run(tmp_path, coverage_output([rule]))
    assert report.rules[0].narration_shorter is True
    markdown = report.markdown()
    assert "旁白比字幕少條件" in markdown and "或所有輪都結束" in markdown
    assert rule["source"] in markdown


def test_both_incomplete(tmp_path: Path) -> None:
    rule = coverage_rule(
        narration=("incomplete", ["b1"], "同時翻開"), subtitle=("incomplete", ["b1"], "同時翻開")
    )
    _, report = _run(tmp_path, coverage_output([rule]))
    checked = report.rules[0]
    assert checked.narration.status == checked.subtitle.status == "incomplete"
    assert checked.narration_shorter is False
    assert report.markdown().count("不完整") >= 2


def test_rule_not_covered(tmp_path: Path) -> None:
    rule = coverage_rule(narration=("missing", [], None), subtitle=("missing", [], None))
    _, report = _run(tmp_path, coverage_output([rule]))
    assert "未涵蓋" in report.markdown()


def test_contradiction_or_extra_rule_listed(tmp_path: Path) -> None:
    problem = {
        "beat_key": "b3",
        "track": "subtitle",
        "kind": "not_in_rulebook",
        "text": "Done.",
        "reason": "原文沒有這條規則",
    }
    _, report = _run(tmp_path, coverage_output(problems=[problem]))
    markdown = report.markdown()
    assert "b3" in markdown and "原文沒有這條規則" in markdown and "字幕" in markdown


def test_all_complete(tmp_path: Path) -> None:
    _, report = _run(tmp_path, coverage_output())
    assert report.has_issues is False
    assert "沒有發現問題" in report.markdown()


def test_llm_input_only_pages_narration_subtitle(tmp_path: Path) -> None:
    llm, _ = _run(tmp_path, coverage_output())
    text = llm.calls[0].kwargs["input"]
    assert FAKE_PAGE.splitlines()[0] in text
    assert "b1" in text and "a" * 12 in text and "Shuffle and flip the cards." in text
    # 不含參考頁、素材、槽位、動作。「flip」會出現在字幕裡，
    # 所以改用只在動作與槽位資料出現的字串
    for absent in (
        FAKE_REFERENCE_PAGE.splitlines()[0],
        "board",
        "sidebar@",
        "back.png",
        "main.c2",
        "main_title",
    ):
        assert absent not in text


def test_unknown_beat_key_marked_unmatched(tmp_path: Path) -> None:
    rule = coverage_rule(narration=("complete", ["b9"], None))
    _, report = _run(tmp_path, coverage_output([rule]))
    assert report.rules[0].unmatched_beats == ["b9"]
    assert "無法對應" in report.markdown()


# --- 規則分類（2026-11-21 永傑決定）：條件、動作、目的說明 ---


def test_schema_asks_for_category() -> None:
    from app.domains.rules_qa.video_coverage import INSTRUCTIONS, SCHEMA

    rule = SCHEMA.schema["properties"]["rules"]["items"]
    assert rule["properties"]["category"]["enum"] == ["condition", "action", "purpose"]
    assert "category" in rule["required"]
    assert "目的說明" in INSTRUCTIONS


def test_purpose_rule_is_a_hint_not_an_omission(tmp_path: Path) -> None:
    purpose = coverage_rule(
        rule_id="R2",
        category="purpose",
        source="so that nobody can tell who played which card.",
        narration=("missing", [], "讓人無法判斷誰打出哪張牌"),
        subtitle=("complete", ["b1"], None),
    )
    _, report = _run(tmp_path, coverage_output([coverage_rule(), purpose]))
    checked = report.rules[1]
    assert checked.has_issue is False
    assert checked.narration_shorter is False
    assert report.has_issues is False
    markdown = report.markdown()
    # 不隱藏：另列在「提示」，不算漏講
    assert "提示" in markdown and "不算漏講" in markdown and purpose["source"] in markdown
    assert "旁白比字幕少條件" not in markdown


def test_category_shown_in_table(tmp_path: Path) -> None:
    condition = coverage_rule(
        rule_id="R3",
        category="condition",
        narration=("incomplete", ["b2"], "沒有血刃牌時"),
        subtitle=("complete", ["b2"], None),
    )
    _, report = _run(tmp_path, coverage_output([condition]))
    assert "| R3 | 條件 |" in report.markdown()
