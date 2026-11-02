from app.integrations.llm.base import LLMProvider

DEFAULT_REPLY = "這是 FakeLLMProvider 的固定回覆"


class FakeLLMProvider(LLMProvider):
    """測試用：對任何輸入回傳固定文字，不發出任何網路請求。"""

    def __init__(self, reply: str = DEFAULT_REPLY) -> None:
        self.reply = reply

    def generate(self, prompt: str) -> str:
        return self.reply
