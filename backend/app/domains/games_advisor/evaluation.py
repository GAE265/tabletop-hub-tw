"""評估題組 eval（spec §15）：用真的模型跑 eval_cases.json 的玩家情境，產生分數與報告。

- 直接呼叫對話 service（和 API 同一個），不經過 HTTP API：API 回應裡沒有工具參數。真的 LLM
  provider 外面包一層記錄器，從裡面取工具參數、工具結果與 token 用量（spec §15.1）。
- 每一輪照 expect 比對，算條件分與偏好分；某一輪不符合就停在那一輪（spec §15.2、§15.3）。
  manual 列成勾選框，由立倫勾選後自己統計。
- 評審（spec §15.6）：每張卡片多呼叫 1 次模型，檢查推薦理由有沒有依據。只給建議，不算分。
- 開始前檢查不通過就拋 Refused，不呼叫模型。報告裡有心得片段原文，寫到 repo 外。
"""

import json
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NamedTuple, Protocol

from pydantic import ValidationError

from app.core.auth import CurrentUser
from app.core.errors import AppError
from app.domains.games_advisor import prompts
from app.domains.games_advisor.conversation import (
    DROPPED_REPLY,
    REJECTED_REPLY,
    AdvisorReply,
    ConversationService,
    RecommendationCard,
)
from app.domains.games_advisor.schemas import (
    EvalCase,
    EvalCasesFile,
    EvalExpect,
    EvalTurn,
    ReasonCheckOutput,
    describe_eval_problems,
)
from app.domains.games_advisor.search import GameSearch, GameSource, ReviewSource, TagSource
from app.domains.games_advisor.service import LLMFailed, Refused, ask_llm, parse_output
from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import LLMError
from app.integrations.llm.types import JsonSchema, LLMResponse, ToolResult, ToolSpec

# Demo 題固定跑 3 次；--repeat 只影響其他題（spec §15.3）
DEMO_RUNS = 3

# 拿到這兩種固定文字，這一輪就算不符合（spec §15.3）
FIXED_REPLIES = (REJECTED_REPLY, DROPPED_REPLY)

# 在本機執行，沒有登入者；對話 service 要一個身分，用玩家
_EVAL_USER = CurrentUser(id=uuid.UUID(int=0), role="player")

ScoreKind = Literal["constraint", "preference"]
TurnStatus = Literal["matched", "mismatched", "not_run"]
JudgeStatus = Literal["supported", "unsupported", "not_judged", "failed"]

# 每個工具參數算進哪一種分數，順序也是報告的順序（spec §15.2）。
# ⚠️ 要和 schemas.EvalToolArgs 的欄位一致
_TOOL_ARG_KINDS: dict[str, ScoreKind] = {
    "players": "constraint",
    "max_minutes": "constraint",
    "min_minutes": "constraint",
    "youngest_age": "constraint",
    "weight_min": "preference",
    "weight_max": "preference",
    "prefer_tags": "preference",
    "avoid_tags": "preference",
    "prefer_categories": "preference",
    "avoid_categories": "preference",
    "prefer_mechanics": "preference",
    "avoid_mechanics": "preference",
    "exclude_bgg_ids": "constraint",
}
# 檢查「有沒有包含」的清單參數：模型多帶其他值不算錯。其他參數比數值相等
_LIST_ARGS = {name for name in _TOOL_ARG_KINDS if name.startswith(("prefer_", "avoid_"))}
# 題組檔用 BGG ID 寫排除清單，工具參數是桌遊 id
_EXCLUDE = "exclude_bgg_ids"
_TOOL_ARGUMENT_NAMES = {_EXCLUDE: "exclude_game_ids"}
# 預期值或實際值是桌遊的項目：報告換成桌遊名稱
_GAME_ITEMS = {"expect_any", "forbid", f"tool_args.{_EXCLUDE}"}


class Score(NamedTuple):
    """一種分數：通過幾項、共幾項。"""

    passed: int
    total: int


@dataclass(frozen=True)
class CheckResult:
    """程式比對的一個項目，算 1 分。name 例如 action、tool_args.players。"""

    name: str
    kind: ScoreKind
    expected: Any
    actual: Any
    passed: bool


