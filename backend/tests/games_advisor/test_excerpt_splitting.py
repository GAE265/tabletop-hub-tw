"""把心得切成心得片段的函式（spec §8.4）。純函式，不連資料庫。

預設長度：中文 40–300 字（不含空白），英文 25–150 個單字。
"""

from types import ModuleType

from app.domains.games_advisor import schemas
from tests.games_advisor.support import make_review


def paragraphs(*parts: str) -> str:
    return "\n\n".join(parts)


def words(word: str, count: int) -> str:
    return " ".join([word] * count)


def test_keeps_paragraphs_that_are_within_limits(excerpts: ModuleType) -> None:
    parts = ["甲" * 50, "乙" * 120, "丙" * 200]

    assert excerpts.split_review(paragraphs(*parts), "zh-TW") == parts


def test_merges_short_paragraph_into_the_next(excerpts: ModuleType) -> None:
    text = paragraphs("甲" * 100, "乙" * 20, "丙" * 100)

    assert excerpts.split_review(text, "zh-TW") == [
        "甲" * 100,
        paragraphs("乙" * 20, "丙" * 100),
    ]


def test_merges_short_last_paragraph_into_the_previous(excerpts: ModuleType) -> None:
    text = paragraphs("甲" * 100, "乙" * 100, "丙" * 20)

    assert excerpts.split_review(text, "zh-TW") == [
        "甲" * 100,
        paragraphs("乙" * 100, "丙" * 20),
    ]


def test_splits_long_paragraph_after_the_last_sentence_end_within_the_limit(
    excerpts: ModuleType,
) -> None:
    # 450 字，句號在第 200、350、450 字：不超過 300 字的最後一個句號是第 200 字
    first, second, third = "甲" * 199 + "。", "乙" * 149 + "。", "丙" * 99 + "。"

    assert excerpts.split_review(first + second + third, "zh-TW") == [first, second + third]


def test_splits_long_paragraph_at_the_limit_when_there_is_no_sentence_end(
    excerpts: ModuleType,
) -> None:
    assert excerpts.split_review("甲" * 450, "zh-TW") == ["甲" * 300, "甲" * 150]


def test_keeps_a_single_short_paragraph(excerpts: ModuleType) -> None:
    assert excerpts.split_review("甲" * 20, "zh-TW") == ["甲" * 20]


def test_english_uses_word_count(excerpts: ModuleType) -> None:
    # 第 2 段有 20 個單字（少於 25），但字元數超過 40：用單字數判斷才會併到下一段
    first, second, third = words("alpha", 40), words("bravo", 20), words("charlie", 40)

    assert excerpts.split_review(paragraphs(first, second, third), "en") == [
        first,
        paragraphs(second, third),
    ]


def test_does_not_merge_across_reviews(excerpts: ModuleType) -> None:
    # 第 1 篇整篇只有一段短的：留在自己那一篇，不併到下一篇
    short = make_review(1, 1, text="甲" * 20)
    normal = make_review(1, 2, text="乙" * 100, language="zh-TW")
    reviews = [schemas.Review.model_validate(review) for review in (short, normal)]

    result = excerpts.split_reviews(reviews)

    assert [(excerpt.text, excerpt.source_url) for excerpt in result] == [
        ("甲" * 20, short["source_url"]),
        ("乙" * 100, normal["source_url"]),
    ]
    # 每段從所屬心得複製網站名稱與語言
    assert [(excerpt.site_name, excerpt.language) for excerpt in result] == [
        (short["site_name"], "zh-TW"),
        (normal["site_name"], "zh-TW"),
    ]


def test_follows_custom_limits(excerpts: ModuleType) -> None:
    limits = excerpts.ExcerptLimits(
        min_chinese_chars=5, max_chinese_chars=10, min_english_words=2, max_english_words=4
    )

    # 下限 5：兩段各 6 字都夠長，不合併（預設的下限 40 會合併成一段）
    assert excerpts.split_review(paragraphs("甲" * 6, "乙" * 6), "zh-TW", limits) == [
        "甲" * 6,
        "乙" * 6,
    ]
    # 上限 10：25 字切成 10、10、5
    assert excerpts.split_review("丙" * 25, "zh-TW", limits) == ["丙" * 10, "丙" * 10, "丙" * 5]
    # 英文的上限 4 個單字
    assert excerpts.split_review(words("delta", 6), "en", limits) == [
        words("delta", 4),
        words("delta", 2),
    ]
