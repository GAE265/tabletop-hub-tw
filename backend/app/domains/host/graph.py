"""主持的圖（host spec §3、§5、§9；ADR 0004）。

每件事（按鍵、語音指令、裝置回報播完、查規則的請求）跑一次圖。整局記憶放 LangGraph 內建的
記憶體儲存，一場主持一份。帶流程由程式決定：只有「思考模型」節點會叫 LLM，其他節點都是照規則
跑的程式。圖往外只走兩條路：查規則找 rules_qa 的 service、思考模型走 integrations/llm。

圖跑完交回「要做的事」的清單（Effect）。真的去做這些事（請主持人開口、送訊息給裝置）
是轉送那一段的工作，這個檔案不碰連線。
"""

import logging
import threading
import unicodedata
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.domains.host import content
from app.integrations.llm import LLMProvider

logger = logging.getLogger(__name__)

# 指令的動作。next：下一步；previous：上一步；pause：暫停；resume：繼續；end：結束
Action = Literal["next", "previous", "pause", "resume", "end"]
# 主持暫停的原因。command：語音指令或按鍵；page_hidden：頁面被切走或鎖屏；
# chatter：同一段被閒聊切斷太多次
PauseReason = Literal["command", "page_hidden", "chatter"]

# 規則問題的種類。lookup：查規則片段，主持人自己回答；thinking：轉交思考模型
QuestionKind = Literal["lookup", "thinking"]
# 《血與刃的白薔薇》在 BoardGameGeek 的編號；games.bgg_id 有唯一限制，用它找這款遊戲
WHITE_ROSE_BGG_ID = 400566
# 同一段被閒聊切斷後，最多自動重講幾次；再被切斷就進入主持暫停（spec §6.5）
MAX_AUTO_REPLAYS = 2
# 整局記憶只留最近幾題（spec §8.2）
RECENT_QUESTIONS_LIMIT = 5

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
    question: str | None = None
    kind: QuestionKind | None = None
    question_id: int | None = None
    answer: str | None = None
    chunks: tuple["FoundChunk", ...] | None = None
    turn_taking_mode: str | None = None

    @staticmethod
    def connected(turn_taking_mode: str | None = None) -> "HostEvent":
        """裝置連上了。這場主持還沒開場就交出開場台詞；開場過了就是重新連線，只接回流程。

        turn_taking_mode 有帶而且和現在不同，就是切換接話方式。
        """
        return HostEvent("connected", turn_taking_mode=turn_taking_mode)

    @staticmethod
    def page_hidden() -> "HostEvent":
        """頁面被切走或鎖屏。"""
        return HostEvent("page_hidden")

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

    @staticmethod
    def chatter(cut_segment_id: int | None = None) -> "HostEvent":
        """閒聊：模型呼叫了「不回應」工具，或那句話被判定成不是在跟主持人說話。

        cut_segment_id 是主持人因此被切斷的那一段；主持人沒在說話就不帶。
        """
        return HostEvent("chatter", segment_id=cut_segment_id)

    @staticmethod
    def ask(question: str, *, kind: QuestionKind) -> "HostEvent":
        """玩家問規則。lookup 查完就交片段；thinking 查完片段後等思考模型的答案。"""
        return HostEvent("ask", question=question, kind=kind)

    @staticmethod
    def think(question: str, chunks: Sequence["FoundChunk"]) -> "HostEvent":
        """請思考模型回答。不屬於任何一場主持，用 HostGraph.think() 送。"""
        return HostEvent("think", question=question, chunks=tuple(chunks))

    @staticmethod
    def answer_ready(question_id: int, answer: str) -> "HostEvent":
        """思考模型的答案回來了。"""
        return HostEvent("answer_ready", question_id=question_id, answer=answer)

    @staticmethod
    def give_up(question_id: int) -> "HostEvent":
        """不等思考模型了（等太久或它回錯誤）：改交查到的片段。"""
        return HostEvent("give_up", question_id=question_id)

    @staticmethod
    def drop_question() -> "HostEvent":
        """等待中玩家說了別的話：舊題作廢。"""
        return HostEvent("drop_question")


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
    # line：固定台詞（code 是 spec §4.1 的代號）；rule_points：規則要點；
    # answer：重新交出一題規則問題的回答（問題與查到的片段，或思考模型的答案）
    kind: Literal["line", "rule_points", "answer"]
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


