# Design

## Context

- **`groups` 現況**：`groups` domain 已有開團、報名、候補、退出與遞補。
  - 遞補由 `GroupsRepository.promote_waitlisted(group_id, count)` 執行，目前只回傳遞補人數，不回傳是誰。
  - 遞補發生在 `remove_member`（成員退出或被移除）與 `update_group`（調高 `capacity`）兩處。
  - 取消揪團走 `update_group` 的 `{"status": "cancelled"}`。
  - 兩者都在 `with self._repo.transaction()` 裡，並先 `lock_group` 鎖住該揪團。
- **前端現況**：
  - 前端外殼 `app/shell.dart` 在平板與桌機顯示 `TopNavigation`，在手機顯示 `BottomNavigation`。
  - 手機目前沒有共用的頂部列。
- **其他**：專案沒有任何通知功能、排程或背景工作。

## Goals / Non-Goals

**Goals**
- 確定成團、解散、候補正取時，受影響的玩家在站內看得到通知。
- 只動 `groups` domain 與前端外殼。

**Non-Goals**
- 店家通知（屬於 `booking`）。
- Email 與推播。
- 即時推送（WebSocket、SSE）。
- 取消成團、刪除通知、全部標成已讀。

## Decisions

### D1：成團用 `confirmed_at` 欄位，不新增 `status` 值

- **做法**：`groups.status` 維持 `open`／`cancelled`，另加可為空的 `confirmed_at timestamptz`。
- **原因**：
  - 成團後仍然開放報名、候補、退出，和 `open` 的行為完全相同。
  - 如果把成團做成 `status=confirmed`，所有判斷「開放中」的地方（`_is_closed`、列表篩選、前端狀態標籤）都要改。
  - 用時間欄位，也同時記錄了什麼時候成團的。
- **前端判斷**：前端用「`confirmed_at != null` 且狀態為 open」來判斷「已成團」。
- **API**：`GroupUpdate` 新增 `confirmed: Literal[True] | None`，帶 `false` 或 `null` 回 422。這和既有的 `status: Literal["cancelled"]` 寫法一致。

### D2：通知表放在 `groups` domain，表名 `groups_notifications`

- **為什麼不新增 domain**：使用者決定這次只做揪團通知；新增 domain 要改 AGENTS.md 第 3 節，需要組內同意。
- **欄位**：

  | 欄位 | 型別 | 說明 |
  |---|---|---|
  | `id` | UUID | 主鍵 |
  | `user_id` | FK `auth_users` | 收到通知的玩家，有索引 |
  | `group_id` | FK `groups`，`ON DELETE CASCADE` | 通知的揪團 |
  | `type` | text，CHECK | 三種值 |
  | `read_at` | 可為空 | 空值代表未讀 |
  | `created_at` | timestamptz | 建立時間 |

- **`type` 的值**（4.4：每個值都要寫中文註解與遊戲例子）：
  - `group_confirmed`：開團主確定成團，例如《阿瓦隆》團人數夠了，開團主按確定。
  - `group_cancelled`：揪團被取消，例如《卡坦島》團湊不到人，開團主取消。
  - `waitlist_promoted`：候補遞補為成員，例如 5 人《阿瓦隆》團有人退出，第一位候補補上。
- **索引**：`(user_id, created_at DESC)`，供列表排序；未讀數用 `WHERE user_id = ? AND read_at IS NULL` 計算，量小不另建索引。
- **通知文字**：不存揪團名稱與文字。列表查詢時 join `groups`，取目前的 `title` 與 `start_at`，揪團改名後通知也跟著更新；前端依 `type` 組句子。
- **未來擴充**：日後若要做全站通知（含店家），可以再拆成獨立 domain，並把這張表搬過去。

### D3：通知在原本的交易裡寫入

- `GroupsService` 在既有的 `with self._repo.transaction()` 中，呼叫 `self._repo.add_notifications(group_id, user_ids, type)`。動作失敗（403、409）會在寫入前就拋出例外，因此不會留下通知。
- **`promote_waitlisted`**：改成回傳被遞補者的 `user_id` 清單（原本回傳人數）。
  - 呼叫端目前沒有使用回傳值，改了不影響既有行為。
  - Fake repository 要同步修改。
