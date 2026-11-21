"""用自然語言修改規則影片（spec rules-video-revision，第 2 階段 MR 2）。

一律用 FakeLLMProvider，不連真正的 LLM（AGENTS.md 7.6）；render 用手寫的假 ffmpeg 指令稿。
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.domains.rules_qa.video_commands import main
from app.domains.rules_qa.video_revision import INSTRUCTIONS
from app.integrations.llm.errors import LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider
from tests.integrations.video.support import base_data, fake_ffmpeg, segment, write_game
from tests.rules_qa.video_script_support import coverage_output, coverage_rule, write_inputs

Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def run(make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]) -> Run:
    def _run(*args: str, llm: FakeLLMProvider | None = None, **kwargs: Any) -> tuple[int, str, str]:
        code = main(list(args), settings=make_settings(), llm=llm, **kwargs)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def _game(tmp_path: Path, data: dict[str, Any] | None = None) -> Path:
    return write_inputs(write_game(tmp_path / "game", data or base_data()))


def _video(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "video.json").read_text(encoding="utf-8"))


def _entry(new: dict[str, Any], requested: list[str], summary: str = "改了") -> dict[str, Any]:
    """LLM 回傳的一段：段資料以 JSON 字串表示（段的槽位名稱不固定，無法用 strict schema 描述）。"""
    return {
        "segment_key": new["segment_key"],
        "requested": requested,
        "summary": summary,
        "segment_json": json.dumps(new, ensure_ascii=False),
    }


def _revise(*entries: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "revise",
        "reason": None,
        "segments": list(entries),
        "alternatives": [],
        "candidates": [],
    }


def _gold_to_red(data: dict[str, Any]) -> dict[str, Any]:
    """s1 的 h1 由金框改成紅框。"""
    new = copy.deepcopy(segment(data, "s1"))
    new["highlights"][0]["style"] = "red"
    return new


def _unsupported(*alternatives: dict[str, Any], reason: str = "沒有旋轉動作") -> dict[str, Any]:
    return {
        "kind": "unsupported",
        "reason": reason,
        "segments": [],
        "alternatives": list(alternatives),
        "candidates": [],
    }


def _alternative(title: str, new: dict[str, Any]) -> dict[str, Any]:
    return {"title": title, "description": f"{title}的說明", "segments": [_entry(new, ["cues"])]}


REQUEST = "情況一的金框改成紅框"


# --- 用自然語言修改 ---


def test_replaces_only_listed_segment(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    before = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(before), ["highlights"]))])
    code, out, err = run("revise", str(folder), REQUEST, llm=llm)
    assert code == 0, err
    after = _video(folder)
    assert segment(after, "s1")["highlights"][0]["style"] == "red"
    assert segment(after, "s2") == segment(before, "s2")
    assert "s1" in out and "highlights" in out


@pytest.mark.parametrize("bad_key", ["s9", "s2"], ids=["unknown", "duplicate"])
def test_bad_segment_keys_trigger_rewrite(tmp_path: Path, run: Run, bad_key: str) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    wrong = _gold_to_red(data)
    wrong["segment_key"] = bad_key
    entries = [_entry(wrong, ["highlights"])]
    if bad_key == "s2":  # 同一段出現兩次
        entries.append(_entry(segment(data, "s2"), []))
    good = _revise(_entry(_gold_to_red(data), ["highlights"]))
    llm = FakeLLMProvider(json_outputs=[_revise(*entries), good])
    code, _, err = run("revise", str(folder), REQUEST, llm=llm)
    assert code == 0, err
    assert len(llm.calls) == 2
    assert bad_key in llm.calls[1].kwargs["input"]  # 改寫時帶上錯誤
    assert segment(_video(folder), "s1")["highlights"][0]["style"] == "red"


def test_rewrite_still_failing_writes_nothing(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    before = _video(folder)
    bad = _gold_to_red(before)
    bad["beats"][0]["narration"] = "每次都洗牌。"
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(bad, ["narration"]))] * 2)
    code, _, err = run("revise", str(folder), REQUEST, llm=llm)
    assert code != 0
    assert "次" in err
    assert _video(folder) == before
    for n in (1, 2):
        assert (folder / "revisions" / f"rejected-{n}.json").is_file()
    assert not list((folder / "revisions").glob("*-before.json"))


def test_backup_before_each_revision(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    original = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(original), ["highlights"]))])
    assert run("revise", str(folder), REQUEST, llm=llm)[0] == 0
    first = _video(folder)
    again = copy.deepcopy(segment(first, "s2"))
    again["beats"][0]["subtitle"] = "All done."
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(again, ["subtitle"]))])
    assert run("revise", str(folder), "改字幕", llm=llm)[0] == 0
    backups = folder / "revisions"
    assert json.loads((backups / "1-before.json").read_text(encoding="utf-8")) == original
    assert json.loads((backups / "2-before.json").read_text(encoding="utf-8")) == first


def test_dry_run_saves_pending_only(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    before = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(before), ["highlights"]))])
    code, out, err = run("revise", str(folder), REQUEST, "--dry-run", llm=llm)
    assert code == 0, err
    assert _video(folder) == before
    assert not list((folder / "revisions").glob("*-before.json"))
    pending = json.loads((folder / "revisions" / "pending.json").read_text(encoding="utf-8"))
    assert pending["kind"] == "proposal" and pending["request"] == REQUEST
    assert "s1" in out and "highlights" in out and "--apply" in out


def test_apply_uses_pending_without_calling_llm(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(data), ["highlights"]))])
    assert run("revise", str(folder), REQUEST, "--dry-run", llm=llm)[0] == 0
    idle = FakeLLMProvider(json_outputs=[])
    code, _, err = run("revise", str(folder), "--apply", llm=idle)
    assert code == 0, err
    assert idle.calls == []
    after = _video(folder)
    assert segment(after, "s1")["highlights"][0]["style"] == "red"
    assert segment(after, "s1")["revisions"][-1]["request"] == REQUEST
    assert (folder / "revisions" / "1-before.json").is_file()
    assert not (folder / "revisions" / "pending.json").exists()


def test_apply_refuses_when_video_changed(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(data), ["highlights"]))])
    assert run("revise", str(folder), REQUEST, "--dry-run", llm=llm)[0] == 0
    segment(data, "s2")["beats"][0]["subtitle"] = "Edited by hand."
    (folder / "video.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, _, err = run("revise", str(folder), "--apply", llm=FakeLLMProvider(json_outputs=[]))
    assert code != 0
    assert "dry-run" in err or "重跑" in err
    assert segment(_video(folder), "s1")["highlights"][0]["style"] == "gold"


def test_unrequested_field_is_flagged(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    new = _gold_to_red(_video(folder))
    new["beats"][0]["narration"] = "d" * 12  # 沒被要求，卻改了旁白
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(new, ["highlights"]))] * 2)
    code, out, _ = run("revise", str(folder), REQUEST, "--dry-run", llm=llm)
    assert code == 0
    assert "未被要求修改" in out and "narration" in out
    code, out, _ = run("revise", str(folder), REQUEST, llm=llm)
    assert code == 0 and "未被要求修改" in out
    record = segment(_video(folder), "s1")["revisions"][-1]
    assert record["changed"] == ["narration", "highlights"]
    assert record["unrequested"] == ["narration"]


def test_instructions_keep_unrequested_fields() -> None:
    assert "沒被點名的欄位" in INSTRUCTIONS


def test_more_than_two_segments_reminds(tmp_path: Path, run: Run) -> None:
    data = base_data()
    third = copy.deepcopy(segment(data, "s2"))
    third["segment_key"] = "s3"
    third["beats"][0]["beat_key"] = "b4"
    data["segments"].append(third)
    folder = _game(tmp_path, data)
    entries = []
    for key in ("s1", "s2", "s3"):
        new = copy.deepcopy(segment(data, key))
        new["beats"][-1]["subtitle"] = f"Changed {key}."
        entries.append(_entry(new, ["subtitle"]))
    code, out, err = run(
        "revise",
        str(folder),
        "每段最後一句字幕都改",
        llm=FakeLLMProvider(json_outputs=[_revise(*entries)]),
    )
    assert code == 0, err
    assert "改了 3 段" in out


# --- 目標不明確、指定段 ---


def test_ambiguous_target_lists_candidates(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    before = _video(folder)
    ambiguous = {
        "kind": "ambiguous",
        "reason": "兩段都有符合的地方",
        "segments": [],
        "alternatives": [],
        "candidates": [
            {"segment_key": "s1", "reason": "有金框"},
            {"segment_key": "s2", "reason": "也有紅色的牌"},
        ],
    }
    code, out, _ = run(
        "revise", str(folder), "改成紅色", llm=FakeLLMProvider(json_outputs=[ambiguous])
    )
    assert _video(folder) == before
    assert "s1" in out and "s2" in out and "--segment" in out
    assert not (folder / "revisions" / "pending.json").exists()
    assert code == 0


def test_segment_option_restricts_target(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    s2 = copy.deepcopy(segment(data, "s2"))
    s2["beats"][0]["subtitle"] = "All done."
    llm = FakeLLMProvider(
        json_outputs=[
            _revise(_entry(_gold_to_red(data), ["highlights"])),  # 指定 s2 卻改了 s1
            _revise(_entry(s2, ["subtitle"])),
        ]
    )
    code, _, err = run("revise", str(folder), "改字幕", "--segment", "s2", llm=llm)
    assert code == 0, err
    assert len(llm.calls) == 2
    assert "s2" in llm.calls[0].kwargs["input"]
    after = _video(folder)
    assert segment(after, "s1")["highlights"][0]["style"] == "gold"
    assert segment(after, "s2")["beats"][0]["subtitle"] == "All done."


def test_unknown_segment_option_does_not_call_llm(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    llm = FakeLLMProvider(json_outputs=[])
    code, _, err = run("revise", str(folder), "改字幕", "--segment", "s9", llm=llm)
    assert code != 0 and "s9" in err
    assert llm.calls == []


# --- 修改紀錄 ---


def test_revision_record_and_state(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    llm = FakeLLMProvider(
        json_outputs=[_revise(_entry(_gold_to_red(data), ["highlights"], "h1 由金框改為紅框"))]
    )
    assert run("revise", str(folder), REQUEST, llm=llm)[0] == 0
    after = _video(folder)
    s1 = segment(after, "s1")
    record = s1["revisions"][-1]
    assert record["number"] == 1 and record["by"] == "staff" and record["kind"] == "revision"
    assert record["request"] == REQUEST and record["summary"] == "h1 由金框改為紅框"
    assert record["changed"] == ["highlights"] and record["unrequested"] == []
    assert record["at"].endswith("Z")
    assert s1["state"]["status"] == "stale"
    assert "revisions" not in segment(after, "s2")
    assert "state" not in segment(after, "s2")


def test_render_marks_revised_segment_rendered(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(data), ["highlights"]))])
    assert run("revise", str(folder), REQUEST, llm=llm)[0] == 0
    ffmpeg = fake_ffmpeg(tmp_path / "bin")
    code, _, err = run("render", str(folder), ffmpeg=ffmpeg)
    assert code == 0, err
    after = _video(folder)
    state = segment(after, "s1")["state"]
    assert state["status"] == "rendered"
    assert isinstance(state["content_hash"], str) and len(state["content_hash"]) == 64
    assert "state" not in segment(after, "s2")  # 沒被修改過的段不動


def test_render_without_revisions_leaves_file_untouched(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    before = (folder / "video.json").read_bytes()
    code, _, err = run("render", str(folder), ffmpeg=fake_ffmpeg(tmp_path / "bin"))
    assert code == 0, err
    assert (folder / "video.json").read_bytes() == before


# --- 超出版型能力 ---


def test_unsupported_saves_alternatives_and_request(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    before = copy.deepcopy(data)
    flip = copy.deepcopy(segment(data, "s1"))
    flip["beats"][1]["cues"][1] = {"at": 1.0, "do": "flip", "target": "main.c1"}
    alternatives = [_alternative("改成翻牌", flip), _alternative("改成移動", segment(data, "s1"))]
    llm = FakeLLMProvider(json_outputs=[_unsupported(*alternatives)])
    code, out, err = run("revise", str(folder), "讓牌旋轉著飛進盤面", llm=llm)
    assert code == 0, err
    assert _video(folder) == before
    assert "改成翻牌" in out and "改成移動" in out and "--choose" in out
    pending = json.loads((folder / "revisions" / "pending.json").read_text(encoding="utf-8"))
    assert pending["kind"] == "alternatives" and len(pending["alternatives"]) == 2
    requests = json.loads((folder / "revisions" / "requests.json").read_text(encoding="utf-8"))
    assert len(requests) == 1
    assert (
        requests[0]["request"] == "讓牌旋轉著飛進盤面" and requests[0]["reason"] == "沒有旋轉動作"
    )


def test_unknown_action_goes_to_alternatives(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    before = copy.deepcopy(data)
    rotate = copy.deepcopy(segment(data, "s1"))
    rotate["beats"][1]["cues"][1] = {"at": 1.0, "do": "rotate", "target": "main.c1"}
    alternatives = _unsupported(_alternative("改成翻牌", segment(data, "s1")), reason="不支援旋轉")
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(rotate, ["cues"])), alternatives])
    code, out, err = run("revise", str(folder), "讓牌旋轉", llm=llm)
    assert code == 0, err
    assert len(llm.calls) == 2
    assert "rotate" in llm.calls[1].kwargs["input"]  # 第二次是要替代做法，不是改寫
    assert _video(folder) == before
    assert "改成翻牌" in out
    requests = json.loads((folder / "revisions" / "requests.json").read_text(encoding="utf-8"))
    assert requests[0]["unsupported_actions"] == ["rotate"]


def test_choose_applies_alternative(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    flip = copy.deepcopy(segment(data, "s1"))
    flip["beats"][1]["cues"][1] = {"at": 1.0, "do": "flip", "target": "main.c1"}
    move = copy.deepcopy(segment(data, "s1"))
    move["beats"][1]["cues"][1]["to"] = "sidebar@zone_b"
    alternatives = [_alternative("改成翻牌", flip), _alternative("改成移到別區", move)]
    llm = FakeLLMProvider(json_outputs=[_unsupported(*alternatives)])
    assert run("revise", str(folder), "讓牌旋轉著飛進盤面", llm=llm)[0] == 0
    idle = FakeLLMProvider(json_outputs=[])
    code, _, err = run("revise", str(folder), "--choose", "2", llm=idle)
    assert code == 0, err
    assert idle.calls == []
    s1 = segment(_video(folder), "s1")
    assert s1["beats"][1]["cues"][1]["to"] == "sidebar@zone_b"
    record = s1["revisions"][-1]
    assert record["kind"] == "alternative" and record["request"] == "讓牌旋轉著飛進盤面"
    assert not (folder / "revisions" / "pending.json").exists()


@pytest.mark.parametrize("situation", ["no_pending", "out_of_range", "proposal_pending"])
def test_choose_errors(tmp_path: Path, run: Run, situation: str) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    if situation == "out_of_range":
        llm = FakeLLMProvider(
            json_outputs=[_unsupported(_alternative("改成翻牌", segment(data, "s1")))]
        )
        assert run("revise", str(folder), "旋轉", llm=llm)[0] == 0
    if situation == "proposal_pending":
        llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(data), ["highlights"]))])
        assert run("revise", str(folder), REQUEST, "--dry-run", llm=llm)[0] == 0
    before = _video(folder)
    code, _, err = run("revise", str(folder), "--choose", "3", llm=FakeLLMProvider(json_outputs=[]))
    assert code != 0 and err
    assert _video(folder) == before


def test_apply_without_proposal_fails(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    code, _, err = run("revise", str(folder), "--apply", llm=FakeLLMProvider(json_outputs=[]))
    assert code != 0 and "pending" in err


# --- LLM 無法使用 ---


def test_llm_unavailable(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    before = _video(folder)
    llm = FakeLLMProvider(json_outputs=[LLMUnavailable("連不上")])
    code, _, err = run("revise", str(folder), REQUEST, llm=llm)
    assert code != 0 and "LLM" in err
    assert _video(folder) == before


# --- 寫入後的涵蓋檢查（只警告，不擋寫入）---


def test_coverage_warnings_only_for_changed_segments(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    related = coverage_rule(
        rule_id="R1", narration=("incomplete", ["b1"], "同時翻開"), source="Reveal together."
    )
    unrelated = coverage_rule(
        rule_id="R2",
        narration=("incomplete", ["b3"], "全部結束"),
        subtitle=("complete", ["b3"], None),  # 預設對應 b1；改成只對應沒被改的 s2
        source="Unrelated rule.",
    )
    llm = FakeLLMProvider(
        json_outputs=[
            _revise(_entry(_gold_to_red(data), ["highlights"])),
            coverage_output([related, unrelated]),
        ]
    )
    code, out, err = run("revise", str(folder), REQUEST, "--pages", "rulebook/en-005.txt", llm=llm)
    assert code == 0, err
    assert segment(_video(folder), "s1")["highlights"][0]["style"] == "red"
    text = out + err
    assert "R1" in text and "同時翻開" in text
    assert "R2" not in text  # 和被改的段無關
    assert not (folder / "coverage.json").exists()  # 不覆寫資料夾裡的涵蓋檢查結果


def test_coverage_failure_only_warns(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    llm = FakeLLMProvider(
        json_outputs=[
            _revise(_entry(_gold_to_red(data), ["highlights"])),
            LLMUnavailable("連不上"),
        ]
    )
    code, out, err = run("revise", str(folder), REQUEST, "--pages", "rulebook/en-005.txt", llm=llm)
    assert code == 0
    assert "涵蓋檢查" in out + err
    assert segment(_video(folder), "s1")["highlights"][0]["style"] == "red"


def test_without_pages_skips_coverage(tmp_path: Path, run: Run) -> None:
    folder = _game(tmp_path)
    data = _video(folder)
    llm = FakeLLMProvider(json_outputs=[_revise(_entry(_gold_to_red(data), ["highlights"]))])
    code, out, _ = run("revise", str(folder), REQUEST, llm=llm)
    assert code == 0
    assert "略過涵蓋檢查" in out
    assert len(llm.calls) == 1


# --- 本機驗收（tasks 3.3）發現的問題 ---


def test_missing_segment_key_in_json_is_filled(tmp_path: Path, run: Run) -> None:
    # 真的 LLM 在 segment_json 裡省略了 segment_key（外層的 segment_key 有寫）
    folder = _game(tmp_path)
    new = _gold_to_red(_video(folder))
    entry = _entry(new, ["highlights"])
    body = json.loads(entry["segment_json"])
    del body["segment_key"]
    entry["segment_json"] = json.dumps(body)
    llm = FakeLLMProvider(json_outputs=[_revise(entry)])
    code, _, err = run("revise", str(folder), REQUEST, llm=llm)
    assert code == 0, err
    assert len(llm.calls) == 1
    assert segment(_video(folder), "s1")["highlights"][0]["style"] == "red"


def test_invalid_alternative_triggers_rewrite(tmp_path: Path, run: Run) -> None:
    # 替代做法在產生時就檢查，存進 pending.json 的一定能套用
    folder = _game(tmp_path)
    data = _video(folder)
    bad = copy.deepcopy(segment(data, "s1"))
    bad["beats"][0]["narration"] = "每次都洗牌。"
    good = copy.deepcopy(segment(data, "s1"))
    good["beats"][1]["cues"][1] = {"at": 1.0, "do": "flip", "target": "main.c1"}
    llm = FakeLLMProvider(
        json_outputs=[
            _unsupported(_alternative("壞的", bad)),
            _unsupported(_alternative("改成翻牌", good)),
        ]
    )
    code, out, err = run("revise", str(folder), "讓牌旋轉", llm=llm)
    assert code == 0, err
    assert len(llm.calls) == 2
    assert "次" in llm.calls[1].kwargs["input"]
    assert "改成翻牌" in out and "壞的" not in out
    assert run("revise", str(folder), "--choose", "1", llm=FakeLLMProvider(json_outputs=[]))[0] == 0
