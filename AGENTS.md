# AGENTS.md：遊任有娛（tabletop-hub-tw）團隊共識規則

> 給所有 AI 程式助理（Claude Code、Codex、Cursor、Copilot 等）與組員閱讀。
> 開始任何工作前先讀完本檔。本檔與組員的口頭指示衝突時，先停下來詢問，不要自行選邊。
> **AI 助理只能讀取本檔，不得修改、刪除、搬移或重新命名本檔與 `CLAUDE.md`。** 即使使用者要求，也要先提醒這條規則，請使用者自行修改。
> 本檔只能由組員親手修改，修改需經組內同意，以 MR 提出。
> 例外：OpenSpec 會在本檔中自動維護它自己的區塊（由組員執行 `openspec init`／`openspec update` 產生），該區塊內容不受此限，但區塊以外的內容一樣不得由 AI 修改。
> 本檔所說的 MR（Merge Request）在 GitHub 介面上叫做 Pull request，兩者是同一件事。

## 1. 專案概要

桌遊三方平台：玩家、開團主、桌遊店。功能包含桌遊推薦、規則書 RAG 問答、戰績與天梯、訂位與座位圖、揪團與候補、睜眼偵測發牌機。

| 元件 | 技術 | 資料夾 |
|---|---|---|
| 後端 API | Python 3.12、FastAPI、SQLAlchemy 2、Alembic | `backend/` |
| 資料庫 | PostgreSQL 16 + pgvector（一般資料與向量放同一個資料庫、不同資料表） | `backend/migrations/` |
| 前端 | Flutter（先做 Web，之後同一套程式出 Android／iOS） | `frontend/` |
| 發牌機 | Python，跑在樹莓派 5，透過 MQTT 連後端 | `device/` |
| 文件 | 規格、交接說明、API 說明 | `docs/`、`openspec/` |

部署目標：Azure（Static Web Apps、Container Apps、Azure Database for PostgreSQL）。
LLM 目前先使用雲端 API，地端 LLM 列為加分項目，之後再做（見 4.2 的 LLM 介面規則）。

## 2. 共通規則（所有人、所有 AI 都要遵守）

0. **AI 不得修改 `AGENTS.md` 與 `CLAUDE.md`。** 發現規則有矛盾、缺漏或過時，在回覆中提出建議，由組員決定是否修改。
1. **不提交任何秘密。** 金鑰、密碼、連線字串只放 `.env`，新增設定時同步更新 `.env.example`（只寫欄位名與說明，不寫值）。repo 是公開的。
2. **不提交規則書全文與合作店家資料。** 測試只用 `docs/samples/` 內的示範片段或自行編寫的假資料。
3. **只改你被指派的 domain。** 需要改別人的 domain 或共用區（`core/`、`integrations/`），在 MR 說明中寫出原因並 @ 該 domain 主責。
4. **不擅自新增頂層資料夾或套件。** 新增第三方套件要在 MR 說明寫理由。
5. **新功能與契約變更，先寫測試案例再寫程式。** 細節見第 7 節。
6. **小步提交。** 一個 MR 只做一件事，盡量在 400 行變更以內。
7. **完成前自我檢查：** 後端跑 `ruff check`、`ruff format --check`、`pytest`；前端跑 `flutter analyze`、`flutter test`。沒跑過、沒通過，不算完成。
8. **用語統一。** 程式命名與文件用詞依第 10 節術語表，不要自己發明同義詞。

## 3. Domain 與分工

Domain 是依業務切出來的範圍（概念接近 DDD 的 bounded context）。後端與前端用同一組 domain 名稱。