- **收件人查詢**：新增 `list_member_user_ids(group_id, statuses)`，依狀態取出成員與候補的 `user_id`。
- **排除操作者**：在 service 用 `user.id` 從收件人中排除。

### D4：通知 API 的路徑 `/api/v1/group-notifications`

- **路徑**：通知屬於「目前使用者」，不屬於某一個揪團，所以不放在 `/groups/{group_id}/...` 底下。
- **為什麼不用 `/groups/notifications`**：會和 `/groups/{group_id}` 的路徑參數搶匹配，`notifications` 會被當成 UUID 解析而回 422，必須靠路由註冊順序才不會出錯。
- **router 位置**：在 `groups/router.py` 另開一個 `APIRouter(prefix="/group-notifications")`，`main.py` 一起掛載。
- **權限**：
  - 所有角色都可以查詢自己的通知。
  - 查詢條件一律帶 `user_id = current_user.id`。
  - 別人的通知回 404，不回 403，避免透露通知 id 是否存在。
- **回應**：列表回應在既有的分頁格式 `{"items", "total"}` 之外，多一個 `unread_count`，讓鈴鐺只要打一支 API。鈴鐺用 `page_size=1` 查詢。

### D5：前端鈴鐺用輪詢，狀態放在 `groups/state/`

- **狀態**：`groupNotificationsProvider` 放在 `frontend/lib/domains/groups/state/`，負責列表、分頁、`unreadCount`、`markRead`。
- **鈴鐺**：
  - 鈴鐺元件放在 `domains/groups/pages/widgets/notification_bell.dart`，`app/navigation.dart` 引用它。這是 app 引用 domain，方向和 `app/router.dart` 引用各 domain 頁面一樣。
  - 每 60 秒用 `Timer.periodic` 呼叫 `refreshUnread()`，`dispose` 時停止。
  - 時間間隔是 provider 的參數，測試用 `fakeAsync` 推進。
- **擺放位置**：
  - 平板與桌機：放在 `TopNavigation` 的右側。
  - 手機：`AppShell` 多一條很矮的頂部列，只放鈴鐺。鈴鐺不放進底部導覽，底部已經有 6 個項目。
- **標成已讀**：先更新畫面，再送 API；API 失敗時改回未讀，但仍然跳頁。
- **頁面**：
  - 使用者是 `groups` 主責，也是 UI 負責人，所以直接做正式頁面 `pages/group_notifications_page.dart`，不另做參考畫面（與 `add-groups-calendar` 的 MR 3 相同）。
  - 顏色、間距只用 `app/theme`。

### D6：前後端放在同一個 MR

- 使用者決定前後端一起做，同一個分支 `feature/groups-notifications`、同一個 MR。
- 同一個功能的前後端算「一件事」；MR 要 @ 立倫（契約）、瑋鋐（migration）。
- 前端的「確定成團」按鈕只給開團主，和既有的「取消揪團」一致（前端目前只知道使用者 id，不知道角色）；後端仍允許 admin。

## Risks / Trade-offs

- **輪詢的延遲與負擔**：通知最晚 60 秒才出現在鈴鐺上；每位開著頁面的使用者每分鐘查一次。對 Demo 的規模可以接受，之後要即時再改成 SSE。
- **大揪團取消時一次寫很多筆**：人數上限沒有上限，取消時一次寫入 N 筆。目前揪團大多在 10 人以內，用一次 `INSERT ... VALUES` 批次寫入即可。
- **通知不記錄當時的揪團名稱**：揪團改名後，舊通知也顯示新名稱。這比較符合「點進去看到的就是那個揪團」，接受。
- **改 `promote_waitlisted` 的回傳型別**：要同步修改 `tests/groups/fakes.py` 的 fake。屬於自己 domain 的修改，在 MR 說明寫明。
