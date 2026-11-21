# Spec Delta

## Purpose

揪團通知的鈴鐺與列表改由 `notifications-page` 提供；這裡只修改網址與鈴鐺的部分，其他要求不變。

## MODIFIED Requirements

### Requirement: 通知鈴鐺
導覽列的通知鈴鐺 SHALL 由 `notifications-page` 的「合併的通知鈴鐺」定義：數字是揪團與訂位未讀數的總和，點鈴鐺前往 `/notifications`。揪團未讀數仍然在進入應用時查詢一次，之後每 60 秒重新查詢；查詢失敗時不跳錯誤。

#### Scenario: 揪團未讀
- **WHEN** 揪團 `unread_count=3`、訂位 0
- **THEN** 鈴鐺顯示「3」

#### Scenario: 點鈴鐺
- **WHEN** 點鈴鐺
- **THEN** 前往 `/notifications`

### Requirement: 通知列表頁
揪團通知列表 SHALL 是 `/notifications` 的「揪團」分頁，依新到舊列出自己的揪團通知。每則顯示：
- 一句說明：
  - 成團：`「揪團名稱」已成團`
  - 解散：`「揪團名稱」已取消`
  - 候補正取：`你已從候補遞補為「揪團名稱」的成員`
- 揪團開始時間（台灣時間）與通知時間。

未讀的通知 MUST 與已讀的看得出差別。點一則通知時，未讀的先標成已讀並更新鈴鐺的未讀數，然後前往該揪團的詳細頁；標成已讀失敗時仍然前往詳細頁。還有下一頁時，捲到底自動載入下一頁。`/groups/notifications` 不再是通知頁。

#### Scenario: 三種通知的文字
- **WHEN** 有成團、解散、候補正取各一則
- **THEN** 依新到舊顯示三句對應的說明與時間

#### Scenario: 點未讀的通知
- **WHEN** 點一則未讀通知
- **THEN** 送出 `PATCH {"read": true}`，那一則變成已讀，鈴鐺少 1，並前往該揪團詳細頁

#### Scenario: 點已讀的通知
- **WHEN** 點一則已讀通知
- **THEN** 不送 `PATCH`，直接前往該揪團詳細頁

#### Scenario: 標成已讀失敗
- **WHEN** `PATCH` 回錯誤
- **THEN** 仍然前往詳細頁，那一則維持未讀

#### Scenario: 載入中
- **WHEN** 列表還在載入
- **THEN** 顯示載入中

#### Scenario: 沒有通知
- **WHEN** 列表為空
- **THEN** 顯示「目前沒有通知」

#### Scenario: 載入失敗
- **WHEN** 列表 API 回錯誤
- **THEN** 顯示中文錯誤訊息（不含錯誤代碼）與「重試」，按重試重新查詢

#### Scenario: 下一頁
- **WHEN** `total` 大於已載入的筆數，且捲到底
- **THEN** 載入下一頁並接在後面

### Requirement: 揪團詳細頁的網址
`/groups/<揪團 id>` SHALL 直接顯示該揪團的詳細頁（和從月曆點進去的是同一個頁面），導覽列選取「揪團」。

#### Scenario: 開啟揪團網址
- **WHEN** 前往 `/groups/g-1`
- **THEN** 顯示揪團 g-1 的詳細頁
