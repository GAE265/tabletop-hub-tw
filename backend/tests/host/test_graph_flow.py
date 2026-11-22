"""圖之一：換節點、結束、整局記憶（host spec §3、§9）。

對應情境 F-01 到 F-11、F-13，C-06 到 C-08，M-01、M-02、M-04、M-05。
"""

import ast
from pathlib import Path

import pytest

from app.domains.host import content
from app.domains.host import graph as graph_module
from app.domains.host.graph import HostEvent, HostGraph, Speak, StateChanged
from tests.host.graph_support import (
    finish_playback,
    new_hosting,
    only_speak,
    position,
    press,
    say,
    speaks,
    to_setup,
    to_turn,
)


def assert_fixed_line(speak: Speak, code: str, **kwargs: object) -> None:
    assert speak.kind == "line"
    assert speak.code == code
    assert content.fixed_line(code, **kwargs) in speak.text  # type: ignore[arg-type]


def assert_rule_points(speak: Speak, *, turn_number: int, phase_number: int) -> None:
    expected = content.rule_points(turn_number=turn_number, phase_number=phase_number)
    assert speak.kind == "rule_points"
    assert speak.phase_number == phase_number
    assert speak.version == expected.version
    assert speak.text == content.rule_points_text(
        turn_number=turn_number, phase_number=phase_number
    )


# --- 流程 ---


def test_f01_opening_then_setup_after_playback() -> None:
    graph, sid = new_hosting(7)
    assert position(graph, sid) == ("opening", None, None)

    opening = graph.handle(sid, HostEvent.connected())
    assert_fixed_line(only_speak(opening), "opening")
    assert position(graph, sid) == ("opening", None, None)

    setup = finish_playback(graph, sid, opening)
    assert_fixed_line(only_speak(setup), "setup")
    assert position(graph, sid) == ("setup", None, None)


def test_setup_waits_for_next_after_playback() -> None:
    graph, sid = new_hosting(7)
    setup = to_setup(graph, sid)
    after = finish_playback(graph, sid, setup)
    assert speaks(after) == []
    assert position(graph, sid) == ("setup", None, None)


def test_f02_setup_next_runs_through_the_night_into_turn_1() -> None:
    graph, sid = new_hosting(7)
    finish_playback(graph, sid, to_setup(graph, sid))

    night_1 = press(graph, sid, "next")
    assert_fixed_line(only_speak(night_1), "night_1")
    assert position(graph, sid) == ("night_1", None, None)

    night_2 = finish_playback(graph, sid, night_1)
    assert_fixed_line(only_speak(night_2), "night_2")
    assert position(graph, sid) == ("night_2", None, None)

    turn_1 = finish_playback(graph, sid, night_2)
    assert_rule_points(only_speak(turn_1), turn_number=1, phase_number=1)
    assert only_speak(turn_1).version == "full"
    assert position(graph, sid) == ("turn", 1, 1)


def test_f03_next_twice_gives_phase_2_and_3_full_version() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)

    phase_2 = press(graph, sid, "next")
    assert_rule_points(only_speak(phase_2), turn_number=1, phase_number=2)
    assert only_speak(phase_2).version == "full"
    finish_playback(graph, sid, phase_2)

    phase_3 = press(graph, sid, "next")
    assert_rule_points(only_speak(phase_3), turn_number=1, phase_number=3)
    assert only_speak(phase_3).version == "full"
    assert position(graph, sid) == ("turn", 1, 3)


def test_turn_phase_does_not_auto_advance_after_playback() -> None:
    graph, sid = new_hosting(7)
    outcome = to_turn(graph, sid, 1, 1)
    assert position(graph, sid) == ("turn", 1, 1)
    # to_turn 已經回報播完；再回報一次同一段也不動
    again = graph.handle(sid, HostEvent.playback_done(only_speak(outcome).segment_id))
    assert speaks(again) == []
    assert position(graph, sid) == ("turn", 1, 1)


def test_f04_turn_1_phase_3_next_goes_to_turn_2_short_version() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 3)
    outcome = press(graph, sid, "next")
    assert position(graph, sid) == ("turn", 2, 1)
    assert_rule_points(only_speak(outcome), turn_number=2, phase_number=1)
    assert only_speak(outcome).version == "short"


