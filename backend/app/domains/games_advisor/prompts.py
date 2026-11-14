"""games_advisor 批次指令送給 LLM 的提示詞與輸出格式。

要調整提示詞只需要改這個檔案。輸出格式（JsonSchema）照 Azure strict 的規定寫：所有欄位都列為
required、additionalProperties 為 false。
"""

import json
from collections.abc import Mapping, Sequence
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


# --- 上標籤（spec §8.7） ---


def tagging_instructions(tags: Sequence[dict[str, str]]) -> str:
    """tags 是標籤詞彙表：每個標籤有 code、name、definition。"""
    vocabulary = "\n".join(f"- {tag['code']}：{tag['name']}。{tag['definition']}" for tag in tags)
    return f"""\
你負責替桌遊貼標籤。請讀完下面同一款桌遊的全部心得，從標籤詞彙表裡選出心得有提到的標籤，\
每個標籤給一個信心分數，並附上依據的心得網址。

標籤詞彙表（只能選這些代碼）：
{vocabulary}

信心分數的標準：
- 0.8 到 1.0：2 篇以上的心得明確提到。
- 0.5 到 0.7：1 篇心得明確提到，或 2 篇以上的心得間接提到。
- 0.2 到 0.4：只有 1 篇心得間接提到。
- 沒有心得提到的標籤不要輸出。

「明確提到」是直接描述這種感受，例如「大家笑到不行」。「間接提到」是要推論才看得出來，\
例如用「很適合聚會」推論出歡樂爆笑。有心得明確說出相反的感受時，分數降一級。

其他規定：
1. 同一個標籤只輸出一次。
2. source_urls 只能用下面每篇心得的 source_url，而且要是真的提到這個標籤的那幾篇。
3. 分數在 0.8 以上的標籤，source_urls 至少要有 2 篇。"""


def tagging_schema(codes: Sequence[str]) -> JsonSchema:
    """上標籤的輸出格式。code 用 enum 限制成詞彙表裡的代碼。"""
    return JsonSchema(
        name="game_tags",
        schema={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "enum": list(codes)},
                            "confidence": {"type": "number"},
                            "source_urls": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["code", "confidence", "source_urls"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["tags"],
            "additionalProperties": False,
        },
    )


# --- 推薦對話（spec §12.1、§12.3） ---

# 每次 respond 都重送：Responses API 不會沿用上一次的 instructions（spec §10）。
# 這些行為 pytest 驗不到，改了要跑評估題組並把分數貼進 MR（spec §12.1、§15）
ADVISOR_INSTRUCTIONS = """\
你是桌遊店的推薦助手，幫玩家挑適合的桌遊。一律用繁體中文（台灣用語）回覆；玩家用英文也用繁體中文回答。

## 條件與偏好
- 依欄位歸類，不看語氣：人數、時長、年齡一律是條件；其他特性（感受、類別、機制、難度）是偏好。
- 只有人數是必要條件。玩家沒提時長、年齡就不篩，也不追問。
- 負面偏好（不想要的）只會讓桌遊排後面，不會排除。

## 追問
- 沒有人數就追問人數。
- 只講人數、沒提偏好時，追問一次偏好，給 2–3 個選項；玩家回「都可以」就直接推薦。
- 缺的項目一次問完。最多追問 2 輪，之後有人數就推薦；沒有人數就繼續追問，只問人數。

## 呼叫 search_games
- 每次查詢都把目前所有條件與偏好完整帶上，不要只帶這次新增的。
- preference_text：把所有正面偏好（包括已經轉成標籤、類別、機制的）寫成一句繁體中文。
  玩家沒有偏好時給 null。
- 口語的「工人放置」「拍賣」這類說法，轉成參數說明裡的 BGG 英文類別或機制名稱。
- 難度換算參考：「不要太燒腦」「輕鬆」是 weight_max 2.5；「想要燒腦」「重策略」是 weight_min 3.0。
- 查無結果時放寬一項條件再查：先放寬時長，再放寬年齡，最多放寬一項。
  還是 0 款就告訴玩家沒有符合的，問要怎麼調整。
- 人數不放寬：只有人數造成查無結果時，建議分桌，問每桌幾個人。
- 推薦後玩家加了偏好：帶新偏好重查，已推薦過的桌遊放進 exclude_game_ids。改了條件：用新條件重查。

## 推薦
- 只推薦 search_games 這次回傳的桌遊，照回傳的順序，最多 3 款，不要自己挑或改順序。
- reply 不列出桌遊名單（名單會顯示在卡片上）。
- 有放寬條件時，在 reply 說明放寬了哪一項，
  例如「沒有 15 分鐘內能玩完的，以下是時長稍長的」。
- 每款的 reason 最多 2 句：寫命中的偏好（標籤用繁中名稱，類別與機制翻成中文）、
  心得片段印證的感受；命中負面偏好一定要說。
  沒有命中的偏好時，寫心得片段裡最突出的感受。
- reason 不寫條件、信心分數、「幾篇心得提到」，也不寫心得片段沒提到的特性。
- excerpt_ids 填你引用的心得片段 id，每款最多 2 個；該款有心得片段時至少引用 1 段。
  不要在句子裡標 [1]、[2]。
- 追問、離題、查無結果時，recommendations 是空陣列。

## 離題
- 問已推薦桌遊的基本資料：用 search_games 回傳過的資料回答，沒有就說不知道。
- 問規則或玩法：不解釋，請玩家改用規則問答。
- 無關的話題：簡短拒絕，把話題帶回推薦。
- 英文的 BGG 類別與機制名稱，回覆時翻成中文。"""

