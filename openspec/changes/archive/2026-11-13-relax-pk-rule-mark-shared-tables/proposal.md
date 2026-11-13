# Proposal

## Why

AGENTS.md 1.8 把 4.4 的主鍵規則從「一律 UUID」改為「預設 UUID」，固定的小型分類表（例如 `game_types`）可用 `bigint` identity；第 3 節也新增「共用資料表」清單，`auth_users` 與 `booking_shops` 都在其中。`openspec/specs/database-baseline/spec.md` 還是舊用詞，與 AGENTS.md 不一致。

## What Changes

- 需求「主鍵一律為 UUID」改名為「主鍵預設為 UUID」。
- 該需求內文改為：資料表的主鍵 `id` 預設 SHALL 為 UUID 型別；固定的小型分類表（如 `game_types`）MAY 使用 `bigint` identity。
- Purpose 的「兩張共用表」改為說明 `auth_users` 與 `booking_shops` 都是 AGENTS.md 第 3 節列出的共用資料表。
- 不改任何程式、model 與 migration。現有兩張表本來就是 UUID 主鍵，行為不變。

## Capabilities

### New Capabilities
無。

### Modified Capabilities
- `database-baseline`: 主鍵需求由「一律 UUID」放寬為「預設 UUID，固定小型分類表可用 bigint identity」。Purpose 的敘述也一併調整（Purpose 不經 delta，直接改主 spec，見 tasks.md）。

## Impact

- 受影響 domain：無程式面影響。`auth_users`（`auth`，共用表，立倫）與 `booking_shops`（`booking`，共用表，瑋鋐）只是文字說明對齊。
- 契約：不變。API、資料表結構、MQTT 都沒有改。
- migration：無。
- 受影響檔案：只有 `openspec/specs/database-baseline/spec.md`（經 archive 套用 delta，加上 Purpose 直接編輯）。
- 不修改 `AGENTS.md`、`docs/review-guide.md` 與 `openspec/changes/archive/`。
