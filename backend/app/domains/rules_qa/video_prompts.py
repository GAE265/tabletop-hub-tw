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
1. 只根據標為「本章內容」的規則書頁面，不加入頁面上沒有的規則，也不憑記憶補充。
   每一段都要在 source_pages 標出依據的頁碼，只能用本章內容的頁碼。
   標為「參考資料」的頁面只供查牌名與牌的分類（例如判斷哪張牌屬於哪一類），
   參考資料裡的規則、說明與問答都不可寫成旁白、字幕或畫面文字，也不可列在 source_pages。
2. 遊戲用語一律照「用語對照表」：旁白、字幕、畫面文字都用表中的中文詞，
   不使用表中列為不要用的譯法。
3. 遊戲教學內容不可以使用「次」這個字，改用局、輪、回合、階段、天等明確用詞。
4. 旁白是要念出來的口語，比字幕短、順口；字幕是書面的完整句。
   一句旁白對應一句字幕，每句字幕不超過 40 個字。
   旁白可以口語，但不能省略字幕裡的任何條件（例如「直到一方獲勝或所有輪結束」不能只留在字幕）。

素材規則（最小清單）：
5. 只列觀眾必須讀到資訊的素材（例如要認得的牌、要知道放在哪裡的盤面），不列裝飾用的配件。
6. priority：少了它觀眾就讀不到必要資訊的用 must（必拍），有它比較好懂的用 optional（選拍）。
7. kind：平面配件（卡牌、板塊、盤面）用 flat_photo（實拍）；
   立體配件（棋子、骰子）用 drawn（繪製）。
8. asset_key 與區域名稱：用語對照表有 key 的，一律使用那個 key；
   沒有的才自己取英文小寫加底線的名稱。
9. regions 只列這一章會用到的區域名稱（例如盤面上的某一區），座標由人量測，不需要提供。
10. 規則寫泛稱時（用語對照表標為「泛稱」的一整類牌，例如花苞牌），素材用泛稱的 key，
    reason 寫明「代表牌：<泛稱>，店員可以替換成同類的任一張牌」。
    用語對照表標為「單一種牌」的素材，reason 不可寫「代表牌」。
    每個素材都要寫 shot（要拍什麼、怎麼拍）。

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
cue 的 target 寫法：槽位直接寫名稱（main、main_title、sidebar）；某一項寫 main.<item_key>；
指向 highlight 或 label 時，直接寫它的 key（例如 h1、l_remove），
不加 highlight: 或 label: 這類前綴。
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
                    "shot": _STRING,
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


# --------------------------------------------------------------------------- 整個遊戲一支影片
# add-rules-video-mobile 整本範圍（2026-11-22 永傑決定）：只講開局、走完一輪、獲勝方式三格，
# 每格各一次呼叫（依序產生，後面的格帶入前面已有的素材）。

