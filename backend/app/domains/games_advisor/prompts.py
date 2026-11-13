"""games_advisor 批次指令送給 LLM 的提示詞與輸出格式。

要調整提示詞只需要改這個檔案。輸出格式（JsonSchema）照 Azure strict 的規定寫：所有欄位都列為
required、additionalProperties 為 false。
"""

from collections.abc import Sequence
from typing import Any, Protocol

from app.domains.games_advisor.schemas import Review
from app.integrations.llm.types import JsonSchema

# --- 心得摘要（spec §8.3） ---

_SUMMARY_INSTRUCTIONS = """\
你負責整理桌遊心得。請讀完下面同一款桌遊的全部心得，寫一段 120 到 200 字的繁體中文摘要。

要寫：玩起來的氣氛、玩家之間的互動方式、對運氣與策略的感受、適合的場合。英文心得也用繁體中文寫。
不要寫：整體好壞的評價（例如好玩、無聊）；價格、版本、翻譯品質、購買管道；規則說明；心得沒有提到的特性。

只輸出摘要本身，不要標題、不要條列、不要前言。"""


def _game_line(game: dict[str, Any]) -> str:
    return f"桌遊：{game['name']}（{game['english_name']}）"


def summary_prompt(game: dict[str, Any], reviews: Sequence[Review]) -> str:
    parts = [_SUMMARY_INSTRUCTIONS, _game_line(game)]
    parts += [
        f"心得 {number}（{review.language}）：\n{review.text}"
        for number, review in enumerate(reviews, start=1)
    ]
    return "\n\n".join(parts)


# --- 歸納詞彙表：擷取候選詞（spec §8.5 第 1 步） ---

# 立倫 2026-11-11 指定的 35 個優先候選詞。和標籤規則衝突的詞（例如和類型重複的「派對」、
# 同義的「搞笑／滑稽／幽默」）不在這裡先刪，由合併同義詞與立倫審核處理
PRIORITY_CANDIDATES = (
    "派對、嘴砲、合作、搞笑、滑稽、出糗、幽默、放鬆、懸疑、推理、分析、決策、觀察、掌控、自由、"
    "分配、學習、專注、活用、動手、主觀、客觀、聯誼、交心、探索、融合、模擬、組合、拆開、破壞、"
    "競爭、刺激、緊張、靜止、平靜"
)

CANDIDATES_INSTRUCTIONS = f"""\
你負責從桌遊心得裡找出「候選詞」：描述這款桌遊玩起來感受的短詞。之後會把候選詞整理成標籤。

規則：
1. 候選詞是 2 到 8 個字的繁體中文短詞，只描述玩起來的感受，例如氣氛、互動方式、運氣的影響、\
適合的場合、美術與配件。英文心得也用繁體中文的候選詞。
2. 下面 4 類不能當候選詞：
   - 整體好壞的評價，例如好玩、無聊、推薦。
   - 和人數、時長、年齡重複的，例如很快玩完、適合小孩、幾個人最好玩。
   - 和類別、機制、難度重複的，例如陣營對抗、容易上手。
   - 價格、版本、翻譯品質、購買管道。
3. 心得裡有提到下面這些詞對應的感受時，優先用這些詞當候選詞；心得沒提到的就不要收。\
這份清單以外的重要感受，照樣可以擷取。
   {PRIORITY_CANDIDATES}
4. 每個候選詞附一句描述（description），以及提到它的心得網址（source_urls）。\
網址只能用下面每篇心得的 source_url。
5. 心得沒有提到的感受不要寫。"""

CANDIDATES_SCHEMA = JsonSchema(
    name="tag_candidates",
    schema={
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "description": {"type": "string"},
                        "source_urls": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["term", "description", "source_urls"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    },
)


def reviews_input(game: dict[str, Any], reviews: Sequence[Review]) -> str:
    """一款桌遊的全部心得，每篇帶 source_url，讓模型可以標出依據。"""
    parts = [_game_line(game)]
    parts += [
        f"心得 {number}\nsource_url：{review.source_url}\n語言：{review.language}\n"
        f"內容：\n{review.text}"
        for number, review in enumerate(reviews, start=1)
    ]
    return "\n\n".join(parts)


# --- 歸納詞彙表：合併同義詞（spec §8.5 第 2 步） ---


class NumberedCandidate(Protocol):
    """編了號的候選詞（c1、c2…）。"""

    id: str
    term: str
    description: str
    game_name: str


def merge_instructions(max_tags: int) -> str:
    return f"""\
下面是從多款桌遊的心得擷取出來的候選詞，每個有編號（c1、c2…）。請把意思相同或相近的候選詞\
合併成標籤。

規則：
1. 每個標籤有英文代碼（code：小寫英文字母開頭，只用小寫英文字母、數字、底線）、\
繁體中文名稱（name）、一句繁體中文定義（definition），以及它合併了哪些候選詞（candidate_ids）。
2. 每個面向只留一個方向：例如留了「運氣影響大」，就不要另設「運氣影響小」。\
反方向的候選詞放進 discarded，並在 reason 寫出原因。
3. 標籤最多 {max_tags} 個。超過時，保留出現在比較多款桌遊的；沒有保留的候選詞放進 discarded，\
並在 reason 寫出原因。
4. 每個候選詞只能出現一次：放在某一個標籤的 candidate_ids，或放在 discarded。"""


MERGE_SCHEMA = JsonSchema(
    name="tag_vocabulary_draft",
    schema={
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "name": {"type": "string"},
                        "definition": {"type": "string"},
                        "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["code", "name", "definition", "candidate_ids"],
                    "additionalProperties": False,
                },
            },
            "discarded": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["candidate_id", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["tags", "discarded"],
        "additionalProperties": False,
    },
)


def merge_input(candidates: Sequence[NumberedCandidate]) -> str:
    """全部候選詞，一行一個：編號、候選詞、描述、來自哪一款桌遊。"""
    return "\n".join(
        f"{candidate.id}｜{candidate.term}｜{candidate.description}｜桌遊：{candidate.game_name}"
        for candidate in candidates
    )
