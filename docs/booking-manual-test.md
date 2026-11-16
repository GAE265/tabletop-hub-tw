# 訂位後端：基礎手動測試步驟

用來確認 `booking` domain 在本機能啟動，並走過主要的正向流程。自動化測試在 `backend/tests/booking/`，這份文件是手動驗收用。

## 1. 前置準備

1. 啟動資料庫（`docker compose up -d postgres`），並在專案根目錄的 `.env` 設定：
   - `DATABASE_URL`：後端連線字串。建議為本專案獨立建一個資料庫（例如 `tabletop_hub_tw`），使用預設的 `public` schema，不要加 `options=-csearch_path=...`：
     - 先建立資料庫：`CREATE DATABASE tabletop_hub_tw;`
     - 連線字串：`postgresql+psycopg://<user>:<password>@localhost:7501/tabletop_hub_tw`
     - 注意：`vector`、`btree_gist` extension 會裝在 migration 當時的 search_path。若指定其他 schema，之後改用預設連線會出現 `type "vector" does not exist`。
   - `AUTH_MODE=dev`：用 `X-Dev-User` 標頭取得身分。
2. 以下指令都在 `backend/` 執行：

```bash
cd backend

# 建立資料表（含 booking 的 8 張表）
uv run alembic upgrade head

# 建立開發用測試帳號與「測試桌遊店」（可重複執行）
uv run python -m app.dev.seed

# 訂位需要電話：替預設測試玩家補上電話
uv run python - <<'PY'
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.db import create_db_engine

settings = get_settings()
with Session(create_db_engine(settings.database_url)) as s, s.begin():
    s.execute(
        text("UPDATE auth_users SET phone = '0912000111' WHERE id = :i"),
        {"i": settings.dev_default_user_id},
    )
PY
```

預期：seed 印出「已建立（或確認存在）3 個測試帳號與 1 間測試店家」。

**店家設定資料（自行準備 DML，不進 repo）**：沒有這些資料，任何訂位都會被拒絕。請以「測試桌遊店」的 `booking_shops.id` 為 `shop_id`，寫入：

| 資料表 | 必要內容 |
|---|---|
| `booking_business_hours` | 各 `weekday`（0=日）的 `open_time`、`close_time` |
| `booking_closing_hours` | 公休日期與時段（可為空） |
| `booking_tables` | 桌位 `table_code`、`min_capacity`、`max_capacity`、`is_active` |
| `booking_table_links` | 桌位相鄰與 `is_combinable`（不可 `table_a_id = table_b_id`，同一對不可重複） |
| `booking_pricing_rules` | 至少 `WEEKDAY_HOURLY_FEE`、`WEEKEND_HOURLY_FEE` 兩筆的 `price`，否則回 503 `BOOKING_PRICING_NOT_CONFIGURED` |

## 2. 啟動服務

```bash
uv run uvicorn app.main:create_app --factory --port 8000
```

另開一個終端機，確認服務與資料庫正常（回應 `{"status":"ok","database":"up"}`）：

```bash
curl -s localhost:8000/api/v1/health
```

API 文件在 http://localhost:8000/docs。

## 3. 基礎正向測試案例

先設定共用變數（身分用 `X-Dev-User: <user_uuid>:<role>[:<shop_uuid>]`，UUID 是開發用固定帳號）。
`D` 取下週三（星期三有營業；日期要在今天起 3 個月內）：

```bash
export API=http://localhost:8000/api/v1
export SHOP=44444444-4444-4444-8444-444444444444
export PLAYER="X-Dev-User: 11111111-1111-4111-8111-111111111111:player"
export STAFF="X-Dev-User: 22222222-2222-4222-8222-222222222222:shop_staff:$SHOP"
export D=$(date -d "next wednesday +7 days" +%F)
```

| # | 案例 | 指令 | 預期 |
|---|---|---|---|
| 1 | 預估費用 | 見下方 | 200，4 人 2 小時平日費用 480.00，不會建立訂位 |
| 2 | 建立訂位 | 見下方 | 201，`status` 為 `confirmed`，有 `reservation_code` 與配到的桌位 |
| 3 | 查詢單筆 | 見下方 | 200，內容與步驟 2 相同 |
| 4 | 修改訂位 | 見下方 | 200，時間延後 30 分鐘，`notice` 有修改提醒 |
| 5 | 我的訂位清單 | 見下方 | 200，`total` ≥ 1 |
| 6 | 店員看板 | 見下方 | 200，看得到該筆訂位 |
| 7 | 店員標記入座 | 見下方 | 200，`status` 為 `seated`，有 `seated_at` |
| 8 | 店員完成結算 | 見下方 | 200，`status` 為 `completed`，有 `final_fee`（此例入座後馬上完成，4 人以 1 小時計為 240.00） |
| 9 | 批次建立 | 見下方 | 201，同日兩個時段建立兩筆訂位 |
| 10 | 取消訂位 | 見下方 | 200，`status` 為 `cancelled`（開始前取消） |

