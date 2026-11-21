"""host 測試用的手寫 fake（AGENTS.md §7.5）：查規則、思考模型、時鐘。"""

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.integrations.llm import LLMProvider, LLMResponse, ToolResult, ToolSpec
from app.integrations.llm.types import JsonSchema


@dataclass(frozen=True)
class FakeChunk:
    page: int
    content: str


SIX_CHUNKS = [FakeChunk(page=index + 2, content=f"規則片段 {index + 1}") for index in range(6)]


class FakeRulesLookup:
    """取代「用問題查白薔薇的規則片段」。記下每一次的問題；可以設定回傳、失敗、卡住。"""

    def __init__(self, chunks: list[FakeChunk] | None = None) -> None:
        self.chunks = SIX_CHUNKS if chunks is None else chunks
        self.questions: list[str] = []
        self.error: Exception | None = None
        # 設定之後，每一次查詢都會等到 release 被 set 才回來
        self.entered = threading.Event()
        self.release: threading.Event | None = None

    def __call__(self, question: str) -> list[FakeChunk]:
        self.questions.append(question)
        self.entered.set()
        if self.release is not None:
            assert self.release.wait(timeout=5), "測試忘了放行查規則"
        if self.error is not None:
            raise self.error
        return list(self.chunks)


class FakeThinkingModel(LLMProvider):
    """取代 integrations/llm：只支援 generate()，記下每一次的 prompt。"""

    def __init__(self, reply: str = "思考模型的答案", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.prompts: list[str] = []
        self.other_calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.reply

    def generate_json(self, *, instructions: str, input: str, schema: JsonSchema) -> dict:
        self.other_calls.append("generate_json")
        raise AssertionError("思考模型節點只該呼叫 generate()")

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
        self.other_calls.append("respond")
        raise AssertionError("思考模型節點只該呼叫 generate()")


class FakeClock:
    """可以控制的假時鐘：呼叫它拿現在的時間（UTC），advance 讓時間往前走。"""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, *, seconds: float = 0, minutes: float = 0) -> None:
        self.now += timedelta(seconds=seconds, minutes=minutes)
