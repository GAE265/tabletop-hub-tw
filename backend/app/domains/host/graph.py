"""主持的圖（host spec §3、§5、§9；ADR 0004）。

每件事（按鍵、語音指令、裝置回報播完）跑一次圖。整局記憶放 LangGraph 內建的記憶體儲存，
一場主持一份。帶流程由程式決定：這裡的節點都是照規則跑的程式，不叫 LLM。

圖跑完交回「要做的事」的清單（Effect）。真的去做這些事（請主持人開口、送訊息給裝置）
是轉送那一段的工作，這個檔案不碰連線。
"""

import threading
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.domains.host import content

# 指令的動作。next：下一步；previous：上一步；pause：暫停；resume：繼續；end：結束
Action = Literal["next", "previous", "pause", "resume", "end"]
# 主持暫停的原因。command：語音指令或按鍵；page_hidden：頁面被切走或鎖屏；
# chatter：同一段被閒聊切斷太多次
PauseReason = Literal["command", "page_hidden", "chatter"]

# 開場與夜晚兩步：那一段在裝置上播完之後，後端自己換到下一個節點（spec §3.1）
_AUTO_ADVANCE_STEPS = ("opening", "night_1", "night_2")
_STEPS_BEFORE_FIRST_TURN = ("opening", "setup", "night_1", "night_2")


# --- 語音指令的核對（spec §5） ---


@dataclass(frozen=True)
class VoiceCommand:
    action: Action
    # 只有 end 會帶；None 代表沒說哪一方
    winner: content.Winner | None = None


# spec §5.1 的說法清單（含「也接受」的同音字）
_PHRASES: dict[str, VoiceCommand] = {
    "等一下": VoiceCommand("pause"),
    "暫停": VoiceCommand("pause"),
    "繼續": VoiceCommand("resume"),
    "下一步": VoiceCommand("next"),
    "下一部": VoiceCommand("next"),
    "上一步": VoiceCommand("previous"),
    "上一部": VoiceCommand("previous"),
    "結束了": VoiceCommand("end"),
    "白薔薇贏了": VoiceCommand("end", "white_rose"),
    "白薔薇陣營贏了": VoiceCommand("end", "white_rose"),
    "血刃贏了": VoiceCommand("end", "blood_blade"),
    "血刃陣營贏了": VoiceCommand("end", "blood_blade"),
}
# 簡體轉繁體的小對照表：只涵蓋說法清單上會出現的字，不加套件（spec §5.2）
_TO_TRADITIONAL = str.maketrans(
    {
        "暂": "暫",
        "继": "繼",
        "续": "續",
        "结": "結",
        "蔷": "薔",
        "赢": "贏",
        "阵": "陣",
        "营": "營",
    }
)
_HOST_PREFIX = "主持人"


def match_voice_command(text: str) -> VoiceCommand | None:
    """spec §5.2 的五個步驟。整句就是指令才算，回傳 None 代表這不是指令。"""
    # 1. 原句有問號：不算
    if "?" in text or "？" in text:
        return None
    # 2. 簡體轉繁體
    text = text.translate(_TO_TRADITIONAL)
    # 3. 去掉標點與空白（Unicode 的標點 P、分隔 Z、控制 C、符號 S）
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] not in "PZCS")
    # 4. 開頭有「主持人」就去掉
    if text.startswith(_HOST_PREFIX):
        text = text[len(_HOST_PREFIX) :]
    # 5. 剩下的字要整句等於清單上的一個說法
    return _PHRASES.get(text)


# --- 進來的事 ---


@dataclass(frozen=True)
class HostEvent:
    """交給圖處理的一件事。用下面的工廠方法建立。"""

    type: str
    action: Action | None = None
    winner: content.Winner | None = None
    text: str | None = None
    segment_id: int | None = None

    @staticmethod
    def connected() -> "HostEvent":
        """裝置連上了。這場主持還沒開場就交出開場台詞。"""
        return HostEvent("connected")

    @staticmethod
    def command(action: Action) -> "HostEvent":
        """按鍵。效果和語音指令相同，不用核對；按鍵的結束不帶贏的一方。"""
        return HostEvent("command", action=action)

    @staticmethod
    def voice_text(text: str) -> "HostEvent":
        """玩家一句話的辨識文字，要過核對才算語音指令。"""
        return HostEvent("voice_text", text=text)

    @staticmethod
    def playback_done(segment_id: int) -> "HostEvent":
        """裝置回報某一段播完了。"""
        return HostEvent("playback_done", segment_id=segment_id)


