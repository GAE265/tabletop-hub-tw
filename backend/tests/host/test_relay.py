"""WebSocket 與轉送（host spec §5.2、§7、§8.3、§9、§10、§12）。

對應情境 W-07 到 W-13、K-01 到 K-08、T-01 到 T-05、Q-06 到 Q-08、V-11 到 V-17、M-06、M-07。
W-01 到 W-06 另外在 test_stream_api 用真的 WebSocket 端點再測一遍。
時間都用假時鐘，不真的等。
"""

import ast
import logging
import threading
from pathlib import Path

import pytest

from app.domains.host import content
from app.domains.host import relay as relay_module
from app.integrations.llm import LLMUnavailable
from app.integrations.realtime_voice import (
    ConnectionLost,
    HostAudio,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerSpeechStarted,
    SpeechNotAddressed,
)
from tests.host.fakes import SIX_CHUNKS, FakeThinkingModel
from tests.host.relay_support import OWNER, Rig, back_to, line, rule_points, run

STATE_FIELDS = {
    "type",
    "status",
    "step",
    "turn_number",
    "phase_number",
    "paused",
    "pause_reason",
    "looking_up",
    "turn_taking_mode",
    "voice",
    "winner",
}
QUESTION = "整桌都不出牌可以嗎"


def blocked_thinking(reply: str = "可以，全桌都不出。") -> FakeThinkingModel:
    thinking = FakeThinkingModel(reply=reply)
    thinking.release = threading.Event()
    return thinking


# --- 連線：W-01、W-05、W-06、W-12、W-13 ---


def test_w01_first_message_is_state_and_the_voice_connection_is_opened() -> None:
    async def scenario() -> None:
        rig = Rig()
        device = await rig.connect()
        first = device.messages[0]
        assert isinstance(first, dict)
        assert set(first) == STATE_FIELDS
        assert first["type"] == "state"
        assert (first["status"], first["step"]) == ("active", "opening")
        assert rig.provider.connect_attempts == 1
        # 剛開主持：請主持人說開場台詞
        assert rig.conn.speech_requests == [line("opening")]

    run(scenario)


def test_w05_voice_model_unreachable_closes_with_error_and_keeps_the_hosting() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.provider.fail_connect(times=None)
        device = await rig.connect()
        assert device.error_codes() == ["HOST_REALTIME_UNAVAILABLE"]
        assert device.closed is True
        assert rig.relay is not None and rig.relay.closed is True
        assert len(rig.service.list_sessions(OWNER)) == 1

    run(scenario)


def test_w06_second_device_takes_over() -> None:
    async def scenario() -> None:
        rig = Rig()
        first = await rig.connect()
        first_conn = rig.conn
        first_relay = rig.relay

        second = await rig.connect()

        assert first.error_codes() == ["HOST_SESSION_TAKEN_OVER"]
        assert first.closed is True
        assert first_conn.closed is True
        assert first_relay is not None and first_relay.closed is True
        # 後連上的那一支正常
        assert second.closed is False
        assert second.error_codes() == []
        await rig.press("next")
        assert rig.position()[0] == "setup"
        # 先連的那支被關掉，不會讓這場主持變成「沒有裝置連著」
        rig.clock.advance(minutes=45)
        assert len(rig.service.list_sessions(OWNER)) == 1

    run(scenario)


def test_w12_device_disconnect_closes_the_voice_connection_and_keeps_the_hosting() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 2)
        await rig.connect()
        assert rig.relay is not None

        await rig.relay.close()

        assert rig.conn.closed is True
        assert rig.position() == ("turn", 1, 2)
        # 保留 30 分鐘，從斷線起算
        rig.clock.advance(minutes=29)
        assert len(rig.service.list_sessions(OWNER)) == 1
        rig.clock.advance(minutes=1)
        assert rig.service.list_sessions(OWNER) == []

    run(scenario)


def test_w13_connecting_to_an_ended_hosting_makes_it_active_again() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        rig.service.handle_event(rig.sid, relay_module.HostEvent.command("end"))
        assert rig.snapshot.status == "ended"

        device = await rig.connect()

        state = device.messages[0]
        assert isinstance(state, dict)
        assert state["status"] == "active"
        assert (state["step"], state["turn_number"], state["phase_number"]) == ("turn", 2, 2)
        assert state["winner"] is None

    run(scenario)


# --- 聲音與訊息：W-07 到 W-11 ---