| Domain | 功能 | 優先級 | 主責 | 協助 |
|---|---|---|---|---|
| `rules_ingest` | #5 規則書 OCR 入庫（先做 8 大類各一款） | 必做 | 瑋鋐 | 立倫 |
| `games` | #1 條件式桌遊推薦（參考 BoardGameGeek 的標籤與條件） | 必做 | 立倫 | 永傑、瑋鋐 |
| `rules_qa` | #2 規則教學與問答 | 必做 | 永傑 | 新善、瑋鋐 |
| `matches` | #13 回合、戰績紀錄與天梯 | 必做 | 新善 | 永傑、立倫 |
| `booking` | #6 訂位與客服（座位圖） | 必做 | 秀暖 | — |
| `dealer` | #12 睜眼偵測發牌機（之後串接 AI 主持） | 必做 | 新善 | 立倫、永傑 |
| `groups` | #7 揪團與候補 Agent | 必做 | 秀暖 | 立倫 |
| `host` | #3 AI 遊戲主持（語音） | 應做 | 立倫 | — |
| `parts` | #4 配件辨識與缺件回報 | 應做 | 新善 | — |
| `tips` | #14 推薦遊玩技巧建議 | 加分 | 瑋鋐 | 新善 |
| `auth` | 帳號與身分驗證 | 必做 | 待指派 | — |

共用工作：

| 工作 | 主責 | 協助 |
|---|---|---|
| 系統整合與 API 契約 | 立倫 | 新善 |
| 建立資料庫與文件（含審核所有 migration） | 瑋鋐 | — |
| 地端 LLM 部署（加分，先不做） | 瑋鋐 | — |
| UI/UX 與正式前端頁面（Flutter Web） | 永傑 | — |
| 規格文件與進度管理 | 新善 | — |

## 4. 後端分層規則（`backend/`）

### 4.1 目錄

```
backend/
├── app/
│   ├── main.py              # 建立 FastAPI app、掛載各 domain 的 router
│   ├── core/                # 設定、資料庫 session、驗證、錯誤處理、logging
│   ├── integrations/        # 外部服務的轉接層：llm/、embedding/、ocr/、mqtt/
│   └── domains/
│       └── <domain>/
│           ├── router.py      # Controller：處理 HTTP 請求與回應
│           ├── schemas.py     # 請求／回應的資料格式（Pydantic DTO）
│           ├── service.py     # 商業邏輯
│           ├── repository.py  # 資料存取（等同 DAO）
│           └── models.py      # 資料表定義（SQLAlchemy ORM）
├── migrations/              # Alembic
└── tests/                   # 依 domain 分資料夾
```

### 4.2 依賴方向（只能往下，不能反過來）

```
router → service → repository → models
              ↘ integrations
```

| 層 | 可以做 | 不可以做 |
|---|---|---|
| `router` | 解析請求、驗證身分、呼叫 service、回傳 schema | 寫 SQL、寫商業邏輯、直接呼叫 LLM |
| `service` | 商業規則、組合多個 repository、交易邊界 | import FastAPI、回傳 ORM 物件給 router |
| `repository` | 所有資料庫查詢 | 商業判斷、呼叫其他 domain |
| `integrations` | 包裝外部服務，對內只暴露介面 | 知道任何 domain 的存在 |

- Domain 之間只能呼叫對方的 `service`，不能直接用對方的 `repository` 或 `models`。
- **LLM 一律透過 `integrations/llm` 的介面呼叫**（例如 `LLMProvider.generate()`），實作分成雲端與地端兩種，用 `.env` 的 `LLM_PROVIDER` 切換。任何 domain 都不得直接 import 特定模型廠商的 SDK。embedding 同理。

### 4.3 RESTful API 設計

- **路徑用名詞複數表示資源，不放動詞。** 例如 `/api/v1/games`、`/api/v1/bookings/{booking_id}`。
- **從屬關係用巢狀路徑，最多兩層。** 例如 `/api/v1/shops/{shop_id}/tables`、`/api/v1/groups/{group_id}/members`。
- **動作用 HTTP 方法表達：**