def test_f05_previous_from_turn_2_goes_back_to_turn_1_phase_3_full() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 1)
    outcome = press(graph, sid, "previous")
    assert position(graph, sid) == ("turn", 1, 3)
    assert_rule_points(only_speak(outcome), turn_number=1, phase_number=3)
    assert only_speak(outcome).version == "full"


def test_f06_previous_from_turn_1_phase_1_goes_back_to_night_2() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    outcome = press(graph, sid, "previous")
    assert position(graph, sid) == ("night_2", None, None)
    assert_fixed_line(only_speak(outcome), "night_2")


def test_f07_previous_at_opening_does_nothing() -> None:
    graph, sid = new_hosting(7)
    graph.handle(sid, HostEvent.connected())
    outcome = press(graph, sid, "previous")
    assert outcome.effects == []
    assert position(graph, sid) == ("opening", None, None)


@pytest.mark.parametrize(
    "start, expected",
    [
        ("setup", "opening"),
        ("night_1", "setup"),
        ("night_2", "night_1"),
    ],
)
def test_previous_between_opening_and_first_turn(start: str, expected: str) -> None:
    graph, sid = new_hosting(7)
    setup = to_setup(graph, sid)
    if start in ("night_1", "night_2"):
        finish_playback(graph, sid, setup)
        night_1 = press(graph, sid, "next")
        if start == "night_2":
            finish_playback(graph, sid, night_1)
    assert position(graph, sid)[0] == start

    outcome = press(graph, sid, "previous")
    assert position(graph, sid) == (expected, None, None)
    assert_fixed_line(only_speak(outcome), expected)


def test_previous_inside_a_turn() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    outcome = press(graph, sid, "previous")
    assert position(graph, sid) == ("turn", 2, 2)
    assert_rule_points(only_speak(outcome), turn_number=2, phase_number=2)


def test_f08_seven_players_board_full_next_ends_without_winner() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 6, 3)
    outcome = press(graph, sid, "next")
    snapshot = graph.snapshot(sid)
    assert snapshot.status == "ended"
    assert snapshot.step == "ended"
    assert snapshot.winner is None
    # 回合與階段保留結束前的值
    assert (snapshot.turn_number, snapshot.phase_number) == (6, 3)
    assert_fixed_line(only_speak(outcome), "end_plain")


def test_seven_players_turn_5_phase_3_next_is_not_the_end() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 5, 3)
    press(graph, sid, "next")
    assert position(graph, sid) == ("turn", 6, 1)


def test_f09_five_players_board_has_four_slots() -> None:
    graph, sid = new_hosting(5)
    to_turn(graph, sid, 4, 3)
    outcome = press(graph, sid, "next")
    snapshot = graph.snapshot(sid)
    assert snapshot.status == "ended"
    assert snapshot.winner is None
    assert_fixed_line(only_speak(outcome), "end_plain")


def test_f10_end_button_ends_without_winner() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 2)
    outcome = press(graph, sid, "end")
    snapshot = graph.snapshot(sid)
    assert snapshot.status == "ended"
    assert snapshot.winner is None
    assert (snapshot.turn_number, snapshot.phase_number) == (2, 2)
    assert_fixed_line(only_speak(outcome), "end_plain")


@pytest.mark.parametrize("action", ["next", "previous", "pause", "resume"])
def test_f11_after_end_commands_do_nothing(action: str) -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 2)
    finish_playback(graph, sid, press(graph, sid, "end"))
    before = graph.memory(sid)

    outcome = press(graph, sid, action)

    assert outcome.effects == []
    assert graph.memory(sid) == before
    assert graph.snapshot(sid).status == "ended"


@pytest.mark.parametrize("text", ["下一步", "上一步", "暫停", "等一下", "繼續", "結束了"])
def test_f11_after_end_voice_commands_do_nothing(text: str) -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 2)
    finish_playback(graph, sid, press(graph, sid, "end"))
    before = graph.memory(sid)
    outcome = say(graph, sid, text)
    assert outcome.effects == []
    assert graph.memory(sid) == before


def test_f13_night_1_interrupted_without_playback_done_does_not_advance() -> None:
    graph, sid = new_hosting(7)
    finish_playback(graph, sid, to_setup(graph, sid))
    night_1 = press(graph, sid, "next")
    assert position(graph, sid) == ("night_1", None, None)

    # 別的一段播完（不是夜晚第一步那一段）不算
    other = graph.handle(sid, HostEvent.playback_done(only_speak(night_1).segment_id + 100))
    assert other.effects == []
    assert position(graph, sid) == ("night_1", None, None)