def test_w07_device_audio_is_forwarded_unchanged() -> None:
    async def scenario() -> None:
        rig = Rig()
        await rig.connect()
        assert rig.relay is not None
        await rig.relay.handle_device_audio(b"\x01\x02\x03\x04")
        await rig.relay.handle_device_audio(b"\x05\x06")
        audio = [a for a in rig.conn.actions if a[0] == "send_audio"]
        assert audio == [("send_audio", b"\x01\x02\x03\x04"), ("send_audio", b"\x05\x06")]

    run(scenario)


def test_w08_host_voice_reaches_the_device_between_utterance_start_and_end() -> None:
    async def scenario() -> None:
        rig = Rig()
        device = await rig.connect()
        before = len(device.messages)
        await rig.emit(
            HostUtteranceStarted(utterance_id="u1"),
            HostAudio(utterance_id="u1", data=b"aa"),
            HostAudio(utterance_id="u1", data=b"bb"),
            HostUtteranceEnded(utterance_id="u1", cancelled=False),
        )
        assert device.messages[before:] == [
            {"type": "utterance", "utterance_id": "u1", "state": "start"},
            b"aa",
            b"bb",
            {"type": "utterance", "utterance_id": "u1", "state": "end"},
        ]

    run(scenario)


def test_w09_command_next_sends_a_new_state() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        device = await rig.connect()
        await rig.press("next")
        state = device.last_state()
        assert set(state) == STATE_FIELDS
        assert (state["step"], state["turn_number"], state["phase_number"]) == ("turn", 1, 2)
        assert state["paused"] is False and state["pause_reason"] is None
        assert state["looking_up"] is False
        assert rig.conn.speech_requests[-1] == rule_points(1, 2)

    run(scenario)


@pytest.mark.parametrize("action", ["previous", "pause", "resume", "end"])
def test_every_command_button_reaches_the_graph(action: str) -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 2)
        device = await rig.connect()
        if action == "resume":
            await rig.press("pause")
        await rig.press(action)
        state = device.last_state()
        expected = {
            "previous": ("phase_number", 1),
            "pause": ("paused", True),
            "resume": ("paused", False),
            "end": ("status", "ended"),
        }[action]
        assert state[expected[0]] == expected[1]
        if action == "end":
            # 按鍵的結束不帶贏的一方
            assert state["winner"] is None
            assert rig.conn.speech_requests[-1] == line("end_plain")

    run(scenario)


def test_w10_unknown_action_gets_bad_message_and_nothing_moves() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        device = await rig.connect()
        assert rig.relay is not None

        await rig.device_sends(type="command", action="jump")
        await rig.device_sends(type="dance")
        await rig.device_sends(type="talk", state="sideways")
        await rig.device_sends(type="playback_done")
        await rig.relay.handle_device_text("這不是 JSON")
        await rig.relay.handle_device_text("[1, 2]")
        await rig.settle()

        assert device.error_codes() == ["HOST_BAD_MESSAGE"] * 6
        assert set(device.json("error")[0]["error"]) == {"code", "message", "details"}
        assert device.closed is False and rig.relay.closed is False
        assert rig.position() == ("turn", 1, 1)
        # 連線還在：之後的訊息照常處理
        await rig.press("next")
        assert rig.position() == ("turn", 1, 2)

    run(scenario)


def test_w11_pause_while_host_is_speaking_sends_flush_then_state() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        device = await rig.connect()
        await rig.press("next")
        await rig.host_starts()
        before = len(device.messages)
        cancels = rig.count_action("cancel_response")

        await rig.press("pause")

        after = [m for m in device.messages[before:] if isinstance(m, dict)]
        assert [m["type"] for m in after] == ["flush", "state"]
        assert after[1]["paused"] is True
        assert after[1]["pause_reason"] == "command"
        # 取消主持人正在產生的回答（前面按下一步時已經取消過舊階段的那一段，所以看增加的次數）
        assert rig.count_action("cancel_response") == cancels + 1

    run(scenario)


def test_page_hidden_pauses() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        device = await rig.connect()
        await rig.device_sends(type="page_hidden")
        assert device.last_state()["paused"] is True
        assert device.last_state()["pause_reason"] == "page_hidden"

    run(scenario)


def test_playback_done_moves_opening_on_to_setup() -> None:
    async def scenario() -> None:
        rig = Rig()
        device = await rig.connect()
        utterance_id = await rig.host_starts()
        await rig.host_finishes(utterance_id, played=False)
        # 語音模型說完了，但裝置還沒播完：不往下走
        assert rig.position()[0] == "opening"

        await rig.device_sends(type="playback_done", utterance_id=utterance_id)

        assert rig.position()[0] == "setup"
        assert device.last_state()["step"] == "setup"
        assert rig.conn.speech_requests[-1] == line("setup")
        # 不認得的編號不理會
        await rig.device_sends(type="playback_done", utterance_id="no-such-utterance")
        assert rig.position()[0] == "setup"

    run(scenario)


