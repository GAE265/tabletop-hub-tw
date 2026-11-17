## Context

- `games_manual`（`games-manual-table`）與 `integrations/ocr`（`ocr-integrations`）都已完成，但 `rules_ingest` 只有 model 與 `ManualPageRepository.upsert_page`，沒有 service、router、schema。
- `docs/manual-test-rules-ingest.md` 的案例都是後端腳本。這次要補一條能從瀏覽器走完的最小路徑，並能讀回資料庫內容驗證。
- 前端目前只有 `health` domain 與參考畫面；沒有檔案上傳、`multipart` 或選檔案的經驗。
- 使用者決定：最小版（不轉正、不裁圖）、要有讀回、先實作後補測試。
- `OCR_PROVIDER` 預設 `fake`，而 `FakeVisionProvider` 沒有腳本時會拋 `OCRUnavailable`。所以預設設定下匯入一定回 503，e2e 必須用 `cloud`。

## Goals / Non-Goals

**Goals:**
- 從瀏覽器選多張圖片，逐頁匯入，並在同一個畫面讀回資料庫內容。
- 端點與錯誤格式符合 AGENTS.md §4.3；權限在 service 檢查（§4.5）。

**Non-Goals:**
- 影像轉正、裁圖、版面分析、三票裁決、PDF、批次一次上傳多頁。
- 桌遊列表端點、刪除或編輯單頁、embedding。
- 正式頁面（`pages/`）與主題。

## Decisions

**1. 一個請求處理一頁：`PUT /api/v1/games/{games_id}/manual-pages/{page}`。**
沿用 `games-manual-table` 預告的路徑，也符合 §4.3「PUT 整筆取代」：同一頁重送就是取代，冪等。多張圖片由前端逐頁呼叫，這樣單頁失敗不影響其他頁，也不會有一個請求跑好幾分鐘的逾時問題（單頁約 30 秒）。替代方案：一次上傳整批的 `POST`，被否決，因為部分成功的回應格式與逾時都難處理。

**2. 上傳用 `multipart/form-data` 的 `file` 欄位，不用 base64 JSON。**
圖片是二進位，multipart 是標準做法；FastAPI 用 `UploadFile`。需要 `python-multipart`（若尚未安裝，列為新增套件）。service 只收 `bytes`，不 import FastAPI（§4.2）；router 讀取內容後傳入。

**3. 先檢查、再呼叫模型、最後才寫入。**
順序：權限 → 圖片檢查（空檔、JPEG／PNG 檔頭、10 MB）→ 桌遊存在 → 視覺模型 → upsert。模型呼叫要錢，所以能先擋的都先擋。桌遊存在檢查用共用表的 `game_exists`（新增在 `core/games/repository.py`）；upsert 的外鍵仍是最後防線，並發刪除時 `GameNotFoundError` 一樣轉成 404。

**4. 轉錄的 prompt 與 schema 放在 `rules_ingest` 的 service。**
符合 ocr-providers 的分工（integration 不內建 domain 內容）。schema 是 `{"markdown": string}`，`additionalProperties: false`。prompt 要求「逐字轉錄成 Markdown、保留標題與清單結構、不要翻譯或補充、沒有文字就回空字串」。教學用語的「次」規則只限遊戲教學內容，這裡是原文轉錄，不改寫。

**5. 錯誤對照。**

| 例外／情況 | 狀態碼 | 錯誤碼 |
|---|---|---|
| 角色不是 `shop_staff`／`admin` | 403 | `PERMISSION_DENIED`（core 既有） |
| 桌遊不存在 | 404 | `GAME_NOT_FOUND` |
| 檔案空或不是 JPEG／PNG | 400 | `INVALID_IMAGE` |
| 檔案超過 10 MB | 400 | `IMAGE_TOO_LARGE` |
| `page < 1`、缺 `file` | 422 | `VALIDATION_ERROR`（core 既有） |
| `OCRUnavailable`（逾時、連線失敗、fake 沒腳本） | 503 | `OCR_UNAVAILABLE` |
| `OCROutputRejected` | 503 | `OCR_OUTPUT_REJECTED` |
| 其他 `OCRError` | 503 | `OCR_FAILED` |