```bash
# 1. 預估費用
curl -s -X POST $API/booking-quotes -H "$PLAYER" -H 'Content-Type: application/json' -d '{
  "shop_id": "'$SHOP'", "party_size": 4,
  "slots": [{"start_at": "'$D'T14:00:00+08:00", "end_at": "'$D'T16:00:00+08:00"}]}' | jq

# 2. 建立訂位（記下 id）
BOOKING=$(curl -s -X POST $API/bookings -H "$PLAYER" -H 'Content-Type: application/json' -d '{
  "shop_id": "'$SHOP'", "party_size": 4, "special_requests": "靠窗",
  "slots": [{"start_at": "'$D'T14:00:00+08:00", "end_at": "'$D'T16:00:00+08:00"}]}' \
  | jq -r '.items[0].id')
echo $BOOKING

# 3. 查詢單筆
curl -s $API/bookings/$BOOKING -H "$PLAYER" | jq

# 4. 修改訂位：延後 30 分鐘
curl -s -X PATCH $API/bookings/$BOOKING -H "$PLAYER" -H 'Content-Type: application/json' -d '{
  "start_at": "'$D'T14:30:00+08:00", "end_at": "'$D'T16:30:00+08:00"}' | jq '{status, start_at, notice}'

# 5. 我的訂位清單
curl -s "$API/bookings?page=1&page_size=20" -H "$PLAYER" | jq '.total'

# 6. 店員看板（依日期範圍）
curl -s -G $API/shops/$SHOP/bookings -H "$STAFF" \
  --data-urlencode "from=${D}T00:00:00+08:00" --data-urlencode "to=${D}T23:59:59+08:00" | jq '.total'

# 7. 店員標記入座
curl -s -X PATCH $API/bookings/$BOOKING -H "$STAFF" -H 'Content-Type: application/json' \
  -d '{"status": "seated"}' | jq '{status, seated_at}'

# 8. 店員完成結算（final_fee 依實際入座到完成的時間計費，不足 1 小時以 1 小時計）
curl -s -X PATCH $API/bookings/$BOOKING -H "$STAFF" -H 'Content-Type: application/json' \
  -d '{"status": "completed"}' | jq '{status, completed_at, final_fee}'

# 9. 批次建立：同日兩個時段
BATCH=$(curl -s -X POST $API/bookings -H "$PLAYER" -H 'Content-Type: application/json' -d '{
  "shop_id": "'$SHOP'", "party_size": 2,
  "slots": [
    {"start_at": "'$D'T18:00:00+08:00", "end_at": "'$D'T19:30:00+08:00"},
    {"start_at": "'$D'T20:00:00+08:00", "end_at": "'$D'T21:30:00+08:00"}]}')
echo $BATCH | jq '.items | length'

# 10. 取消第一筆批次訂位
CANCEL=$(echo $BATCH | jq -r '.items[0].id')
curl -s -X PATCH $API/bookings/$CANCEL -H "$PLAYER" -H 'Content-Type: application/json' \
  -d '{"status": "cancelled"}' | jq '{status, cancelled_at}'
```

## 4. 重複執行與清理

- 步驟 2 與步驟 9 若時段與玩家既有的有效訂位重疊，會回 409 `BOOKING_OVERLAP_CONFIRM_REQUIRED`；重跑時換一個日期（把 `D` 往後延一週），或在請求加上 `"confirm_overlap": true`（會取消舊訂位）。
- 想清掉測試訂位：在開發資料庫對 `booking_reservation_logs`、`booking_reservation_tables`、`booking_reservations` 執行 `TRUNCATE ... CASCADE`。

## 5. 自動化測試

```bash
# DATABASE_URL 不要帶 options=，測試會自己建立 `<資料庫名>_test`（例如 `tabletop_hub_tw_test`）
uv run pytest
```
