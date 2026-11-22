"""圖的測試共用的小工具：開一場主持、把流程推到指定的位置。圖跑真的（spec §13.1）。"""

from uuid import uuid4

from app.domains.host.graph import (
    HostEvent,
    HostGraph,
    Outcome,
    Speak,
)


def new_hosting(
    player_count: int = 7,
    *,
    turn_taking_mode: str = "auto",
    voice: str = "male",
    graph: HostGraph | None = None,
) -> tuple[HostGraph, str]:
    graph = graph or HostGraph()
    session_id = str(uuid4())
    graph.create(
        session_id, player_count=player_count, turn_taking_mode=turn_taking_mode, voice=voice
    )
    return graph, session_id


def speaks(outcome: Outcome) -> list[Speak]:
    return [effect for effect in outcome.effects if isinstance(effect, Speak)]


def only_speak(outcome: Outcome) -> Speak:
    found = speaks(outcome)
    assert len(found) == 1, outcome.effects
    return found[0]


def finish_playback(graph: HostGraph, session_id: str, outcome: Outcome) -> Outcome:
    """裝置回報 outcome 交出的那一段播完了。"""
    return graph.handle(session_id, HostEvent.playback_done(only_speak(outcome).segment_id))


def press(graph: HostGraph, session_id: str, action: str) -> Outcome:
    return graph.handle(session_id, HostEvent.command(action))


def say(graph: HostGraph, session_id: str, text: str) -> Outcome:
    return graph.handle(session_id, HostEvent.voice_text(text))


def to_setup(graph: HostGraph, session_id: str) -> Outcome:
    """連上、開場播完，停在開局準備。回傳交出開局準備台詞的那一次。"""
    opening = graph.handle(session_id, HostEvent.connected())
    return finish_playback(graph, session_id, opening)


def to_turn(
    graph: HostGraph, session_id: str, turn_number: int = 1, phase_number: int = 1
) -> Outcome:
    """把流程推到第 turn_number 回合的階段 phase_number。回傳最後一次的結果。

    每一段都回報播完，所以到達時沒有被打斷的那一段。要留著那一段就用 to_turn_speaking。
    """
    outcome = to_turn_speaking(graph, session_id, turn_number, phase_number)
    finish_playback(graph, session_id, outcome)
    return outcome


def to_turn_speaking(
    graph: HostGraph, session_id: str, turn_number: int = 1, phase_number: int = 1
) -> Outcome:
    """同 to_turn，但最後那一段規則要點還沒播完（主持人說到一半）。"""
    setup = to_setup(graph, session_id)
    finish_playback(graph, session_id, setup)
    night_1 = press(graph, session_id, "next")
    night_2 = finish_playback(graph, session_id, night_1)
    outcome = finish_playback(graph, session_id, night_2)
    steps = (turn_number - 1) * 3 + (phase_number - 1)
    for _ in range(steps):
        finish_playback(graph, session_id, outcome)
        outcome = press(graph, session_id, "next")
    snapshot = graph.snapshot(session_id)
    assert (snapshot.step, snapshot.turn_number, snapshot.phase_number) == (
        "turn",
        turn_number,
        phase_number,
    )
    return outcome


def position(graph: HostGraph, session_id: str) -> tuple[str, int | None, int | None]:
    snapshot = graph.snapshot(session_id)
    return snapshot.step, snapshot.turn_number, snapshot.phase_number