@dataclass(frozen=True)
class TurnOutcome:
    """一輪實際發生的事，比對的依據：每次查詢的工具參數（照先後）、卡片上的桌遊 id、放寬的條件。"""

    searches: list[dict[str, Any]]
    card_game_ids: list[int]
    relaxed_constraint: str | None


@dataclass(frozen=True)
class JudgeVerdict:
    """一張卡片的評審建議。unsupported 是有疑慮時列出的說法；note 是未評審或評審失敗的原因。"""

    status: JudgeStatus
    unsupported: list[str] = field(default_factory=list)
    note: str = ""


@dataclass(frozen=True)
class CardResult:
    game_id: int
    name: str
    reason: str
    # 卡片上的心得片段，每段是 id、text、language
    excerpts: list[dict[str, Any]]
    # None：這次沒有跑評審（--no-judge）
    judge: JudgeVerdict | None


@dataclass(frozen=True)
class TurnResult:
    """一輪的結果。error 是這一輪拿到的錯誤或固定文字；有 error 或未執行時，項目全部算沒通過。"""

    player: str
    manual: list[str]
    status: TurnStatus
    checks: list[CheckResult]
    reply: str | None = None
    error: str | None = None
    searches: list[dict[str, Any]] = field(default_factory=list)
    cards: list[CardResult] = field(default_factory=list)

    @property
    def manual_checkable(self) -> bool:
        """這一輪有真的回覆，人工項目才能勾；否則算沒通過（MR 說明的解讀 4）。"""
        return self.status != "not_run" and self.error is None


@dataclass(frozen=True)
class CaseRun:
    """一題跑一次的結果。number 是這一題的第幾次，從 1 開始。"""

    case_id: str
    demo: bool
    number: int
    turns: list[TurnResult]

    @property
    def all_matched(self) -> bool:
        return all(turn.status == "matched" for turn in self.turns)


@dataclass(frozen=True)
class EvalResult:
    runs: list[CaseRun]
    constraint: Score
    preference: Score
    # 人工項目共幾項；勾選由立倫在報告做，程式不知道過了幾項
    manual_items: int
    # Demo 題的 id → 3 次的程式比對（條件分、偏好分）是不是都全過。全過也還要立倫勾完人工項目
    demo: dict[str, bool]
    # 只算對話；評審的 generate_json 不回傳用量（spec §15.6）
    input_tokens: int
    output_tokens: int
    judge_calls: int
    warnings: list[str]


@dataclass(frozen=True)
class Judge:
    """評審：用批次設定建的 provider（spec §7.2 規則 4），以及報告開頭要印的模型名稱。"""

    llm: LLMProvider
    model: str


class EvalGameSource(GameSource, Protocol):
    """評估題組讀桌遊用到的方法：「查桌遊」用的那些，加上列出全部桌遊。"""

    def list_games(self) -> list[dict[str, Any]]: ...


# --- 比對（spec §15.2） ---


def check_turn(
    expect: EvalExpect, outcome: TurnOutcome, game_ids: Mapping[int, int]
) -> list[CheckResult]:
    """照 expect 比對一輪，寫出來的項目各一個結果；manual 由人工檢查，不在這裡。

    game_ids 是 BGG ID → 桌遊 id。
    """
    cards = set(outcome.card_game_ids)
    results = []
    for name, kind, expected in _expected_items(expect):
        actual: Any
        if name == "action":
            actual = "有卡片" if cards else "沒有卡片"
            # recommend 要有卡片；follow_up、off_topic 要沒有卡片，兩者的差別由 manual 檢查
            passed = bool(cards) == (expected == "recommend")
        elif name == "relaxed_constraint":
            actual = outcome.relaxed_constraint
            passed = actual == expected
        elif name == "expect_any":
            actual = outcome.card_game_ids
            passed = bool(_game_ids(expected, game_ids) & cards)
        elif name == "forbid":
            actual = outcome.card_game_ids
            passed = not _game_ids(expected, game_ids) & cards
        else:
            argument = name.removeprefix("tool_args.")
            actual, passed = _check_tool_arg(argument, expected, outcome.searches, game_ids)
        results.append(CheckResult(name, kind, expected, actual, passed))
    return results


