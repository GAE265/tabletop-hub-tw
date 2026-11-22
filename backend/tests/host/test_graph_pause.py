"""圖之二：主持暫停、繼續、被打斷的那一段、閒聊（host spec §6）。

對應情境 P-01 到 P-16、F-12、M-03。另外有重新連線時圖要交回什麼（spec §9，
M-06、T-02、W-13 在轉送那一段才測得到完整的流程，這裡先測圖的部分）。
"""

import pytest

from app.domains.host import content
from app.domains.host.graph import (
    Flush,
    HostEvent,
    HostGraph,
    Outcome,
    Speak,
    StartThinking,
    StateChanged,
    ToolOutput,
)
from tests.host.fakes import FakeRulesLookup, FakeThinkingModel
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
    to_turn_speaking,
)

QUESTION = "整桌都不出牌可以嗎"


def hosting_with_rules() -> tuple[HostGraph, str]:
    graph = HostGraph(rules_lookup=FakeRulesLookup(), thinking_model=FakeThinkingModel())
    return new_hosting(7, graph=graph)


def flushes(outcome: Outcome) -> list[Flush]:
    return [effect for effect in outcome.effects if isinstance(effect, Flush)]


def tool_outputs(outcome: Outcome) -> list[ToolOutput]:
    return [effect for effect in outcome.effects if isinstance(effect, ToolOutput)]


def assert_same_rule_points(again: Speak, first: Speak) -> None:
    assert again.kind == "rule_points"
    assert (again.text, again.phase_number, again.version) == (
        first.text,
        first.phase_number,
        first.version,
    )
    # 重講是新的一段，編號不同
    assert again.segment_id != first.segment_id


def assert_back_to(speak: Speak, **where: object) -> None:
    assert speak.kind == "line"
    assert speak.code == "back_to"
    assert content.back_to_line(**where) in speak.text  # type: ignore[arg-type]


def cut_by_chatter(graph: HostGraph, sid: str, speak: Speak) -> Outcome:
    return graph.handle(sid, HostEvent.chatter(cut_segment_id=speak.segment_id))


# --- 暫停與繼續：P-01 到 P-07、P-16 ---


def test_p01_pause_mid_rule_points_flushes_and_does_not_ask_host_to_speak() -> None:
    graph, sid = new_hosting(7)
    to_turn_speaking(graph, sid, 1, 1)

    outcome = press(graph, sid, "pause")

    snapshot = graph.snapshot(sid)
    assert snapshot.paused is True
    assert snapshot.pause_reason == "command"
    assert len(flushes(outcome)) == 1
    assert speaks(outcome) == []
    assert tool_outputs(outcome) == []


def test_p02_resume_hands_over_the_same_rule_points_again() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    press(graph, sid, "pause")

    outcome = press(graph, sid, "resume")

    assert graph.snapshot(sid).paused is False
    assert graph.snapshot(sid).pause_reason is None
    assert first.version == "full"
    assert_same_rule_points(only_speak(outcome), first)


def test_p03_pause_and_resume_after_playback_only_says_back_to() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 2)
    press(graph, sid, "pause")
    outcome = press(graph, sid, "resume")
    assert_back_to(only_speak(outcome), step="turn", turn_number=2, phase_number=2)


def test_p03_back_to_before_first_turn_names_the_step() -> None:
    graph, sid = new_hosting(7)
    finish_playback(graph, sid, to_setup(graph, sid))
    press(graph, sid, "pause")
    outcome = press(graph, sid, "resume")
    assert_back_to(only_speak(outcome), step="setup", turn_number=None, phase_number=None)


def test_p04_rules_question_while_paused_is_answered_and_stays_paused() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    press(graph, sid, "pause")

    outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))

    output = tool_outputs(outcome)
    assert len(output) == 1
    assert output[0].respond is True
    assert len(output[0].chunks) == 6
    assert graph.snapshot(sid).paused is True


def test_p04_thinking_question_asked_while_paused_is_answered_right_away() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    press(graph, sid, "pause")
    asked = graph.handle(sid, HostEvent.ask(QUESTION, kind="thinking"))
    started = [effect for effect in asked.effects if isinstance(effect, StartThinking)][0]

    outcome = graph.handle(sid, HostEvent.answer_ready(started.question_id, "可以"))

    assert tool_outputs(outcome)[0].respond is True
    assert "可以" in tool_outputs(outcome)[0].output
    assert graph.snapshot(sid).paused is True