§4.3 沒有 413 與 502，所以超大檔案用 400；模型拒答與其他外部錯誤一律 503，重試可能成功。錯誤訊息不得帶金鑰（integration 已保證）。

**6. 權限只開給 `shop_staff` 與 `admin`，讀回也一樣。**
AGENTS.md §4.5 規定店家人員管理規則書，玩家不行。規則書全文不應被一般玩家整份讀出，所以讀回也限制角色。本次不檢查「店家是否擁有這款桌遊」：`games` 沒有店家欄位，沒有可比對的資料。

**7. 讀回回應多帶 `ocr_provider`。**
畫面需要在匯入前就告訴使用者目前是 `fake` 還是 `cloud`，避免誤以為 fake 的內容是真辨識。放在讀回回應頂層，而不是另開 `/config` 之類的端點，少一個契約。代價是列表回應多一個不屬於列表的欄位；§4.3 的分頁格式 `{"items","total"}` 保持，額外欄位不衝突。本端點不分頁：一本規則書最多數十頁，且畫面需要一次看到全部來驗證。

**8. VisionProvider 在 `create_app` 建立並放 `app.state.vision`。**
和 `app.state.llm` 同一個做法：`OCR_PROVIDER=cloud` 缺設定時啟動就報錯。測試用依賴覆寫換成腳本化的 `FakeVisionProvider`。`OCR_PROVIDER` 設成未知值時，factory 的 `ValueError` 也在啟動時出現。

**9. 前端：`data/` + `state/` + `prototypes/`，頁碼由前端指定。**
- `data/`：`ManualPagesRepository`（介面 + Dio 實作）。上傳用 `FormData` 與 `MultipartFile.fromBytes`；逾時要拉長到比後端 120 秒再長一些。
- `state/`：一個 Notifier 管「匯入中的進度與每頁結果」，另一個管「讀回列表」。逐頁**依序**送出，不並行，避免同時打爆視覺模型。
- 頁碼 = 起始頁碼 + 選取順序。檔案順序由檔名排序後使用（選檔器回傳順序不保證），畫面上顯示最後採用的順序。
- 選檔案用 `file_picker`（Flutter Web 沒有內建元件）；用它的 `withData: true` 取得位元組。選檔案這一步在 `core/platform/` 後面包一個 `ImagePicker` 介面，之後轉 App 才不必大改，state 測試用 fake 實作（§5.3、§7.5）。
- 身分：沿用既有的開發身分切換器；預設是 `player` 會得到 403，畫面錯誤訊息提示切換成 `shop_staff` 或 `admin`。

## Risks / Trade-offs

- **[fake 無法走通匯入]** 預設設定下匯入回 503。 → 手動測試文件寫明 e2e 要用 `OCR_PROVIDER=cloud`；畫面顯示 `ocr_provider`。不為了方便而讓 fake 回編造內容（與 ocr-providers 的設計一致）。
- **[雲端費用]** 每頁一次視覺模型呼叫。 → 畫面在 cloud 模式提示「會產生費用」；單檔 10 MB 上限。
- **[單頁逾時]** 大圖轉錄可能接近 120 秒。 → 前端逐頁處理，失敗的頁可以只重送那一頁（同頁覆蓋是冪等的）。
- **[轉錄品質]** 不轉正、不裁圖，側躺或有雜訊的頁面可能轉錄不佳。 → 本次只驗證管線通；品質由後續完整流程處理。
- **[先實作後補測試]** 偏離 AGENTS.md §7.2。 → specs 的每個 scenario 之後要有對應測試，MR 說明註明這是使用者的決定。
- **[新增 `game_exists` 在共用區]** 屬立倫。 → MR 說明寫原因並 @ 立倫。
- **[新增前端套件 `file_picker`]** → MR 說明寫理由。

## Migration Plan

無資料庫變更。部署時 `.env` 若要真實匯入，需設定 `OCR_PROVIDER=cloud` 與案例 4 所列欄位（`.env.example` 已有）。回滾：移除 router 掛載即可，資料表內容保留。

## Open Questions

- 是否要在後續 change 加 `GET /api/v1/games`，讓畫面能用下拉選單選桌遊？目前由使用者輸入 `games_id`。
- 讀回要不要之後支援分頁？目前不分頁。
