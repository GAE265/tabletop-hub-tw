# Spec Delta

## Purpose

記錄一局遊戲（功能 #13 的第一步）。玩家在遊戲中記錄這局發生什麼，其他人重新查詢即可查看與覆盤；結束時記錄結果，有帳號的參加者都確認後成為有效紀錄。

## ADDED Requirements

### Requirement: 開局
`POST /api/v1/matches` SHALL 建立一局並回 201 與該局資料。必填：`game_id`、`played_on`（日期）、`location_type`（`shop` 或 `home`）；`location_type=shop` 時 `shop_id` 必填，`home`（自家）時 MUST NOT 帶 `shop_id`；選填：`group_id`、`progress`、`seat_number`（開局者自己的座位，>= 1，沒帶時為最小空位）。目前使用者成為開局者（`created_by`）並自動成為參加者（帶 `user_id`），座位由他自己選，不強制 1 號；此時還沒有結果，所以尚未確認（`is_confirmed=false`）。帶 `group_id` 時，`group_id` MUST 是存在的揪團（透過 `groups` 的 service 讀取），只有該揪團的開團主、正式成員或 admin 可以開局，其他人（含候補）MUST 回 403；開局時 MUST 把該揪團的正式成員（不含候補）自動加為參加者：開局者用自己選的座位（沒選為 1），其他成員依加入揪團的順序各取最小的空位，開局者本人不重複加入。新建立的一局 `status=in_progress`、`result` 為空。所有角色都可以開局。一局不一定屬於揪團。

#### Scenario: 在店家開局
- **WHEN** 玩家以存在的 `game_id`、`played_on`、`location_type=shop` 與存在的 `shop_id` 呼叫 `POST /api/v1/matches`
- **THEN** 回 201，`created_by.id` 為目前使用者、`status=in_progress`、`result` 為 null、`participants` 只有 1 位（`seat_number=1`、`user_id` 為目前使用者、`is_confirmed=false`）、`group_id` 為 null

#### Scenario: 在自家開局
- **WHEN** 同上，但 `location_type=home` 且不帶 `shop_id`
- **THEN** 回 201，`location_type=home`、`shop_id` 為 null

#### Scenario: 開局者自己選座位
- **WHEN** 開局時帶 `seat_number=4`
- **THEN** 回 201，開局者的參加者 `seat_number=4`

#### Scenario: 座位不合法
- **WHEN** 開局時 `seat_number` 為 0 或負數
- **THEN** 回 422

#### Scenario: 屬於某個揪團
- **WHEN** 帶存在的 `group_id`
- **THEN** 回 201，回應的 `group_id` 與輸入一致

#### Scenario: 帶揪團開局自動加入成員
- **WHEN** 揪團有開團主 A、成員 B、C，A 帶該 `group_id` 開局、沒選座位
- **THEN** 回 201，參加者依序為 A（座位 1）、B（座位 2）、C（座位 3），人數等於成員數

#### Scenario: 候補不加入
- **WHEN** 揪團另有候補 D
- **THEN** D 不在參加者裡

#### Scenario: 座位依加入順序
- **WHEN** 揪團成員 C 比 B 早加入
- **THEN** C 的座位小於 B

#### Scenario: 開局者選座位
- **WHEN** 開局者帶 `seat_number=2`
- **THEN** 開局者座位 2，其他成員依加入順序取最小空位（1、3…）

#### Scenario: 成員（非開團主）開局
- **WHEN** 揪團的正式成員 B 帶該 `group_id` 開局
- **THEN** 回 201，B 只出現一次，其他成員一併加入

#### Scenario: admin 不是成員也可以開局
- **WHEN** admin 帶該 `group_id` 開局
- **THEN** 回 201，admin 與所有正式成員都是參加者

#### Scenario: 不是成員不能帶揪團開局
- **WHEN** 不是該揪團開團主、正式成員或 admin 的人帶 `group_id` 開局（含候補、`shop_staff`）
- **THEN** 回 403，不建立這一局

