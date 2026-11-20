# Design

## Context

- 規格：根目錄 `影片生產器規格.md` 的產品流程第 2 步：AI 讀規則書，決定放哪些規則，並列出最小素材清單。
- 第 1 階段 1a、1b 已完成（`add-rules-video-maker`）。手寫的《血與刃》步驟三 `backend/.local/rules_video/video.json` 已輸出影片並驗收合格。
- 永傑的決定（2026-11-21）：
  - 1c 先做，1d 往後放。
  - 驗收方式：以《血與刃》步驟三的規則書頁面（英文版 RC1 PDF 第 5 頁）當輸入，把 AI 產生的段資料和手寫版本逐項比對。
  - 規則書來源用**本機文字檔**；遊戲用語由**用語對照表**決定；AI 要產生到**句內動作與區域名稱**。
- 規則書是英文，旁白與字幕是中文；用語要和手寫版一致，才能逐項比對。

## Goals / Non-Goals

**Goals**
- 一個指令，從規則書頁面文字產生一章的段資料草稿，格式和手寫的 `video.json` 相同。
- 草稿只根據輸入的頁面，用語依對照表，遵守 AGENTS.md 10.2（不用「次」）。
- 一份逐項比對報告，讓永傑判斷 AI 的結果離手寫版本多遠。

**Non-Goals**：API、資料表、前端、發布（1d）；OCR 與 `rules_ingest`（1d）；自動判定合格；量測區域座標；其他版型（第 3 階段）。

## Decisions

**D1 程式放在哪裡。**

| 位置 | 內容 | 理由 |
|---|---|---|
| `domains/rules_qa/video_script.py` | 組 LLM 輸入、呼叫 `generate_json`、檢查與改寫、轉成段資料 | 用到 LLM 與遊戲用語規則，屬於專案流程（決定 A3） |
| `domains/rules_qa/video_prompts.py` | 給 LLM 的指示與改寫要求 | 沿用 `rules_qa/prompts.py` 的做法 |
| `integrations/video/model.py` | 草稿模式 | 段資料格式屬於版型引擎，不知道 LLM |
| `integrations/video/compare.py` | 逐項比對兩份段資料，輸出報告 | 比對只看段資料結構，跟遊戲與 LLM 無關 |
| `domains/rules_qa/video_commands.py` | `draft`、`compare` 子指令 | 沿用既有本機指令 |

**D2 本機輸入資料**（`backend/.local/rules_video/`，不提交）。

```
rulebook/en-005.txt     規則書第 5 頁的文字（永傑從 PDF 複製）；檔名 <語言>-<頁碼>.txt
terms.json              用語對照表
```

`terms.json`：

```jsonc
[
  { "en": "White Rose", "zh": "白薔薇", "key": "white_rose" },
  { "en": "Death zone", "zh": "死亡區", "key": "death_zone" },
  { "en": "Bud",        "zh": "花苞", "avoid": ["蓓蕾"] }   // 沒有 key：只規定用詞
]
```

- `zh`：旁白、字幕、畫面文字都要用這個詞。
- `key`（選填）：這個東西在段資料裡的識別名稱。素材的 `asset_key`、區域名稱都用它，這樣 AI 版和手寫版才能用同一個 key 對上。
- `avoid`（選填）：不要用的譯法，出現就算檢查不通過（D5）。

**D3 指令。**

```
uv run python -m app.domains.rules_qa.video_commands draft <資料夾> \
    --pages rulebook/en-005.txt --chapter-number 11 --chapter-title 步驟三
uv run python -m app.domains.rules_qa.video_commands compare <AI 草稿> <手寫 video.json>
```

- `draft` 輸出到 `<資料夾>/draft/video.json`，**不覆寫**手寫的 `video.json`。
- `draft --assets-from <video.json>`（選填）：從手寫版借用同一個 `asset_key` 的照片檔與區域座標，讓 AI 草稿也能直接跑 `stills`、`render`，並排看效果。
- `compare` 輸出 `<AI 草稿的資料夾>/compare.md`。

**D4 LLM 輸入與輸出。**
- 輸入：章節編號與名稱、每一頁的文字（標頁碼）、用語對照表、段資料格式說明（版型、槽位、五種動作、草稿模式）。
- 呼叫 `LLMProvider.generate_json(instructions, input, schema)`。schema 描述：
  - 段（含槽位、highlight、label、句、cue）
  - 素材（`asset_key`、`kind`、`priority`、`reason`、`shot`、要用到的區域名稱）
- 指示重點：
  - 只根據輸入的頁面，不加入頁面上沒有的規則。
  - 只列觀眾必須讀到資訊的素材，並分必拍、選拍。
  - 平面配件（卡牌、板塊、盤面）用 `flat_photo`，立體配件（棋子、骰子）用 `drawn`。
  - 用語照對照表。
  - 不使用「次」。
  - 旁白口語、字幕書面完整句，一句旁白對一句字幕。
