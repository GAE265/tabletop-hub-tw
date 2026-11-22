"""每次 LLM／看圖呼叫的實際 token 用量（2026-11-23 永傑要求，算費用用）。

雲端實作每呼叫一次就 record_usage 一筆，並寫一行 log。呼叫端（例如規則影片的草稿工作）用
`with collect_usage() as usage:` 收集這段期間的呼叫；不在 collect_usage 裡時只寫 log。
用執行緒同時呼叫時，用 in_current_context 包住要在執行緒裡跑的函式，紀錄才會進同一份。

不知道任何 domain 的存在（AGENTS.md 4.2）。
"""

import contextvars
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageRecord:
    kind: str  # llm｜vision
    name: str  # 結構化輸出的 schema 名稱；純文字呼叫是 text
    model: str
    input_tokens: int
    output_tokens: int  # 含推理
    reasoning_tokens: int
    seconds: float


class UsageLog:
    """一段期間內的呼叫紀錄（執行緒安全）。"""

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()

    def add(self, record: UsageRecord) -> None:
        with self._lock:
            self._records.append(record)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            records = list(self._records)
        by_name: dict[str, dict[str, int]] = {}
        for r in records:
            entry = by_name.setdefault(r.name, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            entry["calls"] += 1
            entry["input_tokens"] += r.input_tokens
            entry["output_tokens"] += r.output_tokens
        return {
            "calls": len(records),
            "input_tokens": sum(r.input_tokens for r in records),
            "output_tokens": sum(r.output_tokens for r in records),
            "reasoning_tokens": sum(r.reasoning_tokens for r in records),
            "by_name": by_name,
            "records": [asdict(r) for r in records],
        }


_current: contextvars.ContextVar[UsageLog | None] = contextvars.ContextVar(
    "llm_usage_log", default=None
)


@contextmanager
def collect_usage() -> Iterator[UsageLog]:
    log = UsageLog()
    token = _current.set(log)
    try:
        yield log
    finally:
        _current.reset(token)


def record_usage(record: UsageRecord) -> None:
    logger.info(
        "%s 呼叫 %s（%s）：輸入 %d、輸出 %d（推理 %d）tokens，%.1f 秒",
        record.kind,
        record.name,
        record.model,
        record.input_tokens,
        record.output_tokens,
        record.reasoning_tokens,
        record.seconds,
    )
    log = _current.get()
    if log is not None:
        log.add(record)


def in_current_context[T](fn: Callable[..., T]) -> Callable[..., T]:
    """把現在的紀錄帶進別的執行緒：在送出工作的執行緒呼叫，
    回傳的函式在任何執行緒執行都記進同一份。"""
    log = _current.get()

    def run(*args: Any, **kwargs: Any) -> T:
        token = _current.set(log)
        try:
            return fn(*args, **kwargs)
        finally:
            _current.reset(token)

    return run


def usage_of(response: Any) -> tuple[int, int, int]:
    """Responses API 回應的（輸入, 輸出, 推理）tokens；沒有 usage 時是 0。"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    details = getattr(usage, "output_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", 0) if details is not None else 0
    return usage.input_tokens or 0, usage.output_tokens or 0, reasoning or 0
