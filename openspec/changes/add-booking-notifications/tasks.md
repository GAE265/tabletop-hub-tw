# Tasks

## 1. 準備

- [ ] 1.1 在群組說新表名 `booking_notifications`（AGENTS.md 4.4）
- [ ] 1.2 開 Draft MR，貼上情境表格，@ 瑋鋐、立倫

## 2. 後端

- [x] 2.1 測試：migration `0014`（中文說明、種類限制、降版）
- [x] 2.2 測試：訂位成功產生通知、別家店人員收不到、失敗不寫入
- [x] 2.3 測試：`GET`／`PATCH /api/v1/booking-notifications`（列表、分頁、別人的、已讀、422、401）
- [x] 2.4 model 與 migration `0014`
- [x] 2.5 repository：查店家人員、寫入、列表、標成已讀
- [x] 2.6 service 與 router（加在既有的 booking router，`main.py` 不用改）

## 3. 前端

- [x] 3.1 測試：訂位通知 state（未讀數、列表、分頁、標成已讀）
- [x] 3.2 測試：合併鈴鐺、`/notifications` 兩個分頁、訂位通知列表；修改揪團通知、導覽列、路由的既有測試
- [x] 3.3 測試：超時計算與店家看板、座位圖的標示
- [x] 3.4 `booking/data`、`booking/state`：訂位通知 DTO、repository、state、`bookingClockProvider`、`overtimeMinutes`
- [x] 3.5 `groups`：通知列表改成 `GroupNotificationsList`，移除 `/groups/notifications` 與舊鈴鐺
- [x] 3.6 `app/notifications/`：合併鈴鐺與通知頁，路由 `/notifications`
- [x] 3.7 店家看板與座位圖的超時標示

## 4. 收尾

- [x] 4.1 更新交接說明（`docs/handoff/groups.md`；booking 目前沒有交接說明）
- [x] 4.2 跑完 ruff、pytest、flutter analyze、flutter test
- [x] 4.3 產出 `docs/mr_info/feature/booking-notifications.md`
