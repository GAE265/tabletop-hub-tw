# Spec Delta

## Purpose

揪團與候補（功能 #7）。開團主在某間店家、某個時段發起揪團，玩家報名成為成員；人數額滿後報名的玩家進入候補，成員離開時由候補依報名先後遞補。

## ADDED Requirements

### Requirement: 開團
`POST /api/v1/groups` SHALL 建立一筆揪團並回 201 與揪團資料。必填欄位：`shop_id`、`title`、`start_at`、`end_at`、`capacity`；選填：`fee`（整數，新台幣，>= 0）、`game_id`、`description`。目前使用者成為開團主（`organizer_id`），並且 MUST 自動成為第一位成員，計入人數。所有角色（`player`、`shop_staff`、`admin`）都可以開團。

#### Scenario: 正常開團
- **WHEN** 玩家以 `shop_id`（存在的店家）、`title`、未來的 `start_at`、晚於它的 `end_at`、`capacity=4` 呼叫 `POST /api/v1/groups`
- **THEN** 回 201，body 含 `id`、`organizer.id` 等於目前使用者、`status=open`、`member_count=1`、`waitlist_count=0`、`remaining_slots=3`、`my_status=member`

#### Scenario: 附上選填欄位
- **WHEN** 同上，另帶 `fee=300`、存在的 `game_id`、`description`
- **THEN** 回 201，回應的 `fee`、`game.id`、`game.name`、`description` 與輸入一致

#### Scenario: 店家人員開團
- **WHEN** 以 `as_shop_staff` 開團
- **THEN** 回 201，`organizer.id` 為該店家人員

#### Scenario: 缺少必填欄位
- **WHEN** 不帶 `title`（或 `shop_id`、`start_at`、`end_at`、`capacity` 任一）
- **THEN** 回 422，`error.code=VALIDATION_ERROR`

#### Scenario: 人數上限小於 2
- **WHEN** `capacity=1`
- **THEN** 回 422

#### Scenario: 結束時間不晚於開始時間
- **WHEN** `end_at` 等於或早於 `start_at`
- **THEN** 回 422

#### Scenario: 開始時間已過
- **WHEN** `start_at` 早於現在
- **THEN** 回 422

#### Scenario: 費用為負數
- **WHEN** `fee=-1`
- **THEN** 回 422

#### Scenario: 店家不存在
- **WHEN** `shop_id` 不在 `booking_shops`
- **THEN** 回 404，`error.code=GROUP_SHOP_NOT_FOUND`，不寫入任何資料

#### Scenario: 遊戲不存在
- **WHEN** `game_id` 不在 `games`
- **THEN** 回 404，`error.code=GROUP_GAME_NOT_FOUND`，不寫入任何資料

#### Scenario: 未登入
- **WHEN** 在 `AUTH_MODE=jwt` 下不帶 token 呼叫
- **THEN** 回 401

### Requirement: 查詢揪團列表
`GET /api/v1/groups` SHALL 回 200 與 `{"items": [...], "total": n}`，依 `start_at` 由早到晚排序。查詢參數皆選填：`start_from`、`start_before`（ISO 8601 時間，篩選 `start_from <= start_at < start_before`）、`shop_id`、`organizer_id`、`page`（預設 1）、`page_size`（預設 20，最大 100）。已取消的揪團 MUST NOT 出現在列表中。每一筆的欄位與詳細資料相同（見「揪團資料格式」）。

#### Scenario: 依時間區間查詢
- **WHEN** 有 11/14 和 11/20 各一團，查詢 `start_from=2026-11-14T00:00:00+08:00&start_before=2026-11-15T00:00:00+08:00`
- **THEN** 回 200，只回 11/14 那一團，`total=1`

#### Scenario: 依開團主篩選
- **WHEN** 兩位開團主各開一團，查詢 `organizer_id=<其中一位>`
- **THEN** 只回該開團主的揪團

