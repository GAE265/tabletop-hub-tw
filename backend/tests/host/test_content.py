"""主持內容（host spec §4）：門檻與格數、固定台詞、規則要點、指令文字、工具定義。

對應情境 C-01 到 C-05（C-06 到 C-08 要有圖，在 test_graph_flow）。
"""

import pytest

from app.domains.host import content
from app.integrations.realtime_voice import VoiceToolSpec

# spec §4.4：人數 → (白薔薇陣營的門檻, 血刃陣營的門檻, 圓版格數)
EXPECTED_NUMBERS = {
    5: (4, 3, 4),
    6: (5, 4, 5),
    7: (6, 4, 6),
    8: (7, 5, 6),
    9: (8, 5, 7),
    10: (9, 6, 7),
}
# spec §4.1 的 18 個代號
LINE_CODES = [
    "opening",
    "setup",
    "night_1",
    "night_2",
    "end_white_rose",
    "end_blood_blade",
    "end_plain",
    "back_to",
    "answer_magic_book",
    "answer_winning",
    "answer_deduction",
    "answer_table",
    "answer_record",
    "answer_not_found",
    "wait_lookup",
    "wait_thinking",
    "wait_longer",
    "not_sure",
]
SIX_ANSWERS = [
    "answer_magic_book",
    "answer_winning",
    "answer_deduction",
    "answer_table",
    "answer_record",
    "answer_not_found",
]


def instructions(player_count: int = 7, **overrides: object) -> str:
    kwargs: dict[str, object] = {
        "player_count": player_count,
        "step": "opening",
        "turn_number": None,
        "phase_number": None,
        "paused": False,
    }
    kwargs.update(overrides)
    return content.build_instructions(**kwargs)  # type: ignore[arg-type]


# --- 門檻與格數 ---


@pytest.mark.parametrize("player_count, expected", EXPECTED_NUMBERS.items())
def test_game_numbers_match_spec_table(player_count: int, expected: tuple[int, int, int]) -> None:
    numbers = content.game_numbers(player_count)
    assert (
        numbers.white_rose_threshold,
        numbers.blood_blade_threshold,
        numbers.board_slots,
    ) == expected


@pytest.mark.parametrize("player_count", [4, 11, 0])
def test_game_numbers_reject_out_of_range(player_count: int) -> None:
    with pytest.raises(ValueError):
        content.game_numbers(player_count)


# --- 固定台詞 ---


def test_line_codes_are_exactly_the_18_in_spec() -> None:
    assert sorted(content.LINE_CODES) == sorted(LINE_CODES)


@pytest.mark.parametrize("code", LINE_CODES)
def test_every_line_code_has_text(code: str) -> None:
    text = content.fixed_line(code, player_count=7, step="turn", turn_number=2, phase_number=2)
    assert text.strip()


def test_answer_winning_carries_both_thresholds() -> None:
    seven = content.fixed_line("answer_winning", player_count=7)
    assert "6 張" in seven and "4 張" in seven
    ten = content.fixed_line("answer_winning", player_count=10)
    assert "9 張" in ten and "6 張" in ten


def test_end_lines_do_not_say_thanks_for_hard_work() -> None:
    for code in ("end_white_rose", "end_blood_blade", "end_plain"):
        assert "辛苦" not in content.fixed_line(code)


def test_opening_does_not_read_numbers() -> None:
    """開場不唸人數、圓版格數、門檻（D23 §1）。"""
    opening = content.fixed_line("opening", player_count=7)
    assert not any(ch.isdigit() for ch in opening)


def test_night_lines_carry_the_countdowns() -> None:
    assert "三、二、一" in content.fixed_line("night_1")
    night_2 = content.fixed_line("night_2")
    assert "十、九、八、七、六、五、四、三、二、一" in night_2
    assert "天亮了" in night_2


def test_back_to_inside_a_turn_names_turn_and_phase() -> None:
    text = content.back_to_line(step="turn", turn_number=2, phase_number=2)
    assert "第 2 回合" in text
    assert content.PHASE_NAMES[2] in text


@pytest.mark.parametrize("step", ["opening", "setup", "night_1", "night_2"])
def test_back_to_before_first_turn_names_the_step(step: str) -> None:
    text = content.back_to_line(step=step, turn_number=None, phase_number=None)
    assert content.STEP_NAMES[step] in text
    assert "回合" not in text


