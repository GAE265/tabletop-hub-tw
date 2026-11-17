"""把規則書頁面切成檢索用的段落（design.md D3）。

每頁依空行切成段落，再把相鄰段落合併到 max_chars 以內；段落不跨頁。單一段落超過上限時
依句號切開，仍然太長就硬切。
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

MAX_CHUNK_CHARS = 600

# 句子結尾（中文與英文的句號、問號、驚嘆號），保留標點在句子上
_SENTENCE_END = re.compile(r"(?<=[。！？!?；;.])")


@dataclass(frozen=True)
class Chunk:
    page: int
    content: str


def split_pages(pages: Sequence[tuple[int, str]], max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """依頁碼順序切段；空白頁略過。"""
    chunks: list[Chunk] = []
    for page, content in pages:
        chunks.extend(Chunk(page, text) for text in _split_page(content, max_chars))
    return chunks


def _split_page(content: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        pieces.extend(_split_paragraph(paragraph, max_chars))

    merged: list[str] = []
    for piece in pieces:
        if merged and len(merged[-1]) + 2 + len(piece) <= max_chars:
            merged[-1] = f"{merged[-1]}\n\n{piece}"
        else:
            merged.append(piece)
    return merged


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    parts: list[str] = []
    current = ""
    for sentence in (s for s in _SENTENCE_END.split(paragraph) if s):
        while len(sentence) > max_chars:
            # 一句就超過上限：先送出累積的，再把這句硬切
            if current:
                parts.append(current)
                current = ""
            parts.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if len(current) + len(sentence) <= max_chars:
            current += sentence
        else:
            parts.append(current)
            current = sentence
    if current:
        parts.append(current)
    return parts
