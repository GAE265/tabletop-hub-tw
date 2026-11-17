## 1. 後端：資料存取與共用區

- [x] 1.1 在 `backend/app/core/games/repository.py` 新增 `game_exists(game_id)`（共用區，MR 要 @ 立倫）
- [x] 1.2 在 `rules_ingest/repository.py` 的 `ManualPageRepository` 新增 `list_pages(games_id)`，依 `page` 由小到大回傳
- [x] 1.3 確認 `python-multipart` 已在依賴中，沒有就用 `uv add` 加入（MR 說明寫理由）

## 2. 後端：schema、service、router

- [x] 2.1 `rules_ingest/schemas.py`：`ManualPageOut`（`games_id`、`page`、`content`）、`ManualPageItem`（`page`、`content`）、`ManualPageListOut`（`items`、`total`、`ocr_provider`）
- [x] 2.2 `rules_ingest/service.py`：`import_page(user, games_id, page, image: bytes)`，順序為角色檢查 → 圖片檢查（空、JPEG／PNG 檔頭、10 MB）→ `game_exists` → 視覺模型轉錄 → `upsert_page`，並把 OCR 例外轉成 design 第 5 點的錯誤
- [x] 2.3 `rules_ingest/service.py`：轉錄的 prompt 與 `{"markdown": string}` schema 放在 service（或同 domain 的 `prompts.py`）
- [x] 2.4 `rules_ingest/service.py`：`list_pages(user, games_id)`，角色檢查 → 桌遊存在 → 讀回，回傳含 `ocr_provider`
- [x] 2.5 `rules_ingest/router.py`：`PUT /games/{games_id}/manual-pages/{page}`（`UploadFile`、`page >= 1`）與 `GET /games/{games_id}/manual-pages`，用 `get_current_user` 取得身分傳給 service
- [x] 2.6 `main.py`：用 `get_vision_provider(settings.ocr_provider, settings)` 建立 `app.state.vision`，並掛上 `rules_ingest` router（共用區，MR 要 @ 立倫）
- [x] 2.7 啟動後打開 `/docs`，確認兩個端點與 schema 正確顯示

## 3. 前端：data 與 state

- [x] 3.1 `pubspec.yaml` 新增 `file_picker`（MR 說明寫理由），執行 `flutter pub get`
- [x] 3.2 `core/platform/` 新增 `ImagePicker` 介面與 `file_picker` 實作（回傳檔名與位元組）
- [x] 3.3 `domains/rules_ingest/data/`：DTO（`ManualPage`、`ManualPageList`）與 `ManualPagesRepository`（`importPage` 用 `FormData`、`list`），逾時拉長
- [x] 3.4 `domains/rules_ingest/state/`：匯入 Notifier（輸入驗證、檔名排序、依序逐頁送出、每頁結果、單頁失敗不中止、結束後自動讀回）
- [x] 3.5 `domains/rules_ingest/state/`：讀回 Notifier（載入中、沒資料、錯誤、`ocr_provider`）
- [x] 3.6 執行 `dart run build_runner build` 產生程式碼

## 4. 前端：參考畫面

- [x] 4.1 `prototypes/rules_ingest/rules_ingest_proto_page.dart`：`games_id`、起始頁碼、選圖片、匯入、結果列表、讀回列表、`ocr_provider` 提示，只用預設元件
- [x] 4.2 `app/router.dart` 新增 `/proto/rules-ingest`（受 `SHOW_PROTOTYPES` 控制，共用區，MR 要 @ 永傑）

## 5. 手動 e2e 驗證

- [x] 5.1 `.env` 設 `OCR_PROVIDER=cloud` 與案例 4 的欄位，`alembic upgrade head`，先在資料庫放一筆測試桌遊（或用既有的桌遊）
- [ ] 5.2 啟動後端與前端（`--dart-define=SHOW_PROTOTYPES=true`），用身分切換器切成 `admin`，匯入 2 張自畫的英文字圖片，確認結果列表與讀回列表一致
- [ ] 5.3 用 `psql` 查 `games_manual`，確認內容與畫面一致；同頁重送確認被覆蓋、只有一列
- [ ] 5.4 驗證錯誤：切成 `player` 看到 403、輸入不存在的 `games_id` 看到 404、`OCR_PROVIDER=fake` 看到 503
- [x] 5.5 更新 `docs/manual-test-rules-ingest.md`，新增「案例 6：從前端匯入並驗證」（步驟、預期畫面、`psql` 查詢指令，不含金鑰）

## 6. 測試與收尾（依組員決定，功能完成後補）

- [x] 6.1 後端 service 單元測試：用手寫 fake repository 與腳本化 `FakeVisionProvider`，涵蓋 spec 的每個 scenario（含沒有權限、桌遊不存在時模型沒被呼叫、`OCRUnavailable` 時不寫入）
- [x] 6.2 後端 API 測試：用 `as_player`／`as_shop_staff`／`as_admin` fixture 驗證狀態碼與回應格式、multipart 上傳、讀回排序
- [x] 6.3 前端 state 測試：用 Riverpod override 與 `test/support/fakes.dart` 的 fake repository 與 fake `ImagePicker`，涵蓋參考畫面 spec 的情境
- [x] 6.4 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`、`flutter analyze`、`flutter test` 全部通過
- [x] 6.5 依 `docs/handoff/_template.md` 補 `docs/handoff/rules_ingest.md`；準備 MR 說明（情境表格對應測試、註明先實作後補測試、@ 立倫與永傑）