# --- 接話方式與聲線：T-01 到 T-05、K-08 ---


def test_k08_connection_settings_handed_to_the_integration_layer() -> None:
    async def scenario() -> None:
        rig = Rig(player_count=7)
        await rig.connect()
        config = rig.provider.configs[-1]
        assert config.history_turns == 50
        assert config.turn_taking_mode == "auto"
        assert config.turn_sensitivity == 0.5
        assert config.voice == "male"
        assert [tool.name for tool in config.tools] == [t.name for t in content.host_tools()]
        assert "獻祭區要有 6 張花苞" in config.instructions
        assert len(config.tools) == 8

    run(scenario)


def test_k08_push_to_talk_has_no_turn_sensitivity() -> None:
    async def scenario() -> None:
        rig = Rig(turn_taking_mode="push_to_talk")
        await rig.connect()
        config = rig.provider.configs[-1]
        assert config.turn_taking_mode == "push_to_talk"
        assert config.turn_sensitivity is None

    run(scenario)


def test_t01_switching_turn_taking_mode_keeps_the_same_hosting() -> None:
    async def scenario() -> None:
        rig = Rig(voice="female")
        rig.advance_to(2, 2)
        await rig.connect()
        assert rig.provider.configs[-1].turn_taking_mode == "auto"

        device = await rig.connect(turn_taking_mode="push_to_talk")

        assert rig.position() == ("turn", 2, 2)
        assert rig.snapshot.turn_taking_mode == "push_to_talk"
        assert rig.snapshot.voice == "female"
        config = rig.provider.configs[-1]
        assert config.turn_taking_mode == "push_to_talk"
        assert config.voice == "female"
        state = device.messages[0]
        assert isinstance(state, dict)
        assert state["turn_taking_mode"] == "push_to_talk"

    run(scenario)


def test_t02_after_switching_host_gets_full_instructions_and_only_says_back_to() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.connect(turn_taking_mode="push_to_talk")

        instructions = rig.provider.configs[-1].instructions
        assert len(instructions.splitlines()) == 12
        assert "第 2 回合" in instructions and content.PHASE_NAMES[2] in instructions
        assert rig.conn.speech_requests == [back_to(2, 2)]

    run(scenario)


def test_t03_talk_down_cancels_the_host_and_flushes() -> None:
    async def scenario() -> None:
        rig = Rig(turn_taking_mode="push_to_talk")
        rig.advance_to(1, 1)
        device = await rig.connect()
        await rig.press("next")
        await rig.host_starts()
        cancels = rig.count_action("cancel_response")

        await rig.device_sends(type="talk", state="down")

        assert rig.count_action("press_talk") == 1
        assert rig.count_action("cancel_response") == cancels + 1
        assert device.json()[-1] == {"type": "flush"}
        # 被按鍵打斷不自動重講；那一段留著等「繼續」
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 1

    run(scenario)


def test_t04_talk_up_asks_the_voice_model_to_answer() -> None:
    async def scenario() -> None:
        rig = Rig(turn_taking_mode="push_to_talk")
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.device_sends(type="talk", state="down")
        assert rig.count_action("release_talk") == 0
        await rig.device_sends(type="talk", state="up")
        assert rig.count_action("release_talk") == 1
        names = rig.conn.action_names()
        assert names.index("press_talk") < names.index("release_talk")

    run(scenario)


def test_t05_voice_stays_female_when_continuing() -> None:
    async def scenario() -> None:
        rig = Rig(voice="female")
        rig.advance_to(1, 3)
        await rig.connect()
        await rig.press("end")
        assert rig.relay is not None
        await rig.relay.close()

        await rig.connect()

        assert rig.provider.configs[-1].voice == "female"
        assert rig.snapshot.status == "active"

    run(scenario)


# --- 重新連線時交回的內容：M-06、M-07 ---


def test_m06_continuing_a_paused_hosting_hands_back_status_and_only_says_back_to() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(3, 2)
        await rig.connect()
        await rig.press("pause")
        assert rig.relay is not None
        await rig.relay.close()

        device = await rig.connect()

        instructions = rig.provider.configs[-1].instructions
        assert "第 3 回合" in instructions
        assert content.PHASE_NAMES[2] in instructions
        assert "主持暫停中" in instructions
        state = device.messages[0]
        assert isinstance(state, dict)
        assert (state["turn_number"], state["phase_number"], state["paused"]) == (3, 2, True)
        assert rig.conn.speech_requests == [back_to(3, 2)]

    run(scenario)


