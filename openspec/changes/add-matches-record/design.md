# Design

## Context

- 目前沒有 `matches` domain。`groups`（已有 models／repository／service／router）是最近的分層範例。
- 共用表 `games` 的主鍵是 `bigint`（4.4 例外），`booking_shops`、`auth_users` 是 UUID。`games.result_type`（`faction`／`score`／`cooperative`，可為空）已合併進 `dev`（migration `0004`）。`groups` 資料表（`0003`）與 booking 的資料表（`0005_booking_tables`）也已在 `dev`。**本分支已包含它們（dev 之後又新增了 `0006_games_manual`、`0007_group_games`、`0008_rules_qa_tables`、`0009_groups_table_comments`），migration 為 `0010`，接在 `0009` 後面**，`alembic heads` 只有一個 head。
- `games.bgg_id` 有 unique 限制，`english_name` 沒有；`GameRepository.delete_games_except` 遇到外鍵會拋 `GameInUseError`，新增 `matches.game_id` 外鍵後同步刪除遊戲會被擋下（符合預期）。
- 開發期間不需要登入：`AUTH_MODE=dev` 時 `get_current_user` 沒帶標頭就是預設測試玩家，所以「未登入 401」不在本 change 的情境表（jwt 模式還沒做）。
- AGENTS.md 4.4（1.10 版）要求每張表、每個欄位都用 `comment=` 寫中文說明，Enum 每個值要有中文註解。

## Goals / Non-Goals

**Goals:**
- 一人記錄、其他人用 GET 重新查詢；不做即時推送。
- 遊戲特有的內容（回合內容、陣營）用「每款遊戲一份定義」放在程式裡，日後新增遊戲不用改資料表。
- 先完成後端（測試先、程式後），前端參考畫面等後端完成再做。

**Non-Goals:**
- 成就、天梯、拍照算分、其他遊戲的回合格式、`score`／`cooperative` 的結果記法、修改參加者資料（換名字、換座位）、正式頁面。

## Decisions

### D1 回合用 `turn`（已決定）
術語表（10.2）：`turn`＝輪到某位玩家行動的期間；`round`＝所有玩家各輪過一次。白薔薇 5 人局的 5 次，每次由一位玩家主導，一次就是一個回合。所以表名 `match_turns`、欄位 `turn_number`（從 1 開始）。畫面文字用「回合」，符合術語表即可。日後有遊戲需要整輪紀錄，再另加可空的 `round_number`。

### D2 資料表
三張表，主鍵 `id` 為 UUID（`server_default gen_random_uuid()`）。每張表用 `__table_args__` 的 `comment`、每個欄位用 `comment=` 寫中文說明（以下「說明」欄就是 comment 的內容方向）。表名在建表前要先在群組告知（4.4）。

**`matches`（一局）**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid PK | 一局的編號 |
| `game_id` | bigint FK `games.id`，非空，RESTRICT | 玩的是哪一款遊戲 |
| `played_on` | date，非空 | 這局進行的日期 |
| `location_type` | text，非空，CHECK `shop`／`home` | 地點類型：shop＝桌遊店，home＝自家 |
| `shop_id` | uuid FK `booking_shops.id`，可空 | 桌遊店；自家時為空（自家不需要地址）。CHECK：`location_type='shop'` 才有值 |
| `group_id` | uuid FK `groups.id`，可空，ON DELETE SET NULL | 所屬揪團；不一定屬於揪團，空值代表不是揪團開的局或揪團已被刪除。comment：「所屬揪團；不一定屬於揪團」 |
| `created_by` | uuid FK `auth_users.id`，非空 | 開局的人（開局者）；開局時自動成為參加者 |
| `status` | text，非空，CHECK `in_progress`／`finished` | 進行中或已結束；已記錄結果即為 finished |
| `result` | jsonb，可空 | 結果，含 `type`（例如 `{"type":"faction","winning_faction":"rose"}`）；尚未記錄結果時為空。CHECK：`status='finished'` 才有值 |
| `progress` | text，可空 | 合作遊戲玩到哪個進度（例如「第五關」）；非合作遊戲或沒填為空 |
| `created_at`／`updated_at` | timestamptz | 建立／最後更新時間 |

