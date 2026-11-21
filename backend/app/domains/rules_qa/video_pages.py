"""規則書頁面文字的差異：店員刪掉的段落與改過的行（add-rules-video-mobile design.md D11）。

以行為單位比對原文（games_manual）與店員編輯後的文字；行去掉前後空白、略過空行。
- 完全相同 → 不列。
- 相似度（difflib.SequenceMatcher.ratio）≥ SIMILARITY_THRESHOLD → 「改過」（例如修正 OCR 錯字）。
- 相似度更低或找不到對應 → 「刪掉」，連續刪掉的行合成一段。
每一處都保留原文（改過的也保留編輯後），讓畫面同時顯示，不只顯示分類。
"""

import hashlib
from dataclasses import dataclass
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.6


@dataclass(frozen=True)
class RemovedBlock:
    lines: list[str]


@dataclass(frozen=True)
class ChangedLine:
    original: str
    edited: str
    similarity: float


@dataclass(frozen=True)
class PageDiff:
    removed: list[RemovedBlock]
    changed: list[ChangedLine]


def text_hash(text: str) -> str:
    """原文的雜湊：存在 page_texts，之後比對原文是不是被重新上傳過。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def page_diff(original: str, edited: str) -> PageDiff:
    before, after = _lines(original), _lines(edited)
    removed: list[int] = []
    changed: list[ChangedLine] = []
    matcher = SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "insert"):
            continue
        if tag == "delete":
            removed.extend(range(i1, i2))
            continue
        # replace：每一行原文找編輯後最像、還沒配對過的一行
        used: set[int] = set()
        for i in range(i1, i2):
            best_j, best = None, 0.0
            for j in range(j1, j2):
                if j in used:
                    continue
                ratio = _similarity(before[i], after[j])
                if ratio > best:
                    best_j, best = j, ratio
            if best_j is not None and best >= SIMILARITY_THRESHOLD:
                used.add(best_j)
                changed.append(ChangedLine(before[i], after[best_j], round(best, 3)))
            else:
                removed.append(i)
    return PageDiff(_blocks(before, sorted(removed)), changed)


def _blocks(lines: list[str], indices: list[int]) -> list[RemovedBlock]:
    blocks: list[list[str]] = []
    previous = None
    for index in indices:
        if previous is None or index != previous + 1:
            blocks.append([])
        blocks[-1].append(lines[index])
        previous = index
    return [RemovedBlock(block) for block in blocks]