def test_m07_continuing_does_not_hand_back_old_questions_and_answers() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(3, 2)
        await rig.connect()
        await rig.tool("lookup_rules", question="獨特的問題甲乙丙")
        assert len(rig.tool_results("c1")) == 1
        assert rig.relay is not None
        await rig.relay.close()

        await rig.connect()

        handed = rig.provider.configs[-1].instructions + "".join(
            str(action) for action in rig.conn.actions
        )
        assert "獨特的問題甲乙丙" not in handed
        assert SIX_CHUNKS[0].content not in handed

    run(scenario)


# --- 保持連線：K-01、K-02 ---


def test_k01_silent_system_message_after_150_seconds() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        await rig.connect()
        speeches = len(rig.conn.speech_requests)

        await rig.advance(149)
        assert rig.count_action("send_system_message") == 0
        await rig.advance(1)

        messages = [a[1] for a in rig.conn.actions if a[0] == "send_system_message"]
        assert len(messages) == 1
        assert "第 2 回合" in messages[0] and content.PHASE_NAMES[2] in messages[0]
        # 沒有請主持人開口
        assert len(rig.conn.speech_requests) == speeches
        # 每 150 秒一則
        await rig.advance(150)
        assert rig.count_action("send_system_message") == 2

    run(scenario)


def test_k02_host_speaking_restarts_the_150_seconds() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.advance(100)
        await rig.host_finishes()

        await rig.advance(100)
        assert rig.count_action("send_system_message") == 0
        await rig.advance(49)
        assert rig.count_action("send_system_message") == 0
        await rig.advance(1)
        assert rig.count_action("send_system_message") == 1

    run(scenario)


# --- 後端和語音模型斷線：K-03、K-04 ---


def test_k03_reconnect_succeeds_on_the_second_try() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        device = await rig.connect()
        old_conn = rig.conn
        rig.provider.fail_connect(times=1)

        await rig.emit(ConnectionLost(reason="idle_timeout"))
        assert device.json("connection") == [{"type": "connection", "state": "reconnecting"}]
        assert rig.provider.connect_attempts == 1

        await rig.advance(1)
        assert rig.provider.connect_attempts == 2
        assert device.json("connection")[-1]["state"] == "reconnecting"
        await rig.advance(1.9)
        assert rig.provider.connect_attempts == 2
        await rig.advance(0.1)

        assert rig.provider.connect_attempts == 3
        assert [m["state"] for m in device.json("connection")] == ["reconnecting", "ready"]
        assert rig.conn is not old_conn
        instructions = rig.provider.configs[-1].instructions
        assert len(instructions.splitlines()) == 12
        assert "第 2 回合" in instructions
        assert rig.conn.speech_requests == [back_to(2, 2)]
        assert device.closed is False
        # 連回來之後照常運作
        await rig.press("next")
        assert rig.position() == ("turn", 2, 3)

    run(scenario)


def test_k03_reconnect_while_paused_says_nothing() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.press("pause")
        await rig.emit(ConnectionLost(reason="idle_timeout"))
        await rig.advance(1)
        assert rig.provider.connect_attempts == 2
        assert "主持暫停中" in rig.provider.configs[-1].instructions
        assert rig.conn.speech_requests == []

    run(scenario)


def test_k04_three_failed_reconnects_close_with_error_and_keep_the_hosting() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        device = await rig.connect()
        rig.provider.fail_connect(times=None)

        await rig.emit(ConnectionLost(reason="network"))
        await rig.advance(1)
        await rig.advance(2)
        assert device.error_codes() == []
        await rig.advance(4)

        assert rig.provider.connect_attempts == 4
        assert device.error_codes() == ["HOST_REALTIME_UNAVAILABLE"]
        assert device.closed is True
        assert rig.relay is not None and rig.relay.closed is True
        assert len(rig.service.list_sessions(OWNER)) == 1
        assert rig.position() == ("turn", 2, 2)

    run(scenario)


# --- 後端要主持人開口：K-05 到 K-07 ---


def test_k05_rejected_speech_is_resent_and_only_one_copy_goes_out() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        rig.conn.reject_speech("player_speaking", times=1)

        await rig.press("next")
        assert rule_points(1, 2) not in rig.conn.speech_requests

        await rig.advance(0.4)
        assert rule_points(1, 2) not in rig.conn.speech_requests
        await rig.advance(0.1)
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 1
        await rig.advance(5)
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 1

    run(scenario)


def test_k06_changing_step_stops_resending_the_old_speech() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        rig.conn.reject_speech("response_in_progress", times=None)
        await rig.press("next")
        await rig.advance(1.5)
        assert rule_points(1, 2) not in rig.conn.speech_requests

        await rig.hears("下一步")
        assert rig.position() == ("turn", 1, 3)
        rig.conn.accept_speech()
        await rig.advance(0.5)
        await rig.advance(5)

        assert rig.conn.speech_requests.count(rule_points(1, 3)) == 1
        assert rule_points(1, 2) not in rig.conn.speech_requests

    run(scenario)


