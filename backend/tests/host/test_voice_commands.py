"""語音指令的核對（host spec §5）。對應情境 V-01 到 V-10。

片段等 0.3 秒、同一句只執行一次、模型呼叫工具那一條路（V-11 到 V-17）在轉送那一段。
"""

import pytest

from app.domains.host.graph import VoiceCommand, match_voice_command
from tests.host.graph_support import new_hosting, position, say, speaks, to_turn

# --- 核對函式 ---


@pytest.mark.parametrize(
    "text, expected",
    [
        ("等一下", VoiceCommand("pause")),
        ("暫停", VoiceCommand("pause")),
        ("繼續", VoiceCommand("resume")),
        ("下一步", VoiceCommand("next")),
        ("下一部", VoiceCommand("next")),
        ("上一步", VoiceCommand("previous")),
        ("上一部", VoiceCommand("previous")),
        ("結束了", VoiceCommand("end")),
        ("白薔薇贏了", VoiceCommand("end", "white_rose")),
        ("白薔薇陣營贏了", VoiceCommand("end", "white_rose")),
        ("血刃贏了", VoiceCommand("end", "blood_blade")),
        ("血刃陣營贏了", VoiceCommand("end", "blood_blade")),
    ],
)
def test_every_phrase_in_the_list(text: str, expected: VoiceCommand) -> None:
    assert match_voice_command(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("下一步。", VoiceCommand("next")),
        (" 下一步！ ", VoiceCommand("next")),
        ("主持人，下一步", VoiceCommand("next")),
        ("主持人暫停", VoiceCommand("pause")),
        ("暂停。", VoiceCommand("pause")),
        ("继续", VoiceCommand("resume")),
        ("结束了。", VoiceCommand("end")),
        ("白蔷薇赢了。", VoiceCommand("end", "white_rose")),
        ("白蔷薇阵营赢了", VoiceCommand("end", "white_rose")),
        ("血刃阵营赢了！", VoiceCommand("end", "blood_blade")),
    ],
)
def test_punctuation_prefix_and_simplified_chinese(text: str, expected: VoiceCommand) -> None:
    assert match_voice_command(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "你下一步要出什麼",
        "上一部，他明明没出牌",
        "白薔薇贏了嗎？",
        "下一步?",
        "我覺得快結束了",
        "暫停一下，我去上廁所",
        "等一下再出牌",
        "主持人",
        "",
        "。",
        "下一步下一步",
    ],
)
def test_not_a_command(text: str) -> None:
    assert match_voice_command(text) is None


# --- 情境 ---


def test_v01_next_with_full_stop() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    outcome = say(graph, sid, "下一步。")
    assert position(graph, sid) == ("turn", 1, 2)
    assert outcome.result == {"verified": True, "action": "next"}


def test_v02_next_with_host_prefix() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    say(graph, sid, "主持人，下一步")
    assert position(graph, sid) == ("turn", 1, 2)


def test_v03_command_inside_a_longer_sentence_is_ignored() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 1)
    outcome = say(graph, sid, "你下一步要出什麼")
    assert position(graph, sid) == ("turn", 1, 1)
    assert speaks(outcome) == []


def test_v04_previous_homophone() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 2)
    say(graph, sid, "上一部")
    assert position(graph, sid) == ("turn", 1, 1)


def test_v05_homophone_inside_a_longer_sentence_is_ignored() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 1, 2)
    say(graph, sid, "上一部，他明明没出牌")
    assert position(graph, sid) == ("turn", 1, 2)


def test_v06_simplified_white_rose_won() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    say(graph, sid, "白蔷薇赢了。")
    snapshot = graph.snapshot(sid)
    assert snapshot.status == "ended"
    assert snapshot.winner == "white_rose"


def test_v07_question_mark_is_not_a_command() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    say(graph, sid, "白薔薇贏了嗎？")
    assert graph.snapshot(sid).status == "active"
    assert position(graph, sid) == ("turn", 2, 3)


def test_v08_end_phrase_inside_a_longer_sentence_is_ignored() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    say(graph, sid, "我覺得快結束了")
    assert graph.snapshot(sid).status == "active"


def test_v09_simplified_pause() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 1)
    outcome = say(graph, sid, "暂停。")
    snapshot = graph.snapshot(sid)
    assert snapshot.paused is True
    assert snapshot.pause_reason == "command"
    assert speaks(outcome) == []
    assert position(graph, sid) == ("turn", 2, 1)


def test_v10_pause_inside_a_longer_sentence_is_ignored() -> None:
    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 1)
    say(graph, sid, "暫停一下，我去上廁所")
    assert graph.snapshot(sid).paused is False


# --- 結束改成相信語音模型時用得到的兩樣東西（2026-11-22 立倫決定，spec §5.2） ---


@pytest.mark.parametrize(
    "text, expected",
    [
        ("写着名字。", "寫着名字"),
        ("主持人，白蔷薇赢了！", "白薔薇贏了"),
        (" 确认 延误 ", "确认延误"),
        ("。", ""),
    ],
)
def test_spoken_core_strips_punctuation_prefix_and_converts(text: str, expected: str) -> None:
    from app.domains.host.graph import spoken_core

    assert spoken_core(text) == expected


@pytest.mark.parametrize("text", ["血刃贏了嗎？", "结束了?"])
def test_spoken_core_is_none_for_questions(text: str) -> None:
    from app.domains.host.graph import spoken_core

    assert spoken_core(text) is None


@pytest.mark.parametrize(
    "winner, code", [("blood_blade", "end_blood_blade"), ("white_rose", "end_white_rose")]
)
def test_end_command_can_carry_a_winner(winner: str, code: str) -> None:
    from app.domains.host.graph import HostEvent
    from tests.host.graph_support import only_speak

    graph, sid = new_hosting(7)
    to_turn(graph, sid, 2, 3)
    outcome = graph.handle(sid, HostEvent.command("end", winner=winner))
    assert graph.snapshot(sid).status == "ended"
    assert graph.snapshot(sid).winner == winner
    assert only_speak(outcome).code == code
