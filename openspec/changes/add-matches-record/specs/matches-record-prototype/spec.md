# Spec Delta

## Purpose

記錄一局遊戲的前端 `data/`、`state/` 與參考畫面（AGENTS.md 5.4）。參考畫面只用 Flutter 預設元件，供永傑日後做正式頁面時共用同一份 `state/`。

## ADDED Requirements

### Requirement: data 與 state
前端 SHALL 在 `frontend/lib/domains/matches/data/` 提供 freezed DTO 與 `MatchesRepository` 介面及 `HttpMatchesRepository` 實作（JSON 欄位對應後端 `snake_case`），在 `state/` 提供 Riverpod providers 與操作方法：開局、重新整理（重新查詢這局）、加入自己、新增沒有帳號的參加者、移除參加者、記錄回合、確認覆蓋、取消覆蓋、記錄結果、確認。頁面不直接呼叫 API。

#### Scenario: 記錄回合成功
- **WHEN** 呼叫記錄回合，fake repository 回成功
- **THEN** state 的 `turns` 含新回合，狀態不是載入中也沒有錯誤

#### Scenario: 同一回合已有紀錄
- **WHEN** 記錄回合，fake repository 回 `MATCH_TURN_ALREADY_RECORDED`（409）
- **THEN** state 進入「待確認覆蓋」，帶著既有紀錄與使用者剛輸入的內容，`turns` 尚未改動

#### Scenario: 使用者確認覆蓋
- **WHEN** state 在「待確認覆蓋」時呼叫確認覆蓋
- **THEN** repository 收到帶 `overwrite=true` 的同一份內容，成功後 `turns` 為新內容、待確認狀態清除

#### Scenario: 使用者取消覆蓋
- **WHEN** state 在「待確認覆蓋」時取消
- **THEN** 待確認狀態清除，`turns` 不變，repository 沒有再收到請求

#### Scenario: 重新整理
- **WHEN** 呼叫重新整理，fake repository 回含新回合的這局資料
- **THEN** state 的內容更新為新資料，包含 `participant_count`、`account_count`、`confirmed_count`

#### Scenario: 載入中、沒有資料與錯誤
- **WHEN** 查詢進行中／回空列表／回錯誤
- **THEN** state 分別為載入中、沒有資料、錯誤（含後端的 `error.code` 與 `message`）

#### Scenario: 移除參加者被回合擋下
- **WHEN** 移除參加者，fake repository 回 `MATCH_PARTICIPANT_HAS_TURNS`（409）
- **THEN** state 保留錯誤碼、訊息與相關回合編號供畫面顯示，參加者名單不變

#### Scenario: 其他錯誤碼
- **WHEN** 後端回 403、404 或 409（非覆蓋用途）
- **THEN** state 保留錯誤碼與訊息供畫面顯示，不當作成功

### Requirement: 參考畫面
`frontend/lib/prototypes/matches/` SHALL 提供參考畫面，路由掛在 `/proto/matches` 底下（`SHOW_PROTOTYPES=true` 才出現）：開局（含選座位）、加入參加者（自己加入、新增名字）、移除參加者、記錄回合（白薔薇格式的欄位，含出牌座位）、記錄結果（陣營）、確認，以及重新整理按鈕。所有按鈕、輸入欄位與三種狀態（載入中、沒有資料、錯誤）都要做出來；只用 Flutter 預設元件，不調顏色、字型、間距，也不需要 RWD。同一回合已有紀錄時 MUST 顯示「已經有人記錄了，要更新嗎？」，使用者確認後才覆蓋。

#### Scenario: 覆蓋提示
- **WHEN** 記錄回合收到 409
- **THEN** 畫面顯示「已經有人記錄了，要更新嗎？」與確認、取消按鈕

#### Scenario: 各狀態可見
- **WHEN** 切換載入中、沒有資料、錯誤
- **THEN** 畫面各顯示對應的文字，不是空白

#### Scenario: 顯示人數統計
- **WHEN** 載入一局
- **THEN** 畫面顯示「參加人數、有帳號人數、已確認人數」

#### Scenario: 正式部署看不到
- **WHEN** 沒有 `SHOW_PROTOTYPES=true`
- **THEN** `/proto/matches` 不存在

### Requirement: 前端測試與交接
state 的測試 MUST 用 Riverpod override 換成 `frontend/test/support/fakes.dart` 裡手寫的 `FakeMatchesRepository`，不使用 mock 套件。MUST 提供 `docs/handoff/matches.md`（格式依 `docs/handoff/_template.md`），含頁面與按鈕欄位、每個操作對應的 `state/` 方法與後端 API、載入中／沒有資料／錯誤的顯示、參考畫面截圖。

#### Scenario: 交接說明完整
- **WHEN** 檢查 `docs/handoff/matches.md`
- **THEN** 含上述四項內容，且每個操作都標明 `state/` 方法與 API