# --- 交回去的事 ---


@dataclass(frozen=True)
class HostSnapshot:
    """一場主持的現況，API 的 session 與 WebSocket 的 state 訊息都從這裡來。"""

    # active：進行中；ended：已結束
    status: Literal["active", "ended"]
    player_count: int
    turn_taking_mode: str
    voice: str
    step: content.Step
    turn_number: int | None
    phase_number: int | None
    paused: bool
    pause_reason: PauseReason | None
    looking_up: bool
    winner: content.Winner | None


@dataclass(frozen=True)
class Speak:
    """請主持人說一段內容。text 是要交給語音模型的文字。"""

    segment_id: int
    # line：固定台詞（code 是 spec §4.1 的代號）；rule_points：規則要點
    kind: Literal["line", "rule_points"]
    text: str
    code: str | None = None
    phase_number: int | None = None
    version: content.RulePointsVersion | None = None


@dataclass(frozen=True)
class Flush:
    """請裝置停播並清空待播內容，同時取消主持人正在產生的回答。"""


@dataclass(frozen=True)
class StateChanged:
    """現況變了，帶變了之後的整份現況。"""

    snapshot: HostSnapshot


Effect = Speak | Flush | StateChanged


@dataclass
class Outcome:
    """圖跑一次的結果：要做的事的清單，加上這件事本身的結果（例如語音指令有沒有通過核對）。"""

    effects: list[Effect] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)


# --- 整局記憶（spec §9） ---


class HostMemory(TypedDict, total=False):
    # 開主持時給的三樣
    player_count: int
    turn_taking_mode: str
    voice: str
    # 節點、第幾回合、哪個階段
    step: content.Step
    turn_number: int | None
    phase_number: int | None
    # 是不是已經交出過開場台詞
    opened: bool
    # 結束前在哪個節點（接著主持時回去用）、贏的一方
    step_before_end: content.Step | None
    winner: content.Winner | None
    # 主持暫停與原因
    paused: bool
    pause_reason: PauseReason | None
    # 主持人正在說、還沒播完的那一段；同一段已自動重講幾次
    segment: dict[str, Any] | None
    replay_count: int
    segment_seq: int
    # 最近 5 題的問題與查到的頁碼
    recent_questions: list[dict[str, Any]]
    # --- 每跑一次圖都會換掉的欄位 ---
    event: dict[str, Any]
    # 這次要執行的指令（核對通過的語音指令、按鍵、或自動進）
    command: dict[str, Any] | None


_RUN_ONLY_KEYS = ("event", "command")


def _initial_memory(*, player_count: int, turn_taking_mode: str, voice: str) -> HostMemory:
    return HostMemory(
        player_count=player_count,
        turn_taking_mode=turn_taking_mode,
        voice=voice,
        step="opening",
        turn_number=None,
        phase_number=None,
        opened=False,
        step_before_end=None,
        winner=None,
        paused=False,
        pause_reason=None,
        segment=None,
        replay_count=0,
        segment_seq=0,
        recent_questions=[],
    )


def _snapshot(memory: HostMemory) -> HostSnapshot:
    return HostSnapshot(
        status="ended" if memory["step"] == "ended" else "active",
        player_count=memory["player_count"],
        turn_taking_mode=memory["turn_taking_mode"],
        voice=memory["voice"],
        step=memory["step"],
        turn_number=memory["turn_number"],
        phase_number=memory["phase_number"],
        paused=memory["paused"],
        pause_reason=memory["pause_reason"],
        looking_up=False,
        winner=memory["winner"],
    )


