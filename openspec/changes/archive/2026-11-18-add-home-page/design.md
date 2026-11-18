# Design

## Context

- 前端：Flutter 3.41.4、Riverpod 3、go_router（`ShellRoute` 包住所有頁面，框架在 `app/shell.dart`）。
- 主題 token 在 `app/theme/`（`AppSpacing`、`AppSizes`、`AppColors`、`PillBadge`），斷點在 `core/layout/`（`context.screenSize`）。
- 首頁要讀兩個 domain 的資料：
  - `booking`：`BookingRepository.listMine({status, from, to, page, pageSize})`、`listShops()`（`booking/data/`，瑋鋐）。
  - `groups`：`GroupsRepository.list({startFrom, startBefore, organizerId, page, pageSize})`，回應每筆有 `myStatus`、`memberCount`、`capacity`、`remainingSlots`（`groups/data/`，永傑）。

### 現有後端 API 是否足夠（查證結果）

| 需要 | 現有 API | 夠不夠 |
|---|---|---|
| 我即將到來的訂位 | `GET /api/v1/bookings?status=confirmed&from=<今天>`（前端 `listMine` 固定取第一頁 50 筆） | **勉強夠**。排序是開始時間**由新到舊**（`start_at desc`），最近的一筆可能在後面的分頁；`from` 以資料庫的日期（UTC）比較，不是台灣日期。Demo 資料量小，取第一頁後在前端排序、過濾掉已經開始的即可。 |
| 店家人員的訂位 | 同上 | **不夠**。`list_mine` 只允許 `player`、`admin`，店家人員回 403；首頁當作「沒有訂位」處理。 |
| 訂位的店家名稱 | `GET /api/v1/shops` | 夠。訂位只回 `shop_id`，用店家清單對應名稱；對不到時只顯示桌號。 |
| 我已報名的揪團 | `GET /api/v1/groups?start_from=<現在>&page_size=100` | **勉強夠**。沒有「我已加入」的篩選（只有 `organizer_id`），要取回所有即將開始的揪團，再用 `my_status` 在前端過濾；即將開始的揪團超過 100 筆時會漏掉。排序由近到遠、已排除取消的揪團，這點符合需要。 |

結論：**不改後端也做得出來，Demo 的資料量下結果正確**；但有兩個缺口（見 Open Questions），資料變多後需要後端補強。依指示不自行修改後端。

## Goals / Non-Goals

**Goals**
- `/` 換成首頁；主要導覽列取代 `_TemporaryNav`。
- 「接下來的行程」用現有 API 完成，三種狀態只影響行程區。
- 樣式全部取自 `app/theme/`，頁面不寫死顏色、字級、間距。

**Non-Goals**
- 修改後端（訂位排序、店家人員的訂位、「我已加入的揪團」篩選）。
- 登入功能、角色分流、戰績與天梯。
- 行程列點進去直接打開該筆訂位或揪團的詳細頁（揪團詳細頁目前是從月曆用 `Navigator` 推出，沒有獨立路由；先導到列表頁）。

## Decisions

### 1. 首頁程式放在 `frontend/lib/app/home/`（建議，待確認）

| 選項 | 優點 | 缺點 |
|---|---|---|
| **A. `lib/app/home/`（建議）** | `app/` 是「進入點、路由表、主題」，首頁與導覽列都是整個 App 的組裝，不屬於任何業務 domain；擁有者是永傑，不用 @ 別人；不新增頂層資料夾 | `app/` 裡會有 state 與頁面，比原本多一點東西 |
| B. `lib/domains/home/` | 結構和其他頁面一樣（`state/`、`pages/`） | AGENTS.md 第 3 節規定前端 domain 名稱要與後端相同，`home` 不是後端 domain，等於自己新增一個 domain |
| C. `lib/core/home/` | — | `core/` 放的是共用元件與工具，不是頁面 |

選 A 時的檔案配置（內部仍依 5.3 分層：頁面不直接呼叫 API、操作邏輯在 state）：

