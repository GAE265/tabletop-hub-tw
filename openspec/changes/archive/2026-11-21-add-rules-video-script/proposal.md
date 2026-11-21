# Proposal

## Why

規則影片生產器第 1 階段已經完成：1a、1b，依據是 `add-rules-video-maker`。用手寫的段資料，能輸出含旁白與背景音樂的完整影片；《血與刃》步驟三已驗收合格（2026-11-21）。

但段資料目前是人手寫的。規格的產品流程第 2 步是「AI 讀取規則書，決定哪些規則放進影片，並列出需要的素材（最小清單）」。本 change 做第 1 階段的 **1c**：讓 AI 從規則書頁面產生段資料與最小素材清單，並和手寫版本逐項比對，確認 AI 產生的結果能不能用。1d（API、資料表、前端精靈、發布）往後放。

## What Changes

- **AI 產生段資料**（`domains/rules_qa`）：讀本機的規則書頁面文字與用語對照表，交給 LLM（`LLMProvider.generate_json`），產生一章的段資料草稿。
  - 草稿內容：分段、旁白、字幕、槽位、句內動作、highlight 與 label、出處頁碼，以及最小素材清單（必拍／選拍、平面實拍或繪製、為什麼需要）。
  - 區域只產生名稱，座標要看照片才能量，先留空。
- **檢查與改寫**：產生的內容要通過段資料驗證，並遵守用語規則：不使用「次」（AGENTS.md 10.2）、依用語對照表、出處頁碼只能是輸入的頁面。不符合時，帶著錯誤要求 LLM 改寫一次；仍不符合就失敗，並保留原始輸出供檢查。
- **草稿模式**（`integrations/video`）：段資料可以先沒有照片檔（待拍）、區域可以先沒有座標（待量測）。草稿可以驗證與比對，但要補齊照片與座標才能輸出畫面。
- **逐項比對**（`integrations/video`）：比對 AI 草稿與手寫版本，輸出一份報告。比對項目：分段、旁白與字幕、素材清單、槽位、句內動作、highlight 與 label、區域、出處頁碼，各自標出相同、不同、缺少、多出。
- **本機指令**：`video_commands draft`（產生草稿）、`video_commands compare`（比對兩份段資料）。
- 本機輸入資料（規則書頁面文字、用語對照表）只放 `backend/.local/`，不提交。

**不做**：API、資料表、前端、發布（1d）；用 OCR 或從 `rules_ingest` 讀規則書（1d 再接）；自動判定比對是否合格（由永傑看報告判斷）；量測區域座標。

## Capabilities

### New Capabilities
- `rules-video-script`：AI 產生段資料草稿、草稿模式、逐項比對、本機指令。

### Modified Capabilities
- 無。`rules-video-maker` 的段資料格式不變；草稿模式只放寬「照片檔與區域座標可以晚點補」，正式輸出仍然要求齊全。

## Impact

- **受影響 domain**：`rules_qa`（主責永傑）：新增 `video_script.py`、`video_prompts.py`，`video_commands.py` 新增兩個子指令。
- **共用區**：`integrations/video/`（擁有者永傑）：草稿模式與比對；不改 `integrations/llm/`，只透過介面呼叫。
- **契約**：無（沒有 API、沒有 migration）。
- **新增套件**：無。
- **費用**：產生草稿會呼叫 LLM，一章約一到兩次。測試一律用 `FakeLLMProvider`；實際呼叫的測試加 `external` 標記。
- **資料**：《血與刃》的規則書頁面文字與用語對照表只放本機。測試用自行編寫的假規則書頁面。
- **依賴**：`add-rules-video-maker` 的 #75 要先合併。本 change 用到的 `render`、段資料格式都在那裡。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