def test_p05_next_while_paused_moves_on_and_drops_the_interrupted_segment() -> None:
    graph, sid = new_hosting(7)
    old = only_speak(to_turn_speaking(graph, sid, 1, 1))
    press(graph, sid, "pause")

    outcome = press(graph, sid, "next")

    snapshot = graph.snapshot(sid)
    assert (snapshot.turn_number, snapshot.phase_number) == (1, 2)
    assert snapshot.paused is False
    new = only_speak(outcome)
    assert new.phase_number == 2
    assert new.text != old.text
    # 舊的那一段作廢：再說「繼續」不會重講階段 1
    finish_playback(graph, sid, outcome)
    assert press(graph, sid, "resume").effects == []


def test_previous_while_paused_also_moves_and_unpauses() -> None:
    graph, sid = new_hosting(7)
    to_turn_speaking(graph, sid, 1, 2)
    say(graph, sid, "暫停")
    outcome = say(graph, sid, "上一步")
    assert position(graph, sid) == ("turn", 1, 1)
    assert graph.snapshot(sid).paused is False
    assert only_speak(outcome).phase_number == 1


def test_p06_night_2_countdown_paused_then_resumed_is_handed_over_whole() -> None:
    graph, sid = new_hosting(7)
    finish_playback(graph, sid, to_setup(graph, sid))
    night_1 = press(graph, sid, "next")
    night_2 = finish_playback(graph, sid, night_1)
    assert position(graph, sid) == ("night_2", None, None)

    press(graph, sid, "pause")
    outcome = press(graph, sid, "resume")

    again = only_speak(outcome)
    assert again.code == "night_2"
    assert again.text == only_speak(night_2).text
    # 重講的這一段播完，才自動進第 1 回合
    after = finish_playback(graph, sid, outcome)
    assert position(graph, sid) == ("turn", 1, 1)
    assert only_speak(after).kind == "rule_points"


def test_p07_resume_in_turn_2_gives_the_short_version() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 2, 1))
    assert first.version == "short"
    press(graph, sid, "pause")
    outcome = press(graph, sid, "resume")
    assert only_speak(outcome).version == "short"
    assert_same_rule_points(only_speak(outcome), first)


def test_p16_resume_when_not_paused_and_nothing_interrupted_does_nothing() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    before = graph.memory(sid)
    outcome = say(graph, sid, "繼續")
    assert outcome.effects == []
    assert graph.memory(sid) == before


def test_pause_twice_only_takes_effect_once() -> None:
    graph, sid = new_hosting(7)
    to_turn_speaking(graph, sid, 1, 1)
    press(graph, sid, "pause")
    assert press(graph, sid, "pause").effects == []
    assert graph.snapshot(sid).pause_reason == "command"


# --- 被規則問題打斷：P-08、P-09 ---


def test_p08_question_mid_rule_points_is_answered_without_auto_replay() -> None:
    graph, sid = hosting_with_rules()
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))

    outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))

    assert len(tool_outputs(outcome)) == 1
    assert speaks(outcome) == []
    # 被打斷的那一段還在
    assert graph.memory(sid)["segment"]["id"] == first.segment_id


def test_p09_resume_after_the_question_hands_over_the_rule_points_again() -> None:
    graph, sid = hosting_with_rules()
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))

    outcome = say(graph, sid, "繼續")

    assert graph.snapshot(sid).paused is False
    assert_same_rule_points(only_speak(outcome), first)


# --- 閒聊：P-10 到 P-13 ---


def test_p10_chatter_cutting_the_segment_replays_it_once() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))

    outcome = cut_by_chatter(graph, sid, first)

    assert_same_rule_points(only_speak(outcome), first)
    assert graph.memory(sid)["replay_count"] == 1
    assert graph.snapshot(sid).paused is False


def test_p11_third_cut_stops_replaying_and_pauses_because_of_chatter() -> None:
    graph, sid = new_hosting(7)
    current = only_speak(to_turn_speaking(graph, sid, 1, 1))
    for expected_count in (1, 2):
        outcome = cut_by_chatter(graph, sid, current)
        current = only_speak(outcome)
        assert graph.memory(sid)["replay_count"] == expected_count

    outcome = cut_by_chatter(graph, sid, current)

    assert speaks(outcome) == []
    snapshot = graph.snapshot(sid)
    assert snapshot.paused is True
    assert snapshot.pause_reason == "chatter"
    # 那一段還留著，玩家說「繼續」就重講
    resumed = press(graph, sid, "resume")
    assert only_speak(resumed).kind == "rule_points"
    assert graph.memory(sid)["replay_count"] == 0


