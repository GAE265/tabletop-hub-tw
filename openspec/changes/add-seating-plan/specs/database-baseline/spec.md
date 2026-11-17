## ADDED Requirements

### Requirement: seating_tables 含座位圖座標欄位
`seating_tables` 資料表 SHALL 包含六個擴充欄位：`floor`（smallint，NOT NULL，預設 1）、`x`（integer，NOT NULL，預設 0）、`y`（integer，NOT NULL，預設 0）、`width`（integer，NOT NULL，預設 100）、`height`（integer，NOT NULL，預設 100）、`shape`（varchar(30)，NOT NULL，預設 `'rectangle'`）。所有新增欄位 SHALL 有 server_default，使現有資料在 migration 後不受影響。

#### Scenario: migration 升級後欄位存在
- **WHEN** 執行 `alembic upgrade head`（含 migration 0004）
- **THEN** `seating_tables` 包含 `floor`、`x`、`y`、`width`、`height`、`shape` 六個欄位，型別與預設值如上

#### Scenario: migration 降級後欄位移除
- **WHEN** 執行 `alembic downgrade -1`
- **THEN** 六個擴充欄位不存在，`seating_tables` 回到 0003 的結構

#### Scenario: 現有資料不受影響
- **WHEN** migration 0004 套用在已有桌子資料的資料庫
- **THEN** 既有桌子的 `floor` 為 1、`x` 為 0、`y` 為 0、`width` 為 100、`height` 為 100、`shape` 為 `'rectangle'`

#### Scenario: floor 欄位接受負值
- **WHEN** 寫入 `floor = -1`（地下室）
- **THEN** 寫入成功