#### Scenario: 不帶揪團時行為不變
- **WHEN** 開局時不帶 `group_id`
- **THEN** 參加者只有開局者

#### Scenario: 缺少必填欄位
- **WHEN** 不帶 `game_id`、`played_on` 或 `location_type` 任一
- **THEN** 回 422，`error.code=VALIDATION_ERROR`

#### Scenario: 店家與地點類型不一致
- **WHEN** `location_type=shop` 但沒帶 `shop_id`，或 `location_type=home` 卻帶了 `shop_id`
- **THEN** 回 422

#### Scenario: 地點類型不合法
- **WHEN** `location_type` 為 `Shop`、空字串或 `office`
- **THEN** 回 422

#### Scenario: 遊戲、店家或揪團不存在
- **WHEN** `game_id`、`shop_id` 或 `group_id` 指向不存在的資料
- **THEN** 回 404，`error.code` 分別為 `MATCH_GAME_NOT_FOUND`、`MATCH_SHOP_NOT_FOUND`、`MATCH_GROUP_NOT_FOUND`

#### Scenario: 店家人員開局
- **WHEN** 以 `as_shop_staff` 開局
- **THEN** 回 201，`created_by.id` 為該店家人員

### Requirement: 查詢一局
`GET /api/v1/matches/{match_id}` SHALL 回傳該局資料，含全部參加者（依 `seat_number` 排序）、全部回合紀錄（依 `turn_number` 排序）、`participant_count`（參加人數）、`account_count`（有帳號人數）、`confirmed_count`（有帳號且已確認的人數），以及推導欄位 `is_valid`（已記錄結果，且 `confirmed_count == account_count`）。`is_valid` MUST NOT 存在資料庫。任何已登入的使用者都可以查詢（玩家要先看到這一局才能按加入）。未確認的紀錄照常回傳。`GET /api/v1/matches` SHALL 支援 `game_id`、`group_id`、`user_id`（該使用者參加過）篩選，依 `played_on` 由新到舊，分頁格式 `{"items": [...], "total": n}`。

#### Scenario: 查詢單局
- **WHEN** 呼叫 `GET /api/v1/matches/{match_id}`
- **THEN** 回 200，含 `participants`、`turns`、`participant_count`、`account_count`、`confirmed_count`、`is_valid`

#### Scenario: 人數統計
- **WHEN** 一局有 5 位參加者，其中 3 位有帳號，2 位只有名字，3 位有帳號者中 2 位已確認
- **THEN** `participant_count=5`、`account_count=3`、`confirmed_count=2`、`is_valid=false`

#### Scenario: 其他人重新查詢取得最新內容
- **WHEN** 有帳號的參加者新增一個回合紀錄後，另一位已登入的使用者呼叫 `GET /api/v1/matches/{match_id}`
- **THEN** 回應的 `turns` 含該回合

#### Scenario: 還沒確認的紀錄照常查得到
- **WHEN** 已記錄結果但沒有任何人確認
- **THEN** 查詢回 200，`result` 有值，`is_valid=false`

#### Scenario: 非參加者可以查詢
- **WHEN** 不在這局的玩家呼叫 `GET /api/v1/matches/{match_id}`
- **THEN** 回 200

#### Scenario: 找不到
- **WHEN** `match_id` 不存在
- **THEN** 回 404，`error.code=MATCH_NOT_FOUND`

#### Scenario: 列表篩選與分頁
- **WHEN** 呼叫 `GET /api/v1/matches?game_id=...&page=1&page_size=20`
- **THEN** 回 200，`items` 只含該遊戲的局，依 `played_on` 由新到舊，`total` 為符合條件的總數