**`match_participants`（參加者）**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid PK | 參加者的編號 |
| `match_id` | uuid FK `matches.id` CASCADE | 屬於哪一局 |
| `seat_number` | integer，CHECK >= 1 | 座位編號，從 1 開始；回合紀錄用它指出是誰 |
| `user_id` | uuid FK `auth_users.id`，可空 | 帳號；玩家在 App 按加入才有，沒有帳號的人為空（不以名字比對帳號） |
| `display_name` | text，非空 | 顯示名稱；有帳號時取自帳號當下的名稱，沒有帳號時是輸入的名字（例如 Amy） |
| `faction` | text，可空 | 陣營（結果類型為 faction 時，記錄結果時填入）；尚未記錄為空 |
| `score` | integer，可空 | 分數；不計分的遊戲存空值，**不存 0** |
| `placement` | integer，可空，CHECK >= 1 | 名次；不排名的遊戲為空（不用 `rank`，避免與 SQL 排名函式混淆） |
| `is_winner` | boolean，可空 | 是否獲勝；尚未記錄結果時為空（不是 false） |
| `is_confirmed` | boolean，非空，預設 false | 本人是否已確認這局的紀錄；沒有帳號的參加者永遠是 false 且不計入確認人數 |
| `confirmed_at` | timestamptz，可空 | 確認的時間 |

約束：`UNIQUE(match_id, seat_number)`、`UNIQUE(match_id, user_id)`（PostgreSQL 的 unique 允許多個 NULL，所以可有多位沒有帳號的參加者）。

**`match_turns`（回合紀錄，選填）**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid PK | 回合紀錄的編號 |
| `match_id` | uuid FK `matches.id` CASCADE | 屬於哪一局 |
| `turn_number` | integer，CHECK >= 1 | 第幾個回合，從 1 開始 |
| `seat_number` | integer，非空 | 這個回合由哪個座位的玩家主導 |
| `game_data` | jsonb，非空 | 這款遊戲特有的內容，格式由程式裡該遊戲的定義決定 |
| `recorded_by` | uuid FK `auth_users.id`，非空 | 最後一次寫入這筆紀錄的人（覆蓋時換成覆蓋的人） |
| `created_at`／`updated_at` | timestamptz | 建立／最後更新時間 |

約束：`UNIQUE(match_id, turn_number)`。`seat_number` 與 `game_data.played_seat_numbers` 不加外鍵（座位在 `match_participants`，由 service 檢查存在；移除參加者時由 service 檢查是否被引用，見 D11）。

**Enum（4.4：每個值有中文註解，說明代表什麼、何時使用、舉遊戲為例）**：`MatchStatus`（`in_progress`、`finished`）、`LocationType`（`shop`、`home`）、`WhiteRoseFaction`（`rose`、`blood_blade`）。

### D3 每款遊戲一份定義（程式裡）
`domains/matches/game_definitions.py`，以 `games.bgg_id`（unique）為鍵。一份定義包含：回合 `game_data` 的 Pydantic 模型（`extra="forbid"`）、陣營 Enum。白薔薇：
- `game_data`：`played_seat_numbers`（出牌的座位編號清單，至少一個、不可重複，座位存在與否由 service 對照這局的參加者檢查）、`double_blade_count`、`dark_blade_count`、`giant_blade_count`、`faithful_count`（>= 0 整數）、`has_white_rose`（布林）。幽魂不記。
- 陣營：`rose`（薔薇陣營）、`blood_blade`（血刃陣營）。

沒有定義的遊戲：記錄回合回 422 `MATCH_TURN_NOT_SUPPORTED`；`faction` 結果同樣需要定義，缺少時回 `MATCH_RESULT_TYPE_NOT_SUPPORTED`。白薔薇的 `bgg_id` 於實作第一步從匯入的 `games.json` 查出，不寫死猜測的數字。

### D4 API
遵守 4.3：名詞複數、最多兩層、動作用方法表達、錯誤格式統一。日期與時間 ISO 8601／UTC，欄位 `snake_case`。

| 方法與路徑 | 說明 | 成功 |
|---|---|---|
| `POST /api/v1/matches` | 開局 | 201 |
| `GET /api/v1/matches?game_id&group_id&user_id&page&page_size` | 列表 | 200 |
| `GET /api/v1/matches/{match_id}` | 查詢一局（含參加者、回合、人數統計） | 200 |
| `POST /api/v1/matches/{match_id}/participants` | 加入參加者 | 201 |
| `PATCH /api/v1/matches/{match_id}/participants/{participant_id}` | 確認 | 200 |
| `DELETE /api/v1/matches/{match_id}/participants/{participant_id}` | 移除參加者（退出） | 204 |
| `POST /api/v1/matches/{match_id}/turns[?overwrite=true]` | 記錄回合 | 201／覆蓋 200 |
| `PUT /api/v1/matches/{match_id}/result[?overwrite=true]` | 記錄結果 | 200 |