def test_pausing_stops_resending() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        rig.conn.reject_speech("player_speaking", times=None)
        await rig.press("next")
        await rig.press("pause")
        rig.conn.accept_speech()
        await rig.advance(5)
        assert rule_points(1, 2) not in rig.conn.speech_requests

    run(scenario)


def test_k07_wait_longer_is_not_resent_when_rejected() -> None:
    async def scenario() -> None:
        thinking = blocked_thinking()
        rig = Rig(thinking=thinking)
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.tool("ask_thinking_model", question=QUESTION)
        rig.conn.reject_speech("player_speaking", times=None)

        await rig.advance(8)
        await rig.advance(3)

        wait_longer = ("request_speech", line("wait_longer"))
        assert rig.conn.actions.count(wait_longer) == 1
        thinking.release.set()

    run(scenario)


# --- 查規則與思考模型的計時：Q-06 到 Q-08 ---


def test_lookup_tool_gets_the_chunks_and_device_sees_looking_up() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 2)
        device = await rig.connect()
        states = len(device.json("state"))

        await rig.tool("lookup_rules", question=QUESTION)

        assert rig.lookup.questions == [QUESTION]
        results = rig.tool_results("c1")
        assert len(results) == 1
        _, _, output, respond = results[0]
        assert respond is True
        assert SIX_CHUNKS[0].content in output
        assert [m["looking_up"] for m in device.json("state")[states:]] == [True, False]

    run(scenario)


def test_thinking_model_answers_quickly_without_wait_longer() -> None:
    async def scenario() -> None:
        rig = Rig(thinking=FakeThinkingModel(reply="可以，全桌都不出。"))
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.tool("ask_thinking_model", question=QUESTION)
        await rig.until(lambda: len(rig.tool_results("c1")) == 1)
        assert "可以，全桌都不出。" in rig.tool_results("c1")[0][2]
        await rig.advance(20)
        assert line("wait_longer") not in rig.conn.speech_requests
        assert len(rig.tool_results("c1")) == 1

    run(scenario)


def test_q06_wait_longer_once_at_8_seconds_then_the_answer() -> None:
    async def scenario() -> None:
        thinking = blocked_thinking()
        rig = Rig(thinking=thinking)
        rig.advance_to(2, 2)
        device = await rig.connect()
        await rig.tool("ask_thinking_model", question=QUESTION)
        assert device.last_state()["looking_up"] is True

        await rig.advance(7.9)
        assert line("wait_longer") not in rig.conn.speech_requests
        await rig.advance(0.1)
        assert rig.conn.speech_requests.count(line("wait_longer")) == 1
        assert rig.tool_results("c1") == []

        # 第 10 秒思考模型回來
        await rig.advance(2)
        thinking.release.set()
        await rig.until(lambda: len(rig.tool_results("c1")) == 1)

        _, _, output, respond = rig.tool_results("c1")[0]
        assert "可以，全桌都不出。" in output
        assert respond is True
        assert device.last_state()["looking_up"] is False
        await rig.advance(10)
        assert rig.conn.speech_requests.count(line("wait_longer")) == 1
        assert len(rig.tool_results("c1")) == 1

    run(scenario)


def test_q07_gives_up_at_15_seconds_and_drops_the_late_answer() -> None:
    async def scenario() -> None:
        thinking = blocked_thinking()
        rig = Rig(thinking=thinking)
        rig.advance_to(2, 2)
        device = await rig.connect()
        await rig.tool("ask_thinking_model", question=QUESTION)

        await rig.advance(8)
        assert rig.conn.speech_requests.count(line("wait_longer")) == 1
        await rig.advance(6.9)
        assert rig.tool_results("c1") == []
        await rig.advance(0.1)

        results = rig.tool_results("c1")
        assert len(results) == 1
        output = results[0][2]
        for chunk in SIX_CHUNKS:
            assert chunk.content in output
        assert content.fixed_line("not_sure") in output
        assert device.last_state()["looking_up"] is False

        # 第 20 秒思考模型才回來：答案丟掉
        await rig.advance(5)
        thinking.release.set()
        await rig.until(lambda: len(thinking.prompts) == 1)
        await rig.settle()
        assert len(rig.tool_results("c1")) == 1
        assert "可以，全桌都不出。" not in "".join(str(a) for a in rig.conn.actions)

    run(scenario)


