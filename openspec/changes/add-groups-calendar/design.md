# Design

## Context

`groups` domain 目前沒有任何程式。已有的基礎：
- `core/auth.py` 的 `CurrentUser`、`get_current_user`、`require_role`；`core/errors.py` 的 `AppError`，用來回傳統一的錯誤格式；`core/db.py` 的 `SessionRepository.transaction()`，交易邊界由 service 決定。
- 共用資料表 `booking_shops`（UUID，在 `domains/booking/models.py`，擁有者瑋鋐）、`auth_users`（UUID，在 `domains/auth/models.py`，擁有者立倫）、`games`（`bigint` 主鍵，在 `core/games/models.py`，擁有者立倫）。
- 測試用的 `as_player`、`as_shop_staff`、`as_admin` fixture，以及會建立並升級 `_test` 資料庫的 `db` fixture（`tests/conftest.py`）。
- 前端已有 `core/api/`（dio 與 `ApiException`）、`core/layout/` 斷點、`test/support/fakes.dart`，`health` domain 可以當作分層寫法的範本。

## Goals / Non-Goals

**Goals:**
- 完成 `specs/groups` 的所有情境（後端）與 `specs/groups-calendar-page` 的所有情境（前端）。
- 報名、退出、遞補在同時操作時人數也正確。

**Non-Goals:**
- 地區篩選、遞補通知、揪團 Agent、付款與退費。
- 修改共用表的結構。
- 登入（`auth`，立倫負責，階段 3）。

## Decisions

**D1 一張成員表，用 `status` 區分成員與候補。** `group_members`：`id`、`group_id`、`user_id`、`status`（`member`／`waitlisted`）、`joined_at`（報名時間）、(`group_id`, `user_id`) 唯一。候補順位不另外存欄位，由「同團 `status=waitlisted` 依 `joined_at`、`id` 排序」計算，退出時不需要重新編號。遞補時只把 `status` 改成 `member`，`joined_at` 保持原本的報名時間，所以成員名單依報名先後排序時，遞補者仍排在原本的位置。替代方案：分成 `group_members` 與 `group_waitlist` 兩張表，但遞補時要跨表搬移資料，比較容易出錯，所以不採用。

**D2 `ended` 不儲存。** `groups.status` 只存 `open`／`cancelled`；回應時 service 依 `end_at <= now` 算出 `ended`。這樣不需要排程去更新狀態。service 透過注入的 `now()` 取得現在時間，單元測試可以固定時間。

**D3 並發控制用列鎖。** 報名、退出、修改 `capacity` 時，repository 先以 `SELECT ... FOR UPDATE` 鎖住該筆 `groups`，再計算成員數並寫入，全部在 service 的同一個 `transaction()` 中完成。替代方案：用 `capacity` 的 CHECK 或資料庫觸發器來擋，但成員數無法用 CHECK 表達，觸發器又會把邏輯藏在資料庫裡，所以不採用。

**D4 列表的時間篩選用時間點，不用日期。** API 用 `start_from`、`start_before`（ISO 8601，含時區），由前端依裝置時區換算月份或日期的邊界。後端一律以 UTC 儲存與回傳（4.3），不需要知道使用者的時區。

**D5 列表預設排除已取消的揪團。** 月曆只需要有效的揪團，所以這輪不提供 `include_cancelled` 參數；詳細資料仍可查到已取消的揪團。`page_size` 上限 100，前端一個月超過 100 團時繼續載入後面的分頁。

**D6 回應一次帶齊顯示需要的資料。** 揪團回應內含 `shop`、`organizer`、`game` 的名稱，以及 `member_count`、`waitlist_count`、`remaining_slots`、`my_status`。列表用一次查詢加上聚合計算取得，避免月曆每一團都要再打一次 API（N+1）。

**D7 讀取共用表的方式（待擁有者確認）。** 4.2 規定共用表由擁有者建立 repository，每張表只能有一個 repository，所以 `groups` 不自行建立 `booking_shops`、`auth_users`、`games` 的 repository。需要的讀取方法：
- 店家是否存在、店名：請瑋鋐提供（例如 `BookingShopRepository.get(shop_id)`）。
- 使用者的 `display_name`：請立倫提供（例如 `AuthUserRepository`）。
- 遊戲是否存在、遊戲名稱：請立倫在 `GameRepository` 加上 `get(game_id)`。