請求與回應範例：

```jsonc
// POST /api/v1/matches   （seat_number 選填，開局者自己選座位）
{ "game_id": 12, "played_on": "2026-11-20", "location_type": "shop",
  "shop_id": "5b0d…", "group_id": null, "seat_number": 2 }
// 201（也是 GET /matches/{id} 的格式）
{ "id": "a1…", "game": {"id": 12, "name": "血與刃的白薔薇"}, "played_on": "2026-11-20",
  "location_type": "shop", "shop": {"id": "5b0d…", "name": "測試桌遊店"}, "group_id": null,
  "created_by": {"id": "u1…", "display_name": "小明"}, "status": "in_progress",
  "result": null, "progress": null,
  "participants": [ {"id": "p1…", "seat_number": 2, "user_id": "u1…", "display_name": "小明",
                     "faction": null, "score": null, "placement": null,
                     "is_winner": null, "is_confirmed": false} ],
  "turns": [], "participant_count": 1, "account_count": 1, "confirmed_count": 0, "is_valid": false }

// POST …/participants：自己加入 {}  或  {"seat_number": 3}
// 有帳號的參加者新增沒有帳號的人
{ "display_name": "Amy", "seat_number": 3 }

// POST …/turns
{ "turn_number": 1, "seat_number": 2,
  "game_data": { "played_seat_numbers": [2, 3], "double_blade_count": 1, "dark_blade_count": 1,
                 "giant_blade_count": 0, "faithful_count": 2, "has_white_rose": false } }
// 201 → { "id": "t1…", "turn_number": 1, "seat_number": 2, "game_data": {…},
//         "recorded_by": "u1…", "updated_at": "2026-11-20T12:00:00Z" }
// 同一回合已有紀錄 → 409
{ "error": { "code": "MATCH_TURN_ALREADY_RECORDED", "message": "第 1 回合已經有紀錄",
             "details": { "existing": { "turn_number": 1, "seat_number": 2, "game_data": {…},
                                         "recorded_by": "u9…" } } } }
// 前端提示「已經有人記錄了，要更新嗎？」，確認後 POST …/turns?overwrite=true → 200

// PUT …/result
{ "winning_faction": "rose",
  "participants": [ {"seat_number": 2, "faction": "rose"}, {"seat_number": 3, "faction": "blood_blade"} ] }

// PATCH …/participants/{participant_id}
{ "is_confirmed": true }

// DELETE …/participants/{participant_id} → 204；座位已出現在回合 → 409
{ "error": { "code": "MATCH_PARTICIPANT_HAS_TURNS", "message": "座位 3 已出現在第 1、4 回合",
             "details": { "seat_number": 3, "turn_numbers": [1, 4] } } }
```

錯誤代碼（皆由 service 拋 `AppError`）：
- 404：`MATCH_NOT_FOUND`、`MATCH_GAME_NOT_FOUND`、`MATCH_SHOP_NOT_FOUND`、`MATCH_GROUP_NOT_FOUND`、`MATCH_PARTICIPANT_NOT_FOUND`
- 409：`MATCH_SEAT_TAKEN`、`MATCH_ALREADY_JOINED`、`MATCH_FINISHED`、`MATCH_TURN_ALREADY_RECORDED`、`MATCH_RESULT_ALREADY_RECORDED`、`MATCH_RESULT_NOT_RECORDED`、`MATCH_GAME_RESULT_TYPE_NOT_SET`、`MATCH_PARTICIPANT_HAS_TURNS`
- 422：`VALIDATION_ERROR`、`MATCH_SEAT_NOT_FOUND`（回合或結果的座位不存在，`details.seat_numbers`）、`MATCH_RESULT_SEATS_INCOMPLETE`（結果少了座位，`details.missing_seat_numbers`）、`MATCH_TURN_NOT_SUPPORTED`、`MATCH_RESULT_TYPE_NOT_SUPPORTED`
- 403：`PermissionDenied`

