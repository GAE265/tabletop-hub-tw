# Proposal

## Why

功能 #13「戰績與天梯」的第一步：玩家要能在遊戲進行中，用 App 記錄這局發生了什麼，其他人按刷新就能查看、幫忙覆盤；結束時記錄結果，大家確認後成為有效紀錄。成就與天梯要建立在這份紀錄上，所以先把「記錄一局」做好，demo 遊戲為《血與刃的白薔薇》。

## What Changes

- 新增 `matches` domain 的後端 API（路徑與範例見 design.md D4）：
  - `POST /api/v1/matches`：開局，開局者（`created_by`）自動成為參加者，座位自己選。
  - `GET /api/v1/matches`、`GET /api/v1/matches/{match_id}`：查詢；詳細資料含參加者、回合紀錄、「參加人數／有帳號人數／已確認人數」。其他人用重新查詢取得最新內容，不做即時推送。
  - `POST /api/v1/matches/{match_id}/participants`：加入參加者。玩家自己按加入（有帳號），或有帳號的參加者只寫名字新增沒有帳號的人（例如 Amy）。
  - `DELETE /api/v1/matches/{match_id}/participants/{participant_id}`：移除參加者（退出）。已結束的局不能移除；座位已出現在任何回合時不能移除（409）。
  - `POST /api/v1/matches/{match_id}/turns`：記錄一個回合（白薔薇的內容含 `played_seat_numbers` 出牌座位）。同一回合已有紀錄時回 409，帶 `?overwrite=true` 再送一次才覆蓋。
  - `PUT /api/v1/matches/{match_id}/result`：記錄結果（本次只做結果類型 `faction`）。記錄結果的人自動算已確認；覆蓋結果時清除其他人的確認。
  - `PATCH /api/v1/matches/{match_id}/participants/{participant_id}`：參加者確認。
- 新增三張資料表 `matches`、`match_participants`、`match_turns`（一個 migration，每個欄位有中文 `comment=`）。
- 《血與刃的白薔薇》的回合內容格式與陣營寫在程式裡（每款遊戲一份定義）。
- 共用表 `games`、`booking_shops`、`auth_users` 代為新增「讀取」方法（不加寫入）。
- 新增前端 `frontend/lib/domains/matches/`（`data/`、`state/`）、`prototypes/matches/` 參考畫面、交接說明 `docs/handoff/matches.md`（**等後端完成並經確認後再做**）。
- **不做**：成就、天梯、拍照算分、其他遊戲的回合格式與 `score`／`cooperative` 的結果記法、即時推送、修改參加者資料（換名字、換座位）、正式頁面（`pages/`，永傑負責）。

## Capabilities

### New Capabilities
- `matches-record`：記錄一局遊戲的後端行為（開局、參加者、回合紀錄與覆蓋、結果、確認、查詢、權限）。
- `matches-record-prototype`：前端 `data/`、`state/` 與參考畫面（開局、加入參加者、記錄回合、記錄結果、確認、覆蓋提示）。

### Modified Capabilities
無。（`games.result_type` 的規格屬於另一個 change `add-games-result-type`，本 change 只讀取它。）

## Impact

- **受影響 domain**：`matches`（主責新善，協助永傑、立倫）。
- **相依**：讀取 `games.result_type`，已合併進 `dev`（migration `0004`）。本分支已包含它、groups 的 `0003` 與 booking 的 `0005`，migration 為 `0010`，接在 dev 最新的 `0009` 後面。
- **共用資料表**（第 3 節），只讀取、不改結構：`games`（立倫）、`booking_shops`（瑋鋐）、`auth_users`（立倫）。目前這三張表沒有可供其他 domain 使用的 repository 讀取方法，由本 change 代為新增「讀取」方法，不加寫入（design.md D8），MR @ 立倫、瑋鋐。
- **其他 domain**：`groups` 的揪團（`group_id` 選填，外鍵 `groups.id`、`ondelete=SET NULL`）。透過 `groups` 的 service 確認揪團存在，不直接用其 repository。
- **共用區改動**（第 2 節規則 3，MR 要 @ 擁有者）：`backend/app/main.py` 掛載 router（立倫）；`frontend/lib/app/router.dart` 加 `/proto/matches` 路由（永傑）。
- **契約**：有改動，新增上列 API（要 @ 立倫）。
- **migration**：一個，新增三張表（要 @ 瑋鋐）。建表前先在群組告知表名（4.4）。
- **前端**：新增 `/proto/matches`。MR 加 `needs-ui` 標籤，@ 永傑。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
