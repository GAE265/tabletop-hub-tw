"""AI 產生規則影片段資料的指示與 schema（spec rules-video-script）。

schema 依 Azure strict 規定：所有欄位都列為 required、additionalProperties 為 false、
選填欄位可為 null。
"""

import json
from typing import Any

from app.integrations.llm.types import JsonSchema

INSTRUCTIONS = """你是桌遊規則教學影片的腳本編寫者。
觀看者是來桌遊店、不熟規則的玩家，目標是看完能自己開一局。
請依照輸入的規則書頁面，為指定的一章產生影片的段資料草稿。

內容規則：
1. 只根據輸入的規則書頁面，不加入頁面上沒有的規則，也不憑記憶補充。
   每一段都要在 source_pages 標出依據的頁碼，只能用輸入裡的頁碼。
2. 遊戲用語一律照「用語對照表」：旁白、字幕、畫面文字都用表中的中文詞，
   不使用表中列為不要用的譯法。
3. 遊戲教學內容不可以使用「次」這個字，改用局、輪、回合、階段、天等明確用詞。
4. 旁白是要念出來的口語，比字幕短、順口；字幕是書面的完整句。
   一句旁白對應一句字幕，每句字幕不超過 40 個字。

素材規則（最小清單）：
5. 只列觀眾必須讀到資訊的素材（例如要認得的牌、要知道放在哪裡的盤面），不列裝飾用的配件。
6. priority：少了它觀眾就讀不到必要資訊的用 must（必拍），有它比較好懂的用 optional（選拍）。
7. kind：平面配件（卡牌、板塊、盤面）用 flat_photo（實拍）；
   立體配件（棋子、骰子）用 drawn（繪製）。
8. asset_key 與區域名稱：用語對照表有 key 的，一律使用那個 key；
   沒有的才自己取英文小寫加底線的名稱。
9. regions 只列這一章會用到的區域名稱（例如盤面上的某一區），座標由人量測，不需要提供。
10. 規則寫泛稱時（例如「血刃牌」「花苞牌」這類一整類的牌），畫面上要用一張具體的代表牌：
    從用語對照表中選一張屬於這一類的牌當素材（用它的 key），
    並在 reason 寫明「代表牌：<泛稱>，店員可以替換成同類的其他牌」。
    無法判斷哪張牌屬於這一類時，才用泛稱當素材。

畫面規則（版型 main_with_sidebar）：
11. main：主體，放一張素材（kind=asset）或一排物件
    （kind=items，例如幾張牌，蓋著的牌要給 back_asset_key）。
12. main_title：主體上方的短標題（例如「情況一」），不需要時給 null。
13. sidebar：側欄，放一張素材（例如盤面）、一段文字或條列；不需要時 kind 給 none。
14. highlights：框選（shape=box）或打叉（shape=cross），style 為 gold 或 red；
    target 可以是 main、sidebar、main.<item_key> 或 sidebar@<區域名稱>。
15. labels：短的文字標籤，style 為 plain、gold 或 red，position 為 below、above 或 center。

句內動作（cues），只能用這五種：
- show：讓主體標題、項目、highlight 或 label 出現（它們會先隱藏，直到 show）。
- hide：讓某一項、highlight 或 label 消失，例如移除一張牌。
- flip：把蓋著的牌翻開；target 是 main（全部）或 main.<item_key>。
- shuffle：洗牌；target 是 main。
- move：把一項移進區域；target 是 main.<item_key>，to 是 sidebar@<區域名稱>。
at 是從這一句開始算的秒數，依旁白內容安排先後；動作之間至少間隔 0.4 秒。

分段：一段是畫面狀態連續的一小段，可以有一到三句；
畫面要重置時（例如換下一種情況、換一批牌）就開新的一段。"""

REWRITE_REQUEST = """上一次的輸出有以下問題，請修正後重新輸出完整的結果（不是只輸出修改的部分）：
{errors}

上一次的輸出：
{previous}"""

_STRING = {"type": "string"}
_NULLABLE_STRING = {"type": ["string", "null"]}

_ITEM = {
    "type": "object",
    "properties": {
        "item_key": _STRING,
        "asset_key": _STRING,
        "back_asset_key": _NULLABLE_STRING,
    },
    "required": ["item_key", "asset_key", "back_asset_key"],
    "additionalProperties": False,
}

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "asset_key": _STRING,
                    "kind": {"type": "string", "enum": ["flat_photo", "drawn"]},
                    "priority": {"type": "string", "enum": ["must", "optional"]},
                    "reason": _STRING,
                    "shot": _NULLABLE_STRING,
                    "regions": {"type": "array", "items": _STRING},
                },
                "required": ["asset_key", "kind", "priority", "reason", "shot", "regions"],
                "additionalProperties": False,
            },
        },
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_key": _STRING,
                    "source_pages": {"type": "array", "items": {"type": "integer"}},
                    "main_title": _NULLABLE_STRING,
                    "main": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["asset", "items"]},
                            "asset_key": _NULLABLE_STRING,
                            "items": {"type": "array", "items": _ITEM},
                        },
                        "required": ["kind", "asset_key", "items"],
                        "additionalProperties": False,
                    },
                    "sidebar": {
                        "type": "object",
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": ["none", "asset", "text", "bullets"],
                            },
                            "asset_key": _NULLABLE_STRING,
                            "text": _NULLABLE_STRING,
                            "title": _NULLABLE_STRING,
                            "items": {"type": "array", "items": _STRING},
                        },
                        "required": ["kind", "asset_key", "text", "title", "items"],
                        "additionalProperties": False,
                    },
                    "highlights": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": _STRING,
                                "target": _STRING,
                                "shape": {"type": "string", "enum": ["box", "cross"]},
                                "style": {"type": "string", "enum": ["gold", "red"]},
                            },
                            "required": ["key", "target", "shape", "style"],
                            "additionalProperties": False,
                        },
                    },
                    "labels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": _STRING,
                                "text": _STRING,
                                "target": _STRING,
                                "position": {
                                    "type": "string",
                                    "enum": ["below", "above", "center"],
                                },
                                "style": {"type": "string", "enum": ["plain", "gold", "red"]},
                            },
                            "required": ["key", "text", "target", "position", "style"],
                            "additionalProperties": False,
                        },
                    },
                    "beats": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "narration": _STRING,
                                "subtitle": _STRING,
                                "cues": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "at": {"type": "number"},
                                            "do": {
                                                "type": "string",
                                                "enum": ["show", "hide", "flip", "shuffle", "move"],
                                            },
                                            "target": _STRING,
                                            "to": _NULLABLE_STRING,
                                        },
                                        "required": ["at", "do", "target", "to"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["narration", "subtitle", "cues"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "segment_key",
                    "source_pages",
                    "main_title",
                    "main",
                    "sidebar",
                    "highlights",
                    "labels",
                    "beats",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["assets", "segments"],
    "additionalProperties": False,
}

SCRIPT_SCHEMA = JsonSchema(name="rules_video_script", schema=_SCHEMA)


def rewrite_request(errors: list[str], previous: dict[str, Any]) -> str:
    return REWRITE_REQUEST.format(
        errors="\n".join(f"- {error}" for error in errors),
        previous=json.dumps(previous, ensure_ascii=False, indent=2),
    )