def test_q08_thinking_model_error_hands_over_chunks_right_away() -> None:
    async def scenario() -> None:
        rig = Rig(thinking=FakeThinkingModel(error=LLMUnavailable("連不上")))
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.tool("ask_thinking_model", question=QUESTION)
        await rig.until(lambda: len(rig.tool_results("c1")) == 1)

        output = rig.tool_results("c1")[0][2]
        assert SIX_CHUNKS[0].content in output
        assert content.fixed_line("not_sure") in output
        # 馬上交，沒有等到第 8 秒；之後也不再補
        assert rig.timers.time == 0
        await rig.advance(20)
        assert line("wait_longer") not in rig.conn.speech_requests
        assert len(rig.tool_results("c1")) == 1

    run(scenario)


def test_second_question_closes_the_first_tool_call_without_an_answer() -> None:
    async def scenario() -> None:
        thinking = blocked_thinking(reply="第一題的答案")
        rig = Rig(thinking=thinking)
        rig.advance_to(2, 2)
        await rig.connect()
        await rig.tool("ask_thinking_model", call_id="c1", speech_id="s1", question="第一題")
        await rig.tool("lookup_rules", call_id="c2", speech_id="s2", question="第二題")

        first = rig.tool_results("c1")
        assert len(first) == 1
        assert first[0][3] is False
        assert SIX_CHUNKS[0].content in rig.tool_results("c2")[0][2]

        thinking.release.set()
        await rig.until(lambda: len(thinking.prompts) == 1)
        await rig.advance(20)
        assert len(rig.tool_results("c1")) == 1
        assert "第一題的答案" not in "".join(str(a) for a in rig.conn.actions)
        assert line("wait_longer") not in rig.conn.speech_requests

    run(scenario)


def test_host_replying_to_something_else_voids_the_waiting_question() -> None:
    """等待中玩家說「算了」，主持人自己回了一句：舊題作廢，答案晚到也不唸（spec §8.4）。"""

    async def scenario() -> None:
        thinking = blocked_thinking()
        rig = Rig(thinking=thinking)
        rig.advance_to(2, 2)
        device = await rig.connect()
        # 連上時那句接回流程的話先說完，之後主持人再開口才是它自己要說的
        await rig.host_finishes()
        await rig.tool("ask_thinking_model", question=QUESTION)
        await rig.hears("算了", speech_id="s2")

        await rig.host_starts()

        assert device.last_state()["looking_up"] is False
        thinking.release.set()
        await rig.until(lambda: len(thinking.prompts) == 1)
        await rig.settle()
        assert "可以，全桌都不出。" not in "".join(str(a) for a in rig.conn.actions)

    run(scenario)


# --- 語音指令的兩條路：V-11 到 V-17 ---


def test_v11_partial_command_followed_by_more_words_does_nothing() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 1)
        await rig.connect()
        await rig.hears("等一下", final=False)
        await rig.advance(0.2)
        await rig.hears("等一下再出牌", final=False)
        await rig.advance(0.3)
        assert rig.snapshot.paused is False
        await rig.hears("等一下再出牌。", final=True)
        await rig.advance(1)
        assert rig.snapshot.paused is False

    run(scenario)


def test_v12_partial_command_with_nothing_after_it_runs_after_300_ms() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 1)
        await rig.connect()
        await rig.hears("等一下", final=False)
        await rig.advance(0.29)
        assert rig.snapshot.paused is False
        await rig.advance(0.01)
        assert rig.snapshot.paused is True
        # 之後完整的辨識文字才到：同一句不再執行一次
        await rig.press("resume")
        await rig.hears("等一下。", final=True)
        assert rig.snapshot.paused is False

    run(scenario)


def test_v13_tool_call_is_verified_with_the_backends_own_transcript() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        # 只有片段、還沒等滿 0.3 秒：模型的工具請求先到，用後端手上的辨識文字核對
        await rig.hears("下一步", final=False)
        assert rig.position() == ("turn", 1, 1)

        await rig.tool("next_step")

        assert rig.position() == ("turn", 1, 2)
        results = rig.tool_results("c1")
        assert len(results) == 1
        # 主持人不自己回話；新階段的規則要點由後端另外交
        assert results[0][3] is False
        assert rig.conn.speech_requests[-1] == rule_points(1, 2)

    run(scenario)


def test_v14_tool_call_that_fails_verification_is_told_it_is_not_a_command() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        speeches = list(rig.conn.speech_requests)
        await rig.hears("你下一步要出什麼")

        await rig.tool("next_step")

        assert rig.position() == ("turn", 1, 1)
        _, _, output, respond = rig.tool_results("c1")[0]
        assert "不是指令" in output
        assert respond is False
        assert rig.conn.speech_requests == speeches

    run(scenario)