### Requirement: 加入參加者
`POST /api/v1/matches/{match_id}/participants` SHALL 新增一位參加者並回 201。body 不帶 `display_name` 時，是目前使用者自己加入：新增的參加者帶 `user_id` 為目前使用者，`display_name` 取自其帳號。body 帶 `display_name` 時，是這局有帳號的參加者（或 admin）新增沒有帳號的參加者，`user_id` 為空；不在這局的人這樣呼叫 MUST 回 403。兩種都可以帶 `seat_number`（>= 1）；沒帶時使用最小的空位。body MUST NOT 接受 `user_id`。系統 MUST NOT 以名字比對帳號。已結束（`status=finished`）的局 MUST NOT 再加入參加者。

#### Scenario: 玩家自己加入
- **WHEN** 另一位玩家對進行中的局呼叫 `POST .../participants`，body 為 `{}`
- **THEN** 回 201，新參加者的 `user_id` 為該玩家、`seat_number` 為最小空位、`is_confirmed=false`

#### Scenario: 參加者新增沒有帳號的參加者
- **WHEN** 這局有帳號的參加者（不一定是開局者）送出 `{"display_name": "Amy", "seat_number": 3}`
- **THEN** 回 201，`display_name=Amy`、`user_id` 為 null、`seat_number=3`

#### Scenario: 同名不會綁到帳號
- **WHEN** 有帳號的參加者新增 `display_name` 與某個帳號的 `display_name` 相同的參加者
- **THEN** 該參加者的 `user_id` 仍為 null，`account_count` 不增加

#### Scenario: 座位已被占用
- **WHEN** 送出的 `seat_number` 已有人
- **THEN** 回 409，`error.code=MATCH_SEAT_TAKEN`

#### Scenario: 重複加入
- **WHEN** 已在這局的玩家再次自己加入
- **THEN** 回 409，`error.code=MATCH_ALREADY_JOINED`

#### Scenario: 非參加者新增沒有帳號的參加者
- **WHEN** 不在這局的玩家（非 admin）送出帶 `display_name` 的 body
- **THEN** 回 403

#### Scenario: 不接受 user_id
- **WHEN** body 帶 `user_id`
- **THEN** 回 422

#### Scenario: 名字空白或座位不合法
- **WHEN** `display_name` 為空字串或全空白，或 `seat_number` 為 0 或負數
- **THEN** 回 422

#### Scenario: 已結束的局不能再加入
- **WHEN** 這局 `status=finished`，有人呼叫加入
- **THEN** 回 409，`error.code=MATCH_FINISHED`

### Requirement: 記錄回合
`POST /api/v1/matches/{match_id}/turns` SHALL 記錄一個回合並回 201。必填：`turn_number`（>= 1）、`game_data`（該遊戲特有的內容，格式由該遊戲的定義決定，存為 JSONB）。只有這局有帳號的參加者與 admin 可以記錄。同一局同一 `turn_number` 已有紀錄時 MUST 回 409，且不改動舊紀錄；帶 `overwrite=true` 時覆蓋舊紀錄並回 200。回合紀錄是選填的，沒有任何回合紀錄的局依然成立。遊戲沒有回合格式定義時 MUST 回 422。選填 `seat_number`（本回合首家的座位，>= 1；遊戲沒有這個概念或沒填時省略或為 null，回應也是 null），有值時 MUST 是這局已有的座位。

《血與刃的白薔薇》的 `game_data`：`played_seat_numbers`（這回合出牌的座位編號清單，至少一個、不可重複、每個都 MUST 是這局存在的座位）、`double_blade_count`（雙刃）、`dark_blade_count`（暗刃）、`giant_blade_count`（巨刃）、`faithful_count`（信者）皆為 >= 0 的整數，`has_white_rose`（有沒有白薔薇）為布林；六個欄位都必填、不接受其他欄位。幽魂不記。`seat_number`（本回合首家）不要求出現在 `played_seat_numbers` 裡。

#### Scenario: 正常記錄回合
- **WHEN** 有帳號的參加者送出 `turn_number=1`、存在的 `seat_number`、完整合法的 `game_data`
- **THEN** 回 201，回應含 `turn_number`、`seat_number`、`game_data`、`recorded_by`