@dataclass(frozen=True)
class FoundChunk:
    """查到的一段規則原文。"""

    page: int
    content: str


@dataclass(frozen=True)
class ToolOutput:
    """回給語音模型的工具結果（查規則的片段，或思考模型的答案）。"""

    # 後端替那一題編的號
    question_id: int
    output: str
    # 為假時只把結果記進對話，不請主持人接著回答
    respond: bool = True
    chunks: tuple[FoundChunk, ...] = ()
    # 這個回答被記成「正在說、還沒播完的那一段」時的編號；沒有記就是 None
    segment_id: int | None = None


@dataclass(frozen=True)
class StartThinking:
    """片段查好了，請轉送那一段在圖的外面呼叫 HostGraph.think()，並開始計時。"""

    question_id: int
    question: str
    chunks: tuple[FoundChunk, ...]


Effect = Speak | Flush | StateChanged | ToolOutput | StartThinking


class RuleChunkLike(Protocol):
    @property
    def page(self) -> int: ...
    @property
    def content(self) -> str: ...


# 用問題查規則片段。查不到、出錯都回空的清單，不丟例外
RulesLookup = Callable[[str], Sequence[RuleChunkLike]]


class WhiteRoseRules:
    """查《血與刃的白薔薇》的規則片段（spec §8.2）。

    find_game_id 用 games.bgg_id 找遊戲；search 是 rules_qa 的 service 只檢索的方法。
    找不到遊戲、索引沒建好、embedding 失敗，一律當成空的結果，原因記進紀錄。
    紀錄不寫玩家說的話（spec §13.5）。
    """

    def __init__(
        self,
        *,
        find_game_id: Callable[[int], int | None],
        search: Callable[[int, str], Sequence[RuleChunkLike]],
    ) -> None:
        self._find_game_id = find_game_id
        self._search = search

    def __call__(self, question: str) -> Sequence[RuleChunkLike]:
        try:
            game_id = self._find_game_id(WHITE_ROSE_BGG_ID)
            if game_id is None:
                logger.warning("查規則：找不到 bgg_id=%s 的遊戲，當成沒有結果", WHITE_ROSE_BGG_ID)
                return []
            chunks = self._search(game_id, question)
        except Exception as exc:  # noqa: BLE001 查規則失敗不能讓主持停下來
            logger.warning("查規則失敗，當成沒有結果：%s: %s", type(exc).__name__, exc)
            return []
        if not chunks:
            logger.warning("查規則：遊戲 %s 沒有查到片段（索引可能還沒建好）", game_id)
        return chunks


def _no_rules(question: str) -> Sequence[RuleChunkLike]:
    return []


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
    # 後端替每一題編的號；正在等答案的那一題（沒有就是 None）
    question_seq: int
    open_question: dict[str, Any] | None
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
        question_seq=0,
        open_question=None,
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
        looking_up=memory["open_question"] is not None,
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


def _speak(
    memory: HostMemory, segment: dict[str, Any], run: _Run, *, track: bool = True
) -> dict[str, Any]:
    """替這一段編號、請主持人說。回傳要寫回記憶的欄位。

    track 為真時記成「正在說、還沒播完的那一段」；接回流程那一句很短，不記。
    """
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
    if not track:
        return {"segment_seq": segment_id}
    return {"segment": numbered, "segment_seq": segment_id}