#### Scenario: 依店家篩選
- **WHEN** 查詢 `shop_id=<某店家>`
- **THEN** 只回該店家的揪團

#### Scenario: 不列出已取消的揪團
- **WHEN** 某團已取消
- **THEN** 列表不包含它，`total` 也不計入

#### Scenario: 分頁
- **WHEN** 有 3 團，查詢 `page=2&page_size=2`
- **THEN** `items` 只有第 3 團，`total=3`

#### Scenario: 沒有符合的揪團
- **WHEN** 查詢的區間內沒有任何揪團
- **THEN** 回 200，`{"items": [], "total": 0}`

#### Scenario: 參數格式錯誤
- **WHEN** `start_from=abc` 或 `page_size=101` 或 `page=0`
- **THEN** 回 422

### Requirement: 揪團資料格式
揪團的回應（新增、詳細、列表、修改）SHALL 包含：`id`、`title`、`description`、`start_at`、`end_at`（UTC，ISO 8601）、`capacity`、`fee`、`status`、`shop`（`id`、`name`）、`organizer`（`id`、`display_name`）、`game`（`id`、`name`，或 `null`）、`member_count`、`waitlist_count`、`remaining_slots`（`capacity - member_count`，最小 0）、`my_status`（目前使用者在此團的狀態：`member`、`waitlisted` 或 `null`）、`created_at`。`status` 為 `open`、`cancelled` 或 `ended`；`ended` 不儲存，由「未取消且 `end_at` 已過」計算。

#### Scenario: 揪團結束後的狀態
- **WHEN** 查詢一個 `end_at` 已過、沒有取消的揪團
- **THEN** `status=ended`

#### Scenario: 額滿時的剩餘名額
- **WHEN** `capacity=2`，已有 2 位成員和 1 位候補
- **THEN** `member_count=2`、`waitlist_count=1`、`remaining_slots=0`

### Requirement: 查詢單一揪團
`GET /api/v1/groups/{group_id}` SHALL 回 200 與揪團資料；已取消的揪團仍可查詢（`status=cancelled`）。

#### Scenario: 正常查詢
- **WHEN** 查詢存在的揪團
- **THEN** 回 200，欄位符合「揪團資料格式」

#### Scenario: 查詢已取消的揪團
- **WHEN** 查詢已取消的揪團
- **THEN** 回 200，`status=cancelled`

#### Scenario: 揪團不存在
- **WHEN** `group_id` 不存在
- **THEN** 回 404，`error.code=GROUP_NOT_FOUND`

#### Scenario: id 格式錯誤
- **WHEN** `group_id` 不是 UUID
- **THEN** 回 422

### Requirement: 修改與取消揪團
`PATCH /api/v1/groups/{group_id}` SHALL 只允許該團的開團主或 `admin` 修改，可修改 `title`、`description`、`start_at`、`end_at`、`capacity`、`fee`、`game_id`，或帶 `{"status": "cancelled"}` 取消。成功回 200 與修改後的揪團資料。驗證規則與開團相同。已取消或已結束的揪團 MUST NOT 再修改。調高 `capacity` 時，候補 SHALL 依報名先後自動遞補到新增的名額。

#### Scenario: 開團主修改標題
- **WHEN** 開團主 `PATCH {"title": "新標題"}`
- **THEN** 回 200，`title` 已更新，其餘欄位不變

#### Scenario: 開團主取消揪團
- **WHEN** 開團主 `PATCH {"status": "cancelled"}`
- **THEN** 回 200，`status=cancelled`，且列表不再列出此團

#### Scenario: 管理員取消別人的揪團
- **WHEN** 以 `as_admin` 取消別人開的揪團
- **THEN** 回 200，`status=cancelled`

#### Scenario: 非開團主修改
- **WHEN** 一般玩家（不是開團主）呼叫 `PATCH`
- **THEN** 回 403，揪團不變

#### Scenario: 店家人員修改別人的揪團
- **WHEN** 店家人員修改在自己店家、但不是自己開的揪團
- **THEN** 回 403（店家人員不因為店家相同就有修改權限）

