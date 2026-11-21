"""查規則與思考模型兩個節點（host spec §8）。對應情境 Q-01 到 Q-05、Q-09 到 Q-13。

8 秒與 15 秒的計時（Q-06 到 Q-08）在轉送那一段。查規則與思考模型都換成手寫的 fake。
"""

import logging
import threading

import pytest

from app.domains.host import content
from app.domains.host.graph import (
    WHITE_ROSE_BGG_ID,
    HostEvent,
    HostGraph,
    Outcome,
    StartThinking,
    StateChanged,
    ToolOutput,
    WhiteRoseRules,
)
from app.integrations.llm import LLMUnavailable
from tests.host.fakes import SIX_CHUNKS, FakeChunk, FakeRulesLookup, FakeThinkingModel
from tests.host.graph_support import new_hosting, position, press, say, speaks, to_turn

QUESTION = "整桌都不出牌可以嗎"


def hosting(
    lookup: FakeRulesLookup | None = None, thinking: FakeThinkingModel | None = None
) -> tuple[HostGraph, str, FakeRulesLookup, FakeThinkingModel]:
    lookup = lookup or FakeRulesLookup()
    thinking = thinking or FakeThinkingModel()
    graph = HostGraph(rules_lookup=lookup, thinking_model=thinking)
    graph, sid = new_hosting(7, graph=graph)
    to_turn(graph, sid, 2, 2)
    return graph, sid, lookup, thinking


def tool_outputs(outcome: Outcome) -> list[ToolOutput]:
    return [effect for effect in outcome.effects if isinstance(effect, ToolOutput)]


def only_tool_output(outcome: Outcome) -> ToolOutput:
    found = tool_outputs(outcome)
    assert len(found) == 1, outcome.effects
    return found[0]


def looking_up_values(outcome: Outcome) -> list[bool]:
    return [e.snapshot.looking_up for e in outcome.effects if isinstance(e, StateChanged)]


def ask_thinking(graph: HostGraph, sid: str, question: str = QUESTION) -> StartThinking:
    outcome = graph.handle(sid, HostEvent.ask(question, kind="thinking"))
    started = [effect for effect in outcome.effects if isinstance(effect, StartThinking)]
    assert len(started) == 1, outcome.effects
    return started[0]


# --- 查規則：Q-01 到 Q-04 ---


def test_q01_lookup_gives_six_chunks_and_looking_up_goes_true_then_false() -> None:
    graph, sid, lookup, _ = hosting()
    outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))

    output = only_tool_output(outcome)
    assert lookup.questions == [QUESTION]
    assert [(c.page, c.content) for c in output.chunks] == [(c.page, c.content) for c in SIX_CHUNKS]
    for chunk in SIX_CHUNKS:
        assert f"第 {chunk.page} 頁" in output.output
        assert chunk.content in output.output
    assert output.respond is True
    assert looking_up_values(outcome) == [True, False]
    # 先顯示正在查，再交結果，最後收起來
    kinds = [type(effect).__name__ for effect in outcome.effects]
    assert kinds == ["StateChanged", "ToolOutput", "StateChanged"]
    assert graph.snapshot(sid).looking_up is False
    # 流程不動，也不另外請主持人開口（答案由工具結果帶出來）
    assert position(graph, sid) == ("turn", 2, 2)
    assert speaks(outcome) == []