class _Run:
    """跑一次圖的過程中，節點把要做的事交到這裡。不進整局記憶。"""

    def __init__(self, on_effect: Callable[[Effect], None] | None) -> None:
        self.outcome = Outcome()
        self._on_effect = on_effect

    def emit(self, effect: Effect) -> None:
        self.outcome.effects.append(effect)
        if self._on_effect is not None:
            self._on_effect(effect)


def _run_of(config: RunnableConfig) -> _Run:
    return config["configurable"]["run"]


# --- 換節點的規則（spec §3.2） ---

_Position = tuple[content.Step, int | None, int | None]


def _next_position(memory: HostMemory) -> _Position | Literal["end"] | None:
    """下一步會到哪。None 代表不動；"end" 代表圓版放滿，當成結束。"""
    step = memory["step"]
    if step == "opening":
        return ("setup", None, None)
    if step == "setup":
        return ("night_1", None, None)
    if step == "night_1":
        return ("night_2", None, None)
    if step == "night_2":
        return ("turn", 1, 1)
    if step == "turn":
        turn_number, phase_number = memory["turn_number"], memory["phase_number"]
        assert turn_number is not None and phase_number is not None
        if phase_number < content.PHASES_PER_TURN:
            return ("turn", turn_number, phase_number + 1)
        if turn_number < content.game_numbers(memory["player_count"]).board_slots:
            return ("turn", turn_number + 1, 1)
        return "end"
    return None


def _previous_position(memory: HostMemory) -> _Position | None:
    """上一步會到哪。None 代表不動。"""
    step = memory["step"]
    if step == "setup":
        return ("opening", None, None)
    if step == "night_1":
        return ("setup", None, None)
    if step == "night_2":
        return ("night_1", None, None)
    if step == "turn":
        turn_number, phase_number = memory["turn_number"], memory["phase_number"]
        assert turn_number is not None and phase_number is not None
        if phase_number > 1:
            return ("turn", turn_number, phase_number - 1)
        if turn_number > 1:
            return ("turn", turn_number - 1, content.PHASES_PER_TURN)
        return ("night_2", None, None)
    return None


def _node_segment(position: _Position) -> dict[str, Any]:
    """一個節點要說的那一段（還沒編號）。"""
    step, turn_number, phase_number = position
    if step == "turn":
        assert turn_number is not None and phase_number is not None
        points = content.rule_points(turn_number=turn_number, phase_number=phase_number)
        return {
            "kind": "rule_points",
            "code": None,
            "text": content.rule_points_text(turn_number=turn_number, phase_number=phase_number),
            "phase_number": phase_number,
            "version": points.version,
            # 這一段播完之後要不要自動進下一個節點
            "auto_advance": False,
        }
    return _line_segment(step, auto_advance=step in _AUTO_ADVANCE_STEPS)


def _line_segment(code: str, *, auto_advance: bool = False) -> dict[str, Any]:
    return {
        "kind": "line",
        "code": code,
        "text": content.verbatim_request(content.fixed_line(code)),
        "phase_number": None,
        "version": None,
        "auto_advance": auto_advance,
    }


def _speak(memory: HostMemory, segment: dict[str, Any], run: _Run) -> dict[str, Any]:
    """替這一段編號、請主持人說，並記成「正在說、還沒播完的那一段」。回傳要寫回記憶的欄位。"""
    segment_id = memory["segment_seq"] + 1
    numbered = {**segment, "id": segment_id}
    run.emit(
        Speak(
            segment_id=segment_id,
            kind=numbered["kind"],
            text=numbered["text"],
            code=numbered["code"],
            phase_number=numbered["phase_number"],
            version=numbered["version"],
        )
    )
    return {"segment": numbered, "segment_seq": segment_id}


def _emit_state(memory: HostMemory, updates: dict[str, Any], run: _Run) -> None:
    run.emit(StateChanged(_snapshot({**memory, **updates})))  # type: ignore[typeddict-item]


# --- 節點 ---


