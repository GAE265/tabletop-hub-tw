## Why

店員與玩家目前只能看到訂位的文字列表，無法透過座位圖直觀了解各桌的即時佔用狀態。加上座位圖能讓店員快速判斷空桌、安排客人入座，也讓玩家確認自己當天訂位的桌位位置。

## What Changes

- `seating_tables` 資料表擴充：新增 `floor`（樓層，1=1F、-1=B1）、`x`、`y`、`width`、`height`（固定邏輯畫布 1000×700 的座標）、`shape`（固定 `rectangle`），不加入 rotation。
- 移除 `seating_tables_rel.distance` 欄位（尚未實際使用，直接不新增），維持以 `is_combinable` 手動標註可併桌。
- 新增 API `GET /api/v1/shops/{shop_id}/tables/status?from=&to=&floor=`，回傳指定樓層所有桌子的座標與該時段的佔用狀態（`available`／`unavailable`）。時間範圍可選：有帶 `from`/`to` 時查該範圍，未帶時查整天。
- 前端店員看板 prototype：`InteractiveViewer + Stack + Positioned` 座位圖，可縮放平移、點擊桌子查看詳情，桌子依狀態著色。
- 前端客人訂位查詢 prototype：顯示座位圖，標示 available / unavailable / 自己的訂位位置。
- 測試資料：覆蓋 1F（A–G）與 B1（H–I）共 9 張桌的虛構配置，結構（容量、相鄰）與真實店家相同。

## Capabilities

### New Capabilities
- `seating-plan-api`: 桌子狀態查詢 API，回傳樓層、座標、形狀與時段佔用狀態
- `seating-plan-ui`: Flutter 座位圖元件與店員／客人看板 prototype

### Modified Capabilities
- `database-baseline`: `seating_tables` 新增 `floor`、`x`、`y`、`width`、`height`、`shape` 欄位

## Impact

- Domain: `booking`（瑋鋐），含 migration（需瑋鋐審核）
- 前端 prototype: `booking`（功能負責人）+ 交接說明給永傑
- 共用表 `seating_tables` 結構變更：依 D2 的原則，擴充欄位而非重建
- API 契約變更：新增端點，需 @ 立倫（系統整合）
- 不影響現有訂位建立、桌位分配邏輯（`allocation.py` 只用到 `max_capacity` 與 `is_active`，新增欄位不改變行為）
