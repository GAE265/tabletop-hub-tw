"""規則書切段（spec rules-qa「建立規則書索引」，design.md D3）。"""

from app.domains.rules_qa.chunking import MAX_CHUNK_CHARS, split_pages


def test_each_page_becomes_chunks_with_its_page_number() -> None:
    chunks = split_pages([(1, "第一頁的規則。"), (2, "第二頁的規則。")])
    assert [(c.page, c.content) for c in chunks] == [(1, "第一頁的規則。"), (2, "第二頁的規則。")]


def test_chunks_never_cross_pages() -> None:
    chunks = split_pages([(1, "甲" * 10), (2, "乙" * 10)], max_chars=100)
    assert {c.page for c in chunks} == {1, 2}
    assert all(set(c.content) <= {"甲"} or set(c.content) <= {"乙"} for c in chunks)


def test_short_paragraphs_on_the_same_page_are_merged() -> None:
    page = "第一段。\n\n第二段。\n\n第三段。"
    chunks = split_pages([(3, page)], max_chars=100)
    assert len(chunks) == 1
    assert chunks[0].page == 3
    assert "第一段。" in chunks[0].content and "第三段。" in chunks[0].content


def test_paragraphs_split_when_merged_text_would_exceed_limit() -> None:
    page = ("甲" * 60) + "\n\n" + ("乙" * 60)
    chunks = split_pages([(1, page)], max_chars=100)
    assert [c.content for c in chunks] == ["甲" * 60, "乙" * 60]


def test_long_paragraph_is_split_by_sentences_within_limit() -> None:
    sentence = "每位玩家抽兩張牌。"
    page = sentence * 30  # 一段很長、沒有空行
    chunks = split_pages([(1, page)], max_chars=50)
    assert len(chunks) > 1
    assert all(len(c.content) <= 50 for c in chunks)
    assert "".join(c.content for c in chunks) == page


def test_blank_pages_are_skipped() -> None:
    chunks = split_pages([(1, ""), (2, "   \n\n  "), (3, "有內容。")])
    assert [c.page for c in chunks] == [3]


def test_default_limit() -> None:
    assert MAX_CHUNK_CHARS == 600
    page = "句子。" * 400
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in split_pages([(1, page)]))
