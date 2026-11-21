# Spec Delta

## Purpose

揪團的確定成團與站內通知。開團主確定成團、取消揪團（解散）、候補遞補為成員時，系統替受影響的玩家建立通知；玩家只查得到、只改得了自己的通知。

## ADDED Requirements

### Requirement: 確定成團
`PATCH /api/v1/groups/{group_id}` SHALL 接受 `{"confirmed": true}`，把 `groups.confirmed_at` 設為現在時間，回 200 與揪團資料（`confirmed_at` 不為空）。只有開團主或 `admin` 可以確定成團。`confirmed` 只接受 `true`。成團後揪團仍是 `status=open`，可以繼續報名、候補、退出與取消。

#### Scenario: 開團主確定成團
- **WHEN** 開團主對開放中、還沒結束、還沒成團的揪團送出 `{"confirmed": true}`
- **THEN** 回 200，`confirmed_at` 為現在時間，`status` 仍為 `open`

#### Scenario: 管理員確定成團
- **WHEN** 以 `as_admin` 對別人的揪團送出 `{"confirmed": true}`
- **THEN** 回 200，`confirmed_at` 不為空

#### Scenario: 非開團主
- **WHEN** 成員或其他玩家送出 `{"confirmed": true}`
- **THEN** 回 403，`confirmed_at` 維持空值，不建立任何通知

#### Scenario: 已經成團
- **WHEN** 對已成團的揪團再送出 `{"confirmed": true}`
- **THEN** 回 409，`error.code=GROUP_ALREADY_CONFIRMED`，`confirmed_at` 不變，不建立任何通知

#### Scenario: 已取消或已結束
- **WHEN** 對已取消或已過 `end_at` 的揪團送出 `{"confirmed": true}`
- **THEN** 回 409，`error.code=GROUP_CLOSED`

#### Scenario: confirmed 帶 false 或 null
- **WHEN** 送出 `{"confirmed": false}` 或 `{"confirmed": null}`
- **THEN** 回 422

#### Scenario: 揪團不存在
- **WHEN** `group_id` 不存在
- **THEN** 回 404，`error.code=GROUP_NOT_FOUND`

#### Scenario: 還沒成團
- **WHEN** 查詢一個沒有確定成團的揪團
- **THEN** 回應的 `confirmed_at` 為 `null`

### Requirement: 成團通知
確定成團成功時，系統 SHALL 在同一個交易裡，替每位 `status=member` 的成員建立一則 `type=group_confirmed` 的通知。按下確定的人 MUST NOT 收到，候補 MUST NOT 收到。

#### Scenario: 通知成員
- **WHEN** 開團主 A 的揪團有成員 A、B、C 與候補 D，A 確定成團
- **THEN** B、C 各有一則 `group_confirmed`，A、D 沒有

#### Scenario: 管理員代為確定
- **WHEN** 管理員替開團主 A 的揪團（成員 A、B）確定成團
- **THEN** A、B 各有一則 `group_confirmed`

### Requirement: 解散通知
開團主或 `admin` 以 `{"status": "cancelled"}` 取消揪團成功時，系統 SHALL 在同一個交易裡，替每位成員與候補建立一則 `type=group_cancelled` 的通知。按下取消的人 MUST NOT 收到。不論是否已成團，都一樣通知。

#### Scenario: 通知成員與候補
- **WHEN** 開團主 A 的揪團有成員 A、B 與候補 C，A 取消揪團
- **THEN** B、C 各有一則 `group_cancelled`，A 沒有

#### Scenario: 取消失敗不通知
- **WHEN** 非開團主送出 `{"status": "cancelled"}`
- **THEN** 回 403，不建立任何通知

### Requirement: 候補正取通知
候補依報名先後遞補為成員時，系統 SHALL 在同一個交易裡，替每位被遞補的玩家建立一則 `type=waitlist_promoted` 的通知。觸發情況包括：成員自己退出、成員被開團主或 admin 移除、開團主調高人數上限。

#### Scenario: 成員退出後遞補
- **WHEN** 額滿的揪團有候補 C、D（C 先報名），成員 B 退出
- **THEN** C 變成成員並有一則 `waitlist_promoted`，D 沒有通知

#### Scenario: 調高人數上限後遞補
- **WHEN** 開團主把人數上限加 2，候補有 C、D、E
- **THEN** C、D 變成成員並各有一則 `waitlist_promoted`，E 沒有

#### Scenario: 候補退出不通知
- **WHEN** 候補 C 自己退出
- **THEN** 沒有人遞補，不建立任何通知

#### Scenario: 沒有候補
- **WHEN** 成員退出但沒有候補
- **THEN** 不建立任何通知

### Requirement: 查詢自己的通知
`GET /api/v1/group-notifications` SHALL 回 200 與 `{"items": [...], "total": n, "unread_count": m}`，只包含目前使用者的通知，依建立時間由新到舊排序，並支援 `page`（預設 1）、`page_size`（預設 20，最大 100）。

每則通知包含：
- `id`、`type`（`group_confirmed`、`group_cancelled`、`waitlist_promoted`）
- `group`：`id`、`title`、`start_at`
- `read_at`：空值代表未讀
- `created_at`

`unread_count` 是目前使用者全部未讀的數量，不受分頁影響。

#### Scenario: 只看到自己的
- **WHEN** B 和 C 各有通知，B 查詢
- **THEN** 只回 B 的通知，`total` 與 `unread_count` 只算 B 的

#### Scenario: 新的在前、分頁
- **WHEN** B 有 3 則通知，查 `page_size=2`
- **THEN** 回最新的 2 則，`total=3`，`unread_count=3`

#### Scenario: 沒有通知
- **WHEN** 沒有任何通知的玩家查詢
- **THEN** 回 200，`items=[]`，`total=0`，`unread_count=0`

#### Scenario: 分頁參數錯誤
- **WHEN** `page=0` 或 `page_size=101`
- **THEN** 回 422

#### Scenario: 未登入
- **WHEN** 在 `AUTH_MODE=jwt` 下不帶 token 呼叫
- **THEN** 回 401

### Requirement: 標成已讀
`PATCH /api/v1/group-notifications/{notification_id}` 帶 `{"read": true}` SHALL 把 `read_at` 設為現在時間，並回 200 與該則通知。已讀的再標一次 MUST 回 200，`read_at` 不變。`read` 只接受 `true`。別人的通知視同不存在。

#### Scenario: 標成已讀
- **WHEN** B 對自己未讀的通知送出 `{"read": true}`
- **THEN** 回 200，`read_at` 不為空；之後查詢的 `unread_count` 少 1

#### Scenario: 重複標成已讀
- **WHEN** 對已讀的通知再送一次
- **THEN** 回 200，`read_at` 維持第一次的時間

#### Scenario: 別人的通知
- **WHEN** C 對 B 的通知送出 `{"read": true}`
- **THEN** 回 404，`error.code=GROUP_NOTIFICATION_NOT_FOUND`，B 的通知維持未讀

#### Scenario: 通知不存在
- **WHEN** `notification_id` 不存在
- **THEN** 回 404，`error.code=GROUP_NOTIFICATION_NOT_FOUND`

#### Scenario: read 帶 false
- **WHEN** 送出 `{"read": false}` 或空的 body
- **THEN** 回 422