def test_v14_end_hosting_winner_comes_from_the_transcript_not_the_model() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        await rig.hears("血刃贏了")
        await rig.tool("end_hosting", winner="white_rose")
        assert rig.snapshot.status == "ended"
        assert rig.snapshot.winner == "blood_blade"

    run(scenario)


def test_v15_same_sentence_is_only_executed_once() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        # 路 2 先執行
        await rig.hears("下一步")
        assert rig.position() == ("turn", 1, 2)

        # 路 1 的工具請求後到
        await rig.tool("next_step")

        assert rig.position() == ("turn", 1, 2)
        assert len(rig.tool_results("c1")) == 1
        assert rig.tool_results("c1")[0][3] is False
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 1

    run(scenario)


def test_v15_tool_first_then_transcript_is_also_executed_once() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        # 工具請求先到，辨識文字還沒來：先不動
        await rig.tool("next_step")
        assert rig.position() == ("turn", 1, 1)
        assert len(rig.tool_results("c1")) == 1

        await rig.hears("下一步", final=False)
        await rig.hears("下一步。", final=True)
        await rig.advance(1)

        assert rig.position() == ("turn", 1, 2)

    run(scenario)


def test_v16_two_sentences_move_two_phases() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.hears("下一步", speech_id="s1")
        await rig.advance(30)
        await rig.hears("下一步", speech_id="s2")
        assert rig.position() == ("turn", 1, 3)

    run(scenario)


def test_v17_voice_command_works_while_holding_to_talk() -> None:
    async def scenario() -> None:
        rig = Rig(turn_taking_mode="push_to_talk")
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.device_sends(type="talk", state="down")
        await rig.hears("下一步")
        await rig.device_sends(type="talk", state="up")
        assert rig.position() == ("turn", 1, 2)

    run(scenario)


# --- 閒聊：模型呼叫「不回應」或被判定成不是在跟它說話 ---


def test_no_reply_tool_gets_an_empty_result_and_host_stays_silent() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        speeches = list(rig.conn.speech_requests)
        await rig.tool("no_reply")
        assert rig.tool_results("c1") == [("send_tool_result", "c1", "", False)]
        assert rig.conn.speech_requests == speeches

    run(scenario)


@pytest.mark.parametrize("signal", ["no_reply", "not_addressed"])
def test_chatter_that_cut_the_host_off_replays_the_segment(signal: str) -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        device = await rig.connect()
        await rig.press("next")
        utterance_id = await rig.host_starts()
        # 有人開口，語音模型自己取消了正在說的那一段
        await rig.emit(
            PlayerSpeechStarted(),
            HostUtteranceEnded(utterance_id=utterance_id, cancelled=True),
        )
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 1

        if signal == "no_reply":
            await rig.tool("no_reply", speech_id="s9")
        else:
            await rig.emit(SpeechNotAddressed(speech_id="s9"))

        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 2
        assert device.last_state()["paused"] is False

        # 連續被切斷：重講 2 次之後進入主持暫停
        for expected in (3, 3):
            utterance_id = await rig.host_starts()
            await rig.emit(
                PlayerSpeechStarted(),
                HostUtteranceEnded(utterance_id=utterance_id, cancelled=True),
                SpeechNotAddressed(speech_id=f"s{expected}{utterance_id}"),
            )
            assert rig.conn.speech_requests.count(rule_points(1, 2)) == expected
        assert device.last_state()["paused"] is True
        assert device.last_state()["pause_reason"] == "chatter"

    run(scenario)


def test_a_rules_question_that_cut_the_host_off_does_not_replay() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.press("next")
        utterance_id = await rig.host_starts()
        await rig.emit(
            PlayerSpeechStarted(),
            HostUtteranceEnded(utterance_id=utterance_id, cancelled=True),
        )
        await rig.tool("lookup_rules", question=QUESTION)
        # 之後的閒聊不會回頭重講被問題打斷的那一段
        await rig.emit(SpeechNotAddressed(speech_id="s5"))
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 1
        # 玩家說「繼續」才重講
        await rig.hears("繼續", speech_id="s6")
        assert rig.conn.speech_requests.count(rule_points(1, 2)) == 2

    run(scenario)


def test_unknown_tool_is_answered_without_touching_the_flow() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.tool("open_the_door")
        assert len(rig.tool_results("c1")) == 1
        assert rig.tool_results("c1")[0][3] is False
        assert rig.position() == ("turn", 1, 1)

    run(scenario)


# --- 紀錄與分層（spec §13.3、§13.5） ---