def _expected_items(expect: EvalExpect) -> list[tuple[str, ScoreKind, Any]]:
    """expect 寫了的項目：（名稱，算進哪種分數，預期值），照固定的順序。"""
    written = expect.model_fields_set
    items: list[tuple[str, ScoreKind, Any]] = []
    if "action" in written:
        items.append(("action", "constraint", expect.action))
    if expect.tool_args is not None:
        items += [
            (f"tool_args.{name}", kind, getattr(expect.tool_args, name))
            for name, kind in _TOOL_ARG_KINDS.items()
            if name in expect.tool_args.model_fields_set
        ]
    if "relaxed_constraint" in written:
        items.append(("relaxed_constraint", "constraint", expect.relaxed_constraint))
    if expect.expect_any is not None:
        items.append(("expect_any", "preference", expect.expect_any))
    if expect.forbid is not None:
        items.append(("forbid", "constraint", expect.forbid))
    return items


def _check_tool_arg(
    name: str, expected: Any, searches: list[dict[str, Any]], game_ids: Mapping[int, int]
) -> tuple[Any, bool]:
    """比對這一輪第 1 次查詢的一個參數，也就是玩家原本說的條件；回傳（實際值，過了沒）。"""
    if not searches:
        return "沒有查詢", False
    actual = searches[0].get(_TOOL_ARGUMENT_NAMES.get(name, name))
    if expected is None:
        # 寫 null：必須沒帶。清單參數給空陣列也等於沒帶
        return actual, actual is None or actual == []
    if name == _EXCLUDE:
        return actual, _game_ids(expected, game_ids) <= _as_set(actual)
    if name in _LIST_ARGS:
        return actual, set(expected) <= _as_set(actual)
    is_number = isinstance(actual, int | float) and not isinstance(actual, bool)
    return actual, is_number and actual == expected


def _game_ids(bgg_ids: Sequence[int], game_ids: Mapping[int, int]) -> set[int]:
    return {game_ids[bgg_id] for bgg_id in bgg_ids if bgg_id in game_ids}


def _as_set(value: Any) -> set[Any]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str | int)}


def _unchecked(expect: EvalExpect, actual: str) -> list[CheckResult]:
    """沒有拿回覆比對的輪次（未執行，或拿到錯誤、固定文字）：項目全部算沒通過。"""
    return [
        CheckResult(name, kind, expected, actual, passed=False)
        for name, kind, expected in _expected_items(expect)
    ]


# --- 記錄器（spec §15.1） ---


@dataclass
class _Exchange:
    """記錄器記下的一次 respond：送出的 input，以及模型的回應（呼叫失敗時是 None）。"""

    input: str | list[ToolResult]
    response: LLMResponse | None = None


class _RecordingLLM(LLMProvider):
    """包在真的 LLM provider 外面，記下每次 respond 的輸入與回應，其他照原樣轉送。"""

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        # 這一輪的呼叫；每輪開始時清空
        self.exchanges: list[_Exchange] = []
        self.input_tokens = 0
        self.output_tokens = 0

    def start_turn(self) -> None:
        self.exchanges = []

    def generate(self, prompt: str) -> str:
        return self._inner.generate(prompt)

    def generate_json(self, *, instructions: str, input: str, schema: JsonSchema) -> dict:
        return self._inner.generate_json(instructions=instructions, input=input, schema=schema)

    def respond(
        self,
        *,
        instructions: str,
        input: str | list[ToolResult],
        tools: list[ToolSpec],
        output_schema: JsonSchema,
        previous_response_id: str | None,
        allow_tool_calls: bool = True,
    ) -> LLMResponse:
        exchange = _Exchange(input=input)
        self.exchanges.append(exchange)
        response = self._inner.respond(
            instructions=instructions,
            input=input,
            tools=tools,
            output_schema=output_schema,
            previous_response_id=previous_response_id,
            allow_tool_calls=allow_tool_calls,
        )
        exchange.response = response
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        return response

    def searches(self) -> list[dict[str, Any]]:
        """這一輪每次查詢的工具參數，照先後；一次要求呼叫好幾個工具時只取第 1 個。"""
        return [
            dict(exchange.response.tool_calls[0].arguments)
            for exchange in self.exchanges
            if exchange.response is not None and exchange.response.tool_calls
        ]

    def matches(self, game_id: int) -> list[dict[str, Any]]:
        """這一款在這一輪各次工具結果裡命中的偏好與負面偏好（spec §11.7），照查詢先後。"""
        found = []
        # ⚠️ 要和 search._game_output 回傳給 LLM 的欄位一致（games、id、matched_preferences、
        # matched_avoids）
        for exchange in self.exchanges:
            if isinstance(exchange.input, str):
                continue
            for result in exchange.input:
                for game in result.output.get("games", []):
                    if game["id"] == game_id:
                        found.append(
                            {
                                "matched_preferences": game["matched_preferences"],
                                "matched_avoids": game["matched_avoids"],
                            }
                        )
        return found