def _receive(state: HostMemory) -> dict[str, Any]:
    """入口：按鍵直接變成這次要執行的指令；其他的事交給各自的節點。"""
    event = state["event"]
    if event["type"] == "command":
        return {"command": {"action": event["action"], "winner": None}}
    return {"command": None}


def _route_event(state: HostMemory) -> str:
    event_type = state["event"]["type"]
    if event_type == "command":
        return _route_command(state)
    return {
        "connected": "connect",
        "voice_text": "verify_voice_command",
        "playback_done": "playback_done",
    }[event_type]


def _route_command(state: HostMemory) -> str:
    command = state.get("command")
    if command is None:
        return END
    return {
        "next": "change_step",
        "previous": "change_step",
        "pause": "pause",
        "resume": "resume",
        "end": "end_hosting",
    }[command["action"]]


def _connect(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """裝置連上。還沒開場就交出開場台詞。"""
    run = _run_of(config)
    if state["opened"]:
        return {}
    updates: dict[str, Any] = {"opened": True}
    updates.update(_speak(state, _node_segment(("opening", None, None)), run))
    return updates


def _verify_voice_command(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """核對辨識文字是不是語音指令（spec §5.2）。沒過就什麼都不動。"""
    run = _run_of(config)
    matched = match_voice_command(state["event"]["text"] or "")
    if matched is None:
        run.outcome.result.update({"verified": False, "action": None})
        return {"command": None}
    run.outcome.result.update({"verified": True, "action": matched.action})
    return {"command": {"action": matched.action, "winner": matched.winner}}


def _playback_done(state: HostMemory) -> dict[str, Any]:
    """裝置回報播完：清掉那一段；開場與夜晚兩步播完就自動進下一個節點。"""
    segment = state["segment"]
    if segment is None or segment["id"] != state["event"]["segment_id"]:
        return {"command": None}
    updates: dict[str, Any] = {"segment": None, "replay_count": 0, "command": None}
    if segment["auto_advance"] and state["step"] in _AUTO_ADVANCE_STEPS:
        updates["command"] = {"action": "next", "winner": None}
    return updates


def _change_step(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """下一步、上一步（spec §3.2）。換到新節點後，請主持人說那個節點的內容。"""
    run = _run_of(config)
    command = state["command"]
    assert command is not None
    if command["action"] == "next":
        target = _next_position(state)
        if target == "end":
            return _end(state, None, run)
    else:
        target = _previous_position(state)
    if target is None:
        # 不動的時候，主持人不出聲
        return {}
    step, turn_number, phase_number = target
    updates: dict[str, Any] = {
        "step": step,
        "turn_number": turn_number,
        "phase_number": phase_number,
        "replay_count": 0,
    }
    if state["segment"] is not None:
        # 舊節點的那一段還沒播完：先停掉，換了節點那一段就作廢
        run.emit(Flush())
    _emit_state(state, updates, run)
    updates.update(_speak(state, _node_segment(target), run))
    return updates


def _pause(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """進入主持暫停。已結束或已經在暫停中就不動。"""
    run = _run_of(config)
    if state["step"] == "ended" or state["paused"]:
        return {}
    updates: dict[str, Any] = {"paused": True, "pause_reason": "command"}
    _emit_state(state, updates, run)
    return updates


def _resume(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """繼續。已結束或不在暫停中就不動。"""
    run = _run_of(config)
    if state["step"] == "ended" or not state["paused"]:
        return {}
    updates: dict[str, Any] = {"paused": False, "pause_reason": None}
    _emit_state(state, updates, run)
    return updates


def _end_hosting(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """結束（spec §3.3）：語音指令、按鍵。已結束就不動。"""
    command = state["command"]
    assert command is not None
    return _end(state, command["winner"], _run_of(config))


def _end(state: HostMemory, winner: content.Winner | None, run: _Run) -> dict[str, Any]:
    if state["step"] == "ended":
        return {}
    updates: dict[str, Any] = {
        # 回合與階段保留結束前的值
        "step_before_end": state["step"],
        "step": "ended",
        "winner": winner,
        "paused": False,
        "pause_reason": None,
        "replay_count": 0,
    }
    if state["segment"] is not None:
        run.emit(Flush())
    _emit_state(state, updates, run)
    code = {"white_rose": "end_white_rose", "blood_blade": "end_blood_blade", None: "end_plain"}[
        winner
    ]
    updates.update(_speak(state, _line_segment(code), run))
    return updates


def _build_graph() -> StateGraph:
    builder = StateGraph(HostMemory)
    builder.add_node("receive", _receive)
    builder.add_node("connect", _connect)
    builder.add_node("verify_voice_command", _verify_voice_command)
    builder.add_node("playback_done", _playback_done)
    builder.add_node("change_step", _change_step)
    builder.add_node("pause", _pause)
    builder.add_node("resume", _resume)
    builder.add_node("end_hosting", _end_hosting)

    command_targets = {
        "change_step": "change_step",
        "pause": "pause",
        "resume": "resume",
        "end_hosting": "end_hosting",
        END: END,
    }
    builder.add_edge(START, "receive")
    builder.add_conditional_edges(
        "receive",
        _route_event,
        {
            "connect": "connect",
            "verify_voice_command": "verify_voice_command",
            "playback_done": "playback_done",
            **command_targets,
        },
    )
    builder.add_conditional_edges("verify_voice_command", _route_command, command_targets)
    builder.add_conditional_edges("playback_done", _route_command, command_targets)
    for node in ("connect", "change_step", "pause", "resume", "end_hosting"):
        builder.add_edge(node, END)
    return builder


class HostGraph:
    """主持的圖與每一場主持的整局記憶。整個後端共用一個。"""

    def __init__(self) -> None:
        self._saver = InMemorySaver()
        self._graph = _build_graph().compile(checkpointer=self._saver)
        # 同一場主持一次只處理一件事，其他的排隊（spec §8.1）
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # --- 一場主持的生與滅 ---

    def create(
        self, session_id: str, *, player_count: int, turn_taking_mode: str, voice: str
    ) -> HostSnapshot:
        content.game_numbers(player_count)
        memory = _initial_memory(
            player_count=player_count, turn_taking_mode=turn_taking_mode, voice=voice
        )
        with self._lock_for(session_id):
            self._graph.update_state(self._config(session_id), memory)
        return _snapshot(memory)

    def exists(self, session_id: str) -> bool:
        return bool(self._graph.get_state(self._config(session_id)).values)

    def delete(self, session_id: str) -> None:
        """清掉這場主持的整局記憶。"""
        with self._lock_for(session_id):
            self._saver.delete_thread(session_id)
        with self._locks_guard:
            self._locks.pop(session_id, None)

    # --- 讀 ---

    def memory(self, session_id: str) -> dict[str, Any]:
        """整局記憶（不含每跑一次圖就換掉的欄位）。找不到這場主持時拋 KeyError。"""
        values = self._graph.get_state(self._config(session_id)).values
        if not values:
            raise KeyError(session_id)
        return {key: value for key, value in values.items() if key not in _RUN_ONLY_KEYS}

    def snapshot(self, session_id: str) -> HostSnapshot:
        return _snapshot(self.memory(session_id))  # type: ignore[arg-type]

    def mermaid(self) -> str:
        """流程圖的 Mermaid 文字（spec §13.6）。"""
        return self._graph.get_graph().draw_mermaid()

    # --- 跑圖 ---

    def handle(
        self,
        session_id: str,
        event: HostEvent,
        *,
        on_effect: Callable[[Effect], None] | None = None,
    ) -> Outcome:
        """處理一件事。on_effect 會在節點交出每一件要做的事的當下被呼叫。"""
        run = _Run(on_effect)
        with self._lock_for(session_id):
            if not self.exists(session_id):
                raise KeyError(session_id)
            self._graph.invoke({"event": asdict(event)}, self._config(session_id, run=run))
        return run.outcome

    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    @staticmethod
    def _config(session_id: str, *, run: _Run | None = None) -> RunnableConfig:
        configurable: dict[str, Any] = {"thread_id": session_id}
        if run is not None:
            configurable["run"] = run
        return {"configurable": configurable}