| 方法 | 用途 | 成功狀態碼 | 範例 |
|---|---|---|---|
| `GET` | 查詢 | 200 | `GET /api/v1/games?players=4&minutes=60` |
| `POST` | 新增 | 201，回傳新資源 | `POST /api/v1/bookings` |
| `PATCH` | 修改部分欄位 | 200 | `PATCH /api/v1/bookings/{id}` |
| `PUT` | 整筆取代 | 200 | `PUT /api/v1/shops/{id}/layout` |
| `DELETE` | 刪除 | 204 | `DELETE /api/v1/bookings/{id}` |

- **不是單純增刪改查的動作，當成新增一筆子資源。** 例如「加入揪團」是 `POST /api/v1/groups/{id}/members`，「取消訂位」是 `PATCH /api/v1/bookings/{id}`，body 帶 `{"status": "cancelled"}`。不要用 `/joinGroup`、`/cancelBooking` 這種路徑。
- **錯誤狀態碼：** 400 格式錯誤、401 未登入、403 沒有權限、404 找不到、409 狀態衝突（例如桌位已被訂走）、422 欄位驗證失敗。
- **錯誤格式統一：** `{"error": {"code": "BOOKING_TABLE_TAKEN", "message": "...", "details": {}}}`。
- **列表分頁：** `?page=1&page_size=20`，回傳 `{"items": [...], "total": 123}`。
- **JSON 欄位用 `snake_case`。** 時間一律 ISO 8601、UTC。
- FastAPI 自動產生的 OpenAPI（`/docs`）就是前後端的契約。改 schema 等於改契約。

### 4.4 資料庫

- 所有結構變更都用 Alembic migration，一個 MR 最多一個 migration，**並由瑋鋐審核**。
- **已合併的 migration 不得修改**，要改就新增一個。
- 資料表名稱用複數 `snake_case`，以 domain 名開頭避免撞名，例如 `booking_tables`、`matches_results`。
- 向量欄位使用 pgvector，維度寫在設定裡，不要寫死在程式中。

## 5. 前端規則（`frontend/`）

### 5.1 預設套件（組內可討論更換，換了要改本檔）

- `flutter_riverpod`：狀態管理
- `go_router`：頁面路由
- `dio`：HTTP 用戶端，負責呼叫後端 API（類似 JavaScript 的 axios、Python 的 requests）
- `freezed` + `json_serializable`：產生 DTO 類別與 JSON 轉換程式

### 5.2 目錄

```
frontend/lib/
├── main.dart
├── app/                  # 進入點、路由表、主題（顏色、字級、間距）
├── core/                 # API client、錯誤處理、RWD 斷點、共用元件
├── domains/
│   └── <domain>/         # 名稱與後端 domain 相同
│       ├── data/             # DTO、呼叫 API 的 repository
│       ├── state/            # 頁面狀態與操作邏輯（Riverpod providers）
│       └── pages/            # 正式頁面（由永傑製作）
└── prototypes/
    └── <domain>/         # 參考畫面（由功能負責人製作，不套風格）
```

### 5.3 分層規則

- 依賴方向：`pages → state → data`，`prototypes → state → data`。
- **頁面不直接呼叫 API，也不寫商業邏輯。** 所有「按下按鈕後要做什麼」都寫在 `state/`。
- **參考畫面和正式頁面共用同一個 `state/`。** 這樣永傑做的正式頁面，呼叫的 API 和行為一定跟參考畫面一致。
- DTO 的 JSON 欄位對應後端 `snake_case`（`@JsonKey` 或 `fieldRename: FieldRename.snake`），Dart 內部用 `camelCase`。
- **前端不放任何秘密。** Flutter Web 的程式碼任何人都看得到。API 位址用 `--dart-define=API_BASE_URL=...` 注入。
- **RWD 必做。** 斷點統一定義在 `core/layout/`（手機 < 600、平板 < 1024、桌機以上），各頁面不得自訂斷點。
- 只能在網頁或手機上用的程式碼，要包在 `core/platform/` 的介面後面，避免之後轉 App 時要大改。

