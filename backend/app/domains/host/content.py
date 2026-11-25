"""主持內容（host spec §4）：主持人會說到的所有內容，以及交給語音模型的文字。

全部是純函式與常數，不碰連線、不碰圖。只做《血與刃的白薔薇》一款。
固定台詞與指令的字句都是草稿，定稿在實作 ticket 10 由立倫試聽。
規則的內容一律用自己的話寫，不貼規則書原文（AGENTS.md §2 第 2 點）。
"""

from dataclasses import dataclass
from typing import Literal

from app.integrations.realtime_voice import VoiceToolSpec

# 流程節點（spec §3.1）。
# opening：開場；setup：開局準備；night_1、night_2：夜晚的兩步；
# turn：回合內（再看 turn_number 與 phase_number）；ended：結束
Step = Literal["opening", "setup", "night_1", "night_2", "turn", "ended"]
# 贏的一方。white_rose：白薔薇陣營；blood_blade：血刃陣營
Winner = Literal["white_rose", "blood_blade"]
# 規則要點的版本。full：完整版（第 1 回合）；short：簡短版（第 2 回合起）
RulePointsVersion = Literal["full", "short"]

MIN_PLAYERS = 5
MAX_PLAYERS = 10
PHASES_PER_TURN = 3

STEP_NAMES: dict[str, str] = {
    "opening": "開場",
    "setup": "開局準備",
    "night_1": "夜晚第一步",
    "night_2": "夜晚第二步",
    "turn": "回合",
    "ended": "結束",
}
PHASE_NAMES: dict[int, str] = {
    1: "傳金幣、放水晶",
    2: "決定出牌",
    3: "翻牌結算",
}


# --- 門檻與格數（spec §4.4） ---


@dataclass(frozen=True)
class GameNumbers:
    """一種人數的三個數字。"""

    # 白薔薇陣營獲勝：獻祭區的花苞張數
    white_rose_threshold: int
    # 血刃陣營獲勝：死亡區的張數
    blood_blade_threshold: int
    # 圓版的水晶格數，也就是最多幾個回合
    board_slots: int


_GAME_NUMBERS: dict[int, GameNumbers] = {
    5: GameNumbers(4, 3, 4),
    6: GameNumbers(5, 4, 5),
    7: GameNumbers(6, 4, 6),
    8: GameNumbers(7, 5, 6),
    9: GameNumbers(8, 5, 7),
    10: GameNumbers(9, 6, 7),
}


def game_numbers(player_count: int) -> GameNumbers:
    try:
        return _GAME_NUMBERS[player_count]
    except KeyError:
        raise ValueError(f"人數要在 {MIN_PLAYERS} 到 {MAX_PLAYERS} 人：{player_count}") from None


# --- 固定台詞（spec §4.1，草稿） ---

_STATIC_LINES: dict[str, str] = {
    "opening": (
        "各位晚安，歡迎來到今晚的《血與刃的白薔薇》，我是今天的主持人。"
        "這張桌子上，有人誓死守護白薔薇，也有人正在暗中磨刀。"
    ),
    "setup": (
        "先來準備。每個人拿自己的幽魂牌、信者牌和魔法之書，再抽一顆水晶，數字不要給別人看。"
        "角色牌洗好，每人發一張。金幣交給任意一位玩家。好了就說「下一步」。"
    ),
    "night_1": (
        "天黑了，請所有人閉上眼睛。白薔薇、司教、雙刃、巨刃，請睜開眼睛，看看彼此。"
        "三、二、一，請閉上眼睛。"
    ),
    # 🚧 發牌機還沒接上：現在只有台詞，沒有東西真的送牌。之後接語音工具 call_device，
    # 由發牌機把雙刃牌送到雙刃面前，中間的等待也改成等發牌機回報送到了。
    # 刪節號是寫給語音模型的停頓，實測每個大約停 1 秒，再多寫也不會變長（2026-11-25）
    "night_2": (
        "現在請雙刃睜眼，請看著發牌機並用手比出五，等待發牌機把雙刃牌送到你面前……。"
        "發牌機正在運作……。"
        "雙刃拿好牌請閉眼，並把你的幽魂牌放回到桌子中間。"
        "……五、四、三、二、一，停。天亮了，各位請睜開眼睛。"
    ),
    # 破折號與刪節號是寫給語音模型的停頓：實測只給語氣指示節奏不會變，把停頓寫進字句才有效
    "end_white_rose": "恭喜——白薔薇陣營——獲勝！……刀光散去，白薔薇，依然盛開。",
    "end_blood_blade": "恭喜——血刃陣營——獲勝！……今夜，白薔薇，凋零在刀刃之下。",
    "end_plain": "這一局結束了。",
    "answer_magic_book": "魔法之書的效果要看書上的說明，我不能為你解釋。",
    "answer_deduction": "這個要靠你們自己判斷，我只負責流程和規則。",
    "answer_table": "我看不到桌面，請直接問同桌的玩家。",
    "answer_record": "我不會記戰績，請到戰績畫面輸入。",
    "answer_not_found": "很抱歉，我手上的規則沒寫到這個。請翻一下規則書，或大家商量決定。",
    "wait_lookup": "我翻一下規則",
    "wait_thinking": "讓我來好好的想一想～",
    "wait_longer": "這題比較複雜，再等我一下",
    "not_sure": "這題我沒把握，大家可以再翻規則書確認",
}
# 要帶這局的資料才組得出來的兩句
_DYNAMIC_LINES = ("back_to", "answer_winning")
LINE_CODES: tuple[str, ...] = (*_STATIC_LINES, *_DYNAMIC_LINES)


