---
name: dev-server
description: 啟動 tabletop-hub-tw 的開發伺服器（後端 + 前端）。需要啟動後端和前端時使用。
---

# 開發伺服器啟動

啟動 tabletop-hub-tw 的後端（FastAPI）與前端（Flutter Web）開發伺服器。

## 啟動

```bash
# 步驟 1：停止既有的服務，釋放 port
kill -9 $(lsof -ti:8000) $(lsof -ti:5000) 2>/dev/null
sleep 1

# 步驟 2：啟動後端
cd /data/code/tabletop-hub-tw/backend
setsid uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 \
  </dev/null > /tmp/backend.log 2>&1 &
disown

# 步驟 3：等待後端就緒，再啟動前端
sleep 3
cd /data/code/tabletop-hub-tw/frontend
setsid flutter run -d web-server --web-hostname 0.0.0.0 --web-port 5000 \
  --dart-define=SHOW_PROTOTYPES=true \
  --dart-define=API_BASE_URL=http://100.123.189.49:8000 \
  </dev/null > /tmp/frontend.log 2>&1 &
disown

# 步驟 4：等待前端編譯完成
sleep 20
```

## 環境準備

啟動前確保 `.env` 存在且內容正確：

```bash
cat > /data/code/tabletop-hub-tw/.env <<'EOF'
database_url=postgresql+psycopg://dev_user:qwe123@localhost:5433/tabletop_hub_dev
auth_mode=dev
cors_allow_origins=http://localhost:5000,http://100.123.189.49:5000
EOF
```

## 驗證

```bash
# 後端健康檢查
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health
# 輸出應為 200

# 前端可連線
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000
# 輸出應為 200

# 確認兩者都 bind 在 0.0.0.0（外部可連）
ss -tlnp 2>/dev/null | grep -E "8000|5000"
```

## 對外網址

| 服務 | 網址 |
|---|---|
| 後端 API docs | `http://100.123.189.49:8000/docs` |
| 前端 | `http://100.123.189.49:5000` |

## 注意事項

- 後端用 `create_app` factory 模式，必須加 `--factory` 參數
- 前端必須帶 `--dart-define=API_BASE_URL=http://100.123.189.49:8000`，否則前端打 API 會走相對路徑（同 port 5000）而失敗
- 前端用 `--web-hostname 0.0.0.0` 才能讓外部電腦連線
- 前端 debug 模式首次編譯約需 15-20 秒
- 修改程式碼後，前端需手動按 `R`（hot restart）才能套用
- `100.123.189.49` 是本機 Tailscale IP，遠端電腦需在同一個 tailnet 才能連線

## 重建資料庫

如需重建本機開發 DB：

```bash
# 刪除並重建
docker exec tabletop-hub-tw-postgres-1 psql -U dev_user -d postgres -c "DROP DATABASE IF EXISTS tabletop_hub_dev;"
docker exec tabletop-hub-tw-postgres-1 createdb -U dev_user tabletop_hub_dev
docker exec tabletop-hub-tw-postgres-1 psql -U dev_user -d tabletop_hub_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 執行 migration
cd /data/code/tabletop-hub-tw/backend
database_url="postgresql+psycopg://dev_user:qwe123@localhost:5433/tabletop_hub_dev" uv run alembic upgrade head

# Seed 測試資料
database_url="postgresql+psycopg://dev_user:qwe123@localhost:5433/tabletop_hub_dev" auth_mode=dev uv run python -m app.dev.seed
database_url="postgresql+psycopg://dev_user:qwe123@localhost:5433/tabletop_hub_dev" auth_mode=dev uv run python -m app.dev.seed_shop
```
