## ADDED Requirements

### Requirement: 店員看板顯示座位圖
店員看板 prototype（`/proto/booking/staff`）SHALL 包含座位圖，使用 `InteractiveViewer + Stack + Positioned` 繪製 1000×700 固定畫布上的桌子。桌子 SHALL 依佔用狀態著色：`available` 為綠色、`unavailable` 為紅色。使用者 SHALL 能以 `InteractiveViewer` 縮放（0.25×–2.0×）與平移座位圖。

#### Scenario: 顯示座位圖
- **WHEN** 店家人員進入店員看板，選擇 1F 並查詢
- **THEN** 1F 的 A–G 桌依資料庫座標繪製在畫布上，`available` 桌為綠色、`unavailable` 桌為紅色

#### Scenario: 切換樓層
- **WHEN** 店家人員從樓層下拉選單切換至 B1
- **THEN** 座位圖更新為 B1 的 H–I 桌

#### Scenario: 縮放與平移
- **WHEN** 使用者雙指縮放或拖曳座位圖
- **THEN** 座位圖依手勢縮放或平移

#### Scenario: 點擊桌子查看詳情
- **WHEN** 店家人員點擊一張 `unavailable` 的桌子
- **THEN** 顯示該桌的訂位摘要（訂位編號、聯絡人、時間、人數、狀態）

#### Scenario: 點擊空桌
- **WHEN** 店家人員點擊一張 `available` 的桌子
- **THEN** 顯示桌子代號與容量，無訂位資訊

#### Scenario: 篩選日期範圍
- **WHEN** 店家人員選擇日期範圍 2026-11-17 至 2026-11-17 並查詢
- **THEN** 座位圖與訂位列表皆依該日期範圍更新

#### Scenario: 店員看板同時顯示訂位列表
- **WHEN** 店家人員查詢某日期範圍
- **THEN** 頁面下方或側邊顯示該範圍的所有訂位列表（Card 列表，與現有 `BookingListProtoPage` 類似）

### Requirement: 玩家查詢顯示座位圖
玩家查詢頁面（`/proto/booking/list`）SHALL 顯示當天自己訂位的座位圖。玩家自己的訂位桌子 SHALL 以藍色標示，其他被佔用的桌子 SHALL 以紅色標示，空桌 SHALL 以綠色標示。

#### Scenario: 玩家有當天訂位
- **WHEN** 玩家今天有訂 A 桌，進入查詢頁面
- **THEN** 座位圖顯示 A 桌為藍色，其他被佔用的桌為紅色，空桌為綠色

#### Scenario: 玩家沒有當天訂位
- **WHEN** 玩家今天沒有訂位，進入查詢頁面
- **THEN** 座位圖顯示所有桌子，依 available/unavailable 狀態著色（綠／紅），無藍色桌

#### Scenario: 玩家點擊自己的訂位桌
- **WHEN** 玩家點擊藍色的桌子
- **THEN** 顯示該訂位的詳細資訊（時間、人數、狀態）

#### Scenario: 玩家點擊他人的訂位桌
- **WHEN** 玩家點擊紅色的桌子
- **THEN** 僅顯示「此時段已被預訂」，不顯示訂位人資訊
