# Tasks

> 依序完成 3 個 MR。每個 MR 內先寫測試、確認失敗，再寫功能（AGENTS.md 7.2）。不得修改 AGENTS.md、CLAUDE.md、openspec/ 既有內容、docs/test-first-flow.md、docs/images/。每個 MR 先開 Draft MR 並貼上情境表格，全部通過且 CI 全綠後才改為 Ready for review。每個 MR 合併時都有自己的 CI job 把關。

## 1. 前置確認

- [x] 1.1 Flutter 已確認為 stable 3.41.4（Chrome 可用），README 與 CI 鎖定此版本，驗證：`flutter --version` 輸出為 3.41.4
- [x] 1.2 確認 `uv --version`、`docker --version` 可用，驗證：指令輸出無錯誤
- [ ] 1.3 從 `dev` 開分支（例如 `chore/scaffold-root-backend`）並開 Draft MR 1，說明貼入相關 specs 情境表格並 @ 立倫、瑋鋐，驗證：Draft MR 存在

## 2. MR 1-A：根目錄檔案

- [x] 2.1 新增 `.gitattributes`（`* text=auto eol=lf`）與 `.editorconfig`，驗證：新增的文字檔在 Windows 上以 LF 簽出（`git ls-files --eol` 顯示 `w/lf`）
- [x] 2.2 新增 `.gitignore`（Python、Flutter、Node、VS Code、macOS／Windows 系統檔、`.env`；不排除 `.env.example`、`uv.lock`、`pubspec.lock`），驗證：`git check-ignore` 對 `.env` 命中，對 `backend/uv.lock`、`frontend/pubspec.lock`、`.env.example` 不命中
- [x] 2.3 新增 `.env.example`（資料庫、`AUTH_MODE`（註明正式環境必須為 jwt）、`DEV_DEFAULT_USER_ID`、`LLM_PROVIDER`、雲端模型金鑰、MQTT 含 username／password 欄位、`EMBEDDING_DIM`，僅欄位名與說明），驗證：檔內無任何實際秘密值
- [x] 2.4 新增 `docker-compose.yml`（`pgvector/pgvector:pg16` 具名 volume；`eclipse-mosquitto:2` 以內建 `mosquitto-no-auth.conf` 啟動），驗證：`docker compose up -d` 後兩容器 running、`down` 再 `up` 資料仍在
- [x] 2.5 新增 `docs/handoff/_template.md`（依 5.4 四項內容），驗證：涵蓋頁面、state 對應、載入／空／錯誤、截圖欄
- [x] 2.6 新增 `.github/pull_request_template.md`（測試案例表格、是否動契約、是否需要 UI needs-ui），驗證：三個區塊皆存在
- [x] 2.7 改寫 `README.md`（簡介、啟動步驟含 seed、鎖定的 Flutter 版本、分支規則、commit 摘要、連結），驗證：兩個連結目標存在，且啟動步驟之後可照做（於 7.1 實測）
- [x] 2.8 確認受保護路徑未變動，驗證：`docs/test-first-flow.md` 與 `docs/images/` 的內容雜湊與實作前相同

## 3. MR 1-B：後端核心（測試先行）

- [x] 3.1 以 `uv init` 建立 `backend/`，設定 `pyproject.toml`（ruff 行長 100、E/F/I/B/UP；pytest），驗證：`uv sync` 成功、`uv run ruff check .` 通過、`uv.lock` 未被忽略
- [x] 3.2 撰寫測試：`api-error-format`（404、422、500、403、AppError 409、405 格式），驗證：測試存在且失敗（非 skip／xfail）
- [x] 3.3 撰寫測試：`dev-auth-context` 中不需資料庫的部分（UUID 標頭解析、shop_staff 帶店家／缺店家／player 多帶店家、預設玩家取自 `DEV_DEFAULT_USER_ID`、格式錯誤 400、不查資料表、jwt 模式 401、`require_role`），驗證：測試存在且失敗
- [x] 3.4 撰寫測試：`llm-provider`（Fake 固定／自訂回覆、`LLM_PROVIDER` 選擇、未支援值報錯），驗證：測試存在且失敗
- [x] 3.5 實作 `core/config.py`、`core/errors.py`、`core/auth.py`、`main.py`（`create_app(settings)`）與 `tests/conftest.py`（`as_player`／`as_shop_staff`／`as_admin`，用測試專用 UUID，不依賴資料庫、不 import `app/dev/`），驗證：3.2、3.3 的測試全過
- [x] 3.6 實作 `integrations/llm/`（`LLMProvider`、`FakeLLMProvider`、選擇函式），驗證：3.4 的測試全過

