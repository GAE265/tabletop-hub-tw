## Why

規則書圖片入庫（`rules_ingest`，#5）要靠兩種外部服務：Azure Document Intelligence 取得逐行文字與位置，以及 Azure OpenAI 視覺模型逐頁轉錄與裁圖裁決。依 AGENTS.md §4.2，domain 不能直接 import 廠商 SDK，且測試必須用假實作。目前 `integrations/` 只有 `llm/` 與 `embedding/`，沒有 OCR，也沒有帶圖片的模型呼叫，後續的掃描入庫 API 沒有可依賴的介面。

## What Changes

- 新增 `backend/app/integrations/ocr/`，提供兩個介面：
  - `OCRProvider`：`analyze_layout(image)` 回傳 `prebuilt-layout` 的逐行結果（文字、polygon、頁面寬高與單位、文字角度）；`read_text_angle(image)` 回傳 `prebuilt-read` 的文字角度。
  - `VisionProvider`：`generate_json(instructions, input, images, schema)` 以視覺模型回傳符合 schema 的 JSON，供逐頁轉錄與裁圖三票裁決共用。prompt 與商業規則留在 `rules_ingest` 的 service，不放進 integration。
- 各介面有手寫的 `Fake`（可腳本化回應、記錄呼叫）與 `Cloud` 實作（Azure Document Intelligence、Azure OpenAI）。
- factory 依 `OCR_PROVIDER`（`fake`｜`cloud`）選擇實作；`cloud` 缺設定時拋出 `OCRNotConfigured`，並列出缺哪些欄位（之後 API 轉成 503）。
- 例外：`OCRError`、`OCRNotConfigured`、`OCRUnavailable`、`OCROutputRejected`。
- 新增設定：`OCR_PROVIDER`、`OCR_DI_ENDPOINT`（Document Intelligence，cognitiveservices）、`OCR_VISION_ENDPOINT`（選填，留空用 `LLM_ENDPOINT`）、`OCR_VISION_MODEL`（選填，留空用 `LLM_MODEL`）、`OCR_VISION_TIMEOUT_SECONDS`（預設 120）。**金鑰全部沿用 `LLM_API_KEY`，端點各自獨立設定。** 同步更新 `.env.example`。
- 新增套件 `azure-ai-documentintelligence`。
- 外部服務測試加 `@pytest.mark.external`，缺金鑰時直接失敗並說明缺哪個設定（§7.6）。
- 不含：影像轉正與裁圖（Pillow，屬 `rules_ingest`）、API 端點、資料庫。

## Capabilities

### New Capabilities
- `ocr-providers`: `OCRProvider` 與 `VisionProvider` 兩個介面、Fake 與 Cloud 實作、factory 與設定、例外分類。

### Modified Capabilities
<!-- 無：llm-provider 的需求不變，視覺呼叫另立介面而不改 LLMProvider -->

## Impact

- **Domain／主責**：`integrations/ocr/` 由瑋鋐擁有（AGENTS.md 第 3 節）；`integrations` 不得知道任何 domain 的存在。
- **共用區**：修改 `backend/app/core/config.py` 屬立倫的共用區（第 2 節規則 3），MR 說明要寫出原因（新增 OCR 設定欄位）並 @ 立倫。
- **契約**：無 API、資料表、MQTT 變更；無 migration。
- **程式**：`backend/app/integrations/ocr/{base,types,errors,fake,factory,azure_di,vision}.py`、`core/config.py`、`.env.example`、`pyproject.toml`、`uv.lock`。
- **新增套件**：`azure-ai-documentintelligence`（理由：呼叫 Azure Document Intelligence 取得逐行文字與位置；OpenAI 視覺呼叫沿用既有 `openai`）；dev 依賴 `pillow`（理由：外部服務測試現場畫測試圖片，不使用規則書內容）。
- **參考**：board_game 專案的 v6（`extract_gpt`、`extract_azure_di`、`orient`）與 v7。
- **開發方式**：依組員決定，先完成功能再補測試。
