## Context

- 規則書入庫的管線（board_game v6／v7）要呼叫三種外部能力：Azure DI 的 `prebuilt-read`（文字角度，用於轉正）、`prebuilt-layout`（逐行文字與 polygon，用於交叉驗證）、Azure OpenAI 視覺模型（逐頁轉錄、裁圖裁決）。
- `integrations/llm` 的 `LLMProvider` 只有文字輸入，沒有圖片。`CloudLLMProvider` 用 `openai` SDK 的 Responses API，endpoint 是 Azure v1 端點。
- 規則：domain 不得 import 廠商 SDK；測試替身一律手寫 `Fake`；需金鑰的測試只能放 `integrations/` 並加 `external` 標記；缺金鑰要明確報錯（§4.2、§7.5、§7.6）。
- 後續 change（掃描入庫 API、交叉驗證）會依賴這兩個介面，所以介面要穩，先定在這裡。

## Goals / Non-Goals

**Goals:**
- 兩個介面與 Fake、Cloud 實作，domain 只依賴介面。
- 缺設定時有一個能被 service 轉成 503 的明確例外，並指出缺哪些欄位。
- 外部服務失敗（逾時、連線、429、5xx）有統一的例外，不洩漏 SDK 型別。

**Non-Goals:**
- 影像轉正、裁圖、縮圖（Pillow）；那是影像處理，不是外部服務，放 `rules_ingest`。
- prompt、schema 定義、逐行比對、多數決；屬 `rules_ingest` 的 service。
- 修改 `LLMProvider`、地端模型、embedding。
- API 端點與資料庫。

## Decisions

**1. 視覺呼叫另立 `VisionProvider`，不擴充 `LLMProvider`。**
`LLMProvider` 是 `games_advisor` 在用的穩定介面，且有狀態對話（`respond`）、工具迴圈等不適用於逐頁轉錄的方法。加圖片參數會牽動 `FakeLLMProvider`、`CloudLLMProvider` 與既有測試。`VisionProvider` 只有一個方法 `generate_json(instructions, input, images, schema)`，轉錄與裁決共用。代價是多一個介面與一份 Cloud 實作。

**2. `OCRProvider` 與 `VisionProvider` 分成兩個介面，不合併。**
前者是版面分析服務，後者是模型呼叫，設定、逾時、失敗型態都不同；分開後 service 可以各自注入 Fake，例如測交叉驗證時不需要視覺 Fake。

**3. 介面收 `bytes`，不收路徑或 PIL 物件。**
integration 不該知道檔案系統與 Pillow；API 收到的上傳內容本來就是 bytes。Cloud 實作自己決定 base64 或 octet-stream。圖片格式（JPEG／PNG）由呼叫端保證，integration 傳 MIME 時依檔頭判斷 `image/jpeg`、`image/png`，不認得就拋 `OCRError`。

**4. 回傳值用 dataclass，只保留下游需要的欄位。**
`LayoutResult`：`width`、`height`、`unit`、`angle`、`lines: list[LayoutLine]`；`LayoutLine`：`text`、`polygon: list[float]`（`x1,y1,...`）。不回傳 Azure 的原始 JSON。v7 只用到行與 polygon，段落、表格、圖形等有需要時再加。替代方案：回傳原始 dict，被否決，因為會讓 service 綁死在 Azure 的欄位名稱。

**5. 缺設定拋 `OCRNotConfigured(missing=[...])`，不是通用的 `ValueError`。**
`LLMProvider` 的 factory 用 `ValueError`，但這裡 API 要把它變成 503 並列出缺哪些欄位，所以用專屬型別且帶 `missing` 屬性。`OCR_PROVIDER` 的值不認得仍是 `ValueError`。`OCRNotConfigured` 繼承 `OCRError`，不繼承 `core.errors.AppError`（整合層不帶 HTTP 狀態碼，由 service 轉換，同 `llm/errors.py`）。