def back_to_line(*, step: Step, turn_number: int | None, phase_number: int | None) -> str:
    """接回流程的那一句。回合內說第幾回合的哪個階段；開場到夜晚說節點名稱。"""
    if step == "turn" and turn_number is not None and phase_number is not None:
        return f"回到第 {turn_number} 回合的{PHASE_NAMES[phase_number]}階段。"
    return f"回到{STEP_NAMES[step]}。"


def answer_winning_line(player_count: int) -> str:
    numbers = game_numbers(player_count)
    return (
        "我看不到桌上的牌，請你們自己數。"
        f"這局白薔薇陣營要獻祭 {numbers.white_rose_threshold} 張花苞，"
        f"血刃陣營要死亡區 {numbers.blood_blade_threshold} 張。"
    )


def fixed_line(
    code: str,
    *,
    player_count: int = MIN_PLAYERS,
    step: Step = "opening",
    turn_number: int | None = None,
    phase_number: int | None = None,
) -> str:
    """用代號拿固定台詞。back_to 與 answer_winning 會用到後面幾個參數，其他代號忽略它們。"""
    if code == "back_to":
        return back_to_line(step=step, turn_number=turn_number, phase_number=phase_number)
    if code == "answer_winning":
        return answer_winning_line(player_count)
    return _STATIC_LINES[code]


def verbatim_request(line: str) -> str:
    """請主持人照唸一句固定台詞時，交給語音模型的文字。"""
    return f"請照唸下面這段固定台詞，一個字都不要加、不要改，唸完就停：\n{line}"


# 宣布哪一方獲勝的兩句要有儀式感（立倫 2026-11-22 試聽後要求）：字句不變，語氣與節奏另外指示
_CEREMONY_CODES = ("end_white_rose", "end_blood_blade")
_CEREMONY_DIRECTION = (
    "這是整局最重要的一刻，請像頒獎典禮宣布得主那樣，用隆重、莊嚴、有戲劇感的語氣唸。"
    "節奏：開口前先停頓一拍；整段放慢；「恭喜」之後停頓一下，陣營的名字一個字一個字加重，"
    "「獲勝」兩個字拉長、聲音揚起來；然後停頓兩拍，第二句壓低聲音、慢慢說完。"
)


def line_request(code: str) -> str:
    """請主持人說一句不用帶資料的固定台詞時，交給語音模型的文字。"""
    line = _STATIC_LINES[code]
    if code in _CEREMONY_CODES:
        return f"{_CEREMONY_DIRECTION}\n字句一個字都不要加、不要改，唸完就停：\n{line}"
    return verbatim_request(line)


# --- 規則要點（spec §4.2；條目出自 D23 §3，用自己的話寫） ---

_RULE_POINTS: dict[int, tuple[str, ...]] = {
    1: (
        "拿金幣的人，把金幣交給另一位還有水晶的玩家。給誰由他決定。",
        "大家可以討論、爭取或推掉金幣，但不能說出自己水晶的數字和效果。",
        "收到金幣的人把水晶放上圓版，照格子的順序放，數字朝上。",
        "照水晶的數字，做魔法之書上同一個編號的效果。",
    ),
    2: (
        "從放水晶的人開始，順時針輪流決定。",
        "每個人二選一：蓋一張牌在自己面前，或說「不出」。",
        "每個人只有一個機會。",
    ),
    3: (
        "把所有蓋著的牌收在一起混洗，再全部翻開。",
        "沒有刃牌：幽魂移出遊戲，信者和司教放獻祭區，白薔薇放白薔薇區。",
        "有刃牌、沒有白薔薇：幽魂移出遊戲，信者和司教放死亡區。",
        "刃牌和白薔薇同時出現：血刃陣營立刻獲勝。",
    ),
}
# 簡短版要說到完整版的哪幾條（從 0 起算）
_SHORT_INDEXES: dict[int, tuple[int, ...]] = {1: (0, 2, 3), 2: (0, 1), 3: (0,)}
# 簡短版多補的一句
_SHORT_EXTRA: dict[int, str | None] = {1: None, 2: None, 3: "照翻出來的牌結算"}