def test_state_changed_carries_the_new_snapshot() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    outcome = press(graph, sid, "next")
    changes = [effect for effect in outcome.effects if isinstance(effect, StateChanged)]
    assert len(changes) == 1
    assert changes[0].snapshot == graph.snapshot(sid)
    assert changes[0].snapshot.phase_number == 2
    # 現況先變，再請主持人開口
    assert outcome.effects.index(changes[0]) < outcome.effects.index(only_speak(outcome))


# --- 結束台詞：C-06 到 C-08 ---


def test_c06_white_rose_won() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 3, 3)
    outcome = say(graph, sid, "白薔薇贏了")
    assert_fixed_line(only_speak(outcome), "end_white_rose")
    assert graph.snapshot(sid).winner == "white_rose"


def test_c07_blood_blade_won() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 3, 3)
    outcome = say(graph, sid, "血刃贏了")
    assert_fixed_line(only_speak(outcome), "end_blood_blade")
    assert graph.snapshot(sid).winner == "blood_blade"


def test_c08_just_ended() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 3, 3)
    outcome = say(graph, sid, "結束了")
    assert_fixed_line(only_speak(outcome), "end_plain")
    assert graph.snapshot(sid).status == "ended"
    assert graph.snapshot(sid).winner is None


# --- 整局記憶：M-01、M-02、M-04、M-05 ---


def test_memory_starts_with_the_three_settings() -> None:
    graph, sid = new_hosting(8, turn_taking_mode="push_to_talk", voice="female")
    memory = graph.memory(sid)
    assert memory["player_count"] == 8
    assert memory["turn_taking_mode"] == "push_to_talk"
    assert memory["voice"] == "female"
    assert (memory["step"], memory["turn_number"], memory["phase_number"]) == (
        "opening",
        None,
        None,
    )
    assert memory["winner"] is None
    snapshot = graph.snapshot(sid)
    assert snapshot.status == "active"
    assert (snapshot.player_count, snapshot.turn_taking_mode, snapshot.voice) == (
        8,
        "push_to_talk",
        "female",
    )


def test_m01_next_updates_memory() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 3)
    press(graph, sid, "next")
    memory = graph.memory(sid)
    assert (memory["step"], memory["turn_number"], memory["phase_number"]) == ("turn", 2, 1)


def test_m02_previous_updates_memory() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 1)
    press(graph, sid, "previous")
    memory = graph.memory(sid)
    assert (memory["step"], memory["turn_number"], memory["phase_number"]) == ("turn", 1, 3)


def test_m04_blood_blade_won_is_remembered() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    say(graph, sid, "血刃贏了")
    memory = graph.memory(sid)
    assert memory["step"] == "ended"
    assert memory["winner"] == "blood_blade"
    assert graph.snapshot(sid).status == "ended"


def test_m05_a_sentence_that_fails_verification_leaves_memory_unchanged() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 1)
    before = graph.memory(sid)
    outcome = say(graph, sid, "你下一步要出什麼")
    assert outcome.effects == []
    assert outcome.result == {"verified": False, "action": None}
    assert graph.memory(sid) == before


def test_each_hosting_has_its_own_memory() -> None:
    graph, first = new_hosting(7)
    _, second = new_hosting(5, graph=graph)
    to_turn(graph, first, 2, 2)
    assert position(graph, second) == ("opening", None, None)
    assert graph.memory(second)["player_count"] == 5


def test_delete_clears_memory() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 2)
    assert graph.exists(sid) is True
    graph.delete(sid)
    assert graph.exists(sid) is False
    with pytest.raises(KeyError):
        graph.snapshot(sid)


def test_unknown_hosting_raises_key_error() -> None:
    with pytest.raises(KeyError):
        HostGraph().handle("no-such-hosting", HostEvent.command("next"))


def test_mermaid_names_the_nodes() -> None:
    text = HostGraph().mermaid()
    for node in ("verify_voice_command", "change_step", "end_hosting"):
        assert node in text


# --- 分層（AGENTS.md §4.2） ---


def test_graph_does_not_import_fastapi_or_vendor_sdks() -> None:
    tree = ast.parse(Path(graph_module.__file__).read_text(encoding="utf-8"))
    forbidden = ("fastapi", "starlette", "openai", "dashscope", "azure", "websockets")
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert name.split(".")[0] not in forbidden, name