#### Scenario: 只記結果的局沒有回合
- **WHEN** 一局沒有任何回合紀錄，直接記錄結果
- **THEN** 記錄成功（見「記錄結果」）

#### Scenario: 同一回合重複記錄
- **WHEN** `turn_number=1` 已有紀錄，再送一次 `turn_number=1`，沒帶 `overwrite`
- **THEN** 回 409，`error.code=MATCH_TURN_ALREADY_RECORDED`，`error.details` 含既有紀錄的內容；資料庫裡的舊紀錄不變

#### Scenario: 確認後覆蓋
- **WHEN** 同上，但帶 `?overwrite=true`
- **THEN** 回 200，該回合的 `game_data` 與 `seat_number` 變成新送的內容，`recorded_by` 為這次覆蓋的人；該局回合總數不變

#### Scenario: 覆蓋的對象不存在時就是新增
- **WHEN** `turn_number=2` 還沒有紀錄，帶 `?overwrite=true` 送出
- **THEN** 回 201，新增該回合

#### Scenario: 座位不存在
- **WHEN** `seat_number` 在這局沒有人
- **THEN** 回 422，`error.code=MATCH_SEAT_NOT_FOUND`

#### Scenario: 出牌座位不存在
- **WHEN** `played_seat_numbers` 含這局沒有的座位
- **THEN** 回 422，`error.code=MATCH_SEAT_NOT_FOUND`，`error.details` 列出不存在的座位，資料庫沒有新增

#### Scenario: 出牌座位清單是空的
- **WHEN** `played_seat_numbers` 為 `[]`
- **THEN** 回 422，`error.code=VALIDATION_ERROR`

#### Scenario: 出牌座位重複
- **WHEN** `played_seat_numbers` 為 `[1, 1]`
- **THEN** 回 422，`error.code=VALIDATION_ERROR`

#### Scenario: 出牌座位不合法
- **WHEN** `played_seat_numbers` 含 0、負數或字串
- **THEN** 回 422

#### Scenario: 缺少出牌座位
- **WHEN** `game_data` 沒有 `played_seat_numbers`
- **THEN** 回 422

#### Scenario: game_data 缺欄位或型別錯誤
- **WHEN** 白薔薇的 `game_data` 缺 `has_white_rose`，或 `faithful_count` 為 -1 或 `"2"`，或多帶 `ghost_count`
- **THEN** 回 422，資料庫沒有新增

#### Scenario: 回合編號不合法
- **WHEN** `turn_number` 為 0 或負數
- **THEN** 回 422

#### Scenario: 非參加者不能記錄
- **WHEN** 不在這局的玩家送出回合紀錄
- **THEN** 回 403

#### Scenario: 沒有帳號的參加者名單不影響權限
- **WHEN** 這局只有開局者有帳號，另一位玩家（未加入）送出回合紀錄
- **THEN** 回 403

#### Scenario: 遊戲沒有回合格式
- **WHEN** 這局的遊戲不是《血與刃的白薔薇》，送出回合紀錄
- **THEN** 回 422，`error.code=MATCH_TURN_NOT_SUPPORTED`

#### Scenario: 同時送出同一回合
- **WHEN** 兩個請求同時對同一 `turn_number` 新增
- **THEN** 一個回 201，另一個回 409，資料庫該回合只有一筆

#### Scenario: 局不存在
- **WHEN** `match_id` 不存在
- **THEN** 回 404，`error.code=MATCH_NOT_FOUND`

