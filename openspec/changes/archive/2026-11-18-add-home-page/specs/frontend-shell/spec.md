## ADDED Requirements

### Requirement: 主要導覽列
畫面框架 SHALL 提供主要導覽列，依序為：首頁（`/`）、揪團（`/groups`）、推薦（`/games-advisor`）、規則（`/rules`）、訂位（`/booking`）。手機寬度（< 600）時位於畫面底部，平板與桌機（≥ 600）時位於畫面頂部。目前所在的頁面 SHALL 有選取樣式：路徑等於該項目，或是該項目的子路徑（例如 `/booking/mine` 選取「訂位」、`/rules/1` 選取「規則」）。導覽列取代暫時的頁面入口（`_TemporaryNav`），MUST NOT 同時出現兩者。開發環境的身分切換器維持在最上方。

#### Scenario: 手機在底部
- **WHEN** 畫面寬度為 400
- **THEN** 導覽列在畫面底部，顯示五個項目的圖示與文字

#### Scenario: 桌機在頂部
- **WHEN** 畫面寬度為 1280
- **THEN** 導覽列在畫面頂部，顯示五個項目

#### Scenario: 選取目前頁面
- **WHEN** 目前在 `/booking/mine`
- **THEN** 「訂位」為選取狀態，其他項目不是

#### Scenario: 首頁的選取只看完整路徑
- **WHEN** 目前在 `/groups`
- **THEN** 「揪團」為選取狀態，「首頁」不是

#### Scenario: 點導覽項目
- **WHEN** 使用者點「規則」
- **THEN** 前往 `/rules`

#### Scenario: 不在任何項目
- **WHEN** 目前在 `/health` 或 `/proto/...`
- **THEN** 導覽列照常顯示，沒有項目為選取狀態

#### Scenario: 只有一組導覽
- **WHEN** 開啟任何頁面
- **THEN** 每個導覽項目（`shell-nav-home`、`shell-nav-groups`、`shell-nav-advisor`、`shell-nav-rules`、`shell-nav-booking`）在畫面上只出現一次，暫時的頁面入口已移除