# ⚠️ 要和 conversation._FinalOutput 一致
ADVISOR_REPLY_SCHEMA = JsonSchema(
    name="advisor_reply",
    schema={
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "game_id": {"type": "integer"},
                        "reason": {"type": "string"},
                        "excerpt_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["game_id", "reason", "excerpt_ids"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["reply", "recommendations"],
        "additionalProperties": False,
    },
)


# --- 評估題組的評審（spec §15.6） ---

# 只判斷有沒有依據，不評文筆，也不評推薦得好不好。評審也會判錯，結果只給立倫勾選時參考、不算分
REASON_CHECK_INSTRUCTIONS = """\
你負責檢查桌遊推薦卡片上的推薦理由有沒有依據。輸入是一張卡片的 JSON：
- reason：推薦理由。
- excerpts：卡片上引用的心得片段原文。
- matches：這款桌遊在查詢結果裡命中的偏好（matched_preferences）與負面偏好（matched_avoids）；\
查詢了兩次時有兩筆。

規則：
1. 把推薦理由拆成一個一個說法，逐一判斷能不能在 excerpts 或 matches 裡找到依據。
2. 心得片段是英文時，意思相同就算有依據。命中的標籤（名稱與定義）、類別、機制，以及難度在範圍內\
（weight_in_range 是 true），都算依據。
3. 找不到依據的說法逐條寫進 unsupported，每條一句繁體中文，說明是哪個說法、為什麼找不到。
4. 只判斷有沒有依據：不評文筆，也不評推薦得好不好。
5. 每個說法都找得到依據時，unsupported 是空陣列。"""

# ⚠️ 要和 schemas.ReasonCheckOutput 一致
REASON_CHECK_SCHEMA = JsonSchema(
    name="advisor_reason_check",
    schema={
        "type": "object",
        "properties": {"unsupported": {"type": "array", "items": {"type": "string"}}},
        "required": ["unsupported"],
        "additionalProperties": False,
    },
)


def reason_check_input(
    reason: str, excerpts: Sequence[str], matches: Sequence[Mapping[str, Any]]
) -> str:
    """評審看的一張卡片：推薦理由、卡片上的心得片段原文、這款命中的偏好與負面偏好。"""
    card = {
        "reason": reason,
        "excerpts": list(excerpts),
        "matches": [dict(match) for match in matches],
    }
    return json.dumps(card, ensure_ascii=False, indent=2)