### Requirement: 記錄結果
`PUT /api/v1/matches/{match_id}/result` SHALL 記錄這局的結果，回 200 與該局資料，並使 `status=finished`。結果的格式依 `games.result_type` 決定；本次只支援 `faction`。`faction` 的 body 為 `{"winning_faction": ..., "participants": [{"seat_number": ..., "faction": ...}, ...]}`：`participants` MUST 涵蓋這局全部座位，且座位不可重複、不可含這局沒有的座位，每個 `faction` 與 `winning_faction` 都 MUST 是該遊戲定義裡的陣營（白薔薇：`rose` 薔薇陣營、`blood_blade` 血刃陣營）。每位參加者的 `is_winner` 由伺服器依 `faction == winning_faction` 計算，body MUST NOT 帶。`faction` 不計分，`score` 與 `placement` 保持為 null（不存 0）。`result` 存成含 `type` 的 JSON（例如 `{"type": "faction", "winning_faction": "rose"}`），不隨 `games.result_type` 日後被修改而失去意義。這局任何有帳號的參加者與 admin 都可以記錄結果。記錄結果的人（若是這局有帳號的參加者）自動算已確認。這局已有結果時 MUST 回 409，帶 `?overwrite=true` 才覆蓋；覆蓋時，除了這次覆蓋的人以外，所有參加者的確認 MUST 被清除。

#### Scenario: 正常記錄結果
- **WHEN** 有帳號的參加者送出 `winning_faction=rose` 與五位參加者各自的陣營（`rose` 3 位、`blood_blade` 2 位）
- **THEN** 回 200，`status=finished`，`result.winning_faction=rose`，3 位薔薇陣營 `is_winner=true`，2 位血刃陣營 `is_winner=false`，所有 `score`、`placement` 為 null

#### Scenario: 記錄結果的人自動算已確認
- **WHEN** 有帳號的參加者 A 記錄結果
- **THEN** A 的 `is_confirmed=true`，其他有帳號的參加者 `is_confirmed=false`；開局者若不是 A，也是 `false`

#### Scenario: 陣營不合法
- **WHEN** `winning_faction` 或某位的 `faction` 為 `ghost`、`Rose` 或空字串
- **THEN** 回 422，局仍是 `in_progress`

#### Scenario: 沒涵蓋全部座位
- **WHEN** `participants` 少了某些座位（例如這局有座位 1–4，只送 1–3）
- **THEN** 回 422，`error.code=MATCH_RESULT_SEATS_INCOMPLETE`，`error.details.missing_seat_numbers` 列出缺的座位（例如 `[4]`），局仍是 `in_progress`

#### Scenario: 含不存在的座位
- **WHEN** `participants` 含這局沒有的座位（例如 5）
- **THEN** 回 422，`error.code=MATCH_SEAT_NOT_FOUND`，`error.details.seat_numbers` 列出不存在的座位，局仍是 `in_progress`

#### Scenario: 座位重複
- **WHEN** `participants` 裡同一個座位出現兩次
- **THEN** 回 422，`error.code=VALIDATION_ERROR`，局仍是 `in_progress`

#### Scenario: 不接受 is_winner 與分數
- **WHEN** body 的 `participants` 帶 `is_winner` 或 `score`
- **THEN** 回 422

#### Scenario: 非開局者的參加者也能記錄結果
- **WHEN** 這局有帳號、但不是開局者的參加者記錄結果
- **THEN** 回 200

#### Scenario: 非參加者不能記錄結果
- **WHEN** 不在這局的玩家呼叫記錄結果
- **THEN** 回 403，局仍是 `in_progress`

#### Scenario: 結果重複記錄
- **WHEN** 這局已有結果，再送一次，沒帶 `overwrite`
- **THEN** 回 409，`error.code=MATCH_RESULT_ALREADY_RECORDED`，舊結果不變

#### Scenario: 覆蓋結果會清除其他人的確認
- **WHEN** 這局已有結果，A（原本記錄的人）與 B 都已確認，B 帶 `?overwrite=true` 送出新結果
- **THEN** 回 200，結果為新送的內容，A 的 `is_confirmed=false`，B 的 `is_confirmed=true`

#### Scenario: 遊戲的結果類型為空
- **WHEN** 這局遊戲的 `games.result_type` 為空，記錄結果
- **THEN** 回 409，`error.code=MATCH_GAME_RESULT_TYPE_NOT_SET`，局仍是 `in_progress`（回合紀錄不受影響，仍可記錄）