def test_p12_replay_count_resets_when_the_segment_finishes() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    replayed = cut_by_chatter(graph, sid, first)
    assert graph.memory(sid)["replay_count"] == 1

    finish_playback(graph, sid, replayed)

    assert graph.memory(sid)["replay_count"] == 0
    assert graph.memory(sid)["segment"] is None


def test_replay_count_resets_when_the_step_changes() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    cut_by_chatter(graph, sid, first)
    press(graph, sid, "next")
    assert graph.memory(sid)["replay_count"] == 0


def test_p13_chatter_while_host_is_silent_does_nothing() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    before = graph.memory(sid)
    outcome = graph.handle(sid, HostEvent.chatter())
    assert outcome.effects == []
    assert graph.memory(sid) == before


def test_chatter_that_did_not_cut_the_current_segment_does_nothing() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    assert graph.handle(sid, HostEvent.chatter()).effects == []
    stale = graph.handle(sid, HostEvent.chatter(cut_segment_id=first.segment_id + 50))
    assert stale.effects == []
    assert graph.memory(sid)["replay_count"] == 0


# --- 頁面被切走：P-14 ---


def test_p14_page_hidden_pauses_with_reason_page_hidden() -> None:
    graph, sid = new_hosting(7)
    to_turn_speaking(graph, sid, 1, 1)
    outcome = graph.handle(sid, HostEvent.page_hidden())
    snapshot = graph.snapshot(sid)
    assert snapshot.paused is True
    assert snapshot.pause_reason == "page_hidden"
    assert len(flushes(outcome)) == 1
    assert speaks(outcome) == []


# --- 暫停時還在等的答案：P-15 ---


def test_p15_answer_arriving_after_pause_waits_for_resume() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    asked = graph.handle(sid, HostEvent.ask(QUESTION, kind="thinking"))
    started = [effect for effect in asked.effects if isinstance(effect, StartThinking)][0]
    press(graph, sid, "pause")

    arrived = graph.handle(sid, HostEvent.answer_ready(started.question_id, "可以，全桌都不出。"))

    # 不交給主持人：工具結果裡沒有答案，也不請主持人回答
    assert speaks(arrived) == []
    for output in tool_outputs(arrived):
        assert output.respond is False
        assert "可以，全桌都不出。" not in output.output
    assert graph.snapshot(sid).paused is True
    assert graph.snapshot(sid).looking_up is False
    # 記成被打斷的那一段
    assert graph.memory(sid)["segment"]["kind"] == "answer"

    resumed = press(graph, sid, "resume")
    speak = only_speak(resumed)
    assert speak.kind == "answer"
    assert "可以，全桌都不出。" in speak.text
    assert QUESTION in speak.text


def test_p15_give_up_after_pause_also_waits_for_resume() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    asked = graph.handle(sid, HostEvent.ask(QUESTION, kind="thinking"))
    started = [effect for effect in asked.effects if isinstance(effect, StartThinking)][0]
    press(graph, sid, "pause")
    arrived = graph.handle(sid, HostEvent.give_up(started.question_id))
    assert all(output.respond is False for output in tool_outputs(arrived))
    speak = only_speak(press(graph, sid, "resume"))
    assert speak.kind == "answer"
    assert content.fixed_line("not_sure") in speak.text


# --- 回答也是一段（spec §6.1） ---


def test_answer_becomes_the_current_segment_when_nothing_else_is_pending() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))
    output = tool_outputs(outcome)[0]
    assert output.segment_id is not None
    assert graph.memory(sid)["segment"]["id"] == output.segment_id

    # 回答說到一半被暫停：繼續時重新交出這一題與查到的片段
    press(graph, sid, "pause")
    speak = only_speak(press(graph, sid, "resume"))
    assert speak.kind == "answer"
    assert QUESTION in speak.text
    assert "規則片段 1" in speak.text