列表查詢中 JOIN 共用表取得名稱，屬於 `groups` repository 自己的查詢，只讀不寫，不另外建立共用表的 model。若擁有者同意由永傑代為新增這些方法，就放進 MR 1，並在 MR 說明 @ 擁有者。這點在動工前要先確認（tasks 1.2）。

**D8 開團表單的店家清單（待瑋鋐確認）。** 目前沒有 `GET /api/v1/shops`。方案 A：請瑋鋐在 `booking` 新增（建議）。方案 B：經瑋鋐同意後，由永傑在 MR 1 中代為新增，並 @ 瑋鋐審核。這個 API 不屬於 `groups`，不能把店家清單 API 放在 `/api/v1/groups` 底下。在 API 完成前，參考畫面先用 seed 的「測試桌遊店」開發。

**D9 錯誤代碼。** `GROUP_NOT_FOUND`、`GROUP_SHOP_NOT_FOUND`、`GROUP_GAME_NOT_FOUND`、`GROUP_MEMBER_NOT_FOUND`（404）；`GROUP_ALREADY_JOINED`、`GROUP_CLOSED`、`GROUP_CAPACITY_BELOW_MEMBERS`、`GROUP_ORGANIZER_CANNOT_LEAVE`（409）；欄位驗證交給 Pydantic，回 422 `VALIDATION_ERROR`；權限不足使用 `PermissionDenied`（403）。全部在 service 拋出 `AppError`，router 不判斷。

**D10 後端分層。** `domains/groups/`：`router.py` 只負責解析請求與 `Depends(get_current_user)`；`service.py` 處理權限（開團主或 admin）、狀態判斷、遞補，以及交易邊界；`repository.py` 負責所有查詢；`models.py` 定義 `Group`、`GroupMember`；`schemas.py` 定義請求與回應。service 單元測試用手寫的 `FakeGroupsRepository`（7.5），API 測試連 `_test` 資料庫。`main.py` 加上掛載 `groups` router 的一行，`tests/conftest.py` 的 `TRUNCATE` 加上兩張新表。這兩個檔案屬於立倫的共用區，MR 要 @ 立倫。

**D11 前端分層。** `domains/groups/data/`：freezed DTO（`Group`、`GroupMember`、`JoinResult`、`GroupInput`）與 `GroupsRepository` 介面及 `HttpGroupsRepository` 實作。`state/`：
- `GroupsCalendarNotifier`：管理月份、選取日期、開團主篩選，並計算每日團數與當日列表。
- `GroupDetailNotifier`（family，以 `groupId` 區分）：處理報名、退出、取消揪團，並記錄操作是否進行中、是否發生錯誤。
- `GroupFormNotifier`：處理開團與編輯，包含前端驗證與送出。

月曆格子用 Flutter 內建元件自行排版，不新增套件（例如 `table_calendar`）。這樣不必另寫新增套件的理由，也方便套用 `app/theme/`。使用者 id 從 `core/dev/` 的目前身分取得；`auth` 完成後改從登入狀態取得，所以這部分包成一個 provider，之後只需要替換這一處。

**D12 拆成三個 MR。** 第 2 節規則 6 規定一個 MR 只做一件事：
- MR 1：後端 API 與 migration（@ 立倫、瑋鋐）。
- MR 2：前端 `data/`、`state/`、參考畫面與交接說明（`needs-ui`）。
- MR 3：正式月曆頁 `pages/`。

## Risks / Trade-offs

- [`groups` 在 PostgreSQL 是非保留關鍵字（window frame 的 `GROUPS`）] → 可以當作表名，SQLAlchemy 會視需要加上引號；migration 測試會實際建表來驗證。如果組內偏好避開，可以改名為 `groups_groups`，但要在建表前決定。
- [共用表的讀取方法與店家清單 API 要等其他人] → tasks 1.2 先確認；MR 1 的 service 測試用 fake 實作，不會被卡住。
- [時區換算錯誤會讓揪團顯示在錯的日期] → state 測試涵蓋 UTC+8 跨日的情境（例如台灣時間 00:30 的揪團，換算成 UTC 是前一天 16:30）。
- [`my_status` 讓列表回應依使用者而不同] → 不在伺服器端快取列表，目前規模可以接受。
