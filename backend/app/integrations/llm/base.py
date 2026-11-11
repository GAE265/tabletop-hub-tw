from abc import ABC, abstractmethod

from app.integrations.llm.types import JsonSchema, LLMResponse, ToolResult, ToolSpec


class LLMProvider(ABC):
    """所有 domain 呼叫 LLM 的唯一介面；不得直接 import 模型廠商 SDK。

    每個方法只呼叫模型 1 次。工具迴圈、呼叫次數上限等規則屬於呼叫端的 service。
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """無狀態的純文字輸出。"""

    @abstractmethod
    def generate_json(self, *, instructions: str, input: str, schema: JsonSchema) -> dict:
        """無狀態，輸出符合 schema 的 JSON。"""

    @abstractmethod
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
        """有狀態：接續 previous_response_id 的對話，回傳工具呼叫或最終輸出。

        input 是字串時代表使用者的訊息；是 list[ToolResult] 時代表工具結果。
        allow_tool_calls=False 時保證拿到最終輸出。依賴雲端保存對話（ADR 0001），
        地端實作拋 NotImplementedError。
        """
