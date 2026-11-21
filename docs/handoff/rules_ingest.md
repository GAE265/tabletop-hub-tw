# 交接說明：rules_ingest

> 功能負責人填寫，交給永傑做正式頁面。格式依 AGENTS.md 5.4。

- 功能負責人：瑋鋐
- 後端 domain：`backend/app/domains/rules_ingest/`
- 前端 `state/` 位置：`frontend/lib/domains/rules_ingest/state/`
- 參考畫面路由：`/proto/rules-ingest`（啟動需帶 `--dart-define=SHOW_PROTOTYPES=true`）

## 1. 頁面清單

| 頁面 | 路由 | 用途 |
|---|---|---|
| 規則書圖片匯入 | `/proto/rules-ingest` | 輸入桌遊編號、選多張圖片與起始頁碼、逐頁匯入、讀回已入庫頁面 |

## 2. 各頁面的按鈕與欄位

### 頁面：規則書圖片匯入

| 元件 | 類型 | 按下／輸入後做什麼 | `state/` 方法 | 後端 API |
|---|---|---|---|---|
| 桌遊編號輸入框 | 輸入欄位（數字鍵盤） | 輸入 `games_id`，非正整數時顯示提示、停用匯入與讀回按鈕 | `manualImportProvider.notifier.setGamesInput` | — |
| 起始頁碼輸入框 | 輸入欄位（數字鍵盤） | 輸入起始頁碼（預設 1），小於 1 時顯示提示、停用匯入按鈕 | `manualImportProvider.notifier.setStartPageInput` | — |
| 選擇 JPEG／PNG 圖片 | 按鈕 | 開啟檔案選取器，選取多張圖片，畫面顯示檔名排序後的順序與對應頁碼 | `manualImportProvider.notifier.pickImages`（透過 `ImagePicker` 介面） | — |
| 匯入 | 按鈕 | 依序逐頁呼叫匯入 API，頁碼從起始頁碼起遞增；後端在**同一個請求內**先寫入辨識文字、接著自動重建這一頁的問答索引段落，回應帶回該頁段落數 `chunk_count`，前端不必再打別的 API；顯示進度（目前張數／總張數）；單頁失敗不中止後續頁面；全部結束後自動讀回 | `manualImportProvider.notifier.importPages` | `PUT /api/v1/games/{games_id}/manual-pages/{page}` |
| 讀回已入庫頁面 | 按鈕 | 讀回該桌遊的所有已入庫頁面，顯示頁碼、Markdown 內容與 `ocr_provider` | `manualPagesProvider.notifier.load` | `GET /api/v1/games/{games_id}/manual-pages` |

## 3. 狀態顯示

| 狀態 | 要顯示什麼 |
|---|---|
| 載入中（讀回） | `CircularProgressIndicator` |
| 載入中（匯入） | `LinearProgressIndicator` + 「匯入中：N／M」文字 |
| 選圖中 | `CircularProgressIndicator` |
| 沒有資料（讀回 items 為空） | 「這款桌遊還沒有規則書頁面」 |
| 讀回成功 | 「已讀回桌遊編號：N」、OCR 實作提示（`fake` 時顯示「OCR：fake（內容不是真實辨識結果）」；`cloud` 時顯示「OCR：cloud」與「使用雲端 OCR 匯入會產生費用」）、逐頁列出頁碼與 Markdown（空字串顯示「（整頁沒文字）」） |
| 匯入結果 | 每筆顯示「第 N 頁：檔名」與結果；成功顯示「成功（索引 N 段）」（`PageImportResult.chunkCount`，空白頁為 0），失敗顯示錯誤訊息 |
| 錯誤（403） | 後端錯誤訊息 + 「請切換成 shop_staff 或 admin」 |
| 錯誤（404） | 後端錯誤訊息（`GAME_NOT_FOUND`） |
| 錯誤（503） | 後端錯誤訊息（`OCR_UNAVAILABLE`／`OCR_FAILED`／`RULES_QA_INDEX_FAILED`）。`RULES_QA_INDEX_FAILED` 代表辨識文字已入庫、只有問答索引失敗，提示重新匯入這一頁即可 |
| 錯誤（其他） | 後端錯誤訊息或「操作失敗，請稍後重試」 |
| 輸入驗證錯誤 | 「桌遊編號必須是正整數」或「起始頁碼必須大於或等於 1」 |
| 未讀回前 | 「請先讀回，確認目前 OCR 實作；cloud 匯入會產生費用」 |
| 匯入／選圖進行中 | 所有輸入欄位與按鈕停用，防止重複操作 |

## 4. 參考畫面截圖

<!-- 放在 docs/handoff/images/rules_ingest/，並在此引用 -->

## 5. 給永傑的備註

- `state/` 有兩個 provider：`manualImportProvider`（匯入流程）與 `manualPagesProvider`（讀回列表）。參考畫面同時使用兩者，正式頁面也應如此。
- 匯入按鈕啟用條件：`canImport`（桌遊編號與起始頁碼都有效 + 已選圖片 + 不在匯入或選圖中）且讀回不在載入中。
- 讀回按鈕啟用條件：不在匯入或選圖中、讀回不在載入中、桌遊編號有效。
- 匯入完成後會自動呼叫讀回，不需要使用者手動再按讀回按鈕，但畫面仍保留手動讀回按鈕。
- 匯入每一頁時，後端已同步重建該頁的問答索引（寫入 `rules_qa_chunks`），前端**不要**再另外呼叫任何建立索引的 API。段落數只出現在匯入回應（`ManualPage.chunkCount`），讀回列表不帶這個欄位，因此讀回的資料會是 0，僅在匯入結果顯示。
- 索引失敗時後端回 503 `RULES_QA_INDEX_FAILED`，該頁文字仍然入庫，重新匯入同一頁即可重建索引；錯誤處理走既有 `operationError`，不需額外判斷錯誤碼。
- `state/` 不夠用時，回報功能負責人修改，不要在頁面直接呼叫 API。
- 正式頁面完成後，刪除對應的參考畫面路由（`app/router.dart` 中的 `/proto/rules-ingest`）。
