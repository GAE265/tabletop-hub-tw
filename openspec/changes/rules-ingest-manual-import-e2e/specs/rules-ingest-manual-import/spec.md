## ADDED Requirements

### Requirement: 逐頁匯入規則書圖片
系統 SHALL 提供 `PUT /api/v1/games/{games_id}/manual-pages/{page}`，以 `multipart/form-data` 的 `file` 欄位接收一張 JPEG 或 PNG 圖片，交給 `VisionProvider` 轉錄成 Markdown，並以 `(games_id, page)` 覆蓋寫入 `games_manual`。成功回 200，內容為 `{"games_id", "page", "content"}`。`page` MUST 大於或等於 1。此端點 MUST NOT 對圖片做轉正、裁圖或版面分析。

#### Scenario: 匯入新的一頁
- **WHEN** 管理員對存在的桌遊送出 `PUT .../manual-pages/1`，附上 PNG 圖片，視覺模型回傳 Markdown「# 標題」
- **THEN** 回 200，內容為 `{"games_id": <id>, "page": 1, "content": "# 標題"}`，`games_manual` 有一列 `(<id>, 1, "# 標題")`

#### Scenario: 同一頁重送會覆蓋
- **WHEN** 第 1 頁已入庫，再對同一頁送出另一張圖片，模型回傳不同的 Markdown
- **THEN** 回 200，`games_manual` 仍只有一列 `(<id>, 1)`，內容是新的 Markdown

#### Scenario: 整頁沒有文字
- **WHEN** 視覺模型回傳空字串的 Markdown
- **THEN** 回 200，`content` 為 `""`，資料表有該列且內容為空字串

#### Scenario: 圖片送給視覺模型的內容
- **WHEN** 匯入一頁
- **THEN** 視覺模型被呼叫一次，只帶這一張圖片，且圖片的位元組與上傳的相同（不轉正、不裁圖）

### Requirement: 匯入的輸入檢查
系統 SHALL 在呼叫視覺模型前檢查輸入：桌遊必須存在、檔案必須是 JPEG 或 PNG 且不為空、大小不得超過 10 MB。檢查不過時 MUST NOT 呼叫視覺模型，也 MUST NOT 寫入資料庫。

#### Scenario: 桌遊不存在
- **WHEN** 對不存在的 `games_id` 送出匯入
- **THEN** 回 404，錯誤碼 `GAME_NOT_FOUND`，視覺模型沒有被呼叫

#### Scenario: 頁碼小於 1
- **WHEN** 送出 `PUT .../manual-pages/0`
- **THEN** 回 422，沒有寫入

#### Scenario: 沒有附檔案
- **WHEN** 送出匯入但沒有 `file` 欄位
- **THEN** 回 422，沒有寫入

#### Scenario: 檔案不是 JPEG 或 PNG
- **WHEN** 附上的檔案開頭不是 JPEG 或 PNG 的檔頭（例如純文字）
- **THEN** 回 400，錯誤碼 `INVALID_IMAGE`，視覺模型沒有被呼叫

#### Scenario: 空檔案
- **WHEN** 附上 0 位元組的檔案
- **THEN** 回 400，錯誤碼 `INVALID_IMAGE`

#### Scenario: 檔案過大
- **WHEN** 附上超過 10 MB 的圖片
- **THEN** 回 400，錯誤碼 `IMAGE_TOO_LARGE`，視覺模型沒有被呼叫

### Requirement: 匯入的權限
匯入與讀回 MUST 只允許 `shop_staff` 與 `admin`。`player` 送出時回 403，且不得呼叫視覺模型或寫入資料庫。

#### Scenario: 玩家不能匯入
- **WHEN** 以 `player` 身分送出匯入
- **THEN** 回 403，錯誤碼 `PERMISSION_DENIED`，視覺模型沒有被呼叫

#### Scenario: 店家人員可以匯入
- **WHEN** 以 `shop_staff` 身分送出合法的匯入
- **THEN** 回 200

#### Scenario: 玩家不能讀回
- **WHEN** 以 `player` 身分送出 `GET .../manual-pages`
- **THEN** 回 403

### Requirement: 外部服務失敗時的回應
視覺模型無法使用時，匯入 MUST 回 503 並使用統一錯誤格式，且 MUST NOT 寫入或改動資料庫。

#### Scenario: 視覺模型暫時無法使用
- **WHEN** `VisionProvider` 拋出 `OCRUnavailable`
- **THEN** 回 503，錯誤碼 `OCR_UNAVAILABLE`，`games_manual` 沒有變動（原有的頁面內容保持不變）

#### Scenario: 雲端設定不完整
- **WHEN** `OCR_PROVIDER=cloud` 但缺少必要設定
- **THEN** 後端啟動時就明確報錯並列出缺少的設定名稱，不是等到第一次匯入才失敗

#### Scenario: 模型拒答或輸出被拒
- **WHEN** `VisionProvider` 拋出 `OCROutputRejected`
- **THEN** 回 503，錯誤碼 `OCR_OUTPUT_REJECTED`，沒有寫入

#### Scenario: 其他 OCR 錯誤
- **WHEN** `VisionProvider` 拋出 `OCRError`（例如金鑰錯誤）
- **THEN** 回 503，錯誤碼 `OCR_FAILED`，錯誤訊息不包含金鑰

### Requirement: 讀回已入庫的頁面
系統 SHALL 提供 `GET /api/v1/games/{games_id}/manual-pages`，回傳該桌遊在 `games_manual` 的所有頁面，依 `page` 由小到大排序，格式為 `{"items": [{"page", "content"}], "total": <數量>, "ocr_provider": "fake" | "cloud"}`。這個端點只讀資料庫，MUST NOT 呼叫 OCR 或視覺模型。

#### Scenario: 列出已入庫的頁面
- **WHEN** 某桌遊已入庫第 3、1 頁，以 `admin` 身分讀回
- **THEN** 回 200，`items` 依序是第 1 頁、第 3 頁，`total` 為 2

#### Scenario: 還沒有任何頁面
- **WHEN** 桌遊存在但沒有任何頁面
- **THEN** 回 200，`items` 為空陣列，`total` 為 0

#### Scenario: 桌遊不存在
- **WHEN** 讀回不存在的 `games_id`
- **THEN** 回 404，錯誤碼 `GAME_NOT_FOUND`

#### Scenario: 回報目前的 OCR 實作
- **WHEN** 後端以 `OCR_PROVIDER=fake` 啟動，讀回任一桌遊
- **THEN** 回應的 `ocr_provider` 為 `fake`