def test_lookup_output_tells_host_how_to_answer() -> None:
    graph, sid, _, _ = hosting()
    output = only_tool_output(graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup")))
    # 片段裡沒有答案時說第六句固定回答；答完補一句接回流程
    assert content.fixed_line("answer_not_found") in output.output
    assert content.back_to_line(step="turn", turn_number=2, phase_number=2) in output.output


def test_looking_up_is_true_while_the_lookup_is_running() -> None:
    lookup = FakeRulesLookup()
    lookup.release = threading.Event()
    graph, sid, _, _ = hosting(lookup)
    seen: list[object] = []
    worker = threading.Thread(
        target=lambda: graph.handle(
            sid, HostEvent.ask(QUESTION, kind="lookup"), on_effect=seen.append
        )
    )
    worker.start()
    assert lookup.entered.wait(timeout=5)
    # 查規則還沒回來，「正在查規則」已經先交出去了
    assert [type(effect).__name__ for effect in seen] == ["StateChanged"]
    assert seen[0].snapshot.looking_up is True  # type: ignore[attr-defined]
    lookup.release.set()
    worker.join(timeout=5)
    assert [type(effect).__name__ for effect in seen] == [
        "StateChanged",
        "ToolOutput",
        "StateChanged",
    ]


def test_q02_index_not_built_gives_empty_result_without_error() -> None:
    graph, sid, _, _ = hosting(FakeRulesLookup(chunks=[]))
    outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))
    output = only_tool_output(outcome)
    assert output.chunks == ()
    assert content.fixed_line("answer_not_found") in output.output
    assert looking_up_values(outcome) == [True, False]


def test_q03_embedding_failure_gives_empty_result_and_logs_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    searches: list[tuple[int, str]] = []

    def failing_search(game_id: int, question: str) -> list[FakeChunk]:
        searches.append((game_id, question))
        raise RuntimeError("embedding 連不上")

    rules = WhiteRoseRules(find_game_id=lambda bgg_id: 42, search=failing_search)
    graph = HostGraph(rules_lookup=rules, thinking_model=FakeThinkingModel())
    graph, sid = new_hosting(7, graph=graph)
    to_turn(graph, sid, 1, 1)

    with caplog.at_level(logging.WARNING, logger="app.domains.host.graph"):
        outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))

    assert only_tool_output(outcome).chunks == ()
    assert searches == [(42, QUESTION)]
    assert "embedding 連不上" in caplog.text
    # 紀錄不寫玩家說的話（spec §13.5）
    assert QUESTION not in caplog.text


def test_white_rose_rules_finds_the_game_by_bgg_id() -> None:
    asked: list[int] = []

    def find(bgg_id: int) -> int | None:
        asked.append(bgg_id)
        return 7

    rules = WhiteRoseRules(find_game_id=find, search=lambda game_id, question: SIX_CHUNKS)
    assert [c.page for c in rules(QUESTION)] == [c.page for c in SIX_CHUNKS]
    assert asked == [WHITE_ROSE_BGG_ID] == [400566]


def test_white_rose_rules_game_not_found_is_empty(caplog: pytest.LogCaptureFixture) -> None:
    def search(game_id: int, question: str) -> list[FakeChunk]:
        raise AssertionError("找不到遊戲就不該檢索")

    rules = WhiteRoseRules(find_game_id=lambda bgg_id: None, search=search)
    with caplog.at_level(logging.WARNING, logger="app.domains.host.graph"):
        assert rules(QUESTION) == []
    assert "400566" in caplog.text


def test_lookup_without_any_rules_source_is_empty() -> None:
    graph, sid = new_hosting(7, graph=HostGraph())
    outcome = graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup"))
    assert only_tool_output(outcome).chunks == ()


def test_q04_memory_keeps_last_five_questions_with_pages_only() -> None:
    graph, sid, _, _ = hosting()
    for index in range(6):
        graph.handle(sid, HostEvent.ask(f"問題 {index + 1}", kind="lookup"))
    recent = graph.memory(sid)["recent_questions"]
    assert [item["question"] for item in recent] == [f"問題 {n}" for n in range(2, 7)]
    pages = [chunk.page for chunk in SIX_CHUNKS]
    assert all(item["pages"] == pages for item in recent)
    # 只有問題與頁碼，沒有片段原文，也沒有回答的文字
    assert all(set(item) == {"question", "pages"} for item in recent)


# --- 思考模型：Q-05、Q-13 ---


