## ADDED Requirements

> 本檔情境中的桌位代號（A–I）與容量是測試用的虛構配置，結構（容量、相鄰、可併桌關係）與真實店家相同，但不是真實店家資料。

### Requirement: 自動分配單桌
系統 SHALL 在建立訂位時自動分配桌位，玩家 MUST NOT 能指定桌位。系統 SHALL 先嘗試單桌：選擇 `is_active` 為真、`min_capacity ≤ 人數 ≤ max_capacity`、且該時段無衝突的桌位中 `max_capacity` 最小者。`max_capacity` 相同時 SHALL 以 `table_code` 較小者為準。

#### Scenario: 選最小可容納桌
- **WHEN** 7 人訂位，可用桌為 F（max 8）與 C（max 10）
- **THEN** 系統分配 F

#### Scenario: 小團體
- **WHEN** 1 人訂位且 A 桌（max 6）可用
- **THEN** 系統分配 A

### Requirement: 多桌合併分配
單桌無法容納時，系統 SHALL 嘗試多桌組合，且合併後 MUST NOT 檢查 `min_capacity`、組合總 `max_capacity` MUST 大於等於人數。`seating_tables_rel` 的每筆紀錄 SHALL 視為雙向關係。候選組合依等級排序：
1. 等級 1：組合內的桌位可僅透過 `is_combinable=true` 的關係連通（含鏈狀，例如 B+C+E）。
2. 等級 2：組合需經過 `is_combinable=false` 的相鄰關係才能連通。
3. 等級 3：組合內的桌位不相鄰。

同等級內 SHALL 先比桌數最少，再比總 `max_capacity` 最小。所有等級都無法湊出可用組合時，系統 SHALL 拒絕訂位。

#### Scenario: 優先可併桌
- **WHEN** 13 人訂位，B、C、E、D、H、I 皆可用
- **THEN** 系統分配等級 1 且桌數最少、總 max 最小的組合 B+C（16）

#### Scenario: 鏈狀組合
- **WHEN** 25 人訂位，且 H+I（24）不足，B+C+E（26）可用
- **THEN** 系統分配 B+C+E

#### Scenario: 退回相鄰但不可併
- **WHEN** 無等級 1 組合可用，且 A+B 為相鄰但 `is_combinable=false` 並可容納人數
- **THEN** 系統可分配 A+B

#### Scenario: 退回不相鄰
- **WHEN** 等級 1 與 2 皆無可用組合，但不相鄰桌位組合可容納
- **THEN** 系統可分配該不相鄰組合

#### Scenario: 桌位不足
- **WHEN** 所有可用桌位的總容量小於人數
- **THEN** 系統拒絕訂位

### Requirement: 桌位衝突與緩衝
同一張桌位在時間上 MUST NOT 被兩筆有效訂位（`confirmed`、`seated`）佔用。訂位結束後 SHALL 保留 5 分鐘緩衝，但衝突對象與本訂位屬同一 `user_id` 時緩衝為 0 分鐘。修改訂位檢查衝突時 SHALL 排除該訂位本身。

#### Scenario: 不同玩家緩衝
- **WHEN** 桌位有他人訂位 14:00–16:00，玩家訂同桌 16:03–18:00
- **THEN** 該桌視為衝突，系統改配其他桌或拒絕

#### Scenario: 同玩家無緩衝
- **WHEN** 玩家已有 14:00–16:00 的訂位，再訂 16:00–18:00
- **THEN** 該桌可被分配

#### Scenario: 修改排除自己
- **WHEN** 玩家將自己的 14:00–16:00 訂位改成 14:30–16:30
- **THEN** 系統檢查衝突時忽略原訂位，不因與自己重疊而失敗

### Requirement: 併發保護
建立、修改、取消與改桌 SHALL 在單一資料庫交易內執行。資料庫 SHALL 以 exclusion constraint 保證同一桌位在有效狀態下，時間區間不重疊，避免並發請求重複分配。違反約束時交易 SHALL 回滾。

#### Scenario: 並發搶同一桌
- **WHEN** 兩個請求同時申請同一時段且僅剩一張可用桌
- **THEN** 只有一個請求成功，另一個重新分配後仍無桌位則回傳桌位不足

#### Scenario: 取消後釋放
- **WHEN** 訂位被取消、標為 no_show 或完成
- **THEN** 其桌位列不再占用時段，其他訂位可使用同一桌同一時段

### Requirement: 沿用原桌位與店員改桌
玩家修改訂位時，系統 SHALL 優先沿用原桌位，原桌位無法滿足新時間或人數時才重新分配；重新分配失敗時 SHALL 拒絕修改並保留原訂位。店員 SHALL 能手動變更訂位桌位，且仍需通過桌位衝突檢查。

#### Scenario: 沿用原桌位
- **WHEN** 玩家只延後 30 分鐘，原桌位於新時段仍可用
- **THEN** 訂位維持原桌位

#### Scenario: 人數增加需換桌
- **WHEN** 玩家將人數由 4 增為 9，原桌 A（max 6）不足
- **THEN** 系統重新分配；若找不到桌位則拒絕修改並保留原訂位

#### Scenario: 店員改桌衝突
- **WHEN** 店員將訂位改到時段已被佔用的桌位
- **THEN** 系統拒絕變更