### D5 權限（已決定，記錄權限依「有帳號的參加者」）
| 操作 | 誰可以 |
|---|---|
| 開局、查詢、列表 | 任何已登入使用者（查詢開放，玩家才能先看到再按加入） |
| 自己加入 | 任何已登入使用者（進行中的局） |
| 新增沒有帳號的參加者 | 這局有帳號的參加者、admin |
| 移除參加者 | 有帳號的參加者可移除自己；這局有帳號的參加者可移除沒有帳號的人與其他參加者；admin |
| 記錄回合（含覆蓋） | 這局有帳號的參加者、admin |
| 記錄結果（含覆蓋） | 這局有帳號的參加者、admin |
| 確認 | 該參加者本人、admin |

「開局者」（`created_by`）只是紀錄誰開的局，沒有額外權限。service 用一個「目前使用者是不是這局有帳號的參加者」的判斷（admin 例外）統一處理，附 403 測試案例（4.5）。

### D6 覆蓋機制
- 覆蓋用 query 參數 `overwrite=true`，不放 body：同一份內容重送、只多一個參數，前端狀態機單純。
- 先查再寫有競爭：兩個請求同時新增同一回合，靠 `UNIQUE(match_id, turn_number)` 擋下，service 捕捉違反唯一限制並轉成 409；寫入前對該局的 `matches` 那一列取鎖（`SELECT … FOR UPDATE`，與 groups 的 `lock_group` 同做法），也讓「移除參加者」與「新增回合」不會交錯。
- 結果覆蓋（`PUT …/result?overwrite=true`）：除了這次覆蓋的人，所有參加者的 `is_confirmed`／`confirmed_at` 清除，覆蓋的人自動算已確認。若覆蓋的是 admin 且不是參加者，則全部清除、沒有人被自動確認。

### D7 確認與有效紀錄
- 開局時所有人都未確認（還沒有結果，不能確認）。記錄結果的人自動算已確認。
- `is_valid` 不存資料庫，查詢時計算：`status=finished` 且 `confirmed_count == account_count`，避免儲存值與確認狀態不同步。
- 只能確認為 true，不做取消確認。

### D8 共用表只新增「讀取」方法（已決定）
依 4.2，共用表的 repository 由擁有者建立；非擁有者（本 change）代為新增、**只加讀取、不加寫入**，MR 說明 @ 擁有者：
- `GameRepository.get_game(game_id)`（`core/games/repository.py`，立倫）：回 `id`、`name`、`bgg_id`、`result_type`，不存在回 None。
- `BookingRepository.get_shop(shop_id)`（`domains/booking/repository.py`，瑋鋐；booking 已合併，`booking_shops` 的讀取本來就在這個 repository，所以在既有類別加方法，不另建新類別）：回 `ShopRef`（`id`、`name`）。
- `AuthUserRepository.get_user(user_id)`（`domains/auth/repository.py`，新檔，立倫）：回 `id`、`display_name`。

`matches` 的列表與詳細查詢 JOIN 共用表取名稱，屬於 `matches` repository 自己的查詢，只讀不改，不另外建立共用表的 model。揪團存在檢查呼叫 `groups` 的 service，把 `GROUP_NOT_FOUND` 轉成 `MATCH_GROUP_NOT_FOUND`。
注意：已合併的 `groups` 在自己的 `domains/groups/repository.py` 寫了 `shop_exists`（第 89 行）、`game_exists`（第 93 行），並 JOIN `booking_shops`、`auth_users`、`games` 取名稱。本 change 新增共用表的讀取方法後，同一張表會同時有 `groups` 與共用 repository 兩處查詢（4.2 要求一張表一個 repository）。本 change 不改 `groups`；建議事後由 `groups` 主責（永傑）改用共用方法，MR 說明提醒。

### D9 `games.result_type` 為空時（已決定，方案 B）
開局與記錄回合照常可用；**記錄結果時**才檢查 `games.result_type`，為空回 409 `MATCH_GAME_RESULT_TYPE_NOT_SET`。`score`、`cooperative` 本次回 422 `MATCH_RESULT_TYPE_NOT_SUPPORTED`。