def test_usage_is_logged_but_what_players_say_is_not(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.emit(
            HostUtteranceStarted(utterance_id="u1"),
            HostUtteranceEnded(utterance_id="u1", cancelled=False, usage={"total_tokens": 4321}),
        )
        await rig.hears("我的水晶是三號不要說出去")
        await rig.tool("lookup_rules", question="我的水晶是三號可以放嗎")

    with caplog.at_level(logging.DEBUG, logger="app.domains.host"):
        run(scenario)
    assert "4321" in caplog.text
    assert "水晶是三號" not in caplog.text


def test_relay_does_not_import_vendor_sdks_or_know_vendor_event_names() -> None:
    source = Path(relay_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert name.split(".")[0] not in ("dashscope", "openai", "websockets", "fastapi"), name
    host_dir = Path(relay_module.__file__).parent
    for path in host_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for vendor_word in ("dashscope", "response.audio", "input_audio_buffer", "session.update"):
            assert vendor_word not in text, f"{path.name} 出現 {vendor_word}"


# --- 結束這個動作相信語音模型（2026-11-22 立倫決定，spec §5.2） ---
#
# 實測：語音模型的辨識文字幾乎認不出「血刃」（「血刃贏了」30 句只有 2 句辨識正確，
# 其他變成「写着名字」「确认延误」等），但模型自己聽聲音有 21 句呼叫了結束。


@pytest.mark.parametrize(
    "heard, winner, line_code",
    [
        ("写着名字。", "blood_blade", "end_blood_blade"),
        ("确认延误。", "blood_blade", "end_blood_blade"),
        ("现任郑盈盈了。", "blood_blade", "end_blood_blade"),
        ("白墙为赢了", "white_rose", "end_white_rose"),
        ("确认无误了。", None, "end_plain"),
    ],
)
def test_end_tool_is_trusted_when_the_transcript_is_garbled(
    heard: str, winner: str | None, line_code: str
) -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        await rig.hears(heard)
        assert rig.snapshot.status == "active"

        arguments = {"winner": winner} if winner else {}
        await rig.tool("end_hosting", **arguments)

        assert rig.snapshot.status == "ended"
        assert rig.snapshot.winner == winner
        assert rig.conn.speech_requests[-1] == line(line_code)
        assert rig.tool_results("c1")[0][3] is False

    run(scenario)


@pytest.mark.parametrize(
    "heard",
    [
        "血刃赢了吗？",
        "这局是不是快要结束了",
        "我觉得血刃这次应该会赢了吧",
    ],
)
def test_end_tool_is_not_trusted_for_questions_or_long_sentences(heard: str) -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        await rig.hears(heard)
        await rig.tool("end_hosting", winner="blood_blade")
        assert rig.snapshot.status == "active"
        assert "不是指令" in rig.tool_results("c1")[0][2]

    run(scenario)


def test_end_tool_waits_for_the_transcript_when_it_has_not_arrived() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        # 工具請求先到：還不知道那句話是不是問句、有多長，先不動
        await rig.tool("end_hosting", winner="blood_blade")
        assert rig.snapshot.status == "active"

        await rig.hears("写着名字。")

        assert rig.snapshot.status == "ended"
        assert rig.snapshot.winner == "blood_blade"

    run(scenario)


def test_end_tool_waiting_for_the_transcript_is_dropped_for_a_question() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        await rig.tool("end_hosting", winner="blood_blade")
        await rig.hears("血刃赢了吗？")
        assert rig.snapshot.status == "active"

    run(scenario)


def test_end_tool_with_an_unknown_winner_ends_without_a_winner() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        await rig.hears("写着名字。")
        await rig.tool("end_hosting", winner="everyone")
        assert rig.snapshot.status == "ended"
        assert rig.snapshot.winner is None

    run(scenario)


def test_other_command_tools_still_need_the_exact_words() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(1, 1)
        await rig.connect()
        await rig.hears("写着名字。")
        for index, tool in enumerate(
            ["next_step", "previous_step", "pause_hosting", "resume_hosting"]
        ):
            await rig.tool(tool, call_id=f"c{index}")
            assert "不是指令" in rig.tool_results(f"c{index}")[0][2]
        assert rig.position() == ("turn", 1, 1)
        assert rig.snapshot.paused is False

    run(scenario)


def test_trusted_end_is_only_executed_once_per_sentence() -> None:
    async def scenario() -> None:
        rig = Rig()
        rig.advance_to(2, 3)
        await rig.connect()
        await rig.hears("写着名字。")
        await rig.tool("end_hosting", call_id="c1", winner="blood_blade")
        await rig.tool("end_hosting", call_id="c2", winner="blood_blade")
        assert rig.conn.speech_requests.count(line("end_blood_blade")) == 1

    run(scenario)
