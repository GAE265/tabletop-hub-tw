## ADDED Requirements

### Requirement: 建立即確認
建立訂位成功後，系統 SHALL 直接將狀態設為 `confirmed`（不使用 `pending`），並產生唯一的 `reservation_code`，`source` 對玩家自助訂位設為 `online`。訂位 SHALL 記錄建立者 `user_id`（來自 `CurrentUser`）與訂位所屬 `shop_id`，且店家 MUST 存在於 `booking_shops`。

#### Scenario: 成功建立
- **WHEN** 玩家提交有效訂位
- **THEN** 訂位 `status` 為 `confirmed`，並寫入 `reservation_logs`（action 為建立、operator_type 為 customer、operator_id 為建立者）

#### Scenario: 備註
- **WHEN** 玩家於 `special_requests` 填寫座位偏好
- **THEN** 系統儲存備註，但不影響桌位分配

### Requirement: 狀態流轉
狀態 SHALL 依下列規則流轉：`confirmed → seated`（店員）、`seated → completed`（店員）、`confirmed → cancelled`（開始前取消）、`confirmed → no_show`（開始後玩家取消，或店員手動標記）、`no_show → seated`（店員修正）。系統 MUST NOT 自動將逾時未到的訂位標為 `no_show`。已 `seated` 的訂位 MUST NOT 可取消。

#### Scenario: 店員標記入座
- **WHEN** 店員將 `confirmed` 訂位標記為入座
- **THEN** 狀態為 `seated` 並記錄 `seated_at`

#### Scenario: 逾時不自動處理
- **WHEN** 訂位開始 30 分鐘後店員未做任何操作
- **THEN** 訂位狀態仍為 `confirmed`

#### Scenario: no_show 改回入座
- **WHEN** 店員將 `no_show` 訂位改為 `seated`，且原桌位在該時段無衝突
- **THEN** 狀態改為 `seated`

#### Scenario: no_show 改回入座但桌位已被占用
- **WHEN** 店員將 `no_show` 訂位改為 `seated`，但原桌位已被他人訂位占用
- **THEN** 系統拒絕變更並保留 `no_show`

#### Scenario: 入座後不可取消
- **WHEN** 玩家或店員嘗試取消 `seated` 訂位
- **THEN** 系統拒絕

### Requirement: 取消訂位
玩家與店員 SHALL 能取消訂位，不設最晚時間限制，且取消原因不必填（店員可選填）。取消 SHALL 立即釋放桌位、記錄 `cancelled_at` 與 `cancel_reason`，並於 `reservation_logs` 記錄取消者（`operator_type`、`operator_id`、`operator_name`）。訂位開始後的玩家取消 SHALL 標記為 `no_show` 並同樣立即釋放桌位。

#### Scenario: 開始前取消
- **WHEN** 玩家於訂位開始前取消
- **THEN** 狀態為 `cancelled`，桌位釋放，並記錄取消者

#### Scenario: 開始後取消
- **WHEN** 玩家於訂位開始後取消
- **THEN** 狀態為 `no_show`，桌位立即釋放

#### Scenario: 店員取消
- **WHEN** 店員取消訂位並選填原因
- **THEN** 狀態為 `cancelled`，`cancel_reason` 為所填原因，操作者類型為 staff

### Requirement: 玩家修改訂位
玩家 SHALL 能修改訂位日期、時間、人數與備註，MUST NOT 能透過訂位 API 修改姓名、電話、Email（這些屬於 `auth_users`）。修改 SHALL 重新驗證所有訂位規則、重新分配或確認桌位、重新計算預估費用。修改失敗時 SHALL 保留原訂位不變。修改成功後 SHALL 回傳提醒訊息，不需要玩家二次確認。

#### Scenario: 修改成功
- **WHEN** 玩家將人數與時間改為合法值且桌位可用
- **THEN** 訂位更新、預估費用重算，回應含修改成功提醒

#### Scenario: 修改失敗保留原訂位
- **WHEN** 玩家修改後的時間超出營業時間
- **THEN** 系統拒絕，原訂位所有欄位不變

#### Scenario: 不可改個資
- **WHEN** 修改請求包含姓名、電話或 Email 欄位
- **THEN** 系統忽略或拒絕這些欄位

### Requirement: 修改時與自己的訂位重疊
修改後若與同一玩家的其他有效訂位時間重疊，系統 SHALL 詢問玩家是否合併。玩家選擇合併後，系統 SHALL 在同一交易內建立一筆新訂位，時間涵蓋兩筆訂位的完整範圍，人數由玩家重新輸入，並取消被合併的兩筆舊訂位（`cancel_reason` 註明合併）；舊訂位保留歷史紀錄。新訂位 SHALL 重新通過營業時間、訂位規則、桌位與費用檢查，失敗時 SHALL 保留原訂位。

#### Scenario: 詢問合併
- **WHEN** 玩家修改訂位後與自己另一筆有效訂位重疊且未選擇合併
- **THEN** 系統回傳是否合併的詢問，不寫入任何變更

#### Scenario: 合併成功
- **WHEN** 玩家選擇合併並輸入新人數，且新時間範圍合法、有桌位
- **THEN** 建立涵蓋兩筆時間的新訂位，兩筆舊訂位為 `cancelled` 並註明合併

#### Scenario: 合併失敗
- **WHEN** 合併後的時間範圍超出營業時間或無桌位
- **THEN** 不執行合併，兩筆原訂位維持原狀

### Requirement: 完成與結算
店員 SHALL 能將 `seated` 訂位標記為 `completed`，系統 SHALL 記錄 `completed_at` 並依實際使用時間（`seated_at` 至 `completed_at`）計算並儲存 `final_fee`。

#### Scenario: 結算完成
- **WHEN** 店員將 `seated` 訂位標記為 `completed`
- **THEN** 記錄 `completed_at`，並寫入依實際使用時間計算的 `final_fee`

### Requirement: 角色與擁有者權限
系統 SHALL 以 `CurrentUser` 檢查權限。玩家端操作限 `player` 與 `admin`，且除 `admin` 外只能讀寫 `user_id` 等於自己的訂位。店員端操作（入座、完成、手動 no_show、店員取消、改桌、依日期看板）限 `shop_staff` 與 `admin`，且 `shop_staff` 只能操作 `shop_id` 等於自己所屬店家的訂位。未登入 SHALL 回 401，無權限 SHALL 回 403。

#### Scenario: 玩家動別人的訂位
- **WHEN** 玩家嘗試查詢、修改或取消其他玩家的訂位
- **THEN** 系統回 403

#### Scenario: 玩家做店員操作
- **WHEN** 玩家嘗試將訂位標記為入座或完成
- **THEN** 系統回 403

#### Scenario: 店員動別家店的訂位
- **WHEN** `shop_staff` 嘗試操作其他店家的訂位
- **THEN** 系統回 403

#### Scenario: 管理員不受限
- **WHEN** `admin` 操作任何店家的訂位
- **THEN** 系統允許

#### Scenario: 未登入
- **WHEN** `AUTH_MODE=jwt` 且請求未帶 token
- **THEN** 系統回 401