# --- 評審（spec §15.6） ---


class _CardJudge:
    """每張卡片呼叫 1 次評審，一次只看這一張卡片的依據。"""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self.calls = 0

    def verdict(self, card: RecommendationCard, matches: list[dict[str, Any]]) -> JudgeVerdict:
        if not card.excerpts:
            return JudgeVerdict("not_judged", note="沒有引用心得片段")
        if not card.reason.strip():
            return JudgeVerdict("not_judged", note="推薦理由是空的")
        # 只給卡片上的片段：工具有回傳、但沒被引用的片段，玩家看不到
        judge_input = prompts.reason_check_input(
            card.reason, [excerpt["text"] for excerpt in card.excerpts], matches
        )

        def ask() -> ReasonCheckOutput:
            self.calls += 1
            output = self._llm.generate_json(
                instructions=prompts.REASON_CHECK_INSTRUCTIONS,
                input=judge_input,
                schema=prompts.REASON_CHECK_SCHEMA,
            )
            return parse_output(ReasonCheckOutput, output)

        try:
            # 輸出被拒絕重試 1 次，連不上不重試（spec §7.2 規則 6 的共用函式）
            output = ask_llm(ask)
        except LLMFailed as exc:
            return JudgeVerdict("failed", note=exc.reason)
        except LLMError as exc:
            # 其他 LLMError 也攔下：對話的 token 已經花了，評審出錯不該讓整份報告消失
            return JudgeVerdict("failed", note=f"{type(exc).__name__}：{exc}")
        if output.unsupported:
            return JudgeVerdict("unsupported", unsupported=output.unsupported)
        return JudgeVerdict("supported")


# --- 開始前檢查（spec §15.1） ---


@dataclass(frozen=True)
class _Plan:
    cases: list[EvalCase]
    # BGG ID → 桌遊 id
    game_ids: dict[int, int]
    # 桌遊 id → 繁中名稱
    names: dict[int, str]
    warnings: list[str]


def _prepare(
    data: object,
    games: EvalGameSource,
    reviews: ReviewSource,
    embedding_model: str,
    out_path: Path,
) -> _Plan:
    """開始前檢查，不通過就拋 Refused 並列出所有原因；沒有向量的桌遊只提醒。"""
    problems = []
    if out_path.exists():
        problems.append(f"{out_path} 已經存在；請換一個路徑，或先把它移走")
    try:
        cases = EvalCasesFile.model_validate(data).cases
    except ValidationError as exc:
        raise Refused(*problems, "題組檔的格式不對：", *describe_eval_problems(exc, data)) from exc

    # 讀完就結束交易，不開著交易等模型回應
    with games.transaction():
        all_games = games.list_games()
        ids = [game["id"] for game in all_games]
        summaries = reviews.summary_similarities(
            ids, embedding_model=embedding_model, query_vector=None
        )
        excerpt_models = reviews.list_excerpt_models(ids)
    game_ids = {game["bgg_id"]: game["id"] for game in all_games}
    labels = {game["id"]: f"{game['id']} 號「{game['name']}」" for game in all_games}

    if unknown := sorted(_bgg_ids_in(cases) - game_ids.keys()):
        problems.append(
            f"題組檔有資料庫沒有的 BGG ID：{'、'.join(map(str, unknown))}；請先匯入或同步桌遊"
        )
    problems += _stale_vectors(labels, summaries, excerpt_models, embedding_model)
    if problems:
        raise Refused(*problems)
    return _Plan(
        cases=cases,
        game_ids=game_ids,
        names={game["id"]: game["name"] for game in all_games},
        warnings=_missing_vectors(labels, summaries, excerpt_models),
    )