def test_q05_thinking_model_answer_becomes_the_tool_result() -> None:
    graph, sid, lookup, thinking = hosting(thinking=FakeThinkingModel(reply="可以，全桌都不出。"))

    asked = graph.handle(sid, HostEvent.ask(QUESTION, kind="thinking"))
    started = [effect for effect in asked.effects if isinstance(effect, StartThinking)][0]
    assert looking_up_values(asked) == [True]
    assert tool_outputs(asked) == []
    assert graph.snapshot(sid).looking_up is True
    # 後端自己用那個問題再查一次片段
    assert lookup.questions == [QUESTION]
    assert [c.page for c in started.chunks] == [c.page for c in SIX_CHUNKS]

    answer = graph.think(started.question, started.chunks)
    assert answer == "可以，全桌都不出。"

    delivered = graph.handle(sid, HostEvent.answer_ready(started.question_id, answer))
    output = only_tool_output(delivered)
    assert "可以，全桌都不出。" in output.output
    assert output.question_id == started.question_id
    assert output.respond is True
    assert looking_up_values(delivered) == [False]
    # 沒有等很久的那一句
    assert content.fixed_line("wait_longer") not in output.output
    assert speaks(asked) == speaks(delivered) == []
    assert delivered.result == {"delivered": True}


def test_q13_thinking_node_only_uses_the_llm_interface_with_question_and_chunks() -> None:
    graph, sid, _, thinking = hosting()
    started = ask_thinking(graph, sid)
    graph.think(started.question, started.chunks)

    assert len(thinking.prompts) == 1
    assert thinking.other_calls == []
    prompt = thinking.prompts[0]
    assert QUESTION in prompt
    for chunk in SIX_CHUNKS:
        assert chunk.content in prompt
        assert f"第 {chunk.page} 頁" in prompt


def test_thinking_does_not_touch_any_hosting_memory() -> None:
    graph, sid, _, _ = hosting()
    started = ask_thinking(graph, sid)
    before = graph.memory(sid)
    graph.think(started.question, started.chunks)
    assert graph.memory(sid) == before


def test_thinking_model_error_is_raised_to_the_caller() -> None:
    graph, sid, _, _ = hosting(thinking=FakeThinkingModel(error=LLMUnavailable("連不上")))
    started = ask_thinking(graph, sid)
    with pytest.raises(LLMUnavailable):
        graph.think(started.question, started.chunks)


def test_give_up_hands_over_the_chunks_with_not_sure() -> None:
    """15 秒放棄或思考模型回錯誤時（計時在轉送那一段），改交查到的片段與 not_sure。"""
    graph, sid, _, _ = hosting()
    started = ask_thinking(graph, sid)
    outcome = graph.handle(sid, HostEvent.give_up(started.question_id))
    output = only_tool_output(outcome)
    for chunk in SIX_CHUNKS:
        assert chunk.content in output.output
    assert content.fixed_line("not_sure") in output.output
    assert looking_up_values(outcome) == [False]

    # 放棄之後才回來的答案丟掉
    late = graph.handle(sid, HostEvent.answer_ready(started.question_id, "晚到的答案"))
    assert late.effects == []
    assert late.result == {"delivered": False}


def test_thinking_question_is_remembered_with_pages() -> None:
    graph, sid, _, _ = hosting()
    ask_thinking(graph, sid)
    recent = graph.memory(sid)["recent_questions"]
    assert recent == [{"question": QUESTION, "pages": [c.page for c in SIX_CHUNKS]}]


# --- 等待中玩家又開口：Q-09 到 Q-11 ---


def test_q09_second_question_replaces_the_first() -> None:
    graph, sid, _, _ = hosting()
    first = ask_thinking(graph, sid, "第一題")
    second = ask_thinking(graph, sid, "第二題")
    assert second.question_id != first.question_id

    stale = graph.handle(sid, HostEvent.answer_ready(first.question_id, "第一題的答案"))
    assert stale.effects == []
    assert stale.result == {"delivered": False}
    assert graph.snapshot(sid).looking_up is True

    fresh = graph.handle(sid, HostEvent.answer_ready(second.question_id, "第二題的答案"))
    assert "第二題的答案" in only_tool_output(fresh).output
    assert graph.snapshot(sid).looking_up is False


