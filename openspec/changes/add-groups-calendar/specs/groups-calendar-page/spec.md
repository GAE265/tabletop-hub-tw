# Spec Delta

## Purpose

前端揪團月曆：讓玩家在月曆上看到每天有幾團，點日期看當天的揪團，並直接開團、報名、候補、退出。畫面參考 globalpickleballmeetup.com 的團主揪團月曆。`prototypes/groups/` 參考畫面與 `domains/groups/pages/` 正式頁面共用同一份 `state/`。

## ADDED Requirements

### Requirement: 月曆顯示每天的團數
`GroupsCalendarNotifier` SHALL 依目前顯示的月份，以 `GET /api/v1/groups?start_from=<當月第一天 00:00>&start_before=<下月第一天 00:00>`（依裝置時區換算成 UTC）載入揪團，並提供「日期 → 當天團數」。使用者切換月份時重新載入。月份超過 100 團時，MUST 繼續載入後面的分頁，直到取得全部。

#### Scenario: 載入當月
- **WHEN** 開啟月曆，當月 11/14 有 2 團、11/20 有 1 團
- **THEN** state 的團數為 `{11/14: 2, 11/20: 1}`，畫面在這兩天顯示「2 團」、「1 團」

#### Scenario: 跨日的時區換算
- **WHEN** 裝置時區為 UTC+8，某團 `start_at=2026-11-13T16:30:00Z`（台灣時間 11/14 00:30）
- **THEN** 該團計入 11/14，不計入 11/13

#### Scenario: 切換到下個月
- **WHEN** 按「下個月」
- **THEN** 以 12 月的時間區間重新呼叫 API，團數更新為 12 月的資料

#### Scenario: 回到今天
- **WHEN** 按「今天」
- **THEN** 月份切回本月，選取的日期為今天

#### Scenario: 載入中
- **WHEN** API 尚未回應
- **THEN** 顯示載入中指示，不顯示舊月份的團數

#### Scenario: 載入失敗
- **WHEN** API 回錯誤或無法連線
- **THEN** 顯示錯誤訊息與「重試」按鈕，按下後重新載入

### Requirement: 當日揪團列表
選取某天後，state SHALL 提供當天的揪團（依開始時間排序）。每筆顯示：時段（開始 – 結束，裝置時區）、標題、店家名稱、開團主名稱、遊戲名稱（有的話）、費用（沒有填寫時顯示「免費」或不顯示）、名額狀態。名額狀態依序為：已取消、已結束、「已額滿，候補 N 人」、「剩 N 位」。

#### Scenario: 選取有揪團的日期
- **WHEN** 點選 11/14
- **THEN** 列出 11/14 的 2 團，依開始時間排序

#### Scenario: 選取沒有揪團的日期
- **WHEN** 點選沒有揪團的日期
- **THEN** 顯示「這天還沒有人揪團」與「我要開團」按鈕

#### Scenario: 額滿的揪團
- **WHEN** 某團 `remaining_slots=0`、`waitlist_count=2`
- **THEN** 顯示「已額滿，候補 2 人」

#### Scenario: 已結束的揪團
- **WHEN** 某團 `status=ended`
- **THEN** 顯示「已結束」，不顯示報名按鈕

### Requirement: 依開團主篩選
state SHALL 提供「全部開團主」與當月出現過的開團主選項（附場數）。選擇某位開團主後，月曆團數與當日列表都只計算該開團主的揪團。

#### Scenario: 選擇開團主
- **WHEN** 當月有 A 開 3 團、B 開 1 團，選擇 A
- **THEN** 篩選選單顯示「A（3 場）」，月曆與列表只顯示 A 的揪團

#### Scenario: 切回全部
- **WHEN** 選擇「全部開團主」
- **THEN** 回到顯示所有揪團

### Requirement: 報名、候補與退出
揪團詳細畫面 SHALL 依 `my_status` 與 `status` 顯示一個主要按鈕：未報名且開放中時為「報名」（額滿時為「加入候補」）；已是成員或候補時為「退出」；開團主看到「取消揪團」與「編輯」。操作成功後，state MUST 重新載入該揪團與當月資料。

#### Scenario: 報名成功
- **WHEN** 按「報名」，API 回 `status=member`
- **THEN** 顯示「報名成功」，按鈕變成「退出」，剩餘名額減 1

#### Scenario: 額滿加入候補
- **WHEN** 按「加入候補」，API 回 `status=waitlisted`、`waitlist_position=2`
- **THEN** 顯示「已加入候補，目前第 2 位」，按鈕變成「退出」

#### Scenario: 退出
- **WHEN** 成員按「退出」並在確認對話框按「確定」
- **THEN** 呼叫 `DELETE /api/v1/groups/{id}/members/{自己的 id}`，成功後按鈕變回「報名」

#### Scenario: 取消揪團
- **WHEN** 開團主按「取消揪團」並確認
- **THEN** 呼叫 `PATCH {"status": "cancelled"}`，成功後該團從月曆消失

#### Scenario: 操作失敗
- **WHEN** API 回 409（例如 `GROUP_CLOSED`）
- **THEN** 顯示後端錯誤的 `message`，按鈕恢復可按

#### Scenario: 操作進行中
- **WHEN** 已按下按鈕、API 尚未回應
- **THEN** 按鈕停用並顯示載入中，避免重複送出

### Requirement: 開團與編輯表單
「我要開團」SHALL 開啟表單，欄位：店家（下拉選單）、標題、日期、開始時間、結束時間、人數上限、費用（選填）、遊戲（選填）、簡介（選填）。從某天點「我要開團」時，日期預設為該天。開團主編輯時，同一份表單帶入現有值。送出前，前端 SHALL 檢查必填欄位、人數上限 >= 2、結束時間晚於開始時間；後端回 422 或 404 時，顯示錯誤訊息。

#### Scenario: 開團成功
- **WHEN** 填好必填欄位並送出
- **THEN** 呼叫 `POST /api/v1/groups`，成功後關閉表單，月曆跳到該日並顯示新揪團

#### Scenario: 缺少必填欄位
- **WHEN** 沒填標題就送出
- **THEN** 不呼叫 API，標題欄位顯示「請填寫標題」

#### Scenario: 結束時間早於開始時間
- **WHEN** 結束時間早於開始時間
- **THEN** 不呼叫 API，顯示「結束時間要晚於開始時間」

#### Scenario: 後端驗證失敗
- **WHEN** 後端回 422 或 404
- **THEN** 表單保留輸入內容，並顯示後端回傳的錯誤訊息

### Requirement: RWD 與路由
正式頁面路由為 `/groups`，參考畫面為 `/proto/groups`（只有 `SHOW_PROTOTYPES=true` 時註冊）。正式頁面 SHALL 使用 `core/layout/` 的斷點：手機版月曆在上、當日列表在下；平板與桌機版月曆與列表左右並排。正式頁面 MUST NOT 寫死顏色、字級、間距，一律使用 `app/theme/`。

#### Scenario: 手機寬度
- **WHEN** 視窗寬度 < 600
- **THEN** 月曆與當日列表上下排列，畫面沒有水平捲軸

#### Scenario: 桌機寬度
- **WHEN** 視窗寬度 >= 1024
- **THEN** 月曆與當日列表左右並排

#### Scenario: 參考畫面只在開發版出現
- **WHEN** `SHOW_PROTOTYPES` 不是 `true`
- **THEN** `/proto/groups` 不存在，`/groups` 仍可使用