WHOLE_GAME_SLOT_INSTRUCTIONS = """你是桌遊規則教學影片的腳本編寫者。
觀看者是來桌遊店、不熟規則的玩家，目標是看完能自己開一局、玩完一輪、知道怎麼贏。
整支影片分成三個章節：setup（開局）、round（走完一輪）、win（獲勝方式），每次只產生其中一格。
輸入會寫「這次只產生」哪一格，並附上那一格的規則書原文片段。

內容規則：
1. 只產生這一格的段，每一段的 chapter 都寫這一格的 key；只根據這一格的原文片段，
   不加入片段裡沒有的規則，也不憑記憶補充。
   段數不限，依這一格的規則量決定：片段裡的每一條規則都要講到，不要為了精簡而合併或省略。
   每一段都要在 source_pages 標出依據的頁碼，只能用這一格片段的頁碼。
2. 遊戲用語一律照「用語對照表」：旁白、字幕、畫面文字都用表中的中文詞，
   不使用表中列為不要用的譯法。
3. 遊戲教學內容不可以使用「次」這個字，改用局、輪、回合、階段、天等明確用詞；
   原文寫「次」的也要改寫，例如「一次機會」改說「一個機會」、「第一次」改說「第一輪」或「一開始」。
4. 旁白是要念出來的口語，比字幕短、順口；字幕是書面的完整句。
   一句旁白對應一句字幕，每句字幕不超過 40 個字。
   旁白可以口語，但不能省略字幕裡的任何條件（例如「直到一方獲勝或所有輪結束」不能只留在字幕）。
5. 片段裡的條件、數量與例外都要講到（例如「每位玩家拿 3 張」的 3 張、「立即結束」的立即），
   不要為了精簡而省略。

素材規則：
6. 輸入若列出「已有的素材」（前面幾格產生的），用到同樣的東西時優先沿用那個 asset_key，
   不要為同一樣東西取新的 key；assets 要列出這一格用到的素材（沿用的也列，內容照已有的寫）。
   必要時才新增素材。只列觀眾必須讀到資訊的素材（例如要認得的牌、要知道放在哪裡的盤面），不列裝飾用的配件。
7. priority：少了它觀眾就讀不到必要資訊的用 must（必拍）；只是輔助說明、
   有它比較好懂的用 optional（選拍）。
8. kind 一律是 flat_photo（實拍）：店員用手機拍實物。棋子、骰子等立體配件也是拍照。
9. 每個素材都要寫 label：給店員看的中文名稱（例如「白薔薇」「遊戲盤面」），照用語對照表的中文詞。
10. asset_key：用語對照表有 key 的，一律使用那個 key；沒有的才自己取英文小寫加底線的名稱。
11. regions 列這支影片會用到的區域名稱，座標由人量測，不需要提供。
    區域名稱只能用輸入「可以當區域的名稱」列出的名稱（規則書裡主板上的格子），一字不改；
    不在那份清單的名稱都不可以當區域。「桌上的位置」（例如桌面中央、自己面前）不能當區域：
    要提到它時，高亮直接指整張素材（main 或 sidebar）。
    highlight、label、move 指向區域時，只能用素材 regions 列出的名稱，不可以自己取新的名稱。
    牌類不需要區域（例如牌面、牌背）：要框一張牌時，高亮直接指向那張牌（main 或 main.<item_key>）。
    沒有被任何 highlight、label、move 指到的區域，程式會刪掉。
12. 規則寫泛稱時（用語對照表標為「泛稱」的一整類牌，例如花苞牌），素材用代表牌：用泛稱的 key，
    reason 寫明「代表牌：<泛稱>，店員可以替換成同類的任一張牌」。
    用語對照表標為「單一種牌」的素材，reason 不可寫「代表牌」。
    每個素材都要寫 shot（要拍什麼、怎麼拍）。

畫面規則（版型 main_with_sidebar）：
13. main：主體，放一張素材（kind=asset）或一排物件
    （kind=items，例如幾張牌，蓋著的牌要給 back_asset_key）。
14. main_title：主體上方的短標題（例如「情況一」），不需要時給 null。
15. sidebar：側欄，放一張素材（例如盤面）、一段文字或條列；不需要時 kind 給 none。
16. highlights：框選（shape=box）或打叉（shape=cross），style 為 gold 或 red；
    target 可以是 main、sidebar、main.<item_key> 或 sidebar@<區域名稱>。
17. labels：短的文字標籤，style 為 plain、gold 或 red，position 為 below、above 或 center。

句內動作（cues），只能用這五種：
- show：讓主體標題、項目、highlight 或 label 出現（它們會先隱藏，直到 show）。
- hide：讓某一項、highlight 或 label 消失，例如移除一張牌。
- flip：把蓋著的牌翻開；target 是 main（全部）或 main.<item_key>。
- shuffle：洗牌；target 是 main。
- move：把一項移進區域；target 是 main.<item_key>，to 是 sidebar@<區域名稱>。
cue 的 target 寫法：槽位直接寫名稱（main、main_title、sidebar）；某一項寫 main.<item_key>；
指向 highlight 或 label 時，直接寫它的 key（例如 h1、l_remove），
不加 highlight: 或 label: 這類前綴。
at 是從這一句開始算的秒數，依旁白內容安排先後；動作之間至少間隔 0.4 秒。

分段：一段是畫面狀態連續的一小段，可以有一到三句；
畫面要重置時（例如換下一種情況、換一批牌）就開新的一段。"""


def _whole_game_schema() -> dict[str, Any]:
    schema = json.loads(json.dumps(_SCHEMA))
    asset = schema["properties"]["assets"]["items"]
    asset["properties"]["kind"] = {"type": "string", "enum": ["flat_photo"]}
    asset["properties"]["label"] = _STRING
    asset["required"].append("label")
    segment = schema["properties"]["segments"]["items"]
    segment["properties"]["chapter"] = {"type": "string", "enum": ["setup", "round", "win"]}
    segment["required"].append("chapter")
    return schema


WHOLE_GAME_SCHEMA = JsonSchema(name="rules_video_whole_game", schema=_whole_game_schema())
