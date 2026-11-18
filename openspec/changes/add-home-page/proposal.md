# Proposal

## Why

目前路由 `/` 掛的是 `HealthPage`（後端健康檢查示範頁），頁面之間靠 `app/shell.dart` 的 `_TemporaryNav` 暫時切換。Demo 給評審看時，第一個畫面應該讓人馬上知道這個平台能做什麼，並最快走到下一步。設計說明見 `docs/handoff/home.md`，設計稿見 https://claude.ai/artifact/S9Bz8X4Fn7ttbDQT4dzVip。

## What Changes

- **首頁 `/`**（所有角色同一個畫面）：
  - 頂部：品牌名「遊任有娛」、登入按鈕（登入屬於 `auth` 階段 3，按下先提示「登入功能即將推出」）。
  - 主標「今天想怎麼玩？」與副標。
  - 四張入口卡片：今天玩什麼？（`/games-advisor`）、找人一起玩（`/groups`）、訂個位子（`/booking`）、這遊戲怎麼玩（`/rules`）。手機 2×2，平板以上一橫列、窄時自動換行。
  - 接下來的行程：我即將到來的訂位與已報名的揪團，依時間排序，各一列；有載入中、沒有資料、錯誤三種狀態，只影響這一區。
- **主要導覽列**取代 `_TemporaryNav`：首頁、揪團、推薦、規則、訂位。手機在底部，平板與桌機在頂部；目前所在的頁面有選取樣式。
- **`HealthPage` 移到 `/health`**：只供開發使用，不放進導覽列。
- **不做**：戰績與天梯、健康狀態、角色分流（店家人員專屬首頁）、登入功能本身、後端修改。

## Capabilities

### New Capabilities
- `home-page`：首頁的內容、入口、接下來的行程。

### Modified Capabilities
- `frontend-shell`：新增「主要導覽列」需求，取代暫時的頁面入口。

## Impact

- **受影響範圍**：`frontend/lib/app/`（擁有者永傑，本次明確授權修改）。首頁不屬於 AGENTS.md 第 3 節的任何 domain，程式位置見 design.md 的 Decisions。
- **讀取其他 domain 的資料**（只讀，不修改對方程式）：
  - `booking`（主責瑋鋐）：`BookingRepository.listMine`、`listShops`。
  - `groups`（主責永傑）：`GroupsRepository.list`。
- **後端**：不修改。現有 API 的不足之處列在 design.md 的 Open Questions，由組員決定是否另開 change。
- **契約**：沒有改動（不改 API、資料表、MQTT）；`/` 從健康檢查頁改成首頁、健康檢查頁移到 `/health` 是前端路由的變動。
- **migration**：沒有。