@dataclass(frozen=True)
class RulePoints:
    """一個階段要說到的條目。字句由主持人自己組，這裡只規定要說到哪幾條。"""

    phase_number: int
    version: RulePointsVersion
    points: tuple[str, ...]
    # 簡短版另外要帶到的一句；沒有就是 None
    extra: str | None


def rule_points(*, turn_number: int, phase_number: int) -> RulePoints:
    """用哪一版只看第幾回合：第 1 回合完整版，第 2 回合起簡短版（D23 §3）。"""
    if turn_number < 1:
        raise ValueError(f"回合從 1 開始：{turn_number}")
    if phase_number not in _RULE_POINTS:
        raise ValueError(f"階段只有 1 到 {PHASES_PER_TURN}：{phase_number}")
    full = _RULE_POINTS[phase_number]
    if turn_number == 1:
        return RulePoints(phase_number, "full", full, None)
    short = tuple(full[index] for index in _SHORT_INDEXES[phase_number])
    return RulePoints(phase_number, "short", short, _SHORT_EXTRA[phase_number])


def rule_points_text(*, turn_number: int, phase_number: int) -> str:
    """交給主持人的格式（spec §4.2）：先寫哪個階段，再寫要求，後面是編號的條目。

    不報第幾回合，不報圓版剩幾格。
    """
    points = rule_points(turn_number=turn_number, phase_number=phase_number)
    lines = [
        f"現在是「{PHASE_NAMES[phase_number]}」階段。",
        "請用自己的話說到下面每一條，不要加別的規則，說完就停：",
    ]
    lines += [f"{index}. {point}" for index, point in enumerate(points.points, start=1)]
    if points.extra:
        lines.append(f"最後補一句：{points.extra}。")
    return "\n".join(lines)


# --- 現況與指令（spec §4.3） ---

# 九項不管的事（D23 §2）
NOT_HOSTS_JOB: tuple[str, ...] = (
    "不解釋魔法之書的效果",
    "不判勝負，也不記獻祭區、死亡區有幾張",
    "不讀戰績",
    "不向玩家要陣營、手牌、水晶數字；玩家自己說出來，也不重複、不記",
    "不先教整套規則，只在每個階段開始時說那個階段的規則要點",
    "不計時、不催，只有夜晚的兩個倒數",
    "不點名、不追蹤換誰了",
    "不主動糾正違規，被問才照規則回答",
    "不給打法建議，結束後也不提醒記戰績",
)


def status_text(
    *, step: Step, turn_number: int | None, phase_number: int | None, paused: bool
) -> str:
    """一句現況：第幾回合、哪個階段、是不是主持暫停中。"""
    if step == "turn" and turn_number is not None and phase_number is not None:
        where = f"第 {turn_number} 回合的「{PHASE_NAMES[phase_number]}」階段"
    elif step == "ended":
        where = "這一局已經結束"
    else:
        where = f"「{STEP_NAMES[step]}」"
    text = f"現況：現在是{where}。"
    if paused:
        text += "主持暫停中，玩家說「繼續」之前不要自己往下說。"
    return text