def _bgg_ids_in(cases: list[EvalCase]) -> set[int]:
    """題組檔寫到的所有 BGG ID：排除清單、expect_any、forbid。"""
    found: set[int] = set()
    for case in cases:
        for turn in case.turns:
            expect = turn.expect
            if expect.tool_args is not None:
                found.update(expect.tool_args.exclude_bgg_ids or [])
            found.update(expect.expect_any or [])
            found.update(expect.forbid or [])
    return found


def _stale_vectors(
    labels: dict[int, str],
    summaries: dict[int, dict[str, Any]],
    excerpt_models: dict[int, list[str]],
    embedding_model: str,
) -> list[str]:
    """向量的模型和目前設定不同的桌遊：查桌遊會當作沒有向量，分數就不準。"""
    stale_summaries = [
        f"{labels.get(game_id, f'{game_id} 號')}（{info['embedding_model']}）"
        for game_id, info in sorted(summaries.items())
        if info["embedding_model"] != embedding_model
    ]
    stale_excerpts = [
        f"{labels.get(game_id, f'{game_id} 號')}（{'、'.join(others)}）"
        for game_id, models in sorted(excerpt_models.items())
        if (others := [model for model in models if model != embedding_model])
    ]
    problems = []
    if stale_summaries:
        problems.append(
            f"這些桌遊的心得摘要向量不是目前的模型 {embedding_model} 產生的："
            f"{'、'.join(stale_summaries)}；請重跑 summarize-reviews"
        )
    if stale_excerpts:
        problems.append(
            f"這些桌遊有心得片段不是目前的模型 {embedding_model} 產生的："
            f"{'、'.join(stale_excerpts)}；請重跑 build-excerpts"
        )
    return problems


def _missing_vectors(
    labels: dict[int, str],
    summaries: dict[int, dict[str, Any]],
    excerpt_models: dict[int, list[str]],
) -> list[str]:
    no_summary = [label for game_id, label in labels.items() if game_id not in summaries]
    no_excerpts = [label for game_id, label in labels.items() if game_id not in excerpt_models]
    warnings = []
    if no_summary:
        warnings.append(
            f"這些桌遊沒有心得摘要向量，查桌遊時比不到心得的相似度：{'、'.join(no_summary)}"
        )
    if no_excerpts:
        warnings.append(f"這些桌遊沒有心得片段，卡片不會有片段：{'、'.join(no_excerpts)}")
    return warnings


# --- 執行 ---


def run_eval(
    data: object,
    *,
    games: EvalGameSource,
    tags: TagSource,
    reviews: ReviewSource,
    embedding: EmbeddingProvider,
    embedding_model: str,
    llm: LLMProvider,
    llm_model: str,
    judge: Judge | None,
    out_path: Path,
    repeat: int = 1,
    warn: Callable[[str], None] | None = None,
) -> EvalResult:
    """跑一次評估題組，報告寫到 out_path。開始前檢查不通過就拋 Refused，不呼叫模型。

    data 是 eval_cases.json 的內容。題目照檔案順序跑，每題連續跑完它的次數：Demo 題 3 次，
    其他題 repeat 次。judge 是 None 代表 --no-judge。
    warn 在開始前檢查之後、呼叫模型之前收到每一則提醒（沒有向量的桌遊），讓執行的人來得及停下。
    """
    plan = _prepare(data, games, reviews, embedding_model, out_path)
    if warn is not None:
        for warning in plan.warnings:
            warn(warning)
    recorder = _RecordingLLM(llm)
    search = GameSearch(
        games=games,
        tags=tags,
        reviews=reviews,
        embedding=embedding,
        embedding_model=embedding_model,
    )
    runner = _Runner(
        conversation=ConversationService(search=search, llm=recorder),
        recorder=recorder,
        game_ids=plan.game_ids,
        judge=None if judge is None else _CardJudge(judge.llm),
    )
    runs = [
        runner.run_case(case, number)
        for case in plan.cases
        for number in range(1, (DEMO_RUNS if case.demo else repeat) + 1)
    ]
    result = _result(runs, runner, plan.warnings)
    report = _Report(plan.game_ids, plan.names).render(
        result, llm_model=llm_model, judge_model=None if judge is None else judge.model
    )
    # 跑完才寫報告，資料夾不存在就建起來：寫不進去的話，前面花的 token 就白費了
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    return result


