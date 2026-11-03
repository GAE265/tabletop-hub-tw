# tabletop-hub-tw
桌遊三方平台 : 營運、開團、紀錄幫手

玩家、開團主、桌遊店三方共用：桌遊推薦、規則書 RAG 問答、戰績與天梯、訂位與座位圖、揪團與候補、睜眼偵測發牌機。

- 團隊規則：[AGENTS.md](AGENTS.md)（所有人與所有 AI 助理開工前必讀）
- 測試案例優先流程：[docs/test-first-flow.md](docs/test-first-flow.md)
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
- [uv](https://docs.astral.sh/uv/)
- Flutter **stable 3.41.4**（README 與 CI 使用同一版本；不使用 fvm）

## 本機啟動

```bash
# 1. 設定檔：複製後填入本機值（.env 不會被提交）
cp .env.example .env

# 2. 資料庫與 MQTT
docker compose up -d

# 3. 後端
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.dev.seed        # 建立開發用測試帳號（player / shop_staff / admin）
uv run uvicorn app.main:create_app --factory --reload # http://localhost:8000/docs
```

`.env` 的 `AUTH_MODE` 請設為 `dev`。測試帳號只存在於後端的 `app/dev/`，前端身分切換器會從 `GET /api/v1/dev/users` 讀取。

前端（`frontend/`）將在後續 MR 加入。啟動時請固定 port，才會在後端 CORS 的允許清單內：

```bash
flutter run -d chrome --web-port 5000
```

後端允許的前端網址由 `.env` 的 `CORS_ALLOW_ORIGINS` 設定（逗號分隔，預設 `http://localhost:5000`）。

## 發 MR 前自我檢查

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && flutter analyze && flutter test
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