#### Scenario: 結果類型本次尚未支援
- **WHEN** 這局遊戲的 `games.result_type` 為 `score` 或 `cooperative`，記錄結果
- **THEN** 回 422，`error.code=MATCH_RESULT_TYPE_NOT_SUPPORTED`

### Requirement: 確認紀錄
`PATCH /api/v1/matches/{match_id}/participants/{participant_id}` SHALL 讓參加者本人確認，body 為 `{"is_confirmed": true}`，回 200 與該參加者。只有該參加者本人（`user_id` 等於目前使用者）與 admin 可以確認；沒有帳號的參加者不需要也不能被確認。只能確認為 `true`，已記錄結果之後才能確認。重複確認 MUST 成功且結果不變。未確認的紀錄照存。

#### Scenario: 參加者確認
- **WHEN** 有帳號的參加者在已有結果的局呼叫確認
- **THEN** 回 200，該參加者 `is_confirmed=true`，`confirmed_count` 加 1

#### Scenario: 全部確認後成為有效紀錄
- **WHEN** 最後一位有帳號的參加者確認
- **THEN** 查詢該局 `confirmed_count == account_count` 且 `is_valid=true`

#### Scenario: 沒有帳號的參加者不影響有效紀錄
- **WHEN** 5 位參加者中 4 位有帳號且都已確認，1 位只有名字
- **THEN** `is_valid=true`

#### Scenario: 非參加者不能確認
- **WHEN** 不在這局的玩家對任何參加者送出確認
- **THEN** 回 403

#### Scenario: 不能替別人確認
- **WHEN** 參加者 A 對參加者 B（有帳號）的 `participant_id` 送出確認
- **THEN** 回 403，B 的 `is_confirmed` 不變

#### Scenario: 沒有帳號的參加者不能被確認
- **WHEN** 有帳號的參加者對沒有帳號的參加者送出確認
- **THEN** 回 403

#### Scenario: 還沒有結果不能確認
- **WHEN** 局是 `in_progress`，參加者送出確認
- **THEN** 回 409，`error.code=MATCH_RESULT_NOT_RECORDED`

#### Scenario: 重複確認
- **WHEN** 已確認的參加者再確認一次
- **THEN** 回 200，`confirmed_count` 不變

#### Scenario: 取消確認不被接受
- **WHEN** body 為 `{"is_confirmed": false}`
- **THEN** 回 422

#### Scenario: 參加者不存在
- **WHEN** `participant_id` 不屬於這局
- **THEN** 回 404，`error.code=MATCH_PARTICIPANT_NOT_FOUND`

### Requirement: 移除參加者
`DELETE /api/v1/matches/{match_id}/participants/{participant_id}` SHALL 移除一位參加者並回 204，座位隨之空出。有帳號的參加者可以移除自己（退出）；這局任何有帳號的參加者與 admin 可以移除沒有帳號的參加者與其他參加者；不在這局的玩家 MUST 回 403。已結束（`status=finished`）的局 MUST NOT 移除，回 409。該參加者的座位只要出現在這局任何回合紀錄的 `seat_number` 或 `game_data.played_seat_numbers` 裡，MUST 回 409 並不移除，避免覆盤資料對不上。

#### Scenario: 退出
- **WHEN** 有帳號的參加者移除自己
- **THEN** 回 204，之後查詢不再有該參加者，`participant_count` 與 `account_count` 各少 1

#### Scenario: 移除沒有帳號的人
- **WHEN** 有帳號的參加者移除沒有帳號的 Amy
- **THEN** 回 204，`participant_count` 少 1，`account_count` 不變

#### Scenario: 移除其他有帳號的參加者
- **WHEN** 有帳號的參加者 A 移除另一位有帳號的參加者 B
- **THEN** 回 204，B 不再是參加者

#### Scenario: 座位空出後可再使用
- **WHEN** 座位 3 的參加者被移除後，另一位玩家自己加入且指定 `seat_number=3`
- **THEN** 回 201

#### Scenario: 非參加者不能移除
- **WHEN** 不在這局的玩家（非 admin）呼叫移除
- **THEN** 回 403，參加者不變

