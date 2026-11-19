# Tasks

依 AGENTS.md 第 7.2 節：先列情境、寫測試（失敗），再寫功能。

## 1. 前置確認

- [ ] 1.1 在群組告知新表名 `groups_notifications` 與新欄位 `groups.confirmed_at`（AGENTS.md 4.4）
- [ ] 1.2 開 Draft MR，貼上 `groups-notifications` 的情境表，@ 一位組員確認

## 2. MR 1：後端 API 與 migration（@ 立倫、瑋鋐）

- [x] 2.1 寫測試，先提交（此時失敗）：
  - `tests/groups/test_service.py`：確定成團、三種通知的收件人、排除操作者、失敗不寫通知
  - `tests/groups/test_api.py`：`confirmed` 的 200／403／409／422／404；通知列表、分頁、`unread_count`、只看自己；標成已讀、重複標、別人的 404、422；未登入 401
  - `tests/migrations`：新表與欄位都有中文說明（沿用既有的 comment 檢查）
- [x] 2.2 `models.py`：
  - `Group.confirmed_at`
  - 新增 `GroupNotification` 與 `NOTIFICATION_TYPES`，每個值都要有中文註解
- [x] 2.3 Migration `0013_groups_notifications.py`：新增欄位、建表、CHECK 限制、`(user_id, created_at)` 索引，以及所有欄位的 comment
- [x] 2.4 `repository.py`：
  - `promote_waitlisted` 改成回傳 `list[uuid.UUID]`
  - 新增 `list_member_user_ids`、`add_notifications`、`list_notifications`、`count_unread`、`find_notification`、`mark_read`
- [x] 2.5 `tests/groups/fakes.py`：同步修改 fake repository
- [x] 2.6 `schemas.py`：
  - `GroupUpdate.confirmed`、`GroupResponse.confirmed_at`
  - `NotificationResponse`、`NotificationListResponse`（含 `unread_count`）、`NotificationUpdate`
- [x] 2.7 `service.py`：
  - 確定成團的檢查（權限、已成團、已關閉）
  - 在取消、確定成團、遞補三處寫入通知，排除操作者
  - 通知的查詢與標成已讀
- [x] 2.8 `router.py` 新增 `/group-notifications` router，並在 `main.py` 掛載
- [x] 2.9 自我檢查：在 `backend/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`
- [ ] 2.10 產出 `docs/mr_info/<分支>.md`，附情境表與對應的測試

## 3. MR 2：前端（MR 1 合併後，從 `dev` 開分支）

- [ ] 3.1 寫測試，先提交（此時失敗）：
  - `test/domains/groups/group_notifications_state_test.dart`：列表、分頁、未讀數、標成已讀（成功與失敗）、60 秒更新
  - `test/domains/groups/pages/`：鈴鐺數字（0、3、99+、失敗）、通知頁的三種文字、點擊後已讀並跳頁、載入中、空、錯誤與重試；「確定成團」的顯示條件、對話框、成功與失敗；「已成團」標示
  - `test/support/fakes.dart`：`FakeGroupsRepository` 加上通知相關方法
- [ ] 3.2 `data/`：`GroupNotification` DTO，`Group.confirmedAt`，repository 新增 `listNotifications`、`markNotificationRead`、`confirmGroup`
- [ ] 3.3 `state/`：`groupNotificationsProvider`（輪詢時間間隔可注入）；`group_detail_state` 新增 `confirm()` 與顯示條件
- [ ] 3.4 `pages/`：
  - `widgets/notification_bell.dart`
  - `group_notifications_page.dart`
  - 詳細頁的「確定成團」與「已成團」
  - 卡片的「已成團」
- [ ] 3.5 `app/`：導覽列與手機頂部列放鈴鐺，`router.dart` 加上 `/groups/notifications`
- [ ] 3.6 更新 `docs/handoff/groups.md`
- [ ] 3.7 自我檢查：在 `frontend/` 跑 `flutter analyze`、`flutter test`
- [ ] 3.8 產出 `docs/mr_info/<分支>.md`

## Workflow follow-up

- 店家通知（訂位成功、客人超過結束時間還沒離開）交給瑋鋐，在 `booking` 另開 change。