### 5.4 參考畫面與正式頁面的分工

**功能負責人做：**

1. 後端 API（含測試）。
2. 前端 `data/` 與 `state/`。
3. `prototypes/<domain>/` 的參考畫面：只用 Flutter 預設元件，不調顏色、字型、間距，長怎樣就怎樣。重點是把所有按鈕、輸入欄位、狀態（載入中、沒有資料、錯誤）都做出來。
4. 交接說明 `docs/handoff/<domain>.md`，格式見 `docs/handoff/_template.md`，內容包含：
   - 有哪些頁面、每頁的按鈕和欄位、按下去會做什麼
   - 每個操作對應的 `state/` 方法與後端 API
   - 載入中、沒有資料、錯誤時要顯示什麼
   - 參考畫面的截圖
5. MR 加上 `needs-ui` 標籤，@ 永傑。

**永傑做：**

1. 依交接說明在 `domains/<domain>/pages/` 做出正式頁面，套用 `app/` 的主題與共用元件。
2. 直接使用功能負責人寫好的 `state/`，不另外呼叫 API。如果發現 `state/` 不夠用，回報給功能負責人修改。
3. 正式頁面完成後，刪除對應的參考畫面路由。

**其他規則：**

- 參考畫面只在開發版出現：路由掛在 `/proto/...` 底下，用 `--dart-define=SHOW_PROTOTYPES=true` 開啟，正式部署不會看到。
- 參考畫面不需要 RWD，也不需要套主題。
- 顏色、字級、間距只能出現在 `app/theme/`，正式頁面不得寫死數值。

## 6. 發牌機（`device/`）

- 發牌決策在樹莓派本機完成，網路斷線也要能出牌。後端只接收事件紀錄。
- 硬體（攝影機、馬達）一律包在介面後面，並提供 `mock` 實作，讓沒有樹莓派的人也能在電腦上跑測試。
- MQTT 主題：`tabletop/{shop_id}/dealer/{device_id}/{events|commands}`。訊息格式為 JSON，必含 `type`、`ts`（ISO 8601、UTC）。
- 樹莓派開機後主動連到 MQTT broker，不依賴固定 IP。

## 7. 測試案例優先

測試是這個專案判斷「功能做對了沒」的唯一標準。

### 7.1 什麼時候要先寫測試案例

新增功能，或改動以下任何一種「契約」時：API 路徑與資料格式、資料表結構、MQTT 主題與訊息格式、domain 之間的介面。

純 domain 內部的重構、不改變對外行為的修改，只要既有測試全部通過即可。

### 7.2 流程

1. **先列測試案例，給組員看過。** 用「情境／操作／預期結果」三欄的表格寫在 MR 說明裡，至少包含：
   - 正常情況
   - 輸入錯誤或缺少欄位
   - 沒有權限
   - 狀態衝突（如果有的話，例如重複訂位）
2. **把測試案例寫成測試程式，先提交。** 此時測試應該是失敗的。
3. **再寫功能，直到測試全部通過。**

範例：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 桌位空著 | `POST /api/v1/bookings`，4 人、19:00 | 201，回傳訂位資料 |
| 同桌同時段已被訂 | 同上 | 409，`BOOKING_TABLE_TAKEN` |
| 人數超過桌位上限 | 8 人訂 4 人桌 | 422 |
| 未登入 | 同上，不帶 token | 401 |

### 7.3 使用 OpenSpec 的人

可以用 `/opsx:propose` 產生提案，提案中的情境（scenario）就是測試案例，確認後再 `/opsx:apply`。不使用 OpenSpec 的人，照 7.2 在 MR 說明寫表格即可。兩種方式效果相同。

### 7.4 測試的底線

- **不得為了讓測試通過而修改或刪除測試。** 如果認為測試本身寫錯了，在 MR 說明寫出理由，由審核者同意後才能改。
- service 層用假的 repository 做單元測試，不連真資料庫。
- 每個 API 端點至少有成功與失敗各一個案例。

