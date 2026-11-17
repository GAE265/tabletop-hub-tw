# Design

## Context

- Model：`backend/app/core/games/models.py`（`Game`，table args 已有 5 個 CHECK，命名 `ck_games_*`）。
- Migration：`backend/migrations/versions/`，目前最新是 `0003_groups_tables.py`，新的是 `0004`（`down_revision = "0003"`）。`games` 由 `0002_games_tables.py` 建立，已合併不得修改。
- `GameRepository.list_games()`／`find_games_by_bgg_ids()`／`filter_games()` 用 `select(Game.__table__)`，新欄位會自動出現在回傳的 dict 裡。
- `games_advisor.schemas.GameData`／`ExportedGame`／`GamesExport` 是 `extra="forbid", strict=True`；`export_games()` 把 `list_games()` 的 dict 直接丟進 `GamesExport.model_validate`。
- **既有資料**：本機 Docker 未啟動，無法查資料庫。依 ADR 0003，立倫的資料庫已匯入 `games.json`（至少 1–4 號：血與刃的白薔薇、阿不思學院、馬可波羅、阿瓦隆），其他組員已同步一份，Azure 可能也有。測試資料庫是空的。所以**一定有既有資料**，migration 必須能在有資料的表上執行。
- 沒有任何 HTTP 端點回傳 `games` 整列；推薦 API 的 `AdvisorGame` 與 `search.GAME_FIELDS` 是明列欄位。

## Goals / Non-Goals

**Goals:**
- 只加 `result_type` 與其 CHECK，既有欄位、repository、其他 domain 不動。
- 加欄位後匯入／匯出／同步仍可正常運作。

**Non-Goals:**
- 不做 `matches`、不決定每回合紀錄格式。
- 不補既有欄位 comment、不重構立倫的程式。
- 不提供「設定結果類型」的 API（登錄遊戲目前只有匯入／同步指令；日後新增桌遊的方式 ADR 0003 說到時再設計）。

## Decisions

### D1：Enum 用 `StrEnum`，放在 `app/core/games/models.py`
`class ResultType(StrEnum)`，三個值各有中文註解（代表什麼＋例子）。欄位仍宣告為 `Text`，CHECK 的值清單由 `ResultType` 產生，避免 Python 與資料庫兩處手寫不一致。
- 替代：`sqlalchemy.Enum`（會建 PostgreSQL 原生 enum 或要設 `native_enum=False`）——需求明確不要原生 enum，且改值要動型別，不採用。
- 替代：Enum 放 `games_advisor` ——`games` 是共用表，`matches` 也要用，放 `core/games/` 才不會讓 `matches` 依賴 `games_advisor`。

### D2：既有資料的處理（**待使用者決定**，建議 A）
| 選項 | 做法 | 影響 |
|---|---|---|
| **A（建議）** nullable，無預設 | `ADD COLUMN result_type text NULL` + CHECK。既有列為 NULL | 最單純、不編造資料；`matches` 必須處理 NULL（例如「這款遊戲還沒設定結果類型，無法記錄戰績」）。之後資料補齊，再開一個 change 改 `NOT NULL` |
| B NOT NULL + 預設值（如 `score`） | `ADD COLUMN ... NOT NULL DEFAULT 'score'` | 既有 4 款以上會被**默默標成錯的類型**（血與刃、阿瓦隆其實是 `faction`），`matches` 無法分辨「真的是 score」與「沒設定」。不建議 |
| C 先 nullable，migration 內按名稱回填已知遊戲，再 `SET NOT NULL` | migration 用 `UPDATE ... WHERE english_name IN (...)` | 資料寫進 migration（違反「資料不放 migration」的精神，雖然該條只明列測試帳號）；只知道 Demo 4 款，其他遊戲無答案，`SET NOT NULL` 會失敗，或又要給預設值，回到 B。不建議 |

採 A 時，資料由立倫補：更新 `games.json`／匯出檔後重新匯出，其他組員同步。

### D3：`GameData`／`ExportedGame` 加 `result_type`（必要的連帶修改）
不改的話：`export_games()` 會因 `extra="forbid"` 對每一款丟驗證錯誤。改法：`GameData` 加 `result_type: ResultType | None = None`（有預設值，舊格式檔案仍可通過；`strict=True` 下用 `ResultType` 時 JSON 的字串要能通過，需加 `Field`/validator 接受字串值，實作時以測試確認）；`columns()` 因為只排除 `id`、`types`，會自動帶出 `result_type`。`ExportedGame` 繼承 `GameData`，自動有。
- 替代：`list_games()` 排除 `result_type`——匯出檔就不帶這個欄位，同步無法傳遞，等於欄位只有立倫一台機器有。不採用。
- 權衡：欄位有預設值（可省略）而不是「必填可為 null」，換取舊匯出檔相容；代價是同步舊檔案會把資料庫裡的值清成 NULL（同步本來就是「和檔案完全一樣」）。docstring 裡「12 個欄位都必填」要改成 13 個、`result_type` 可省略；這是這個 change 必須動的那一行說明，不順手改別處。

### D4：migration 內容
`op.add_column("games", sa.Column("result_type", sa.Text(), nullable=True, comment="…"))` 與 `op.create_check_constraint("ck_games_result_type", "games", "result_type IN ('faction','score','cooperative')")`；`downgrade` 反向。只動這一欄。CHECK 對 NULL 為通過（SQL 三值邏輯），所以空值不被擋。

## Risks / Trade-offs

- **migration 編號撞號**：其他進行中的分支（例如 `add-groups-calendar`）若也新增 `0004`，會在合併時撞 → 建表前先在群組說一聲（AGENTS.md 4.4 同精神），合併前確認 `alembic heads` 只有一個。
- **同步清掉值**：D3 的相容寫法讓舊檔同步時把 `result_type` 清空 → 立倫補完資料後要重新匯出覆蓋 GAE265G5，並通知組員重新同步。
- **`matches` 遇到 NULL**：由 `matches` 負責人處理，已在 D2 說明。
- 測試需要 PostgreSQL（CHECK、comment、升級降版）；本機要先啟動 Docker。

## Migration Plan

1. 合併後各人 `uv run alembic upgrade head`（既有列為 NULL，立即可用）。
2. 立倫補齊 `result_type`，重新匯出到 GAE265G5；組員重新同步。
3. 回滾：`alembic downgrade -1`（移除欄位與 CHECK，不影響其他欄位）。