@dataclass(frozen=True)
class _Runner:
    conversation: ConversationService
    recorder: _RecordingLLM
    game_ids: dict[int, int]
    judge: _CardJudge | None

    def run_case(self, case: EvalCase, number: int) -> CaseRun:
        turns: list[TurnResult] = []
        # 每次都開新對話：第 1 輪不帶 previous_response_id
        previous_id: str | None = None
        for turn in case.turns:
            if turns and turns[-1].status != "matched":
                # 某一輪不符合：這題停在那一輪，後面的輪次標「未執行」（spec §15.3）
                turns.append(
                    TurnResult(
                        player=turn.player,
                        manual=list(turn.expect.manual),
                        status="not_run",
                        checks=_unchecked(turn.expect, "未執行"),
                    )
                )
                continue
            result, previous_id = self._run_turn(turn, previous_id)
            turns.append(result)
        return CaseRun(case_id=case.id, demo=case.demo, number=number, turns=turns)

    def _run_turn(self, turn: EvalTurn, previous_id: str | None) -> tuple[TurnResult, str | None]:
        """送出這一輪的玩家訊息並比對；回傳結果與下一輪要接的 response_id。"""
        self.recorder.start_turn()
        reply: AdvisorReply | None = None
        error: str | None = None
        try:
            reply = self.conversation.send_message(_EVAL_USER, turn.player, previous_id)
        except AppError as exc:
            # ⚠️ 要和 ConversationService.send_message 的錯誤轉換一致：503 是 LLM 或 embedding
            # 暫時連不上，404 是對話過期
            error = f"{exc.status_code} {exc.code}：{exc.message}"
        except LLMError as exc:
            # ⚠️ 要和 API 一致：send_message 不攔截其他 LLMError，API 會回 500
            error = f"500 {type(exc).__name__}：{exc}"
        else:
            if reply.reply in FIXED_REPLIES:
                error = f"固定文字：{reply.reply}"

        manual = list(turn.expect.manual)
        searches = self.recorder.searches()
        if reply is None or error is not None:
            # 解讀 4：不拿固定文字去比對，項目全部算沒通過
            failed = TurnResult(
                player=turn.player,
                manual=manual,
                status="mismatched",
                checks=_unchecked(turn.expect, "沒有比對（這一輪出錯）"),
                error=error,
                searches=searches,
            )
            return failed, previous_id

        outcome = TurnOutcome(
            searches=searches,
            card_game_ids=[card.game["id"] for card in reply.recommendations],
            relaxed_constraint=reply.relaxed_constraint,
        )
        checks = check_turn(turn.expect, outcome, self.game_ids)
        result = TurnResult(
            player=turn.player,
            manual=manual,
            status="matched" if all(check.passed for check in checks) else "mismatched",
            checks=checks,
            reply=reply.reply,
            searches=searches,
            cards=[self._card(card) for card in reply.recommendations],
        )
        return result, reply.response_id

    def _card(self, card: RecommendationCard) -> CardResult:
        verdict = None
        if self.judge is not None:
            verdict = self.judge.verdict(card, self.recorder.matches(card.game["id"]))
        return CardResult(
            game_id=card.game["id"],
            name=card.game["name"],
            reason=card.reason,
            excerpts=card.excerpts,
            judge=verdict,
        )


