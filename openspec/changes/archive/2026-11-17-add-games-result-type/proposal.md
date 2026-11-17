# Proposal

## Why

戰績功能（`matches`）要知道每款遊戲的結果怎麼記：記哪一方獲勝、記每人分數，還是記全隊是否通過。這是遊戲本身的屬性（依規則書每款只有一種），所以放在共用表 `games`，登錄遊戲時設定，`matches` 之後直接讀取。

## What Changes

- `games` 新增欄位 `result_type`（文字），值只有 `faction`、`score`、`cooperative`。
  - `faction`：陣營勝負，記哪一方獲勝。例：血與刃的白薔薇、阿瓦隆、總統與炸彈客
  - `score`：個人分數，記每人的分數與名次。例：馬可波羅、阿布斯學院
  - `cooperative`：合作，記全隊是否通過，以及玩到哪個進度（例如第五關）。例：瘋狂鬼宅
- Python 端用 Enum（`ResultType`），每個值寫中文註解。
- 資料庫存成 `text`，用 CHECK 限制三個值，不使用 PostgreSQL 原生 enum。
- 新增一個 migration（`0004`），只加這個欄位與其 CHECK。
- `result_type` 暫時**可以為空**（NULL＝尚未設定），理由見 design.md D2；**需使用者確認**。
- 因為匯入／匯出／同步共用桌遊資料的檔案格式是嚴格驗證（`extra="forbid"`），`games_advisor` 的 `GameData`／`ExportedGame` 必須同步認得 `result_type`，否則加欄位後「匯出桌遊」會直接失敗（見 design.md D3）。
- 不做：`matches` 的任何功能、每回合紀錄格式、前端、替既有欄位補 comment、修改其他欄位。

## Capabilities

### New Capabilities
- `games-result-type`: 共用桌遊表的結果類型欄位——允許的值、資料庫層限制、空值行為，以及匯入／匯出／同步檔案對它的處理。

### Modified Capabilities

（無。目前沒有 games 相關的主規格，`database-baseline` 只涵蓋 `auth_users`、`booking_shops`。）

## Impact

- **受影響 domain／主責**：共用表 `games`（擁有者：立倫，`backend/app/core/games/`）；`games_advisor`（主責：立倫）的匯入／匯出／同步 schema。使用者（非立倫）改共用區，MR 要 @ 立倫（AGENTS.md 第 2 節規則 3、第 3 節）。
- **契約**：有。
  - 資料表結構：`games` 多一欄 → migration，**要 @ 瑋鋐審核**。
  - 檔案格式：`games.json`、匯出檔多一個 `result_type` 欄位（同步檔案是團隊共用的契約，**要 @ 立倫審核**）。
  - HTTP API：**沒有端點的回應格式改變**。`POST /api/v1/.../messages` 的 `AdvisorGame` 與 `search.GAME_FIELDS` 都是明列欄位，不含 `result_type`；`groups` 只讀 `Game.id`、`Game.name`。
- **程式**：`app/core/games/models.py`、新 migration、`app/domains/games_advisor/schemas.py`（`GameData`、`ExportedGame`）。`repository.py` 因為用 `select(Game.__table__)`，欄位會自動帶出，不需改。
- **前端／交接說明**：無（`needs-ui` 不需要）。
- **套件**：無新增。
