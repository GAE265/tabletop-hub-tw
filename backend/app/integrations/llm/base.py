from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """所有 domain 呼叫 LLM 的唯一介面；不得直接 import 模型廠商 SDK。"""

    @abstractmethod
    def generate(self, prompt: str) -> str: ...