```
frontend/lib/app/
├── home/
│   ├── state/upcoming_state.dart   # 合併訂位與揪團、排序、取 5 筆；處理 403
│   └── pages/
│       ├── home_page.dart          # 首頁
│       └── widgets/home_widgets.dart  # 入口卡片、行程列
├── navigation.dart                 # 主要導覽列（底部／頂部）
├── shell.dart                      # 改用 navigation.dart，刪除 _TemporaryNav
└── router.dart                     # `/` → HomePage；HealthPage 移到 `/health`
```

### 2. 首頁讀其他 domain 的資料：直接使用對方的 `data/` repository provider

- AGENTS.md 4.2「domain 之間只能呼叫對方的 service」是後端規則；前端沒有對應的規定。各 domain 的 `state/` 都是為自己的頁面設計（例如 `bookingProvider` 會在畫面上顯示錯誤訊息），首頁拿來用會互相干擾。
- 因此 `upcoming_state.dart` 只讀 `bookingRepositoryProvider` 與 `groupsRepositoryProvider`（唯讀、不改對方程式），測試用 `frontend/test/support/fakes.dart` 既有的 `FakeBookingRepository`、`FakeGroupsRepository` 覆寫。
- 目前使用者：watch `groups` 的 `currentUserIdProvider`（取自 `currentDevUserProvider`），切換身分時重新載入。
- 測試：`FakeBookingRepository` 新增 `mineError`、`mineGate`、`mineCalls`（`test/support/fakes.dart`，MR 說明 @ 瑋鋐）。

### 3. 「接下來的行程」的資料規則

- 「現在」用 `groups` 的 `groupClockProvider`（可在測試固定時間），日期以台灣時間顯示。
- 訂位：`status=confirmed`、`from=<台灣今天>`（`listMine` 固定 50 筆，`booking/data/` 不修改），前端再過濾 `status == confirmed` 與 `startAt > 現在`。403（`ApiException.statusCode == 403`）視為沒有訂位。
- 揪團：`startFrom=現在`、`pageSize=100`，過濾 `myStatus in {member, waitlisted}`。
- 兩邊合併後依開始時間排序，取前 5 筆。兩個請求同時發出；任一個失敗（403 以外）整區顯示錯誤與重試。

### 4. 導覽列

- 手機（`ScreenSize.mobile`）用 Material 3 `NavigationBar` 放在底部；平板與桌機在頂部放一列按鈕（選取項目用主題的選取色），樣式全部來自主題。
- 選取規則：首頁只在路徑剛好是 `/` 時選取；其他項目在路徑等於或以 `<項目>/` 開頭時選取。由 `GoRouterState.of(context).uri.path` 判斷，判斷函式放在 `navigation.dart` 並有單元測試。
- 沿用既有的 Key（`shell-nav-home` 等），`router_test.dart` 既有的「畫面框架的入口」測試不用改。

### 5. 登入按鈕

`auth` 尚未完成，按下顯示 SnackBar「登入功能即將推出」，不導頁。

## Risks / Trade-offs

- **取一頁 100 筆再過濾**：資料多時會漏，且多傳資料。→ Demo 可接受；Open Questions 提出後端改善，改好後只需改 `upcoming_state.dart`。
- **`from` 用 UTC 日期比較**：台灣 0–8 點之間的「今天」可能多取到前一天的訂位，前端再用 `startAt > 現在` 過濾，所以結果正確。
- **既有測試要調整**：`router_test.dart` 的「首頁是套主題的正式 health 頁面」改成「首頁是 HomePage、`/health` 是 health 頁面」。這是本次需求造成的路由變動，MR 說明會寫出理由。

## Migration Plan

- 純前端，無資料遷移。組員拉 `dev` 後不需要額外指令。
- 回復方式：revert 該 MR 即可。

## Open Questions

1. **首頁程式位置**：照 Decision 1 選 A（`lib/app/home/`）可以嗎？
2. **後端缺口要不要處理**（不在本 change 內，由組員決定是否另開）：
   - `groups`（永傑）：`GET /api/v1/groups` 加「我已加入」的篩選（例如 `member=me`）。
   - `booking`（瑋鋐）：`GET /api/v1/bookings` 提供由近到遠的排序（或 `upcoming` 篩選），並決定店家人員要不要能看自己的訂位。
