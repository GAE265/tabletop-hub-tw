# Spec Delta

## Purpose

揪團的遊戲由單選改為複選。以下取代 `add-groups-calendar` 的 `groups` spec 中所有關於 `game_id`、`game` 的部分；其他行為不變。

## MODIFIED Requirements

### Requirement: 揪團的遊戲
開團（`POST /api/v1/groups`）與修改（`PATCH /api/v1/groups/{group_id}`）SHALL 接受選填的 `game_ids`（整數陣列，不限數量，可以是空陣列），取代原本的 `game_id`。揪團的回應 SHALL 以 `games`（陣列，每筆 `id`、`name`，依選擇的順序）取代原本的 `game`；沒有遊戲時為空陣列。`PATCH` 帶 `game_ids` 時整份取代，帶空陣列代表清除所有遊戲；不帶時不變。

#### Scenario: 開團時選多款遊戲
- **WHEN** 開團帶 `game_ids=[3, 1]`，兩款都存在
- **THEN** 回 201，`games` 依序為遊戲 3、遊戲 1（各有 `id`、`name`）

#### Scenario: 不選遊戲
- **WHEN** 開團不帶 `game_ids`，或帶空陣列
- **THEN** 回 201，`games` 為空陣列

#### Scenario: 遊戲不存在
- **WHEN** `game_ids` 中有遊戲不在 `games`
- **THEN** 回 404，`GROUP_GAME_NOT_FOUND`（沿用既有的錯誤代碼），`details.game_ids` 列出不存在的編號；不建立揪團

#### Scenario: 重複的遊戲
- **WHEN** `game_ids=[3, 3]`
- **THEN** 回 422

#### Scenario: 修改遊戲
- **WHEN** 開團主 `PATCH` 帶 `game_ids=[2]`
- **THEN** 回 200，`games` 只剩遊戲 2

#### Scenario: 清除遊戲
- **WHEN** 開團主 `PATCH` 帶 `game_ids=[]`
- **THEN** 回 200，`games` 為空陣列

#### Scenario: 修改其他欄位時遊戲不變
- **WHEN** `PATCH` 只帶 `title`
- **THEN** `games` 維持原本的遊戲

#### Scenario: 列表也帶遊戲
- **WHEN** `GET /api/v1/groups` 查到有遊戲的揪團
- **THEN** 每筆的 `games` 都正確，不因遊戲數量重複列出同一個揪團

### Requirement: 揪團與遊戲的資料表
migration SHALL 新增 `group_games`（`group_id` 參照 `groups.id`，刪除揪團時一併刪除；`game_id`（`bigint`）參照 `games.id`，遊戲被刪除時刪掉這筆對應、揪團保留；`position` 為選擇的順序；(`group_id`, `game_id`) MUST 唯一），把既有 `groups.game_id` 不為空的資料搬進 `group_games`，再移除 `groups.game_id`。新表與欄位 SHALL 有中文說明（`comment`）。migration MUST 可以 downgrade：降級時把每個揪團順序第一的遊戲放回 `groups.game_id`。

#### Scenario: 升級時搬移既有資料
- **WHEN** 升級前有一個揪團 `game_id=3`
- **THEN** 升級後 `group_games` 有 (該揪團, 3, position=1)，`groups` 沒有 `game_id` 欄位

#### Scenario: 遊戲被刪除
- **WHEN** 某個被揪團選用的遊戲被刪除（例如共用桌遊同步）
- **THEN** 刪除成功，`group_games` 中的對應被刪除，揪團本身保留

#### Scenario: 降級
- **WHEN** 從新版降級
- **THEN** `groups.game_id` 恢復，值為每個揪團順序第一的遊戲，`group_games` 被移除