def test_q09_a_lookup_also_replaces_a_waiting_question() -> None:
    graph, sid, _, _ = hosting()
    first = ask_thinking(graph, sid, "第一題")
    second = graph.handle(sid, HostEvent.ask("第二題", kind="lookup"))
    assert only_tool_output(second).respond is True
    assert graph.snapshot(sid).looking_up is False
    stale = graph.handle(sid, HostEvent.answer_ready(first.question_id, "第一題的答案"))
    assert stale.effects == []


def test_q10_chatter_does_not_void_the_waiting_question() -> None:
    graph, sid, _, _ = hosting()
    started = ask_thinking(graph, sid)
    graph.handle(sid, HostEvent.chatter())
    assert graph.snapshot(sid).looking_up is True
    delivered = graph.handle(sid, HostEvent.answer_ready(started.question_id, "答案"))
    assert "答案" in only_tool_output(delivered).output


def test_q11_voice_command_does_not_void_the_waiting_question() -> None:
    graph, sid, _, _ = hosting()
    started = ask_thinking(graph, sid)
    say(graph, sid, "下一步")
    assert position(graph, sid) == ("turn", 2, 3)
    assert graph.snapshot(sid).looking_up is True
    delivered = graph.handle(sid, HostEvent.answer_ready(started.question_id, "答案"))
    output = only_tool_output(delivered)
    assert "答案" in output.output
    # 接回流程那一句用的是換了之後的階段
    assert content.back_to_line(step="turn", turn_number=2, phase_number=3) in output.output


def test_dropping_the_waiting_question_discards_its_answer() -> None:
    """等待中玩家說了別的話（例如「算了」）：舊題作廢，舊答案晚到也不唸（spec §8.4）。"""
    graph, sid, _, _ = hosting()
    started = ask_thinking(graph, sid)
    dropped = graph.handle(sid, HostEvent.drop_question())
    assert looking_up_values(dropped) == [False]
    late = graph.handle(sid, HostEvent.answer_ready(started.question_id, "答案"))
    assert late.effects == []
    # 沒有在等的題目時，再作廢一次也不動
    assert graph.handle(sid, HostEvent.drop_question()).effects == []


# --- 一次只處理一件事：Q-12 ---


def test_q12_two_requests_at_once_are_handled_one_by_one() -> None:
    lookup = FakeRulesLookup()
    graph, sid, _, _ = hosting(lookup)
    lookup.release = threading.Event()
    order: list[str] = []

    def ask() -> None:
        graph.handle(
            sid,
            HostEvent.ask(QUESTION, kind="lookup"),
            on_effect=lambda effect: order.append(f"ask:{type(effect).__name__}"),
        )

    def go_next() -> None:
        graph.handle(
            sid,
            HostEvent.command("next"),
            on_effect=lambda effect: order.append(f"next:{type(effect).__name__}"),
        )

    first = threading.Thread(target=ask)
    first.start()
    assert lookup.entered.wait(timeout=5)
    second = threading.Thread(target=go_next)
    second.start()
    # 查規則還卡著的時候，下一步在排隊，流程還沒動
    second.join(timeout=0.2)
    assert second.is_alive()
    assert position(graph, sid) == ("turn", 2, 2)

    lookup.release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    # 依到達順序一個一個處理
    assert order == [
        "ask:StateChanged",
        "ask:ToolOutput",
        "ask:StateChanged",
        "next:StateChanged",
        "next:Speak",
    ]
    # 整局記憶沒有互相蓋掉：問過的題目與換過的階段都在
    memory = graph.memory(sid)
    assert [item["question"] for item in memory["recent_questions"]] == [QUESTION]
    assert (memory["turn_number"], memory["phase_number"]) == (2, 3)


def test_ended_hosting_still_answers_rules_without_back_to() -> None:
    graph, sid, _, _ = hosting()
    press(graph, sid, "end")
    output = only_tool_output(graph.handle(sid, HostEvent.ask(QUESTION, kind="lookup")))
    assert len(output.chunks) == 6
    assert "回到" not in output.output