def test_unknown_line_code_rejected() -> None:
    with pytest.raises(KeyError):
        content.fixed_line("no_such_line")


# --- 規則要點：C-04、C-05 ---


def test_c04_first_turn_gives_full_version() -> None:
    counts = [len(content.rule_points(turn_number=1, phase_number=p).points) for p in (1, 2, 3)]
    assert counts == [4, 3, 4]
    for phase in (1, 2, 3):
        points = content.rule_points(turn_number=1, phase_number=phase)
        assert points.version == "full"
        assert points.extra is None


@pytest.mark.parametrize("turn_number", [2, 3, 7])
def test_c05_later_turns_give_short_version(turn_number: int) -> None:
    phases = [content.rule_points(turn_number=turn_number, phase_number=p) for p in (1, 2, 3)]
    assert [len(p.points) for p in phases] == [3, 2, 1]
    assert all(p.version == "short" for p in phases)
    assert phases[0].extra is None and phases[1].extra is None
    assert phases[2].extra == "照翻出來的牌結算"


def test_short_version_is_a_subset_of_full_version() -> None:
    full_1 = content.rule_points(turn_number=1, phase_number=1).points
    assert content.rule_points(turn_number=2, phase_number=1).points == (
        full_1[0],
        full_1[2],
        full_1[3],
    )
    full_2 = content.rule_points(turn_number=1, phase_number=2).points
    assert content.rule_points(turn_number=2, phase_number=2).points == full_2[:2]
    full_3 = content.rule_points(turn_number=1, phase_number=3).points
    assert content.rule_points(turn_number=2, phase_number=3).points == full_3[:1]


def test_rule_points_text_format() -> None:
    """spec §4.2：先寫哪個階段，再寫請用自己的話說到每一條，後面是編號的條目。"""
    points = content.rule_points(turn_number=1, phase_number=1)
    text = content.rule_points_text(turn_number=1, phase_number=1)
    lines = text.splitlines()
    assert content.PHASE_NAMES[1] in lines[0]
    assert "請用自己的話說到下面每一條，不要加別的規則" in text
    for index, point in enumerate(points.points, start=1):
        assert f"{index}. {point}" in text
    # 不報第幾回合、不報圓版剩幾格
    assert "第 1 回合" not in text and "剩" not in text


def test_rule_points_text_short_phase_3_has_extra_sentence() -> None:
    text = content.rule_points_text(turn_number=2, phase_number=3)
    assert "照翻出來的牌結算" in text
    assert "2. " not in text


@pytest.mark.parametrize("turn_number, phase_number", [(0, 1), (1, 0), (1, 4)])
def test_rule_points_reject_bad_position(turn_number: int, phase_number: int) -> None:
    with pytest.raises(ValueError):
        content.rule_points(turn_number=turn_number, phase_number=phase_number)


# --- 指令：C-01 到 C-03 ---


def test_c01_seven_players_instructions_carry_game_facts() -> None:
    text = instructions(7)
    assert "獻祭區要有 6 張花苞" in text
    assert "死亡區要有 4 張" in text
    assert "圓版有 6 格" in text
    assert "瞞刃就是暗刃" in text


def test_c02_ten_players_instructions_carry_game_facts() -> None:
    text = instructions(10)
    assert "獻祭區要有 9 張花苞" in text
    assert "死亡區要有 6 張" in text
    assert "圓版有 7 格" in text


def test_c03_instructions_have_the_12_sections() -> None:
    sections = content.instruction_sections(
        player_count=7, step="opening", turn_number=None, phase_number=None, paused=False
    )
    assert len(sections) == 12
    text = instructions(7)
    for index, section in enumerate(sections, start=1):
        assert f"{index}. {section}" in text
    keywords = [
        "只說中文",  # 1 身分
        "照唸",  # 2 固定台詞照唸、規則要點說到每一條
        "不自己換階段",  # 3
        "lookup_rules",  # 4 規則問題一律先查
        "ask_thinking_model",  # 5 查不到不猜；要推理才轉交
        "不查規則",  # 6 五類固定回答
        "不解釋魔法之書",  # 7 九項不管的事
        "no_reply",  # 8 閒聊
        "next_step",  # 9 語音指令呼叫工具
        "不重講這個階段",  # 10 答完補 back_to
        "瞞刃就是暗刃",  # 11 這局的補充
        "現況",  # 12
    ]
    for keyword, section in zip(keywords, sections, strict=True):
        assert keyword in section, keyword


