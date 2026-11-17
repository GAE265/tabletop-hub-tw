# Spec Delta

## Purpose

遊戲清單 API：讓各功能（目前是開團表單）用下拉選單選遊戲，可以依名稱搜尋。讀取共用表 `games`，不修改。

## ADDED Requirements

### Requirement: 遊戲清單與搜尋
`GET /api/v1/games` SHALL 回傳 `{"items": [...], "total": N}`，每筆包含 `id`、`name`（中文名稱）、`english_name`，依 `name` 排序。可選參數：`q`（關鍵字，去掉前後空白後比對 `name` 或 `english_name`，不分大小寫、部分相符）、`page`（預設 1）、`page_size`（預設 20，最大 100）。所有已登入的角色都可以查詢。

#### Scenario: 列出遊戲
- **WHEN** 不帶參數查詢，資料庫有 3 款遊戲
- **THEN** 回 200，`items` 有 3 款，依名稱排序，`total=3`

#### Scenario: 依中文名稱搜尋
- **WHEN** `q=阿瓦`
- **THEN** 只回傳名稱含「阿瓦」的遊戲（例如阿瓦隆）

#### Scenario: 依英文名稱搜尋，不分大小寫
- **WHEN** `q=AVALON`
- **THEN** 回傳英文名稱含「avalon」的遊戲

#### Scenario: 沒有符合的遊戲
- **WHEN** `q` 沒有任何遊戲符合
- **THEN** 回 200，`items` 為空陣列，`total=0`

#### Scenario: 分頁
- **WHEN** 有 25 款遊戲，`page=2&page_size=20`
- **THEN** `items` 有 5 款，`total=25`

#### Scenario: 分頁參數錯誤
- **WHEN** `page=0` 或 `page_size=101`
- **THEN** 回 422

#### Scenario: 未登入
- **WHEN** `AUTH_MODE=jwt` 且沒有帶 token
- **THEN** 回 401