def _back_to_segment(memory: HostMemory) -> dict[str, Any]:
    line = content.back_to_line(
        step=memory["step"],
        turn_number=memory["turn_number"],
        phase_number=memory["phase_number"],
    )
    return {
        "kind": "line",
        "code": "back_to",
        "text": content.verbatim_request(line),
        "phase_number": None,
        "version": None,
        "auto_advance": False,
    }


def _answer_segment(question: str, output: str) -> dict[str, Any]:
    """一題規則問題的回答。記的是問題與要交給主持人的內容，不是主持人說出口的字。"""
    return {
        "kind": "answer",
        "code": None,
        "text": f"玩家剛才問：「{question}」\n{output}",
        "phase_number": None,
        "version": None,
        "auto_advance": False,
    }


def _enter_pause(state: HostMemory, reason: PauseReason, run: _Run) -> dict[str, Any]:
    """進入主持暫停：主持人馬上停、不回話；那一段留著，「繼續」時重講（spec §6.2）。"""
    updates: dict[str, Any] = {"paused": True, "pause_reason": reason}
    run.emit(Flush())
    _emit_state(state, updates, run)
    return updates


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
        "page_hidden": "pause",
        "chatter": "chatter",
        "ask": "begin_question",
        "think": "thinking_model",
        "answer_ready": "deliver_answer",
        "give_up": "deliver_answer",
        "drop_question": "deliver_answer",
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
    """裝置連上。還沒開場就交出開場台詞；開場過了就是重新連線，主持人只說接回流程那一句。"""
    run = _run_of(config)
    updates: dict[str, Any] = {}
    mode = state["event"]["turn_taking_mode"]
    if mode is not None and mode != state["turn_taking_mode"]:
        updates["turn_taking_mode"] = mode
    if not state["opened"]:
        updates["opened"] = True
        if "turn_taking_mode" in updates:
            _emit_state(state, updates, run)
        updates.update(_speak(state, _node_segment(("opening", None, None)), run))
        return updates
    if state["open_question"] is not None:
        # 舊連線上的工具請求已經不在了，還在等的題目作廢
        updates["open_question"] = None
    if state["step"] == "ended":
        # ✅ 接著主持：回到結束前的節點，狀態變回進行中（spec §2.1）
        updates.update(
            step=state["step_before_end"] or "opening",
            step_before_end=None,
            winner=None,
            segment=None,
            replay_count=0,
        )
    if updates:
        _emit_state(state, updates, run)
    merged: HostMemory = {**state, **updates}  # type: ignore[typeddict-item]
    if not merged["paused"]:
        # 不重講那個階段；玩家說「繼續」才重講（D10 §4）
        updates.update(_speak(merged, _back_to_segment(merged), run, track=False))
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
    """裝置回報播完：清掉那一段；開場與夜晚兩步播完就自動進下一個節點。

    主持暫停中不清也不往下走：那一段留到「繼續」時重講（spec §3.1）。
    """
    segment = state["segment"]
    if state["paused"] or segment is None or segment["id"] != state["event"]["segment_id"]:
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
        # 主持暫停中換節點：照做，暫停解除，被打斷的那一段作廢（spec §3.2）
        "paused": False,
        "pause_reason": None,
    }
    if state["segment"] is not None and not state["paused"]:
        # 舊節點的那一段還沒播完：先停掉，換了節點那一段就作廢
        run.emit(Flush())
    _emit_state(state, updates, run)
    updates.update(_speak(state, _node_segment(target), run))
    return updates