def _result(runs: list[CaseRun], runner: _Runner, warnings: list[str]) -> EvalResult:
    """算三種分數（spec §15.3）：每一次執行的每個項目都算，未執行的輪次算沒通過。"""
    checks = [check for run in runs for turn in run.turns for check in turn.checks]
    demo: dict[str, bool] = {}
    for run in runs:
        if run.demo:
            demo[run.case_id] = demo.get(run.case_id, True) and run.all_matched
    return EvalResult(
        runs=runs,
        constraint=_score(checks, "constraint"),
        preference=_score(checks, "preference"),
        manual_items=sum(len(turn.manual) for run in runs for turn in run.turns),
        demo=demo,
        input_tokens=runner.recorder.input_tokens,
        output_tokens=runner.recorder.output_tokens,
        judge_calls=0 if runner.judge is None else runner.judge.calls,
        warnings=warnings,
    )


def _score(checks: list[CheckResult], kind: ScoreKind) -> Score:
    picked = [check for check in checks if check.kind == kind]
    return Score(passed=sum(check.passed for check in picked), total=len(picked))


# --- 報告（spec §15.4） ---

_STATUS_TEXT: dict[TurnStatus, str] = {
    "matched": "符合",
    "mismatched": "不符合",
    "not_run": "未執行",
}


def _one_line(text: str) -> str:
    """換行與連續空白合成一個空白，放進 Markdown 的清單或表格不會跑版。"""
    return " ".join(text.split())