def test_c03_instructions_have_six_answers_and_two_waiting_lines() -> None:
    text = instructions(7)
    for code in SIX_ANSWERS:
        assert content.fixed_line(code, player_count=7) in text, code
    assert content.fixed_line("wait_lookup") in text
    assert content.fixed_line("wait_thinking") in text


def test_instructions_name_all_five_command_tools() -> None:
    text = instructions(7)
    for tool in ("next_step", "previous_step", "pause_hosting", "resume_hosting", "end_hosting"):
        assert tool in text


def test_instructions_list_nine_things_host_does_not_do() -> None:
    assert len(content.NOT_HOSTS_JOB) == 9
    text = instructions(7)
    for item in content.NOT_HOSTS_JOB:
        assert item in text


def test_instructions_carry_current_status() -> None:
    text = instructions(7, step="turn", turn_number=3, phase_number=2, paused=True)
    assert "第 3 回合" in text
    assert content.PHASE_NAMES[2] in text
    assert "主持暫停中" in text
    assert "主持暫停中" not in instructions(7, step="turn", turn_number=3, phase_number=2)


# --- 現況 ---


def test_status_text_inside_a_turn() -> None:
    text = content.status_text(step="turn", turn_number=3, phase_number=2, paused=False)
    assert "第 3 回合" in text and content.PHASE_NAMES[2] in text
    assert "暫停" not in text


def test_status_text_paused_and_before_first_turn() -> None:
    text = content.status_text(step="night_1", turn_number=None, phase_number=None, paused=True)
    assert content.STEP_NAMES["night_1"] in text
    assert "主持暫停中" in text


def test_status_text_ended() -> None:
    text = content.status_text(step="ended", turn_number=4, phase_number=3, paused=False)
    assert content.STEP_NAMES["ended"] in text


# --- 工具：spec §8.1 ---


def test_tools_match_spec() -> None:
    tools = content.host_tools()
    assert all(isinstance(tool, VoiceToolSpec) for tool in tools)
    assert [tool.name for tool in tools] == [
        "lookup_rules",
        "ask_thinking_model",
        "next_step",
        "previous_step",
        "pause_hosting",
        "resume_hosting",
        "end_hosting",
        "no_reply",
    ]
    by_name = {tool.name: tool for tool in tools}
    for name in ("lookup_rules", "ask_thinking_model"):
        params = by_name[name].parameters
        assert list(params["properties"]) == ["question"]
        assert params["properties"]["question"]["type"] == "string"
        assert params["required"] == ["question"]
    for name in ("next_step", "previous_step", "pause_hosting", "resume_hosting", "no_reply"):
        params = by_name[name].parameters
        assert params["properties"] == {}
        assert params.get("required", []) == []
    end = by_name["end_hosting"].parameters
    assert list(end["properties"]) == ["winner"]
    assert end["properties"]["winner"]["enum"] == ["white_rose", "blood_blade"]
    assert end.get("required", []) == []
    assert all(tool.description.strip() for tool in tools)


# --- 結束的祝詞要有儀式感（2026-11-22 立倫試聽後要求） ---


@pytest.mark.parametrize("code", ["end_white_rose", "end_blood_blade"])
def test_winner_lines_are_announced_with_ceremony(code: str) -> None:
    request = content.line_request(code)
    # 字句還是固定台詞，一個字都不能改
    assert content.fixed_line(code) in request
    assert "不要加、不要改" in request
    # 語氣與節奏：隆重、放慢、加重、停頓
    for word in ("隆重", "放慢", "加重", "停頓"):
        assert word in request, word
    assert request != content.verbatim_request(content.fixed_line(code))


@pytest.mark.parametrize("code", ["end_plain", "opening", "setup", "night_1", "night_2"])
def test_other_lines_are_requested_as_before(code: str) -> None:
    assert content.line_request(code) == content.verbatim_request(content.fixed_line(code))


def test_winner_lines_have_a_beat_between_the_two_sentences() -> None:
    for code in ("end_white_rose", "end_blood_blade"):
        line = content.fixed_line(code)
        assert "獲勝" in line
        assert "辛苦" not in line
        # 停頓寫在字句裡：陣營名稱前後各一個破折號，兩句之間一個刪節號
        assert line.count("——") == 2
        assert "！……" in line