#### Scenario: 人數上限改得比現有成員少
- **WHEN** 已有 3 位成員，開團主 `PATCH {"capacity": 2}`
- **THEN** 回 409，`error.code=GROUP_CAPACITY_BELOW_MEMBERS`，揪團不變

#### Scenario: 調高人數上限自動遞補
- **WHEN** `capacity=2`，已滿且有 2 位候補，開團主 `PATCH {"capacity": 3}`
- **THEN** 回 200，最早報名的候補成為成員，`member_count=3`、`waitlist_count=1`

#### Scenario: 修改已取消的揪團
- **WHEN** 對已取消的揪團 `PATCH`
- **THEN** 回 409，`error.code=GROUP_CLOSED`

#### Scenario: 修改成不合法的時間
- **WHEN** `PATCH {"end_at": <早於 start_at>}`
- **THEN** 回 422

#### Scenario: 不支援的狀態值
- **WHEN** `PATCH {"status": "open"}` 或其他非 `cancelled` 的值
- **THEN** 回 422

#### Scenario: 揪團不存在
- **WHEN** `group_id` 不存在
- **THEN** 回 404，`error.code=GROUP_NOT_FOUND`

### Requirement: 報名
`POST /api/v1/groups/{group_id}/members` SHALL 讓目前使用者報名（不需要 body）。還有名額時，新增一位成員，回 201 與 `{"user_id", "status": "member", "waitlist_position": null}`；已額滿時，回 201 與 `{"status": "waitlisted", "waitlist_position": n}`（n 從 1 開始）。同時報名搶最後一個名額時，MUST 只有一人成為成員，其餘進入候補。

#### Scenario: 還有名額
- **WHEN** `capacity=4`、目前 1 位成員，另一位玩家報名
- **THEN** 回 201，`status=member`，揪團的 `member_count=2`

#### Scenario: 額滿時加入候補
- **WHEN** `capacity=2`、已有 2 位成員，第三位玩家報名
- **THEN** 回 201，`status=waitlisted`、`waitlist_position=1`，`member_count` 仍為 2

#### Scenario: 候補順位依報名先後
- **WHEN** 額滿後，玩家 A、B 依序報名
- **THEN** A 的 `waitlist_position=1`，B 的 `waitlist_position=2`

#### Scenario: 重複報名
- **WHEN** 已是成員或已在候補的玩家再次報名
- **THEN** 回 409，`error.code=GROUP_ALREADY_JOINED`

#### Scenario: 報名已取消的揪團
- **WHEN** 揪團已取消
- **THEN** 回 409，`error.code=GROUP_CLOSED`

#### Scenario: 報名已結束的揪團
- **WHEN** 揪團 `end_at` 已過
- **THEN** 回 409，`error.code=GROUP_CLOSED`

#### Scenario: 同時搶最後一個名額
- **WHEN** 只剩 1 個名額，兩位玩家同時報名
- **THEN** 一人 `status=member`，另一人 `status=waitlisted`，`member_count` 不超過 `capacity`

#### Scenario: 揪團不存在
- **WHEN** `group_id` 不存在
- **THEN** 回 404，`error.code=GROUP_NOT_FOUND`

#### Scenario: 未登入
- **WHEN** 在 `AUTH_MODE=jwt` 下不帶 token 報名
- **THEN** 回 401

### Requirement: 成員與候補名單
`GET /api/v1/groups/{group_id}/members` SHALL 回 200 與 `{"items": [...], "total": n}`，每筆含 `user_id`、`display_name`、`status`、`waitlist_position`、`joined_at`；先列成員（依報名先後，開團主第一位），再列候補（依候補順位）。

#### Scenario: 正常查詢
- **WHEN** 揪團有 2 位成員、1 位候補
- **THEN** 回 200，前兩筆 `status=member`（第一筆是開團主），第三筆 `status=waitlisted`、`waitlist_position=1`

