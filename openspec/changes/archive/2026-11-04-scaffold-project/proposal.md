# Proposal

## Why

repo 目前只有 AGENTS.md、docs/、openspec/ 與一行 README，沒有任何程式骨架。七位組員要在各自 domain 平行開發，需要先有統一的目錄、分層、認證替身、錯誤格式、測試 fixture、CI 與本機環境，否則各人會各自發明，之後合併成本很高。骨架也要先把 AGENTS.md 的共用區（`core/`、`integrations/`、`frontend/lib/app/`）立好，讓後續 MR 只需動自己的 domain。

## What Changes

- 根目錄：新增 `.gitignore`、`.gitattributes`（`* text=auto eol=lf`）、`.editorconfig`、`.env.example`、`docker-compose.yml`（PostgreSQL 16 + pgvector、Mosquitto）、`.github/pull_request_template.md`、`.github/workflows/ci.yml`、`docs/handoff/_template.md`；改寫現有 `README.md`。`uv.lock` 與 `pubspec.lock` 必須提交，不得列入 `.gitignore`。
- `backend/`：FastAPI + uv 專案；`core/`（設定、同步 DB session、`CurrentUser`／`get_current_user`／`require_role`／`PermissionDenied`、統一錯誤處理）；`integrations/llm/`（`LLMProvider` 介面 + `FakeLLMProvider`）；`domains/health/`（`GET /api/v1/health`）；Alembic 與第一個 migration（啟用 pgvector、建立 UUID 主鍵的 `auth_users`、`booking_shops`）；`app/dev/`（僅 `AUTH_MODE=dev` 啟用）：seed 指令建立固定 UUID 的 player、shop_staff、admin 測試帳號（**不寫進 migration**），以及 `GET /api/v1/dev/users` 列出這些帳號；`tests/conftest.py`（`as_player`、`as_shop_staff`、`as_admin`）；ruff 與 pytest 設定。
- `frontend/`：Flutter Web 專案；`app/`、`core/`（API client、`core/layout/` 斷點、`core/platform/`、`core/dev/` 開發身分切換器，從 `GET /api/v1/dev/users` 讀取帳號，前端不存 UUID）、`domains/health/`（`data/`、`state/`、`pages/`）、`prototypes/health/`；`SHOW_PROTOTYPES` 控制 `/proto/...` 路由；開發環境自動帶 `X-Dev-User: <user_uuid>:<role>[:<shop_uuid>]`。
- `device/`：資料夾、README（含 picamera2 以 apt 安裝、虛擬環境須能讀取系統套件的說明）、攝影機與馬達的介面與 mock 實作（不接硬體）。
- **不做**：JWT 登入（`auth` 階段 3，立倫）、其他任何業務 domain、MQTT 實際連線程式、Azure 部署。
- **不動**：`AGENTS.md`、`CLAUDE.md`、`openspec/` 既有內容、`docs/test-first-flow.md` 與 `docs/images/`。
- 契約：新增 `GET /api/v1/health`、`GET /api/v1/dev/users`（僅 dev 模式）、統一錯誤格式、`X-Dev-User` 標頭格式（皆為新契約，非修改既有）。含 **一個 migration**（需瑋鋐審核）。
- 例外說明：`.gitattributes` 與 `.editorconfig` 不在 AGENTS.md 原有清單內；組員混用 Windows／Mac 且 `device/` 腳本要在樹莓派執行，需統一換行符號，已獲使用者明確同意（AGENTS.md 規則 4 的例外）。

受影響 domain 與主責（AGENTS.md 第 3 節）：`health` 由立倫代管（示範 domain，正式 domain 開始後可刪除）；`auth_users` 屬 `auth`（立倫）、`booking_shops` 屬 `booking`（秀暖），皆只建最少欄位。共用區：`core/` 與 `app/dev/`（立倫）、`integrations/llm/`（瑋鋐）、`device/`（新善）、`frontend/lib/app/` 與 `core/`（永傑）。

## 交付方式：3 個 MR，依序合併

| MR | 內容 | CI | @ |
|---|---|---|---|
| 1 | 根目錄檔案 ＋ 後端 ＋ migration ＋ `app/dev/` | 建立 `ci.yml` 與後端 job | 立倫、瑋鋐 |
| 2 | 前端 | 加入前端 job | 永傑 |
| 3 | device | 加入 device job | 新善 |

每個 MR 合併時都有 CI 把關：MR 1 由後端 job、MR 2 由前端 job、MR 3 由 device job。三個 MR 皆預期超過 400 行（規則 6），原因是骨架本質；MR 說明需寫明。device job（`ruff` 與 `pytest`）已列入 AGENTS.md 8.3。

## Capabilities

### New Capabilities
- `local-dev-environment`: `.env.example` 欄位、docker-compose 服務、README 啟動流程、`.gitignore`／`.gitattributes`／`.editorconfig`，讓新組員能照步驟在本機跑起後端與資料庫，且換行符號一致。
- `health-check`: `GET /api/v1/health` 回報服務與資料庫連線狀態。
- `api-error-format`: 所有錯誤回應統一為 `{"error": {"code", "message", "details"}}`，並對應 AGENTS.md 4.3 狀態碼。
- `dev-auth-context`: `AUTH_MODE=dev` 下以 UUID 標頭解析目前使用者、角色檢查、權限不足回 403、開發用 seed 與測試身分 fixture。
- `dev-users-api`: `GET /api/v1/dev/users` 列出 seed 的測試帳號，僅 `AUTH_MODE=dev` 掛載；測試帳號 UUID 只定義在後端 `app/dev/`。
- `database-baseline`: 第一個 migration 的結果（pgvector 擴充、UUID 主鍵的 `auth_users`、`booking_shops`）與 Alembic 可重複執行。
- `llm-provider`: LLM 呼叫的統一介面與測試用固定回覆實作，由 `LLM_PROVIDER` 選擇。
- `ci-checks`: MR 到 `dev`／`main` 時自動跑的後端、前端與 device 檢查，各 job 獨立。
- `frontend-shell`: Flutter 前端的 API 位址注入、RWD 斷點、`/proto/...` 開關、開發身分切換器，與 health 範例的分層示範。
- `device-hardware-abstraction`: 發牌機攝影機與馬達的介面及 mock，使無硬體環境可跑測試。

### Modified Capabilities
<!-- 無：openspec/specs/ 目前沒有任何既有 spec -->

## Impact

- 新增頂層資料夾 `backend/`、`frontend/`、`device/`（AGENTS.md 已定義，非擅自新增）；不新增其他頂層資料夾（Mosquitto 不另建設定目錄）。
- 新增第三方套件（規則 4 要求寫理由，細節在 design.md）：後端 fastapi、uvicorn、sqlalchemy、alembic、psycopg、pydantic-settings、pgvector、pytest、httpx、ruff；前端 flutter_riverpod、go_router、dio、freezed、json_serializable、build_runner 等。
- 新增 GitHub Actions workflow，分 3 個 MR 逐步加入各 job；backend job 使用 pgvector 映像檔。
- 現有 `README.md` 會被改寫（僅 2 行，保留標題與一句簡介）。
- 測試帳號 UUID 只定義在後端；前端 `core/dev/` 於執行時從 API 取得，不內嵌。