- 輸出轉成段資料：照片檔與區域座標留空（草稿模式），句的 key 用「章節編號-序號」（例如 `11-0`）。

**D5 檢查與改寫一次。** 產生後依序檢查：
1. 草稿模式的段資料驗證（`parse_video(draft=True)`）。
2. 旁白、字幕、畫面文字沒有「次」。
3. 用語：對照表列的 `avoid`（不要用的譯法）不得出現在旁白、字幕與畫面文字（槽位文字、label）。對照表沒列的譯法無法自動判斷，會在比對報告中顯示出來。
4. `source_pages` 只能是輸入的頁碼。

有任何一項不通過，就把錯誤清單交給 LLM 改寫一次。仍不通過時失敗，並把兩次原始輸出存成 `draft/rejected-1.json`、`draft/rejected-2.json`，方便檢查。做法與 `rules_qa` 規則問答一致：改寫一次，仍不行就失敗。

**D6 草稿模式**（`integrations/video`）。`load_video(folder, draft=True)` 與 `parse_video(raw, base_dir, draft=True)` 放寬三項：
- `flat_photo` 素材的 `file` 可以是 `null`（待拍）。
- 區域座標可以是 `null`（待量測）。
- 可以列 `drawn` 素材（本版還畫不出來，但素材清單要能列）。

其他驗證照舊。`stills`、`render` 一律用正式模式，遇到待拍、待量測或 `drawn` 時，載入就失敗，並列出缺什麼。

**D7 逐項比對**（`integrations/video/compare.py`）。輸入兩份段資料（草稿模式載入），輸出 Markdown 報告：

| 項目 | 怎麼對齊 | 列出 |
|---|---|---|
| 分段 | 依順序 | 段數、每段句數 |
| 旁白、字幕 | 依句的順序 | 兩邊並列，加上相似度（0–1，`difflib`） |
| 素材清單 | 依 `asset_key` | 相同、只有 AI 有、只有手寫有；`kind`、`priority` 不同時標出 |
| 槽位 | 依段的順序 | 每個槽位用的素材或文字 |
| 句內動作 | 依句的順序；target 換算成素材（例如 `main.c2` → `ghost`），不受項目命名影響 | 動作序列逐一對齊；缺少、多出、`at` 相差幾秒 |
| highlight、label | 依段 | 指向的對象與文字 |
| 區域 | 依名稱 | 用到的區域名稱 |
| 出處頁碼 | 依段 | 兩邊的頁碼 |

報告最上面是摘要，列出各項目「相同／不同／缺少／多出」的數量。不判定合格與否，由永傑判斷。

**D8 測試。**
- 單元測試（不連 LLM）：用 `FakeLLMProvider` 照腳本回傳 JSON。涵蓋：正常產生、改寫一次後通過、改寫後仍不通過、LLM 無法使用、各項檢查、草稿模式、比對、指令。
- 外部服務測試（`external`）：用自行編寫的假規則書頁面，實際呼叫 LLM，確認輸出能通過檢查。需要 `.env` 的 `LLM_*`。
- 《血與刃》的實際產生與比對是本機的驗收步驟（tasks），不寫成自動測試，因為不能提交規則書內容。

**D9 一個 MR。** 草稿模式、比對、AI 產生、指令都屬於「AI 產生段資料並比對」這一件事，用一個 MR，分成 docs、test、feat 三個 commit。分支 `feature/rules_qa-video-script`。2026-11-21 決定從 #75 的分支往下接，#75 合併後再把 dev 合併進來。

## Risks / Trade-offs

- **[AI 加入頁面沒有的規則]** → 指示只根據輸入；每段必須標出處頁碼；比對報告並列手寫版，由永傑判斷規則是否正確。
- **[英翻中的用語不一致]** → 用語對照表加上檢查。對照表沒涵蓋的詞仍可能譯法不同，會在比對報告中顯示出來。
- **[動作時間不準]** AI 不知道旁白實際多長。→ 時間軸會依動作延長句長（第 1 階段已有），不會被切掉；`at` 的差異列在報告中。
- **[區域座標要人量]** → 草稿模式留空；`--assets-from` 讓比對時可以借用手寫版的座標。
- **[結構化輸出的 schema 限制]** 段資料有巢狀、選填欄位，有些 LLM 的嚴格 schema 不支援選填。→ schema 用「必填＋可為 null」的寫法，轉換時再去掉 null。
- **[費用]** → 一章只呼叫一到兩次；測試用 fake。

## Open Questions

無。三項決定（規則書來源、用語、產生範圍）已在 2026-11-21 確認。