def test_answer_segment_is_cleared_when_playback_finishes() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    output = tool_outputs(graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup")))[0]
    graph.handle(sid, HostEvent.playback_done(output.segment_id))
    assert graph.memory(sid)["segment"] is None
    assert position(graph, sid) == ("turn", 2, 2)


def test_answer_does_not_replace_an_interrupted_node_segment() -> None:
    graph, sid = hosting_with_rules()
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    output = tool_outputs(graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup")))[0]
    assert output.segment_id is None
    assert graph.memory(sid)["segment"]["id"] == first.segment_id


# --- 暫停中不自動進：F-12 ---


def test_f12_pause_before_night_1_finishes_stops_auto_advance() -> None:
    graph, sid = new_hosting(7)
    finish_playback(graph, sid, to_setup(graph, sid))
    night_1 = press(graph, sid, "next")

    press(graph, sid, "pause")
    # 就算裝置這時候回報播完，暫停中也不往下走
    late = finish_playback(graph, sid, night_1)

    assert late.effects == []
    assert position(graph, sid) == ("night_1", None, None)

    # 繼續：重講夜晚第一步，這次播完才進夜晚第二步
    resumed = press(graph, sid, "resume")
    assert only_speak(resumed).code == "night_1"
    after = finish_playback(graph, sid, resumed)
    assert position(graph, sid) == ("night_2", None, None)
    assert only_speak(after).code == "night_2"


# --- 整局記憶：M-03 ---


def test_m03_pause_flag_goes_true_then_false() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    press(graph, sid, "pause")
    assert graph.memory(sid)["paused"] is True
    assert graph.memory(sid)["pause_reason"] == "command"
    press(graph, sid, "resume")
    assert graph.memory(sid)["paused"] is False
    assert graph.memory(sid)["pause_reason"] is None


# --- 重新連線時圖交回什麼（spec §9） ---


def test_reconnect_only_says_back_to_and_keeps_position() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 3, 2)
    outcome = graph.handle(sid, HostEvent.connected())
    assert position(graph, sid) == ("turn", 3, 2)
    assert_back_to(only_speak(outcome), step="turn", turn_number=3, phase_number=2)


def test_reconnect_while_paused_says_nothing() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 3, 2)
    press(graph, sid, "pause")
    outcome = graph.handle(sid, HostEvent.connected())
    assert speaks(outcome) == []
    assert graph.snapshot(sid).paused is True


def test_reconnect_keeps_the_interrupted_segment_for_resume() -> None:
    graph, sid = new_hosting(7)
    first = only_speak(to_turn_speaking(graph, sid, 1, 1))
    outcome = graph.handle(sid, HostEvent.connected())
    assert only_speak(outcome).code == "back_to"
    assert_same_rule_points(only_speak(press(graph, sid, "resume")), first)


def test_reconnect_with_another_turn_taking_mode_switches_it() -> None:
    graph, sid = new_hosting(7, voice="female")
    to_turn(graph, sid, 2, 2)
    outcome = graph.handle(sid, HostEvent.connected(turn_taking_mode="push_to_talk"))
    snapshot = graph.snapshot(sid)
    assert snapshot.turn_taking_mode == "push_to_talk"
    assert snapshot.voice == "female"
    assert position(graph, sid) == ("turn", 2, 2)
    assert any(isinstance(effect, StateChanged) for effect in outcome.effects)
    assert only_speak(outcome).code == "back_to"


def test_reconnect_to_an_ended_hosting_makes_it_active_again() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    say(graph, sid, "血刃贏了")
    assert graph.snapshot(sid).status == "ended"

    outcome = graph.handle(sid, HostEvent.connected())

    snapshot = graph.snapshot(sid)
    assert snapshot.status == "active"
    assert (snapshot.step, snapshot.turn_number, snapshot.phase_number) == ("turn", 2, 3)
    assert snapshot.winner is None
    assert_back_to(only_speak(outcome), step="turn", turn_number=2, phase_number=3)
    # 回到進行中之後，指令照常有效
    press(graph, sid, "previous")
    assert position(graph, sid) == ("turn", 2, 2)


def test_reconnect_drops_a_question_that_was_waiting() -> None:
    graph, sid = hosting_with_rules()
    to_turn(graph, sid, 2, 2)
    asked = graph.handle(sid, HostEvent.ask(QUESTION, kind="thinking"))
    started = [effect for effect in asked.effects if isinstance(effect, StartThinking)][0]
    graph.handle(sid, HostEvent.connected())
    assert graph.snapshot(sid).looking_up is False
    late = graph.handle(sid, HostEvent.answer_ready(started.question_id, "答案"))
    assert late.effects == []


@pytest.mark.parametrize("action", ["pause", "resume"])
def test_pause_and_resume_do_nothing_after_end(action: str) -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    press(graph, sid, "end")
    assert press(graph, sid, action).effects == []
    assert graph.handle(sid, HostEvent.page_hidden()).effects == []