def instruction_sections(
    *,
    player_count: int,
    step: Step,
    turn_number: int | None,
    phase_number: int | None,
    paused: bool,
) -> list[str]:
    """spec §4.3 的 12 項，一項一段文字。"""
    numbers = game_numbers(player_count)
    line = _STATIC_LINES
    not_my_job = "；".join(NOT_HOSTS_JOB)
    return [
        # 1 身分
        "你是桌遊《血與刃的白薔薇》的主持人，在桌邊用聲音帶玩家走流程、回答規則問題。"
        "只說中文，語氣自然、有精神，句子短。",
        # 2 固定台詞與規則要點
        "後端交給你「固定台詞」時，一個字都不改地照唸。"
        "後端交給你「規則要點」時，用自己的話說到每一條，不加別的規則。",
        # 3 不自己推進
        "不自己換階段，也不自己往下推進流程。換階段只由後端決定，你只說後端交給你的內容。",
        # 4 規則問題一律先查
        f"玩家問規則時，一律先說「{line['wait_lookup']}」，呼叫 lookup_rules 查規則，"
        "再只根據查到的片段回答，不憑記憶回答。例外只有語音指令與第 6 點的五類問題。",
        # 5 查不到與要推理
        f"查到的片段裡沒有答案時，照唸「{line['answer_not_found']}」，不猜，也不轉交。"
        "片段裡有相關規則、但要推理才答得出來時，"
        f"只說「{line['wait_thinking']}」，再呼叫 ask_thinking_model，把回來的答案說給玩家聽。",
        # 6 五類固定回答
        "下面五類問題不查規則，直接照唸對應的句子。"
        f"問魔法之書的效果：「{line['answer_magic_book']}」"
        f"問現在誰贏、獻祭區或死亡區幾張了：「{answer_winning_line(player_count)}」"
        f"問誰是血刃、該不該出牌這類推理或打法：「{line['answer_deduction']}」"
        f"問換誰了、金幣或水晶在誰手上：「{line['answer_table']}」"
        f"要你記戰績或算分：「{line['answer_record']}」",
        # 7 九項不管的事
        f"這些事你不做：{not_my_job}。",
        # 8 閒聊
        "聽到的話不是在問你、也不是語音指令時（例如玩家之間的討論、閒聊），"
        "只呼叫 no_reply，不出聲。",
        # 9 語音指令
        "聽到語音指令時，只呼叫對應的工具，不自己回話："
        "「下一步」呼叫 next_step；「上一步」呼叫 previous_step；"
        "「等一下」「暫停」呼叫 pause_hosting；「繼續」呼叫 resume_hosting；"
        "「結束了」「白薔薇贏了」「血刃贏了」呼叫 end_hosting。"
        "整句話就是指令才算；指令只是句子的一部分（例如「你下一步要出什麼」）就不算。",
        # 10 答完補一句
        "答完規則問題後，補一句後端交給你的「回到第幾回合的哪個階段」，不重講這個階段的內容。",
        # 11 這局的補充
        f"這局的補充：這局有 {player_count} 位玩家。"
        f"白薔薇陣營獲勝，獻祭區要有 {numbers.white_rose_threshold} 張花苞；"
        f"血刃陣營獲勝，死亡區要有 {numbers.blood_blade_threshold} 張；"
        f"圓版有 {numbers.board_slots} 格。瞞刃就是暗刃。"
        "門檻的數字不主動說，只在玩家問勝負或張數、或回答勝負規則時說。",
        # 12 現況
        status_text(step=step, turn_number=turn_number, phase_number=phase_number, paused=paused),
    ]


def build_instructions(
    *,
    player_count: int,
    step: Step,
    turn_number: int | None,
    phase_number: int | None,
    paused: bool,
) -> str:
    """組出交給語音模型的完整指令。文字由程式組，不叫模型做摘要（D10 §4）。"""
    sections = instruction_sections(
        player_count=player_count,
        step=step,
        turn_number=turn_number,
        phase_number=phase_number,
        paused=paused,
    )
    return "\n".join(f"{index}. {section}" for index, section in enumerate(sections, start=1))


# --- 工具（spec §8.1） ---

_NO_PARAMETERS: dict[str, object] = {"type": "object", "properties": {}, "required": []}
_QUESTION_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "玩家的問題，用完整的一句話寫"}},
    "required": ["question"],
}


def host_tools() -> list[VoiceToolSpec]:
    """語音模型能呼叫的八個工具，開連線時傳給整合層。"""
    return [
        VoiceToolSpec(
            name="lookup_rules",
            description="查規則書的原文片段。玩家問規則時一律先呼叫它，再根據片段回答。",
            parameters=dict(_QUESTION_PARAMETERS),
        ),
        VoiceToolSpec(
            name="ask_thinking_model",
            description="把要推理才答得出來的規則難題交給後端的思考模型，回傳答案文字。",
            parameters=dict(_QUESTION_PARAMETERS),
        ),
        VoiceToolSpec(
            name="next_step",
            description="語音指令：玩家整句話就是「下一步」時呼叫。",
            parameters=dict(_NO_PARAMETERS),
        ),
        VoiceToolSpec(
            name="previous_step",
            description="語音指令：玩家整句話就是「上一步」時呼叫。",
            parameters=dict(_NO_PARAMETERS),
        ),
        VoiceToolSpec(
            name="pause_hosting",
            description="語音指令：玩家整句話就是「等一下」或「暫停」時呼叫。",
            parameters=dict(_NO_PARAMETERS),
        ),
        VoiceToolSpec(
            name="resume_hosting",
            description="語音指令：玩家整句話就是「繼續」時呼叫。",
            parameters=dict(_NO_PARAMETERS),
        ),
        VoiceToolSpec(
            name="end_hosting",
            description="語音指令：玩家說「結束了」，或說某一方贏了時呼叫。",
            parameters={
                "type": "object",
                "properties": {
                    "winner": {
                        "type": "string",
                        "enum": ["white_rose", "blood_blade"],
                        "description": (
                            "贏的一方：white_rose 是白薔薇陣營，blood_blade 是血刃陣營。"
                            "玩家只說結束了就不填"
                        ),
                    }
                },
                "required": [],
            },
        ),
        VoiceToolSpec(
            name="no_reply",
            description="這句話不是對主持人說的（玩家之間的討論或閒聊）時呼叫，然後不要出聲。",
            parameters=dict(_NO_PARAMETERS),
        ),
    ]
