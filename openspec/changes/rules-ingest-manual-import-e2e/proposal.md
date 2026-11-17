## Why

`games_manual` 資料表與 OCR／視覺模型整合層都已完成，但 `rules_ingest` 還沒有任何 API，手動測試只能靠後端腳本（`docs/manual-test-rules-ingest.md`），沒有辦法從使用者的角度走完「選規則書圖片 → 入庫 → 在資料庫確認」。這次補上最小的一條 e2e 路徑，讓組員能在瀏覽器完成匯入並讀回驗證。

## What Changes

- 後端 `rules_ingest` 新增逐頁匯入端點 `PUT /api/v1/games/{games_id}/manual-pages/{page}`：收一張圖片（JPEG／PNG），交給 `VisionProvider` 轉錄成 Markdown，以 `(games_id, page)` 覆蓋寫入 `games_manual`。**不做影像轉正、不裁圖、不用版面分析**。
- 後端新增讀回端點 `GET /api/v1/games/{games_id}/manual-pages`：列出某款桌遊已入庫的頁面（`page`、`content`），並回報目前的 `ocr_provider`（`fake`｜`cloud`），供畫面提示。
- 後端建立 `VisionProvider`（依 `OCR_PROVIDER`）並掛到 `app.state`，`OCRNotConfigured`／`OCRUnavailable` 轉成 503，`OCROutputRejected` 與圖片格式不認得有各自的錯誤碼。
- 前端新增 `frontend/lib/domains/rules_ingest/{data,state}` 與參考畫面 `frontend/lib/prototypes/rules_ingest/`，路由 `/proto/rules-ingest`：輸入 `games_id`、選多張圖片與起始頁碼、逐頁匯入並顯示每頁結果、讀回已入庫頁面。
- 新增 `GET /api/v1/games` **不在**本次範圍；`games_id` 由使用者輸入。
- 不含：完整 OCR 流程（轉正、裁圖、三票裁決）、PDF、刪除或編輯單頁、embedding。

## Capabilities

### New Capabilities
- `rules-ingest-manual-import`：規則書單頁圖片匯入（轉錄並覆蓋寫入）與讀回已入庫頁面的 API，含權限與錯誤處理。
- `rules-ingest-import-prototype`：`/proto/rules-ingest` 參考畫面與其 `state/` 的行為。

### Modified Capabilities
<!-- 無：games-manual-storage 與 ocr-providers 的需求不變，只是使用它們 -->

## Impact

- **Domain／主責**：`rules_ingest`（瑋鋐）。
- **契約**：新增兩個 API 端點與其 schema，動到 API 契約，MR 要 @ 立倫（系統整合）。無 migration、無資料表變更。
- **共用區（MR 說明要寫原因並 @ 立倫）**：
  - `backend/app/main.py`：掛 `rules_ingest` router、啟動時建立 `VisionProvider`。
  - `backend/app/core/games/repository.py`：新增 `game_exists(game_id)`，讓 service 在呼叫視覺模型（要錢）之前先確認桌遊存在；`rules_ingest` 不能自己建 `games` 的 model 或查詢（§4.2）。
  - `frontend/lib/app/router.dart`：新增 `/proto/rules-ingest`（屬永傑的共用區）。
  - OCR 例外轉成 HTTP 錯誤寫在 `rules_ingest` 的 service，不改 `core/errors.py`。
- **程式**：`backend/app/domains/rules_ingest/{schemas,service,router}.py`、`repository.py`（新增查詢）；前端 `domains/rules_ingest/`、`prototypes/rules_ingest/`。
- **新增套件**：前端 `file_picker`（理由：Flutter Web 需要選取多個本機圖片檔，Flutter SDK 沒有內建的檔案選取元件）；後端無（`python-multipart` 若尚未安裝則一併加入，用於接收上傳檔案）。
- **測試與環境**：`OCR_PROVIDER=fake` 且沒有腳本時，匯入會回 503；要真正走通 e2e 必須用 `OCR_PROVIDER=cloud`（會呼叫 Azure 產生費用）。後端測試用腳本化的 `FakeVisionProvider`，不連外部服務。
- **開發方式**：依組員決定，先完成功能再補測試；情境仍列在 specs，作為測試與 MR 說明依據。