### D10 分層與前端
- 後端 `domains/matches/`：`router.py`、`schemas.py`、`service.py`、`repository.py`、`models.py`、`game_definitions.py`。依賴方向 `router → service → repository → models`；service 不 import FastAPI；router 取得 `CurrentUser` 後傳給 service。
- 測試：service 用手寫 `FakeMatchesRepository`（7.5）；API 測試連 `_test` 資料庫，權限用 `as_player`、`as_shop_staff`、`as_admin`。`main.py` 要掛載 router（立倫的共用區，MR @ 立倫）；`tests/conftest.py` 的 `TRUNCATE … CASCADE` 會連帶清掉 matches 的三張表，不用改。
- 前端（後端完成後才做）：`domains/matches/data/`（freezed DTO、`MatchesRepository`、`HttpMatchesRepository`）、`state/`（`MatchNotifier`：載入、重新整理、各操作、「待確認覆蓋」狀態）、`prototypes/matches/`。不碰 `pages/`、`app/theme/`。`app/router.dart` 加 `/proto/matches` 一行（永傑的共用區，MR @ 永傑）。

### D11 移除參加者
- 已結束的局不能移除（409 `MATCH_FINISHED`）。
- 要移除的座位只要出現在這局任何回合的 `seat_number` 或 `game_data.played_seat_numbers`，就回 409 `MATCH_PARTICIPANT_HAS_TURNS`，`details` 列出座位與回合編號；要先覆蓋那些回合（改掉座位）才能移除。
- 檢查在 service 取鎖後，用 repository 的查詢找出引用該座位的回合（JSONB 陣列包含查詢，例如 `game_data->'played_seat_numbers' @> '[3]'`）。
- 座位空出後可被別人使用；不改其他人的座位。
- 沒有「修改參加者」API（換名字、換座位）：要換就移除再加；已出現在回合的座位不能這樣做，屬於預期限制。

## Risks / Trade-offs

- [揪團被刪除後 `matches.group_id` 變空值，這局失去與揪團的關聯] → 預期行為（`SET NULL`，比照 `groups.game_id`），這局與其紀錄保留。
- [`games` 同步刪除遊戲會被 `matches` 外鍵擋下] → 預期行為，`GameInUseError` 已處理；MR 說明提醒立倫。
- [`game_definitions` 以 `bgg_id` 為鍵，遊戲資料重新匯入時 `bgg_id` 變動會失效] → `bgg_id` 有 unique 且是外部穩定編號；缺定義時回 422 而不是壞掉。
- [`game_data` 格式日後要改] → JSONB，舊紀錄不會被 migration 破壞；改格式時另提 change 處理舊資料相容。例如這次新增的 `played_seat_numbers` 在更早的資料不存在，但目前沒有舊資料。
- [任何已登入的人能查詢任何一局] → 戰績不含敏感資料；日後要限制再加條件，不影響現有路徑。
- [任何有帳號的參加者都能覆蓋結果、移除別人] → 覆蓋會清除他人確認、結果已結束後不能移除；沒有稽核紀錄，惡意操作靠組內信任（Demo 範圍）。
- [最後一位有帳號的參加者退出後，這局沒有人能再修改（admin 例外）] → 見下方待確認。
- [不做即時推送] → 其他人要手動刷新，符合已確認的設計。
- [共用表讀取方法與已合併的 `groups` repository 重複] → 見 D8 的說明，本 change 不動 `groups`。

## Migration Plan

1. 本分支已包含 `0003`（groups）、`0004`（games.result_type）、`0005`（booking），`0010` 的 `down_revision = "0009"`。
2. 新增 migration `0010_matches_tables`（`down_revision = "0009"`）：建立三張表（含表與欄位 comment、CHECK、UNIQUE）；`downgrade` 依序刪除 `match_turns`、`match_participants`、`matches`。
3. 欄位 comment 在 migration 與 model 兩處一致；測試檢查非空且為中文。
4. 一個 MR 只含一個 migration（4.4），由瑋鋐審核；建表前先在群組告知三個表名。
5. 回滾：`alembic downgrade -1`，沒有資料搬移，風險低。

## Open Questions

- 最後一位有帳號的參加者要退出時，要不要擋下（409 `MATCH_LAST_ACCOUNT_PARTICIPANT`）？建議擋，否則這局之後沒有人有權限修改。這會新增一個 scenario，尚未寫進 spec，等確認。
- 「自家」以後要不要讓使用者命名（例如「Amy 家」）：這次只存 `location_type=home`，日後可加可空的 `location_note`，不影響現有欄位。
- 白薔薇在資料庫的 `bgg_id`（tasks 1.1 查出即可，不影響規格）。