## 4. MR 1-C：資料庫、health、app/dev 與 backend CI（含 migration，@ 瑋鋐）

- [x] 4.1 撰寫測試：`database-baseline`（空庫升級、UUID 型別與預設值、自行指定 id、role CHECK、shop_id 外鍵、升級後兩表為空、downgrade）與 `health-check`（正常、資料庫中斷、免身分、405），驗證：測試存在且失敗
- [x] 4.2 撰寫測試：seed 指令（首次建立三帳號與測試店家、重複執行不重複、`AUTH_MODE=jwt` 拒絕執行且不寫入、預設玩家與 seed 的 player 同 id；以 subprocess 執行，不 import `app/dev/`），驗證：測試存在且失敗
- [x] 4.3 撰寫測試：`dev-users-api`（seed 後回 3 筆且與資料庫一致、未 seed 回空、免身分、只列測試帳號、jwt 模式 404 且不在 OpenAPI、jwt 啟動時未載入 `app.dev`、以 `ast` 掃描確認 `app/dev/` 以外無 import `app.dev`），驗證：測試存在且失敗
- [x] 4.4 設定 Alembic，新增 `domains/auth/models.py`、`domains/booking/models.py`，產生並整理唯一的 migration（啟用 pgvector、兩表 UUID 主鍵、含 downgrade、不含種子資料），驗證：4.1 的 migration 測試全過
- [x] 4.5 實作 `core/db.py`（同步 session）與 `domains/health/`（router／schemas／service／repository）並掛載，驗證：4.1 的 health 測試全過，且 `/docs` 顯示 `GET /api/v1/health`
- [x] 4.6 實作 `app/dev/`（`accounts.py`、`seed.py`、`router.py`），`main.py` 在 `AUTH_MODE=dev` 時以 `importlib` 動態掛載，驗證：4.2、4.3 的測試全過，且依 README 步驟對本機 DB 實跑 seed 兩次結果相同、`curl /api/v1/dev/users` 回 3 筆
- [ ] 4.7 新增 `.github/workflows/ci.yml` 與 backend job（pull_request 到 dev/main；`pgvector/pgvector:pg16` service；`ruff check`、`ruff format --check`、`pytest`；無秘密），驗證：Draft MR 1 上 backend job 被觸發並通過
- [ ] 4.8 驗證 backend job 失敗路徑：在暫時分支引入格式錯誤，驗證：job 失敗，修正後轉綠（此提交不留在 MR）
- [ ] 4.9 自我檢查，驗證：本機 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest` 通過、CI 全綠；MR 標明含 migration、改 Ready for review

## 5. MR 2：前端與 frontend CI（@ 永傑；於 MR 1 合併後從 dev 開分支）

- [ ] 5.1 開 Draft MR 2 並貼上 `frontend-shell` 情境表格，驗證：Draft MR 存在且 @ 永傑
- [ ] 5.2 `flutter create` 建立 `frontend/`（啟用 web），加入 flutter_riverpod、go_router、dio、freezed、json_serializable、build_runner 與 `analysis_options.yaml`，驗證：`flutter pub get`、`flutter analyze` 成功，`pubspec.lock` 已加入追蹤
- [ ] 5.3 撰寫測試：斷點邊界（599/600/1023/1024）、`SHOW_PROTOTYPES` 開／關路由、`X-Dev-User` 攔截器（開發帶／shop_staff 帶 `:<shop_id>`／正式不帶／清單未載入不帶）、切換器（從 API 載入、選取後標頭變更、載入失敗顯示錯誤與重試、空清單提示、正式環境不顯示且不呼叫 API）、原始碼不含測試帳號 UUID、health state（載入中／成功／錯誤），驗證：測試存在且失敗
- [ ] 5.4 實作 `core/layout/`、`core/api/`（含 `API_BASE_URL`）、`core/platform/` 介面、`core/dev/`（呼叫 `/api/v1/dev/users` 的 data／state、身分 provider、切換器 widget，僅開發環境），驗證：對應測試全過
- [ ] 5.5 實作 `domains/health/data/` 與 `state/`（freezed DTO、provider），驗證：health state 測試全過
- [ ] 5.6 實作 `app/` 路由與 `app/theme/`、`prototypes/health/`、`domains/health/pages/`，並在畫面框架掛上 `core/dev/` 切換器，驗證：`flutter test` 全過，`flutter run -d chrome`（後端 dev 模式且已 seed）手動確認參考畫面、正式頁面、身分切換皆可用
- [ ] 5.7 撰寫 `docs/handoff/health.md`（依範本，含截圖），驗證：涵蓋範本所有欄位
- [ ] 5.8 在 `ci.yml` 加入 frontend job（`subosito/flutter-action`，版本與 README 相同；`flutter analyze`、`flutter test`），驗證：MR 2 上 frontend job 被觸發並通過，且 README 與 `ci.yml` 版本字串一致
- [ ] 5.9 自我檢查，驗證：本機 `flutter analyze`、`flutter test` 通過、CI 全綠；MR 加 `needs-ui`、改 Ready for review
- [ ] 5.10 【人工操作，由新善在 GitHub 設定；AI 不執行】MR 2 合併到 `dev` 且 frontend job 實際跑過一次後，到 GitHub Settings → Rulesets，在 `main protect` 與 `dev protect` 兩條 ruleset 的必要檢查（Require status checks）中加入 frontend。原因：GitHub 只能選取實際跑過的檢查；若在檢查存在之前就設為必要，所有 MR 會一直卡在等待該檢查，無法合併。驗證：兩條 ruleset 的必要檢查都列有 frontend，且之後的 MR 會顯示並等待該檢查

## 6. MR 3：device 與 device CI（@ 新善；於 MR 2 合併後從 dev 開分支）

- [ ] 6.1 開 Draft MR 3 並貼上 `device-hardware-abstraction` 與 `ci-checks` 的 device 情境表格，驗證：Draft MR 存在且 @ 新善
- [ ] 6.2 建立 `device/` README 與 `pyproject.toml`（`requires-python = ">=3.13"`、含 ruff 設定），README 說明用途、測試指令，以及樹莓派上 `picamera2` 以 apt 安裝、虛擬環境需能讀取系統套件（`uv venv --system-site-packages`），驗證：README 含這三項，`uv.lock` 已加入追蹤
- [ ] 6.3 撰寫測試：mock 攝影機回傳影格、mock 馬達記錄動作、上層只依賴介面，驗證：測試存在且失敗
- [ ] 6.4 實作攝影機與馬達介面及 mock，驗證：6.3 的測試全過，`device/` 相依不含硬體套件，且在 Windows 開發機可執行
- [ ] 6.5 在 `ci.yml` 加入 device job（`uv sync`、`ruff check`、`ruff format --check`、`pytest`），驗證：MR 3 上 device job 被觸發並通過；暫時引入失敗時 job 失敗且 backend／frontend job 仍照常執行
- [ ] 6.6 自我檢查，驗證：本機 device 的 ruff 與 pytest 通過、CI 三個 job 全綠；改 Ready for review
- [ ] 6.7 【人工操作，由新善在 GitHub 設定；AI 不執行】MR 3 合併到 `dev` 且 device job 實際跑過一次後，到 GitHub Settings → Rulesets，在 `main protect` 與 `dev protect` 兩條 ruleset 的必要檢查（Require status checks）中加入 device。原因：GitHub 只能選取實際跑過的檢查；若在檢查存在之前就設為必要，所有 MR 會一直卡在等待該檢查，無法合併。驗證：兩條 ruleset 的必要檢查都列有 device，且之後的 MR 會顯示並等待該檢查

## 7. 整合驗收

- [ ] 7.1 在乾淨 clone（Windows）依 README 指令順序走一次，驗證：DB、seed、後端 `/docs`、`/api/v1/dev/users`、前端 health 畫面與身分切換皆正常
- [ ] 7.2 以 `AUTH_MODE=jwt` 啟動後端，驗證：`/api/v1/dev/users` 回 404，前端正式建置沒有切換器
- [ ] 7.3 回填 design.md 套件版本表的實際版本，驗證：表內無「最新穩定」字樣
- [ ] 7.4 列出改動檔案、已跑檢查與未完成項目（AGENTS.md 第 9 節），驗證：回覆含三項

## Workflow follow-up

- 每個 MR 經至少一位其他組員審核、CI 全綠後合併回 `dev`。
- 全部合併後執行 `/opsx:archive`。
