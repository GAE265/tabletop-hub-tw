## 說明

新增規則書逐頁圖片匯入與讀回 API，以及 `/proto/rules-ingest` 參考畫面。圖片原樣交給視覺模型轉錄成 Markdown，同頁重送覆蓋；前端依檔名排序逐頁送出，單頁失敗不中止，結束自動讀回。

Change：`rules-ingest-manual-import-e2e`。依使用者決定先實作後補測試。

共用修改：`core/games/repository.py` 加入桌遊存在查詢，避免不存在的桌遊呼叫付費模型；`app/main.py` 建立 provider 並掛載 API，請 @ 立倫審核。前端 `core/platform/` 封裝選檔與 `app/router.dart` 掛開發路由，請 @ 永傑審核。

## 測試案例表格

測試檔案簡稱：S＝`backend/tests/rules_ingest/test_manual_pages_service.py`；A＝`backend/tests/rules_ingest/test_manual_pages_api.py`；F＝`frontend/test/domains/rules_ingest/manual_pages_state_test.dart`；W＝同目錄 `manual_pages_widget_test.dart`；R＝同目錄 `manual_pages_route_test.dart`；D＝同目錄 `manual_pages_repository_test.dart`。

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 匯入新頁（S `test_import_transcribes_original_image_once`、A `test_upload_overwrite_and_readback`） | 管理員上傳 PNG／JPEG | 200，轉錄內容存入資料庫 |
| 同頁重送（S `test_overwrite_including_empty_page`、A `test_upload_overwrite_and_readback`） | 重送第 1 頁 | 覆蓋內容且只有一列 |
| 整頁沒文字（同上） | 模型回空 Markdown | 儲存空字串 |
| 圖片原樣送模型（S `test_import_transcribes_original_image_once`） | 匯入一頁 | 只呼叫一次，圖片位元組與 strict schema 一致 |
| 桌遊不存在（S `test_invalid_input_never_calls_vision_or_writes`、A `test_game_not_found`） | 對不存在的桌遊匯入 | 404，不呼叫模型、不寫入 |
| 頁碼小於 1（A `test_upload_validation`） | 上傳第 0 頁 | 422，無寫入 |
| 缺檔案（同上） | 未帶 multipart `file` | 422，無寫入 |
| 格式錯誤（S `test_invalid_input_never_calls_vision_or_writes`、A `test_upload_validation`） | 上傳純文字 | 400 `INVALID_IMAGE`，無模型呼叫 |
| 空檔案（同上） | 上傳 0 位元組 | 400 `INVALID_IMAGE` |
| 檔案過大（同上） | 上傳超過 10 MB | 400 `IMAGE_TOO_LARGE`，無模型呼叫 |
| 玩家不能匯入（S `test_player_denied_before_any_side_effect`、A `test_player_denied`） | 玩家上傳 | 403，無模型呼叫及寫入 |
| 店家人員可匯入（S `test_import_transcribes_original_image_once`、A `test_staff_can_import`） | 店家人員上傳合法圖片 | 200 |
| 玩家不能讀回（S `test_player_denied_before_any_side_effect`、A `test_player_denied`） | 玩家 GET | 403 |
| 模型不可用／fake 無腳本（S `test_ocr_failure_preserves_old_content_and_hides_details`、A `test_ocr_error_keeps_existing_page`） | 模型逾時或 fake 無腳本 | 503 `OCR_UNAVAILABLE`，保留原內容 |
| 雲端設定缺漏（A `test_cloud_missing_settings_fails_at_startup`） | cloud 缺設定啟動 | 明確列出缺少設定 |
| 模型拒答（S `test_ocr_failure_preserves_old_content_and_hides_details`、A `test_ocr_error_keeps_existing_page`） | 拋 `OCROutputRejected` | 503 `OCR_OUTPUT_REJECTED`，無寫入 |
| 其他 OCR 錯誤（同上） | 拋 `OCRError` | 503 `OCR_FAILED`，訊息不含金鑰 |
| 讀回排序（S `test_list_sorted_pages_and_provider_without_vision`、A `test_list_sorted_and_empty`） | 已入庫第 3、1 頁後 GET | 第 1、3 頁順序，total 正確，不呼叫模型 |
| 沒有頁面（同上） | 桌遊存在但尚未入庫 | 空列表、total 0 |
| 讀回不存在的桌遊（S `test_list_unknown_game`、A `test_game_not_found`） | GET 不存在的編號 | 404 `GAME_NOT_FOUND` |
| OCR 實作提示（S `test_list_sorted_pages_and_provider_without_vision`、A `test_list_sorted_and_empty`） | fake 模式 GET | 回應 `ocr_provider=fake` |
| 開發旗標開啟（R「開啟旗標顯示 rules-ingest 參考畫面」） | 開啟旗標導向路由 | 顯示參考畫面 |
| 開發旗標關閉（R「關閉旗標顯示找不到頁面」） | 關閉旗標導向路由 | 找不到頁面 |
| 全部匯入成功（F「檔名排序、指定起始頁碼、逐頁送出並自動讀回」） | 三張圖、起始頁 5 | 依檔名排序送第 5、6、7 頁，全部成功 |
| 其中一頁失敗（F「第二頁失敗不中止，結果保留後端錯誤訊息」） | 第二頁回 503 | 第三頁仍送出，第二頁保留錯誤訊息 |
| 匯入中（F「匯入期間防止重送、改欄位與重選圖片，顯示當前進度」） | 匯入尚未完成 | 防止重送並顯示進度 |
| 未填欄位（W「欄位與按鈕存在，缺欄位禁用匯入」、F「缺圖片或起始頁碼小於 1 不送出 API」） | 未填編號或未選圖片 | 匯入不可按，不送 API |
| 無效輸入（F「無效桌遊編號…不送出 API」、F「缺圖片或起始頁碼小於 1 不送出 API」） | 編號非正整數、起始頁 0 | 欄位提示，不送 API |
| 前端列出內容（F「讀回載入中、排序、空文字與 OCR provider」、W「空文字顯示整頁沒文字」） | API 回頁面 | 列出頁碼與完整內容，空字串顯示提示 |
| 自動讀回（F「檔名排序、指定起始頁碼、逐頁送出並自動讀回」、W「選圖匯入後自動讀回與顯示 cloud 提示」） | 一批匯入結束 | 自動 GET 更新列表 |
| 前端無資料（F「空列表與 fake provider」、W「讀回空列表與 fake 提示」） | API 回空列表 | 顯示尚無規則書頁面 |
| 前端 provider 提示（同上及 W「選圖匯入後自動讀回與顯示 cloud 提示」） | fake／cloud 回應 | 顯示 provider；cloud 顯示費用提示 |
| 讀回載入中（F「讀回載入中、排序、空文字與 OCR provider」） | GET 未回應 | loading 為 true，保留既有資料 |
| 前端無權限（F「404 保留成功列表，403 提示切換身分」） | API 回 403 | 顯示後端訊息並提示切換身分 |
| 前端桌遊不存在（同上） | 成功讀回後 API 回 404 | 保留原列表與原桌遊編號 |
| multipart 契約（D「multipart 使用 file 欄位、保留位元組、路徑與逾時」） | HTTP repository 上傳 | file 欄位、檔名、原始內容與 180 秒逾時 |
| DTO 與錯誤格式（D「讀回 DTO 正確對應 snake_case 與空文字」「HTTP 錯誤保留統一的後端訊息與錯誤碼」） | 解析回應及 403 | 欄位對應正確，保留 error.message |
| 桌遊並發刪除（S `test_concurrent_game_deletion_is_not_found`） | 模型回應後桌遊已刪除 | 404，不留新頁面 |
| 模型輸出格式錯誤（S `test_invalid_model_output_is_rejected`） | fake 回不符 schema 內容 | 拒絕寫入 |
| 取消選圖／讀檔失敗（F「取消選檔保留原圖，選檔失敗可重試」） | 取消或讀圖失敗 | 保留原圖，可再次選取 |

## 是否動到契約

- [ ] 沒有
- [x] 有，內容：
  - [x] API 契約：新增 PUT／GET，請 @ 立倫
  - [ ] migration：無
  - [x] 其他：新增前端 repository 與 ImagePicker 介面

## 是否需要 UI（needs-ui）

- [ ] 不需要
- [x] 需要：已寫 `docs/handoff/rules_ingest.md`；組員開 MR 時請加 `needs-ui` 並 @ 永傑

## 自我檢查

- [x] 後端：ruff check、ruff format --check；393 個預設測試通過，17 個外部服務測試未在預設執行
- [x] 前端：Flutter 3.41.4／Dart 3.11.1，flutter analyze 無問題，44 個測試通過；DTO 產生成功
- [x] 沒有提交秘密、真實規則書全文或合作店家資料
- [x] 只改指定 domain 與必要共用區，原因列於說明；請組員 @ 主責
- [x] 新套件理由：`python-multipart` 接收 multipart 檔案；`file_picker` 跨平台多檔選取，包在平台介面內

未修改 `integrations/`，不新增需要金鑰的 domain 測試。雲端 OCR 僅透過既有 provider 做手動 e2e。