#### Scenario: 揪團不存在
- **WHEN** `group_id` 不存在
- **THEN** 回 404，`error.code=GROUP_NOT_FOUND`

### Requirement: 退出與遞補
`DELETE /api/v1/groups/{group_id}/members/{user_id}` SHALL 讓成員或候補自己退出，或由開團主、`admin` 移除他人，成功回 204。成員離開後，最早報名的候補 MUST 在同一個交易中自動成為成員；候補離開後，其後的候補順位依序往前。開團主 MUST NOT 退出自己的揪團（要改用取消揪團）。

#### Scenario: 成員自己退出，候補遞補
- **WHEN** `capacity=2` 已滿、有 1 位候補，其中一位非開團主的成員退出
- **THEN** 回 204，候補第一位成為成員，`member_count=2`、`waitlist_count=0`

#### Scenario: 成員退出，沒有候補
- **WHEN** 成員退出且沒有人候補
- **THEN** 回 204，`member_count` 減 1

#### Scenario: 候補自己退出
- **WHEN** 候補 A（順位 1）退出，B 原為順位 2
- **THEN** 回 204，B 的 `waitlist_position=1`，成員不變

#### Scenario: 開團主移除成員
- **WHEN** 開團主移除某位成員
- **THEN** 回 204，候補依先後遞補

#### Scenario: 管理員移除成員
- **WHEN** 以 `as_admin` 移除某位成員
- **THEN** 回 204

#### Scenario: 移除別人但沒有權限
- **WHEN** 一般玩家（不是開團主）移除另一位成員
- **THEN** 回 403，名單不變

#### Scenario: 開團主退出自己的揪團
- **WHEN** 開團主 `DELETE` 自己
- **THEN** 回 409，`error.code=GROUP_ORGANIZER_CANNOT_LEAVE`

#### Scenario: 不在名單上
- **WHEN** `user_id` 不是此團的成員或候補
- **THEN** 回 404，`error.code=GROUP_MEMBER_NOT_FOUND`

#### Scenario: 揪團已取消或已結束
- **WHEN** 對已取消或已結束的揪團退出
- **THEN** 回 409，`error.code=GROUP_CLOSED`

### Requirement: 資料表
migration SHALL 新增 `groups` 與 `group_members`，主鍵為 UUID 且資料庫有預設值。`groups.shop_id` 參照 `booking_shops.id`、`groups.organizer_id` 參照 `auth_users.id`、`groups.game_id`（可為空，`bigint`）參照 `games.id`，遊戲被刪除時設為空值（遊戲是選填，不能因此擋住共用桌遊的同步指令）；`group_members.group_id` 參照 `groups.id`（刪除揪團時一併刪除）、`group_members.user_id` 參照 `auth_users.id`，且 (`group_id`, `user_id`) MUST 唯一。資料庫 SHALL 以 CHECK 限制 `capacity >= 2`、`fee >= 0`、`end_at > start_at`、`groups.status IN ('open', 'cancelled')`、`group_members.status IN ('member', 'waitlisted')`。migration MUST 可以 downgrade。

#### Scenario: 升級與降級
- **WHEN** 在空資料庫執行 `alembic upgrade head` 再 `downgrade` 回上一版
- **THEN** 兩張表依序建立後移除，其他表不受影響

#### Scenario: 同一位玩家不能重複出現在同一團
- **WHEN** 直接寫入兩筆相同 (`group_id`, `user_id`) 的 `group_members`
- **THEN** 資料庫拒絕第二筆

#### Scenario: 遊戲被刪除
- **WHEN** 某團的 `game_id` 指向的遊戲被刪除
- **THEN** 刪除成功，該團的 `game_id` 變成空值，揪團本身保留

#### Scenario: CHECK 限制
- **WHEN** 直接寫入 `capacity=1` 或 `end_at <= start_at` 的 `groups`
- **THEN** 資料庫拒絕寫入