#### Scenario: 已結束的局不能移除
- **WHEN** 這局 `status=finished`，有人呼叫移除
- **THEN** 回 409，`error.code=MATCH_FINISHED`，參加者不變

#### Scenario: 座位是回合的本回合首家
- **WHEN** 座位 2 出現在某回合的 `seat_number`，移除座位 2 的參加者
- **THEN** 回 409，`error.code=MATCH_PARTICIPANT_HAS_TURNS`，`error.details` 列出相關的 `turn_number`，參加者不變

#### Scenario: 座位出現在出牌清單
- **WHEN** 座位 3 出現在某回合的 `game_data.played_seat_numbers`，移除座位 3 的參加者
- **THEN** 回 409，`error.code=MATCH_PARTICIPANT_HAS_TURNS`，參加者不變

#### Scenario: 沒有出現在任何回合就可以移除
- **WHEN** 這局有回合紀錄，但座位 5 沒有出現在任何回合的 `seat_number` 或 `played_seat_numbers`，移除座位 5 的參加者
- **THEN** 回 204

#### Scenario: 參加者不存在
- **WHEN** `participant_id` 不屬於這局
- **THEN** 回 404，`error.code=MATCH_PARTICIPANT_NOT_FOUND`

### Requirement: 資料表與欄位說明
資料表 `matches`、`match_participants`、`match_turns` MUST 由一個 Alembic migration 建立；主鍵為 UUID 欄位 `id`，參照桌遊的 `game_id` 為 `bigint`（`games.id`）。開局者欄位為 `created_by`（參照 `auth_users.id`）。`matches.group_id` 為可空的 UUID，MUST 有外鍵參照 `groups.id`，`ondelete=SET NULL`（比照 `groups.game_id` 的寫法），欄位 comment 為「所屬揪團；不一定屬於揪團」。每張表與每個欄位 MUST 有中文 comment；Python 端的 Enum（局的狀態、地點類型、白薔薇陣營）每個值 MUST 有中文註解，說明代表什麼、什麼情況使用並舉一款遊戲當例子。可為空的欄位，空值 MUST 代表「沒有資料」（例如不計分時 `score` 為 null，不存 0）。資料庫 MUST 以約束保證：同一局座位編號不重複、同一局同一帳號只出現一次、同一局回合編號不重複。

#### Scenario: 約束
- **WHEN** 直接對資料庫寫入同一局重複的 `seat_number`、同一局重複的 `user_id`、同一局重複的 `turn_number`
- **THEN** 資料庫拒絕

#### Scenario: 同一局可有多位沒有帳號的參加者
- **WHEN** 同一局寫入兩位 `user_id` 為空的參加者
- **THEN** 寫入成功

#### Scenario: 欄位說明
- **WHEN** 查詢三張表本身與每個欄位的 comment
- **THEN** 全部非空且為中文

#### Scenario: group_id 的外鍵
- **WHEN** 查詢 `matches` 的外鍵
- **THEN** `group_id` 參照 `groups.id` 且刪除規則為 `SET NULL`；`group_id` 的 comment 為「所屬揪團；不一定屬於揪團」

#### Scenario: 揪團被刪除後這局仍在
- **WHEN** 一局的 `group_id` 指向某揪團，該揪團被刪除
- **THEN** 這局仍然存在，`group_id` 變成空值，其他欄位、參加者與回合紀錄不變

#### Scenario: group_id 指向不存在的揪團
- **WHEN** 直接對資料庫寫入不存在的 `group_id`
- **THEN** 資料庫拒絕

#### Scenario: 升級與降版
- **WHEN** 執行 `alembic upgrade head` 再 `alembic downgrade -1`
- **THEN** 升級建立三張表，降版移除三張表，其他資料表與資料不變

#### Scenario: 不計分存空值
- **WHEN** 記錄 `faction` 類型的結果
- **THEN** 資料庫裡 `score` 與 `placement` 為 NULL，不是 0
