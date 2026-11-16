## ADDED Requirements

### Requirement: 版面分析介面
系統 SHALL 提供 `OCRProvider` 介面，含 `analyze_layout(image: bytes)` 與 `read_text_angle(image: bytes)`。`analyze_layout` MUST 回傳頁面寬、高、單位、文字角度，以及逐行的文字與 polygon；`read_text_angle` MUST 回傳第一頁的文字角度（度），沒有任何文字時回傳 `None`。任何 domain MUST NOT 直接 import Azure 的 SDK。

#### Scenario: 取得逐行結果
- **WHEN** service 對一張有文字的圖呼叫 `analyze_layout`
- **THEN** 回傳的每一行都有 `text` 與至少 8 個座標的 `polygon`，且有 `width`、`height`、`unit`、`angle`

#### Scenario: 取得文字角度
- **WHEN** 對一張側躺的頁面呼叫 `read_text_angle`
- **THEN** 回傳接近 90 或 -90 的角度

#### Scenario: 沒有文字
- **WHEN** 對沒有任何文字的圖呼叫 `read_text_angle`
- **THEN** 回傳 `None`

### Requirement: 視覺模型介面
系統 SHALL 提供 `VisionProvider` 介面，含 `generate_json(instructions, input, images, schema)`，回傳符合 schema 的 dict。`images` 是一張或多張圖片的 bytes；prompt 與 schema 由呼叫端提供，integration MUST NOT 內建任何 domain 的 prompt。

#### Scenario: 帶一張圖
- **WHEN** 以一張圖與一份 schema 呼叫 `generate_json`
- **THEN** 回傳符合該 schema 的 dict

#### Scenario: 帶多張圖
- **WHEN** 以兩張圖呼叫 `generate_json`
- **THEN** 兩張圖都送給模型，順序與傳入相同

#### Scenario: 圖片格式不認得
- **WHEN** `images` 中有不是 JPEG 或 PNG 的 bytes
- **THEN** 拋出 `OCRError`，不發出任何網路請求

### Requirement: 測試用假實作
系統 SHALL 提供手寫的 `FakeOCRProvider` 與 `FakeVisionProvider`，不發出任何網路請求，並記錄每次呼叫。Fake MUST 依序回傳預先放入的結果；結果用完仍被呼叫時 MUST 拋出明確錯誤，而不是回傳預設值。

#### Scenario: 依序回傳
- **WHEN** `FakeVisionProvider` 放入兩個回覆並呼叫兩次
- **THEN** 依序回傳這兩個回覆

#### Scenario: 結果用完
- **WHEN** 放入一個回覆卻呼叫兩次
- **THEN** 第二次拋出說明「沒有預先放入的回覆」的錯誤

#### Scenario: 沒有放入腳本
- **WHEN** 以 `OCR_PROVIDER=fake` 建立的實作（沒有腳本）被呼叫
- **THEN** 拋出 `OCRUnavailable`，不編造結果

#### Scenario: 記錄呼叫
- **WHEN** 以指定的 `instructions` 與兩張圖呼叫 `FakeVisionProvider`
- **THEN** `calls` 記錄該次的 `instructions`、`input`、每張圖的 MIME 與大小，但不保存圖片內容

### Requirement: 由設定選擇實作
`OCR_PROVIDER` 設定 SHALL 決定使用的實作，合法值為 `fake`、`cloud`。factory MUST 在建立時就驗證設定，不得延到第一次呼叫。

#### Scenario: 設為 fake
- **WHEN** `OCR_PROVIDER=fake`，不需任何其他設定
- **THEN** `get_ocr_provider` 與 `get_vision_provider` 回傳 Fake 實作

#### Scenario: 未知的值
- **WHEN** `OCR_PROVIDER=local`
- **THEN** 拋出說明合法值的 `ValueError`，不退回 fake

#### Scenario: 缺少版面分析設定
- **WHEN** `OCR_PROVIDER=cloud` 且 `OCR_DI_ENDPOINT`、`OCR_DI_API_KEY` 沒填，呼叫 `get_ocr_provider`
- **THEN** 拋出 `OCRNotConfigured`，`missing` 包含 `OCR_DI_ENDPOINT` 與 `OCR_DI_API_KEY`

#### Scenario: 缺少視覺模型設定
- **WHEN** `OCR_PROVIDER=cloud` 且 `LLM_ENDPOINT`、`LLM_API_KEY` 沒填，呼叫 `get_vision_provider`
- **THEN** 拋出 `OCRNotConfigured`，`missing` 包含 `LLM_ENDPOINT` 與 `LLM_API_KEY`

#### Scenario: 視覺模型名稱的退回
- **WHEN** `OCR_VISION_MODEL` 沒填但 `LLM_MODEL` 有填
- **THEN** 視覺實作使用 `LLM_MODEL`

#### Scenario: 兩個模型名稱都沒有
- **WHEN** `OCR_VISION_MODEL` 與 `LLM_MODEL` 都沒填
- **THEN** 拋出 `OCRNotConfigured`，`missing` 說明要填 `OCR_VISION_MODEL` 或 `LLM_MODEL`

### Requirement: 外部服務失敗的例外分類
整合層 SHALL 把 SDK 的失敗轉成 `OCRError` 的子類別，不洩漏廠商型別：逾時、連線失敗、429、5xx（SDK 重試後仍失敗）為 `OCRUnavailable`；模型拒答、被內容過濾擋下、輸出被截斷或不是合法 JSON 為 `OCROutputRejected`；缺設定為 `OCRNotConfigured`。例外 MUST NOT 帶 HTTP 狀態碼。

#### Scenario: 服務逾時
- **WHEN** Azure 在逾時內沒有回應
- **THEN** 拋出 `OCRUnavailable`

#### Scenario: 服務回 5xx
- **WHEN** Azure 重試後仍回 503
- **THEN** 拋出 `OCRUnavailable`

#### Scenario: 輸出不是合法 JSON
- **WHEN** 視覺模型的回覆無法解析成 JSON
- **THEN** 拋出 `OCROutputRejected`

#### Scenario: 金鑰錯誤
- **WHEN** Azure 回 401
- **THEN** 拋出 `OCRError`（不是 `OCRUnavailable`），訊息不含金鑰

### Requirement: 外部服務測試的分類
實際連到 Azure 的測試 MUST 加 `@pytest.mark.external`，預設不執行；缺少需要的金鑰時 MUST 直接失敗並說明缺哪個設定，不得自動跳過。

#### Scenario: 預設不執行
- **WHEN** 執行 `uv run pytest`
- **THEN** 不執行任何 `external` 測試

#### Scenario: 缺金鑰
- **WHEN** 執行 `uv run pytest -m external` 但沒有設定 `OCR_DI_ENDPOINT`
- **THEN** 相關測試失敗，訊息指出缺 `OCR_DI_ENDPOINT`
