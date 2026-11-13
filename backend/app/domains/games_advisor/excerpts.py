"""把心得切成心得片段（spec §8.4）。

純函式：不用 LLM、不連資料庫，同一篇心得每次都切出一樣的結果。存原文，不翻譯。
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.domains.games_advisor import constants
from app.domains.games_advisor.schemas import Review


@dataclass(frozen=True)
class ExcerptLimits:
    """心得片段的長度上下限。中文算字元數（不含空白），英文算單字數。"""

    min_chinese_chars: int = constants.EXCERPT_MIN_CHINESE_CHARS
    max_chinese_chars: int = constants.EXCERPT_MAX_CHINESE_CHARS
    min_english_words: int = constants.EXCERPT_MIN_ENGLISH_WORDS
    max_english_words: int = constants.EXCERPT_MAX_ENGLISH_WORDS


DEFAULT_LIMITS = ExcerptLimits()


@dataclass(frozen=True)
class Excerpt:
    """一段心得片段，加上從所屬心得複製來的出處。"""

    text: str
    source_url: str
    site_name: str
    language: str


def _units(text: str, language: str) -> list[tuple[int, bool]]:
    """計算長度用的單位，每個單位是（結束位置，是不是句子的結尾）。

    英文一個單字算一個單位，句子的結尾是以 . ! ? 收尾的單字；
    中文一個非空白字元算一個單位，句子的結尾是 。！？。
    """
    if language == "en":
        return [(word.end(), word.group()[-1] in ".!?") for word in re.finditer(r"\S+", text)]
    return [(char.end(), char.group() in "。！？") for char in re.finditer(r"\S", text)]


def _cut(paragraph: str, language: str, maximum: int) -> list[str]:
    """把太長的段落切開：切在不超過上限的最後一個句子結尾後面；沒有句子結尾就照上限切。"""
    pieces = []
    rest = paragraph
    while True:
        units = _units(rest, language)
        if len(units) <= maximum:
            pieces.append(rest)
            return pieces
        sentence_ends = [end for end, ends_sentence in units[:maximum] if ends_sentence]
        cut = sentence_ends[-1] if sentence_ends else units[maximum - 1][0]
        pieces.append(rest[:cut])
        rest = rest[cut:].lstrip()


def split_review(text: str, language: str, limits: ExcerptLimits = DEFAULT_LIMITS) -> list[str]:
    """把一篇心得切成心得片段。

    1. 依空行（\\n\\n）切成段落。
    2. 太短的段落併到下一段；最後一段太短就併到前一段；整篇只有一段太短就保留。
    3. 太長的段落在句子結尾切開。切開後的小段不再合併。
    """
    if language == "en":
        minimum, maximum = limits.min_english_words, limits.max_english_words
    else:
        minimum, maximum = limits.min_chinese_chars, limits.max_chinese_chars

    merged: list[str] = []
    pending = ""
    for paragraph in (part.strip() for part in text.split("\n\n")):
        if not paragraph:
            continue
        current = f"{pending}\n\n{paragraph}" if pending else paragraph
        if len(_units(current, language)) < minimum:
            pending = current
        else:
            merged.append(current)
            pending = ""
    if pending and merged:
        merged[-1] = f"{merged[-1]}\n\n{pending}"
    elif pending:
        merged.append(pending)

    return [piece for paragraph in merged for piece in _cut(paragraph, language, maximum)]


def split_reviews(
    reviews: Iterable[Review], limits: ExcerptLimits = DEFAULT_LIMITS
) -> list[Excerpt]:
    """把同一款桌遊的幾篇心得切成心得片段。一篇一篇切，不跨篇合併。"""
    return [
        Excerpt(
            text=piece,
            source_url=review.source_url,
            site_name=review.site_name,
            language=review.language,
        )
        for review in reviews
        for piece in split_review(review.text, review.language, limits)
    ]