**6. factory 回傳的實作在被呼叫時才報缺設定？不，在建立時報。**
`get_ocr_provider(settings)` 與 `get_vision_provider(settings)` 在 `OCR_PROVIDER=cloud` 且缺欄位時立刻拋出，不延到第一次呼叫。這樣 service 在處理請求的最前面就知道，不會做完轉正才失敗。`fake` 不需要任何設定。

**7. 金鑰全部沿用 `LLM_API_KEY`，端點各自獨立設定。**
組員決定：Document Intelligence（`*.cognitiveservices.azure.com`）、Azure OpenAI（`*.openai.azure.com`）是不同網域，端點不互相推導，各有自己的設定：`OCR_DI_ENDPOINT`、`OCR_VISION_ENDPOINT`（留空用 `LLM_ENDPOINT`）。金鑰不另設，兩者都用 `LLM_API_KEY`；視覺模型名稱 `OCR_VISION_MODEL` 留空用 `LLM_MODEL`。逾時預設 120 秒，因為 v6 單頁轉錄約 30 秒，加上上傳大圖，`LLM_TIMEOUT_SECONDS` 的 30 秒會誤判。替代方案：(a) 由 `LLM_ENDPOINT` 的資源名稱推得 Document Intelligence 端點，被否決，因為依賴 Azure 網域命名，換成自訂網域就失效；(b) 另設 `OCR_DI_API_KEY`，被否決，目前同一個資源共用一把金鑰。代價：若日後兩個服務改用不同的金鑰，要再加回專用欄位。

**8. Fake 可腳本化並記錄呼叫。**
`FakeOCRProvider(layouts=..., angle=...)` 與 `FakeVisionProvider(replies=[...])`：依序回傳預先放入的結果，用完拋 `AssertionError`；`calls` 記錄收到的參數（不記錄圖片 bytes 內容，只記長度與 MIME），讓 service 測試能驗證「呼叫了幾次、帶了什麼指令」。不使用 `unittest.mock`（§7.5）。

**9. 使用 `azure-ai-documentintelligence` SDK，不自己打 REST。**
SDK 處理長時間作業的輪詢與重試。SDK 型別只出現在 `azure_di.py`，例外轉成 `OCRUnavailable`／`OCRError`。

**10. Cloud 實作用直連 Azure 的外部服務測試，不用假 transport。**
組員決定。圖片用 Pillow 現場畫英文字（Pillow 只加在 dev 依賴，不使用規則書內容）。直連已抓到一個單元測試看不到的錯誤：SDK 的 `unit` 是 enum，`str()` 會變成 `LengthUnit.PIXEL`。代價：這些測試要金鑰、要花錢（每次約 12 次呼叫），也無法穩定製造 429／5xx／模型拒答／非 JSON 輸出，這幾種轉換只靠程式碼審查，沒有自動測試。

## Risks / Trade-offs

- **[介面先於使用者定案]** 下游還沒寫，`LayoutResult` 欄位可能不夠。 → 先只放 v7 實際用到的欄位；需要時再加欄位（向後相容），不改既有欄位。
- **[視覺模型參數差異]** v6 記錄 `gpt-6-luna` 只收預設 `temperature`，長度欄是 `max_completion_tokens`。 → Cloud 實作不送 `temperature`，沿用 Responses API 的寫法；實測以 `external` 測試確認。
- **[大圖上傳]** 4K 照片約 7 MB，base64 後更大，可能超過請求大小或逾時。 → 縮圖屬呼叫端（`rules_ingest`，v6 預設長邊 2048）；integration 不縮圖，但把逾時預設調到 120 秒。
- **[新增 core/config 欄位]** 動到立倫的共用區。 → 只新增欄位，不改既有欄位；MR @ 立倫。
- **[先實作後補測試]** 偏離 AGENTS.md §7.2。 → 測試仍要補齊，spec 每個情境對應一個測試；MR 註明為組員決定。

## Open Questions

- `OCR_VISION_MODEL` 留空退回 `LLM_MODEL` 時，若 `LLM_MODEL` 不是支援圖片的部署，錯誤要在哪一層提示？目前交給 Azure 回錯誤，轉成 `OCRError`。