class _Report:
    """把評估結果寫成 Markdown。桌遊顯示成名稱，BGG ID 與桌遊 id 用 plan 的對照換算。"""

    def __init__(self, game_ids: dict[int, int], names: dict[int, str]) -> None:
        self._game_ids = game_ids
        self._names = names

    def render(self, result: EvalResult, *, llm_model: str, judge_model: str | None) -> str:
        lines = ["# 評估題組報告", "", *self._header(result, llm_model, judge_model)]
        if result.warnings:
            lines += ["", "## 提醒", "", *(f"- {warning}" for warning in result.warnings)]
        lines += ["", "## 分數", "", *self._scores(result)]
        if result.demo:
            lines += ["", "## Demo 題", "", *self._demo(result)]
        lines += ["", "## 各題"]
        for run in result.runs:
            lines += self._run(run)
        if judge_model is not None:
            lines += ["", "## 評審統計", "", *self._judge_summary(result)]
        return "\n".join(lines) + "\n"

    def _header(self, result: EvalResult, llm_model: str, judge_model: str | None) -> list[str]:
        lines = [f"- 對話模型：{llm_model}"]
        if judge_model is None:
            lines.append("- 這次沒有跑評審（--no-judge）")
        else:
            lines.append(f"- 評審模型：{judge_model}")
            if judge_model == llm_model:
                lines.append("- 評審和對話是同一個模型")
            lines.append(
                f"- 評審呼叫 {result.judge_calls} 次；評審的 token 用量不算在下面，請到 Azure 看"
            )
        lines.append(
            f"- token 用量（只算對話）：輸入 {result.input_tokens:,}、輸出 {result.output_tokens:,}"
        )
        return lines

    def _scores(self, result: EvalResult) -> list[str]:
        unchecked = sum(
            len(turn.manual)
            for run in result.runs
            for turn in run.turns
            if not turn.manual_checkable
        )
        manual = f"共 {result.manual_items} 項，請在下面勾選後自己統計"
        if unchecked:
            manual += f"；其中 {unchecked} 項在未執行或出錯的輪次，算沒通過"
        constraint, preference = result.constraint, result.preference
        return [
            "| 分數 | 結果 |",
            "|---|---|",
            f"| 條件分 | {constraint.passed}/{constraint.total} |",
            f"| 偏好分 | {preference.passed}/{preference.total} |",
            f"| 人工項目 | {manual} |",
        ]

    def _demo(self, result: EvalResult) -> list[str]:
        lines = []
        for case_id, passed in result.demo.items():
            if passed:
                lines.append(f"- {case_id}：程式比對 {DEMO_RUNS} 次全過，人工項目請勾選後確認")
                continue
            failed = [
                str(run.number)
                for run in result.runs
                if run.case_id == case_id and not run.all_matched
            ]
            lines.append(f"- {case_id}：沒過（第 {'、'.join(failed)} 次不符合）")
        return lines

    def _run(self, run: CaseRun) -> list[str]:
        kind = "Demo 題，" if run.demo else ""
        lines = ["", f"### {run.case_id}（{kind}第 {run.number} 次）"]
        for number, turn in enumerate(run.turns, start=1):
            lines += ["", f"#### 第 {number} 輪：{_STATUS_TEXT[turn.status]}", ""]
            lines += self._turn(turn)
        return lines

    def _turn(self, turn: TurnResult) -> list[str]:
        lines = [f"- 玩家：{_one_line(turn.player)}"]
        if turn.status == "not_run":
            names = "、".join(check.name for check in turn.checks)
            if names:
                lines.append(f"- 項目全部算沒通過：{names}")
            lines += [f"- 人工項目算沒通過：{_one_line(item)}" for item in turn.manual]
            return lines
        if turn.error is not None:
            lines.append(f"- 這一輪停下：{_one_line(turn.error)}")
        if turn.reply is not None:
            lines.append(f"- 回覆：{_one_line(turn.reply)}")
        for index, arguments in enumerate(turn.searches, start=1):
            given = {name: value for name, value in arguments.items() if value is not None}
            shown = json.dumps(given, ensure_ascii=False)
            lines.append(f"- 工具參數（第 {index} 次查詢）：`{shown}`")
        if turn.checks:
            lines += ["", "| 項目 | 預期 | 實際 | 結果 |", "|---|---|---|---|"]
            lines += [self._check_row(check) for check in turn.checks]
        if turn.cards:
            lines += ["", "卡片：", ""]
            for index, card in enumerate(turn.cards, start=1):
                lines += self._card(index, card)
        if turn.manual:
            lines += ["", "人工檢查：", ""]
            if turn.manual_checkable:
                lines += [f"- [ ] {_one_line(item)}" for item in turn.manual]
            else:
                lines += [f"- {_one_line(item)}（這一輪出錯，算沒通過）" for item in turn.manual]
        return lines

    def _check_row(self, check: CheckResult) -> str:
        expected, actual = _plain(check.expected), _plain(check.actual)
        if check.name in _GAME_ITEMS:
            if isinstance(check.expected, list):
                expected = self._games([self._game_ids.get(bgg_id) for bgg_id in check.expected])
            if isinstance(check.actual, list):
                actual = self._games(check.actual)
        result = "過" if check.passed else "**不過**"
        cells = [check.name, expected, actual, result]
        return "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"

    def _games(self, game_ids: Sequence[Any]) -> str:
        if not game_ids:
            return "沒有"
        return "、".join(self._names.get(game_id, f"{game_id} 號") for game_id in game_ids)

    def _card(self, index: int, card: CardResult) -> list[str]:
        lines = [
            f"{index}. {card.name}（{card.game_id} 號）",
            f"   - 推薦理由：{_one_line(card.reason) or '（空的）'}",
        ]
        lines += [f"   - 心得片段：{_one_line(excerpt['text'])}" for excerpt in card.excerpts]
        verdict = card.judge
        if verdict is None:
            return lines
        if verdict.status == "supported":
            lines.append("   - 評審建議：有依據")
        elif verdict.status == "unsupported":
            lines.append("   - 評審建議：有疑慮")
            lines += [f"     - {_one_line(item)}" for item in verdict.unsupported]
        elif verdict.status == "not_judged":
            lines.append(f"   - 未評審：{verdict.note}")
        else:
            lines.append(f"   - 評審失敗：{_one_line(verdict.note)}")
        return lines

    def _judge_summary(self, result: EvalResult) -> list[str]:
        counts = Counter(
            card.judge.status
            for run in result.runs
            for turn in run.turns
            for card in turn.cards
            if card.judge is not None
        )
        return [
            f"評審統計：有依據 {counts['supported']} 張／有疑慮 {counts['unsupported']} 張／"
            f"未評審 {counts['not_judged']} 張／評審失敗 {counts['failed']} 張",
            "",
            "評審建議不算分，以人工勾選為準。",
        ]


def _plain(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
