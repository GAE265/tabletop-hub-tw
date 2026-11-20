# Spec Delta

## Purpose

導覽列的通知鈴鐺合併揪團與訂位的未讀數，通知頁 `/notifications` 分「揪團」「訂位」兩個分頁（前端）。

## ADDED Requirements

### Requirement: 合併的通知鈴鐺
導覽列 SHALL 顯示通知鈴鐺（手機在畫面頂部的窄列，平板與桌機在頂部導覽列），數字是揪團與訂位未讀數的總和，超過 99 顯示「99+」，總和為 0 時不顯示數字。兩邊各自在進入應用時查詢一次，之後每 60 秒重新查詢。一邊查詢失敗時只算另一邊；兩邊都失敗時不顯示數字，也不跳錯誤。點鈴鐺前往 `/notifications`。

#### Scenario: 兩邊相加
- **WHEN** 揪團 2 則未讀、訂位 1 則未讀
- **THEN** 鈴鐺顯示「3」

#### Scenario: 超過 99
- **WHEN** 揪團 60 則、訂位 50 則未讀
- **THEN** 鈴鐺顯示「99+」

#### Scenario: 沒有未讀
- **WHEN** 兩邊都是 0
- **THEN** 鈴鐺不顯示數字

#### Scenario: 一邊失敗
- **WHEN** 揪團通知 API 失敗，訂位 1 則未讀
- **THEN** 鈴鐺顯示「1」，不跳錯誤

#### Scenario: 兩邊都失敗
- **WHEN** 兩個通知 API 都回錯誤
- **THEN** 鈴鐺照常顯示、沒有數字，不跳錯誤

#### Scenario: 定時更新
- **WHEN** 過了 60 秒，後端的訂位未讀數從 0 變成 1
- **THEN** 鈴鐺多 1

#### Scenario: 點鈴鐺
- **WHEN** 點鈴鐺
- **THEN** 前往 `/notifications`

### Requirement: 通知頁分兩個分頁
`/notifications` SHALL 有「揪團」「訂位」兩個分頁，分頁標題各自顯示未讀數（0 時不顯示）。只有訂位有未讀時預設開「訂位」分頁，其他情況開「揪團」。「揪團」分頁的內容與行為和原本的揪團通知列表相同。導覽列不選取任何項目。

#### Scenario: 預設分頁
- **WHEN** 揪團 0 則未讀、訂位 2 則未讀，開啟 `/notifications`
- **THEN** 顯示「訂位」分頁

#### Scenario: 兩邊都有未讀
- **WHEN** 揪團 1 則、訂位 2 則未讀
- **THEN** 顯示「揪團」分頁，兩個分頁標題各有數字

#### Scenario: 切換分頁
- **WHEN** 點「訂位」分頁
- **THEN** 顯示訂位通知列表

### Requirement: 訂位通知列表
「訂位」分頁 SHALL 依新到舊列出自己的訂位通知，每則顯示：
- 一句說明：
  - `booking_confirmed`：`你在「店名」的訂位已成功`
  - `shop_new_booking`：`新訂位：11/22（日）19:00・4 人`（台灣時間）
- 訂位時間（台灣時間）與通知時間。

未讀與已讀 MUST 看得出差別。點一則時，未讀的先標成已讀並讓鈴鐺少 1，然後 `booking_confirmed` 前往 `/booking/mine`、`shop_new_booking` 前往 `/booking/board`；標成已讀失敗時仍然前往，那一則維持未讀。捲到底自動載入下一頁。有載入中、沒有通知（「目前沒有訂位通知」）、載入失敗（中文錯誤與「重試」）三種狀態。

#### Scenario: 兩種通知的文字
- **WHEN** 有 `booking_confirmed` 與 `shop_new_booking` 各一則
- **THEN** 依新到舊顯示兩句對應的說明與時間

#### Scenario: 玩家點通知
- **WHEN** 點一則未讀的 `booking_confirmed`
- **THEN** 送出 `PATCH {"read": true}`，鈴鐺少 1，前往 `/booking/mine`

#### Scenario: 店家人員點通知
- **WHEN** 點一則 `shop_new_booking`
- **THEN** 前往 `/booking/board`

#### Scenario: 點已讀的通知
- **WHEN** 點一則已讀通知
- **THEN** 不送 `PATCH`，直接前往

#### Scenario: 標成已讀失敗
- **WHEN** `PATCH` 回錯誤
- **THEN** 仍然前往，那一則維持未讀

#### Scenario: 沒有通知
- **WHEN** 列表為空
- **THEN** 顯示「目前沒有訂位通知」

#### Scenario: 載入失敗
- **WHEN** 列表 API 回錯誤
- **THEN** 顯示中文錯誤訊息（不含錯誤代碼）與「重試」，按重試重新查詢

#### Scenario: 下一頁
- **WHEN** `total` 大於已載入的筆數，且捲到底
- **THEN** 載入下一頁並接在後面