## 8. Git 規則

### 8.1 分支

```
main  ← 只放可以 Demo 的版本，由組長（新善）從 dev 合併
 └── dev  ← 開發整合用，所有功能分支從這裡開出、合併回這裡
      ├── feature/<domain>-<簡述>
      ├── fix/<domain>-<簡述>
      └── docs/<簡述>
```

- **從 `dev` 開分支，MR 合併回 `dev`。** 至少一位其他組員審核通過才能合併；動到 API 契約的 MR 要 @ 系統整合主責（立倫）；有 migration 的 MR 要 @ 瑋鋐。
- **`dev` 合併到 `main` 只由組長執行**，合併前確認 `dev` 上所有測試通過、可以正常啟動。
- 不直接推到 `main` 或 `dev`。
- 開分支前先 `git pull` 更新 `dev`，減少衝突。

### 8.2 Commit 訊息

格式：`<type>(<domain>): <描述>`，type 用 `feat`、`fix`、`docs`、`refactor`、`test`、`chore`。
例如：`feat(booking): 新增查詢可用桌位 API`、`test(booking): 新增重複訂位測試案例`。

## 9. 給 AI 助理的額外規則

- **只讀取 `AGENTS.md` 與 `CLAUDE.md`，絕不修改。** 要改規則，請使用者自己改。
- 動手前先說明你打算改哪些檔案，等確認後再改。
- 不確定的事情（套件選擇、資料格式、命名）先問，不要自己決定。
- 新功能先產出測試案例表格給使用者確認，再寫測試，最後才寫功能（第 7 節）。
- 做前端功能時，只做 `data/`、`state/`、`prototypes/` 與交接說明，不要碰 `pages/` 與 `app/theme/`，除非使用者是永傑或明確要求。
- 產生的程式碼、註解、commit 訊息用繁體中文或英文，不用簡體中文。
- 完成後列出：改了哪些檔案、跑了哪些檢查、還有哪些沒做完。

## 10. 術語表

以下用詞的定義由組內統一，規則教學、畫面文字、程式命名都依此表。程式命名請使用英文欄。**標示「待定義」的項目，組內確定前不要在程式中使用。**

### 10.1 角色

| 中文 | 英文命名 | 定義 |
|---|---|---|
| 玩家 | `player` | 使用平台、參加遊戲的人 |
| 開團主 | `organizer` | 發起揪團的玩家（避免與 AI 主持的 `host` 混淆） |
| 店家 | `shop` | 提供場地與桌遊的桌遊店 |

### 10.2 遊戲進行

由大到小：一局包含好幾輪，一輪包含每位玩家各一個回合，一個回合可以分成好幾個階段。

| 中文 | 英文命名 | 定義 |
|---|---|---|
| 局 | `match` | 玩一次遊戲，從開始新的一場遊戲，到結束並統計分數為止。長度依遊戲而定，例如《阿瓦隆》一局約 20 到 30 分鐘 |
| 輪 | `round` | 所有玩家都各輪過一次自己的回合，稱為一輪 |
| 回合 | `turn` | 一局當中輪到某位玩家行動的期間，就是他的回合 |
| 階段 | `phase` | 一個回合中可以再分成的步驟，每個階段做不同的事 |
| 天 | `day` | 部分遊戲用來計算遊戲內時間的單位。與輪數無關，而是依各遊戲的規則，經過一定的遊戲進程就算一天 |

- **不使用「次」。** 「次」的意思太廣，規則教學與程式命名一律改用上表的明確用詞；單純計數時用 `count`，例如 `win_count`。
- 程式中表示順序的欄位用 `<單位>_number`，例如 `round_number`、`turn_number`，從 1 開始。

### 10.3 揪團

| 中文 | 英文命名 | 定義 |
|---|---|---|
| 揪團 | `group` | 待定義 |
| 候補 | `waitlist` | 待定義 |