def _pause(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """進入主持暫停：指令、按鍵，或頁面被切走。已結束或已經在暫停中就不動。"""
    if state["step"] == "ended" or state["paused"]:
        return {}
    reason: PauseReason = "page_hidden" if state["event"]["type"] == "page_hidden" else "command"
    return _enter_pause(state, reason, _run_of(config))


def _resume(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """繼續（spec §6.3）。有被打斷的那一段就從頭重講；沒有的話，暫停中只接回流程，否則不動。"""
    run = _run_of(config)
    if state["step"] == "ended":
        return {}
    updates: dict[str, Any] = {}
    if state["paused"]:
        updates.update(paused=False, pause_reason=None)
        _emit_state(state, updates, run)
    segment = state["segment"]
    if segment is not None:
        updates["replay_count"] = 0
        updates.update(_speak(state, segment, run))
    elif state["paused"]:
        updates.update(_speak(state, _back_to_segment(state), run, track=False))
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


def _chatter(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """閒聊（spec §6.5）。不會作廢正在等的題目。

    主持人沒在說話就不做事；那一段因此被切斷就自動重講，同一段最多 2 次，
    再被切斷就進入主持暫停。
    """
    run = _run_of(config)
    segment = state["segment"]
    cut_segment_id = state["event"]["segment_id"]
    if state["paused"] or segment is None or segment["id"] != cut_segment_id:
        return {}
    if state["replay_count"] >= MAX_AUTO_REPLAYS:
        return _enter_pause(state, "chatter", run)
    updates: dict[str, Any] = {"replay_count": state["replay_count"] + 1}
    updates.update(_speak(state, segment, run))
    return updates


# --- 查規則與思考模型（spec §8） ---


def _chunks_text(chunks: Sequence[dict[str, Any]]) -> str:
    return "\n".join(f"[第 {chunk['page']} 頁] {chunk['content']}" for chunk in chunks)


def _back_to_hint(state: HostMemory) -> str:
    """答完規則問題補的那一句（spec §4.3 第 10 點）。已結束就不補。"""
    if state["step"] == "ended":
        return ""
    line = content.back_to_line(
        step=state["step"], turn_number=state["turn_number"], phase_number=state["phase_number"]
    )
    return f"\n答完之後補一句：「{line}」不要重講這個階段的內容。"


def _lookup_output(state: HostMemory, chunks: Sequence[dict[str, Any]]) -> str:
    not_found = content.fixed_line("answer_not_found")
    if not chunks:
        return f"沒有查到任何規則片段。請照唸：「{not_found}」" + _back_to_hint(state)
    return (
        f"查到的規則片段（共 {len(chunks)} 段）：\n{_chunks_text(chunks)}\n"
        "請只根據上面的片段回答玩家，不要加片段裡沒有的規則。"
        f"片段裡沒有答案就照唸：「{not_found}」" + _back_to_hint(state)
    )


def _answer_output(state: HostMemory, answer: str) -> str:
    return f"思考模型的答案：\n{answer}\n請把這個答案用口語說給玩家聽，不要加別的規則。" + (
        _back_to_hint(state)
    )


def _give_up_output(state: HostMemory, chunks: Sequence[dict[str, Any]]) -> str:
    not_sure = content.fixed_line("not_sure")
    if not chunks:
        return _lookup_output(state, chunks)
    return (
        f"思考模型來不及回答。查到的規則片段（共 {len(chunks)} 段）：\n{_chunks_text(chunks)}\n"
        f"請只根據上面的片段自己回答，最後補一句：「{not_sure}」" + _back_to_hint(state)
    )


def thinking_prompt(question: str, chunks: Sequence[dict[str, Any]]) -> str:
    """交給思考模型的文字：問題與查到的片段都要帶。"""
    found = _chunks_text(chunks) if chunks else "（沒有查到片段）"
    return (
        "你是桌遊《血與刃的白薔薇》的規則顧問。請只根據下面的規則片段回答玩家的問題，"
        "用繁體中文、三句話以內、口語、直接給結論。片段裡沒有寫到的事不要猜，"
        "直接說規則沒有寫到。不要解釋魔法之書的效果。\n\n"
        f"規則片段：\n{found}\n\n玩家的問題：{question}"
    )


def _found_chunks(chunks: Sequence[dict[str, Any]]) -> tuple[FoundChunk, ...]:
    return tuple(FoundChunk(page=chunk["page"], content=chunk["content"]) for chunk in chunks)


_HELD_OUTPUT = "主持暫停中。這一題先不要回答，等玩家說「繼續」再說。"


def _hand_over(
    state: HostMemory,
    run: _Run,
    *,
    open_question: dict[str, Any],
    output: str,
    chunks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """把一題的結果交給主持人。回傳要寫回記憶的欄位。

    問了之後才進入主持暫停：答案不唸，記成被打斷的那一段，「繼續」時才說。
    其他情況照常交；沒有別的段落還沒播完時，這個回答就是「正在說的那一段」。
    """
    segment = _answer_segment(open_question["question"], output)
    segment_id = state["segment_seq"] + 1
    if state["paused"] and not open_question["asked_while_paused"]:
        run.emit(ToolOutput(question_id=open_question["id"], output=_HELD_OUTPUT, respond=False))
        return {"segment": {**segment, "id": segment_id}, "segment_seq": segment_id}
    if state["segment"] is not None:
        # 被問題打斷的那一段留著：答完只接回流程，玩家說「繼續」才重講（spec §6.4）
        run.emit(
            ToolOutput(question_id=open_question["id"], output=output, chunks=_found_chunks(chunks))
        )
        return {}
    run.emit(
        ToolOutput(
            question_id=open_question["id"],
            output=output,
            chunks=_found_chunks(chunks),
            segment_id=segment_id,
        )
    )
    return {"segment": {**segment, "id": segment_id}, "segment_seq": segment_id}


def _begin_question(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """替這一題編號，並讓現況顯示「正在查規則」。新的一題會取代還在等的舊題（spec §8.4）。"""
    run = _run_of(config)
    event = state["event"]
    question_id = state["question_seq"] + 1
    updates: dict[str, Any] = {
        "question_seq": question_id,
        "open_question": {
            "id": question_id,
            "kind": event["kind"],
            "question": event["question"],
            "chunks": [],
            # 暫停中才問的照常回答；問了之後才暫停的，答案留到「繼續」（spec §6.2）
            "asked_while_paused": state["paused"],
        },
    }
    if state["open_question"] is None:
        _emit_state(state, updates, run)
    return updates


def _deliver_answer(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
    """思考模型的答案回來、放棄、或舊題作廢。只把最新那一題的結果交給主持人。"""
    run = _run_of(config)
    event = state["event"]
    open_question = state["open_question"]
    if event["type"] == "drop_question":
        if open_question is None:
            return {}
        updates: dict[str, Any] = {"open_question": None}
        _emit_state(state, updates, run)
        return updates
    if open_question is None or open_question["id"] != event["question_id"]:
        # 已作廢或已放棄的題目：晚到的答案丟掉
        run.outcome.result["delivered"] = False
        return {}
    chunks = open_question["chunks"]
    if event["type"] == "answer_ready":
        output = _answer_output(state, event["answer"])
    else:
        output = _give_up_output(state, chunks)
    updates = _hand_over(state, run, open_question=open_question, output=output, chunks=chunks)
    updates["open_question"] = None
    _emit_state(state, updates, run)
    run.outcome.result["delivered"] = True
    return updates


def _build_graph(rules_lookup: RulesLookup, thinking_model: LLMProvider | None) -> StateGraph:
    def lookup_rules(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
        """查規則：呼叫 rules_qa 的只檢索方法，記下這一題的問題與頁碼。"""
        run = _run_of(config)
        open_question = state["open_question"]
        assert open_question is not None
        found = rules_lookup(open_question["question"])
        chunks = [{"page": chunk.page, "content": chunk.content} for chunk in found]
        recent = [
            *state["recent_questions"],
            {"question": open_question["question"], "pages": [chunk["page"] for chunk in chunks]},
        ][-RECENT_QUESTIONS_LIMIT:]
        updates: dict[str, Any] = {"recent_questions": recent}
        if open_question["kind"] == "thinking":
            # 片段先記著：思考模型來不及時要改交這些片段
            updates["open_question"] = {**open_question, "chunks": chunks}
            run.emit(
                StartThinking(
                    question_id=open_question["id"],
                    question=open_question["question"],
                    chunks=_found_chunks(chunks),
                )
            )
            return updates
        updates.update(
            _hand_over(
                state,
                run,
                open_question=open_question,
                output=_lookup_output(state, chunks),
                chunks=chunks,
            )
        )
        updates["open_question"] = None
        _emit_state(state, updates, run)
        return updates

    def call_thinking_model(state: HostMemory, config: RunnableConfig) -> dict[str, Any]:
        """思考模型：圖裡唯一叫 LLM 的節點，只經過 integrations/llm 的介面。"""
        if thinking_model is None:
            raise RuntimeError("沒有設定思考模型")
        event = state["event"]
        answer = thinking_model.generate(thinking_prompt(event["question"], event["chunks"] or []))
        _run_of(config).outcome.result["answer"] = answer
        return {}

    builder = StateGraph(HostMemory)
    builder.add_node("receive", _receive)
    builder.add_node("connect", _connect)
    builder.add_node("verify_voice_command", _verify_voice_command)
    builder.add_node("playback_done", _playback_done)
    builder.add_node("change_step", _change_step)
    builder.add_node("pause", _pause)
    builder.add_node("resume", _resume)
    builder.add_node("end_hosting", _end_hosting)
    builder.add_node("chatter", _chatter)
    builder.add_node("begin_question", _begin_question)
    builder.add_node("lookup_rules", lookup_rules)
    builder.add_node("thinking_model", call_thinking_model)
    builder.add_node("deliver_answer", _deliver_answer)

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
            "pause": "pause",
            "chatter": "chatter",
            "begin_question": "begin_question",
            "thinking_model": "thinking_model",
            "deliver_answer": "deliver_answer",
            **command_targets,
        },
    )
    builder.add_conditional_edges("verify_voice_command", _route_command, command_targets)
    builder.add_conditional_edges("playback_done", _route_command, command_targets)
    builder.add_edge("begin_question", "lookup_rules")
    for node in (
        "connect",
        "change_step",
        "pause",
        "resume",
        "end_hosting",
        "chatter",
        "lookup_rules",
        "thinking_model",
        "deliver_answer",
    ):
        builder.add_edge(node, END)
    return builder


class HostGraph:
    """主持的圖與每一場主持的整局記憶。整個後端共用一個。"""

    def __init__(
        self,
        *,
        rules_lookup: RulesLookup | None = None,
        thinking_model: LLMProvider | None = None,
    ) -> None:
        self._saver = InMemorySaver()
        self._graph = _build_graph(rules_lookup or _no_rules, thinking_model).compile(
            checkpointer=self._saver
        )
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

    def think(self, question: str, chunks: Sequence[FoundChunk]) -> str:
        """請思考模型回答一題，回傳答案文字；integrations/llm 的錯誤原樣往外丟。

        這一步可能要等好幾秒，所以不屬於任何一場主持、不占那場主持的排隊：
        等待中的暫停、下一步都能照常處理。答案回來後用 answer_ready 交回那場主持。
        """
        run = _Run(None)
        thread_id = f"think:{uuid.uuid4()}"
        try:
            self._graph.invoke(
                {"event": asdict(HostEvent.think(question, chunks))},
                self._config(thread_id, run=run),
            )
        finally:
            self._saver.delete_thread(thread_id)
        return run.outcome.result["answer"]

    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    @staticmethod
    def _config(session_id: str, *, run: _Run | None = None) -> RunnableConfig:
        configurable: dict[str, Any] = {"thread_id": session_id}
        if run is not None:
            configurable["run"] = run
        return {"configurable": configurable}
