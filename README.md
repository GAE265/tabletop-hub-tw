# tabletop-hub-tw
桌遊三方平台 : 營運、開團、紀錄幫手

玩家、開團主、桌遊店三方共用：桌遊推薦、規則書 RAG 問答、戰績與天梯、訂位與座位圖、揪團與候補、睜眼偵測發牌機。

- 團隊規則：[AGENTS.md](AGENTS.md)（所有人與所有 AI 助理開工前必讀）
- 測試案例優先流程：[docs/test-first-flow.md](docs/test-first-flow.md)
- MR 審核指南：[docs/review-guide.md](docs/review-guide.md)（被指定為 Reviewer 時必讀）
- 前端交接說明範本：[docs/handoff/_template.md](docs/handoff/_template.md)

## 專案結構

| 資料夾 | 內容 |
|---|---|
| `backend/` | FastAPI + SQLAlchemy 2 + Alembic（Python 3.13，uv 管理） |
| `frontend/` | Flutter（先做 Web） |
| `device/` | 發牌機（樹莓派 5） |
| `docs/`、`openspec/` | 規格、交接說明、API 說明 |

## 需要安裝

- [Docker](https://docs.docker.com/get-docker/)（PostgreSQL 16 + pgvector、Mosquitto）
  - **Windows 要先裝 WSL 2**，否則 Docker Desktop 無法啟動：
    1. 確認 BIOS 已開啟虛擬化（工作管理員 → 效能 → CPU →「虛擬化：已啟用」）
    2. 用系統管理員身分開 PowerShell，執行 `wsl --install`，完成後重新開機（已裝過但版本舊，改執行 `wsl --update`）
    3. 安裝 Docker Desktop，安裝時勾選「Use WSL 2 instead of Hyper-V」
  - Windows／Mac 執行 `docker compose` 前，**要先打開 Docker Desktop** 並等它顯示執行中，否則指令會連不上 Docker。
- [uv](https://docs.astral.sh/uv/)（Python 套件管理）
  - Windows（PowerShell）：`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Mac：`curl -LsSf https://astral.sh/uv/install.sh | sh`
- Flutter **stable 3.41.4**（README 與 CI 使用同一版本；不使用 fvm）

## 本機啟動

### 1. 建立並填寫 `.env`（只有第一次要做）

只在 `.env` 不存在時才複製，避免覆蓋已設定好的檔案。從 repo 根目錄執行：

```powershell
# Windows（PowerShell）
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

```bash
# Mac／Linux
[ -f .env ] || cp .env.example .env
```

`.env.example` 依規則只有欄位名、沒有值，複製後請自行填入。本機開發**必須**設定：

| 欄位 | 填法 |
|---|---|
| `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB` | 自己決定。`docker compose` 建立資料庫時會用這三個值 |
| `POSTGRES_PORT` | 本機對外埠號，一般填 `5432` |
| `DATABASE_URL` | 格式 `postgresql+psycopg://<user>:<password>@localhost:<port>/<db>`，其中 `<user>`、`<password>`、`<db>`、`<port>` 要與上面的 `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`、`POSTGRES_PORT` **完全一致** |
| `AUTH_MODE` | 填 `dev` |

其餘欄位（`LLM_PROVIDER`、`EMBEDDING_DIM`、`CORS_ALLOW_ORIGINS`、`MQTT_*` 等）本機可留空，程式有預設值。**不要把真實密碼寫進 README 或提交 `.env`。**

> 資料庫第一次啟動後，帳號、密碼、資料庫名稱就寫進資料卷了。之後改 `.env` 裡的這三個值不會生效，需要先 `docker compose down -v`（會清空資料庫）再重新啟動。

### 2. 資料庫與 MQTT

先確認 Docker Desktop 已開啟，再從 repo 根目錄執行：

```bash
docker compose up -d
```

### 3. 後端

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.dev.seed        # 建立開發用資料：測試帳號、共用桌遊、推薦 Agent 的資料、教學影片
uv run python -m app.dev.seed_shop
uv run uvicorn app.main:create_app --factory --reload # http://localhost:8000/docs
```

測試帳號只存在於後端的 `app/dev/`，前端身分切換器會從 `GET /api/v1/dev/users` 讀取。

#### seed 會建立哪些資料

`uv run alembic upgrade head` 只建好資料表（另外寫入 8 個遊戲類型 `genres`），其他資料表是空的。`uv run python -m app.dev.seed` 會寫入下面這些開發用資料，可以重複執行：

| 資料 | 資料表 | 來源 |
|---|---|---|
| 測試帳號 3 個（player／shop_staff／admin）、測試店家 1 間 | `auth_users`、`booking_shops` | `backend/app/dev/accounts.py` |
| 共用桌遊資料 16 款（1–16 號，1–4 號是 4 款 Demo 遊戲） | `games`、`game_genres` | `backend/app/dev/seed_data/games-export.json` |
| 推薦 Agent 的資料：標籤、每款桌遊的標籤、心得摘要、心得片段（含向量） | `games_advisor_` 開頭的 4 張表 | `backend/app/dev/seed_data/games_advisor_data.sql` |
| 3 款 Demo 遊戲的規則教學影片 | `rules_qa_videos` | `backend/app/dev/lesson_videos.py` |

跑完 seed，每個人的桌遊與編號都相同，講「3 號」都是同一款。資料檔放在 repo 的原因與後果見 [ADR 0004](docs/adr/0004-seed-data-in-repo.md)；資料檔的來源與更新方法見 [`backend/app/dev/seed_data/README.md`](backend/app/dev/seed_data/README.md)。

注意：

- **先升級、再 seed。** 資料表比資料檔舊時，seed 會出現「欄位不存在」之類的錯誤；跑完 `uv run alembic upgrade head` 再跑一次 seed 即可。
- **seed 會讓桌遊與推薦 Agent 的資料和 repo 的資料檔完全一樣**（`games`、`game_genres` 與 `games_advisor_` 的 4 張表）。自己在本機新增的桌遊會被刪掉，揪團選用它的那筆對應（`group_games`）也會一起被刪，揪團本身保留；測試請用寫在測試程式裡的假資料。
- 本機新增的桌遊如果還被規則書頁面、規則問答、教學影片或戰績用到，資料庫會擋下刪除：seed 會印出是哪一款、被哪張資料表用到，桌遊與推薦 Agent 的資料維持原狀，結束碼不是 0。請照訊息處理，或找立倫。
- 桌遊這一步失敗（上面那種情況，或資料檔有問題）時，測試帳號、測試店家與教學影片仍會照常建立。
- 除了上面提到的 `group_games`，其他資料表原本的資料不會被 seed 刪除或修改。已經存在的測試帳號、店家與教學影片不會被覆蓋，帳號只在電話是空的時候補上假電話。
- 推薦 Agent 的向量是 1536 維，`.env` 的 `GAMES_ADVISOR_EMBEDDING_DIM` 請留空（預設就是 1536）。

#### 哪些資料不由 seed 建立

| 資料 | 怎麼建立 |
|---|---|
| 訂位用的店家設定（營業時間、桌子與座位圖、定價規則、FAQ、菜單） | 在 `backend/` 另外執行 `uv run python -m app.dev.seed_shop`（可重複執行） |
| 規則書頁面（`games_manual`） | 不放在 repo（AGENTS.md 第 2 節：不提交規則書全文）。用規則書入庫的 API 匯入，步驟見 [docs/manual-test-rules-ingest.md](docs/manual-test-rules-ingest.md) |
| 規則問答的檢索段落（`rules_qa_chunks`） | 規則書頁面入庫後，在 `backend/` 執行 `uv run python -m app.domains.rules_qa.commands index --game-id <遊戲編號>` |
| 揪團、訂位紀錄、戰績 | repo 目前沒有這些資料的 seed |

`sync-games` 指令（`uv run python -m app.domains.games_advisor.commands sync-games <匯出檔>`）還在，seed 的桌遊這一步就是呼叫它背後的同一段程式；本機開發不用再另外執行，也不用再到雲端資料夾下載匯出檔。

### 4. 前端

另開終端機；需先完成上面的後端步驟。

```bash
cd frontend
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # 產生 *.g.dart／*.freezed.dart（不提交）
flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=SHOW_PROTOTYPES=true
```

- **拉下程式或切換分支後，要先在 `frontend/` 執行 `dart run build_runner build`**，否則缺少 `*.g.dart`／`*.freezed.dart` 會編譯失敗。
- `--web-port 5000`：請固定 port，才會在後端 CORS 的允許清單內。後端允許的前端網址由 `.env` 的 `CORS_ALLOW_ORIGINS` 設定（逗號分隔，預設 `http://localhost:5000`）。
- `API_BASE_URL`：後端位址，未指定時為 `http://localhost:8000`。
- `SHOW_PROTOTYPES=true`：才會出現 `/proto/...` 參考畫面（例如 `/#/proto/health`）。
- 開發建置會在畫面最上方顯示「開發身分」切換器（從 `GET /api/v1/dev/users` 讀取，需後端 `AUTH_MODE=dev` 並已 seed）；release 建置不會顯示。

### 驗證身分切換

用 Chrome 開發者工具確認切換有生效：按 F12 → Network → 點任一個對後端的請求 → Headers → Request Headers，找 `X-Dev-User`。用身分切換器換身分後再觸發請求，該標頭的值（`<user_uuid>:<role>[:<shop_uuid>]`）應該跟著改變。

## 每天開工

資料庫與 seed 建立的資料都會保留，每天只需要三步：

```bash
# repo 根目錄
docker compose up -d    # 先確認 Docker Desktop 已開啟
docker compose ps       # 確認服務都已啟動

# 終端機 A
cd backend
uv run uvicorn app.main:create_app --factory --reload

# 終端機 B
cd frontend
flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=SHOW_PROTOTYPES=true
```

只有以下情況才需要重跑：

- `docker compose ps`  的 STATUS 欄位要顯示 `Up`（或 `Up (healthy)`），兩個服務都是才算成功。
如果顯示 `Exited` 或沒有出現，先確認 Docker Desktop 已經打開，再執行 `docker compose logs` 查看錯誤訊息。
- 後端套件有變動（`pyproject.toml`／`uv.lock` 被改）：`uv sync`（在 `backend/`）。有新的 migration 時也要跑 `uv run alembic upgrade head`。
- 測試帳號、共用桌遊資料或推薦 Agent 的資料有變動（桌遊資料更新時立倫會在群組通知）：拉下最新的 `dev`，在 `backend/` 先跑 `uv run alembic upgrade head`，再跑 `uv run python -m app.dev.seed`（可重複執行；會做什麼見「本機啟動」第 3 步的「seed 會建立哪些資料」）。

## 結束時怎麼關

1. 前端：在跑 `flutter run` 的終端機按 `q`。
2. 後端：在跑 `uvicorn` 的終端機按 `Ctrl+C`。
3. 資料庫與 MQTT（repo 根目錄）：`docker compose down`。資料庫資料會保留；**不要加 `-v`**，否則會連資料一起刪掉。

## 常見問題

**port 8000 或 5000 被占用**（啟動時出現 address already in use／無法綁定）：找出佔用的程式再停掉。

```powershell
# Windows（PowerShell）：把 8000 換成被占用的 port
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalPort, OwningProcess
Get-Process -Id <OwningProcess>    # 確認是哪個程式
Stop-Process -Id <OwningProcess>
```

```bash
# Mac／Linux
lsof -i :8000
kill <PID>
```

**前端顯示連不上後端**：

1. 後端是否已啟動：瀏覽器開 http://localhost:8000/docs 看得到畫面。
2. 前端是否用 `--web-port 5000` 啟動（其他 port 不在 CORS 允許清單內，請求會被瀏覽器擋掉）。
3. `--dart-define=API_BASE_URL` 是否指向後端位址。

**切換分支後前端編譯失敗**：在 `frontend/` 重跑 `dart run build_runner build --delete-conflicting-outputs`。

## 發 MR 前自我檢查

從 repo 根目錄出發，每一行都要通過。

```powershell
# Windows（PowerShell 5 不支援 &&，逐行執行並確認每行都通過）
Set-Location backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
Set-Location ../frontend
flutter analyze
flutter test
Set-Location ..
```

```bash
# Mac／Linux
(cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest)
(cd frontend && flutter analyze && flutter test)
```

## 分支規則

```
main  ← 只放可以 Demo 的版本，由組長（新善）從 dev 合併
 └── dev  ← 開發整合用，所有功能分支從這裡開出、合併回這裡
      └── <type>/<scope>-<簡述>
```

- 從 `dev` 開分支，MR 合併回 `dev`，至少一位其他組員審核通過才能合併。
- 不直接推到 `main` 或 `dev`。
- 例如：`feature/booking-available-tables`、`fix/core-error-format`、`chore/scaffold`。
- 開 Draft MR → 先列測試案例 → 先寫失敗的測試 → 再寫功能 → 改成 Ready for review（詳見 [docs/test-first-flow.md](docs/test-first-flow.md)）。

## Commit 格式

`<type>(<scope>): <描述>`

- type：`feat`、`fix`、`docs`、`refactor`、`test`、`chore`、`ci`
- scope：單一 domain 用 domain 名稱；後端共用區用 `core`／`integrations`；前端共用區用 `frontend`；發牌機用 `device`；跨多處省略
- 例如：`feat(booking): 新增查詢可用桌位 API`、`docs: 更新 README 啟動步驟`
