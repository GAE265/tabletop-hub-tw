# Tasks

> 依序完成 3 個 MR（design.md D12）。每個 MR 都先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開（第 9 節規定 AI 不得開 MR）；AI 只依 `.github/pull_request_template.md` 產出 MR 說明，並附上情境表格（7.4）。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置確認

- [ ] 1.1 在群組告知新表名 `rules_qa_videos`、`rules_qa_chunks`（4.4），驗證：沒有人提出撞名或反對
- [ ] 1.2 與瑋鋐確認 design.md D4（`rules_ingest` 新增不檢查使用者的頁面讀取方法，由誰新增）與 D5（embedding 設定），驗證：結論記在本檔的「1.2 結論」註記
- [ ] 1.3 確認影片放在哪裡（design.md Open Questions 1），驗證：結論記在本檔；若影片在 YouTube，先更新 design.md D9 再開始 MR 2
- [ ] 1.4 等 `feature/ocr`（`games_manual`、`rules_ingest` service）合併到 `dev`，驗證：`dev` 上有 `backend/app/domains/rules_ingest/`

## 2. MR 1：後端 API、索引指令與 migration（@ 立倫、瑋鋐）

- [ ] 2.1 永傑開 Draft MR 1，AI 從 `specs/rules-qa` 整理情境表格供貼上，驗證：Draft MR 已存在，並 @ 立倫、瑋鋐
- [ ] 2.2 撰寫 migration 測試（`tests/migrations/test_rules_qa_tables.py`）：兩張表存在、外鍵沒有 cascade、`page >= 1` 的 CHECK、`rules_qa_videos` 一款遊戲一筆、可以 downgrade，驗證：測試存在且失敗，沒有使用 skip 或 xfail
- [ ] 2.3 撰寫切段的單元測試（`tests/rules_qa/test_chunking.py`）：段落不跨頁、合併到上限、超長段落切開、空白頁略過，驗證：測試存在且失敗
- [ ] 2.4 撰寫 service 單元測試（`tests/rules_qa/test_service.py`，使用 `FakeLLMProvider`、`FakeEmbeddingProvider`、`FakeRulesQaRepository`、`FakeManualPagesSource`）：教學清單、教學內容、設定影片與取代、建立索引與重建、問答（出處對回頁碼、同頁合併、丟棄來源外出處、找不到答案、只檢索該遊戲、追問帶 `previous_response_id`、用語改寫一次與拒絕、沒有段落時不呼叫 LLM、錯誤對應）、設定影片的權限，驗證：測試存在且失敗
- [ ] 2.5 撰寫 API 測試（`tests/rules_qa/test_api.py`，連 `_test` 資料庫，使用 `as_player`、`as_shop_staff`、`as_admin` 與 `jwt_client`）：涵蓋 `specs/rules-qa` 每個 API 情境的狀態碼、錯誤代碼與回應格式，驗證：測試存在且失敗，每個端點至少有成功與失敗案例各一
- [ ] 2.6 依 1.2 的結論，取得 `rules_ingest` 的頁面讀取方法；若由永傑代為新增，在 MR 說明 @ 瑋鋐，驗證：`rules_qa` 沒有 import `rules_ingest` 的 model 或 repository
- [ ] 2.7 新增 `RULES_QA_EMBEDDING_*` 設定（`core/config.py`、`.env.example` 只寫欄位名與說明），驗證：沒填時使用 fake，`uv run pytest` 不需要金鑰
- [ ] 2.8 新增 `app/domains/rules_qa/models.py` 與 migration（版本號依當時 `dev` 的最新 migration 決定），驗證：2.2 的測試全部通過
- [ ] 2.9 實作 `chunking.py`、`repository.py`（pgvector cosine 檢索）、`prompts.py`、`service.py`、`schemas.py`、`router.py`、索引指令，在 `main.py` 掛載 router 並建立 embedding provider，驗證：2.3–2.5 的測試全部通過，`/docs` 列出 4 個 rules_qa 端點
- [ ] 2.10 自我檢查：在 `backend/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`，驗證：全部通過、CI 全綠；MR 標明有改契約、含 migration，再改成 Ready for review

## 3. MR 2：前端 data、state、參考畫面與交接說明（於 MR 1 合併後從 dev 開分支）

- [ ] 3.1 依 1.3 的結論確定影片播放方式；需要新增套件時先徵得組內同意，並在 MR 說明寫理由，驗證：結論記在本檔
- [ ] 3.2 永傑開 Draft MR 2，AI 從 `specs/rules-qa-page` 整理情境表格，驗證：Draft MR 已存在
- [ ] 3.3 撰寫 state 測試（`test/domains/rules_qa/`，在 `test/support/fakes.dart` 新增 `FakeRulesQaRepository`，用 Riverpod override 替換）：清單載入／空／錯誤、教學頁有影片與沒有影片、看完影片開始提問、發問與頁碼出處、建議問題、追問帶 `response_id`、只有影片沒有規則書時不能提問、找不到答案、開始新對話、對話已失效、送出中不能重複送出、送出失敗保留問題、空白不能送出，驗證：測試存在且失敗
- [ ] 3.4 實作 `domains/rules_qa/data/`（freezed DTO、`RulesQaRepository`、`HttpRulesQaRepository`），執行 `dart run build_runner build --delete-conflicting-outputs`，驗證：`flutter analyze` 沒有錯誤
- [ ] 3.5 實作 `domains/rules_qa/state/`，驗證：3.3 的測試全部通過
- [ ] 3.6 實作影片播放的 `core/platform/` 介面與 fake，以及 `prototypes/rules_qa/`（只用 Flutter 預設元件，做出所有按鈕、欄位與載入中、沒有資料、錯誤三種狀態），在 `app/router.dart` 註冊 `/proto/rules_qa`，驗證：後端以 dev 模式啟動，手動走過有影片與沒有影片兩款遊戲的教學與問答
- [ ] 3.7 撰寫 `docs/handoff/rules_qa.md`（依 `_template.md`，附參考畫面截圖），驗證：涵蓋範本所有欄位
- [ ] 3.8 自我檢查：在 `frontend/` 跑 `flutter analyze`、`flutter test`，驗證：全部通過、CI 全綠；加上 `needs-ui` 標籤後改成 Ready for review

## 4. MR 3：正式頁面（於 MR 2 合併後從 dev 開分支）

- [ ] 4.1 撰寫 widget 測試：`/rules`、`/rules/{game_id}` 路由存在、未開啟 `SHOW_PROTOTYPES` 時沒有 `/proto/rules_qa`、手機上下排列、桌機左右並排、頁碼出處顯示，驗證：測試存在且失敗
- [ ] 4.2 實作 `domains/rules_qa/pages/`，只使用 `rules_qa/state/` 與 `app/theme/`，驗證：4.1 的測試通過；用 grep 確認 `pages/` 沒有寫死的顏色、字級、間距
- [ ] 4.3 在 `app/router.dart` 註冊 `/rules`，在畫面框架加上入口；依 5.4 刪除 `/proto/rules_qa`，驗證：`flutter test` 全部通過
- [ ] 4.4 自我檢查：在 `frontend/` 跑 `flutter analyze`、`flutter test`，並在 Chrome 手動檢查手機與桌機寬度，驗證：全部通過、CI 全綠，再改成 Ready for review

## Workflow follow-up

- 每個 MR 都經至少一位其他組員審核、CI 全綠後，才合併回 `dev`。
- 三個 MR 都合併後，執行 `/opsx:archive`。
- 規則書重新入庫後自動重建索引、LLM 產生分段教學內容、檢索品質的評估題組，之後另開 change。
