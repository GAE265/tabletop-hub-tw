## 1. 設定與依賴

- [x] 1.1 `backend/pyproject.toml` 新增 `azure-ai-documentintelligence`，更新 `uv.lock`
- [x] 1.2 `backend/app/core/config.py` 新增 `ocr_provider`（預設 `fake`）、`ocr_di_endpoint`、`ocr_di_api_key`、`ocr_vision_model`、`ocr_vision_timeout_seconds`（預設 120）
- [x] 1.3 `.env.example` 同步新增 `OCR_*` 欄位與說明（只寫欄位名與說明，不寫值）

## 2. 介面與假實作

- [x] 2.1 `backend/app/integrations/ocr/errors.py`：`OCRError`、`OCRNotConfigured(missing)`、`OCRUnavailable`、`OCROutputRejected`
- [x] 2.2 `types.py`：`LayoutLine`、`LayoutResult`；`base.py`：`OCRProvider`、`VisionProvider`
- [x] 2.3 圖片 MIME 判斷（JPEG／PNG 檔頭），不認得拋 `OCRError`
- [x] 2.4 `fake.py`：`FakeOCRProvider`、`FakeVisionProvider`（依序回傳、用完拋錯、記錄呼叫但不存圖片內容）

## 3. Cloud 實作

- [x] 3.1 `azure_di.py`：`AzureDocumentIntelligenceProvider`（`prebuilt-layout`、`prebuilt-read`），SDK 例外轉成 `OCR*`
- [x] 3.2 `vision.py`：`CloudVisionProvider`（`openai` Responses API，圖片以 data URL 傳送，`json_schema` 輸出），例外轉成 `OCR*`
- [x] 3.3 `factory.py`：`get_ocr_provider`、`get_vision_provider`，缺設定拋 `OCRNotConfigured`，未知值拋 `ValueError`
- [x] 3.4 `integrations/ocr/__init__.py` 匯出對外名稱

## 4. 測試（先實作後補，依組員決定）

- [x] 4.1 `backend/tests/integrations/`：Fake 的行為（依序、用完拋錯、記錄呼叫）、MIME 判斷、factory 各情境
- [x] 4.2 Cloud 實作改直連 Azure 測試（組員決定，不用假 transport，見 design 決策 10）：逐行結果與角度、側躺頁、無文字回 `None`、錯誤金鑰、連不上的主機、圖片順序、圖片格式；429／5xx／拒答／非 JSON 輸出無法穩定製造，沒有自動測試
- [x] 4.3 `@pytest.mark.external` 測試（`test_ocr_external.py`，12 項）；缺金鑰時 `ocr_external_settings` 直接失敗並指出缺哪個設定
- [x] 4.4 每個 spec scenario 都對應到一個測試

## 5. 發 MR 前

- [x] 5.1 在 `backend/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`（覆蓋 `DATABASE_URL` 為不帶 `options` 的版本）
- [x] 5.2 本機跑 `uv run pytest -m external`，記錄通過與失敗數（有改 `integrations/` 的 MR 必須附上）
- [ ] 5.3 產出 MR 說明：情境表格、change 名稱 `ocr-integrations`、@ 立倫（動到 `core/config.py`）、註明新增套件理由與先實作後補測試
