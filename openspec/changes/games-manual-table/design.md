## Context

- 遠端開發資料庫（schema `games`）已有手動建立的 `games_manual(games_id, page, content)`，主鍵 `(games_id, page)`，外鍵 `ON DELETE CASCADE`，不在本 repo 任何 migration 裡。
- 本 repo 的共用表 `games` 由 `0002` 建立，`games.id` 是 bigint（ADR 0003）。ADR 0003 規定參照 `games.id` 的表不可跟著桌遊刪除，因為同步指令刪桌遊時要被資料庫擋下並指出誰在用。
- `rules_ingest` 還沒有任何程式；這是第一份。後續 change（OCR 介面、`PUT` 掃描入庫 API）都會寫入這張表。
- 使用者決定：沿用舊表名與欄位；外鍵不 cascade；加 `page >= 1`；本次不做 API 與查詢／編輯／刪除。
- 使用者決定本 change 先實作、後補測試（不照 AGENTS.md §7.2 的先寫測試流程）；情境仍列在 specs，作為測試依據與 MR 說明的情境表。

## Goals / Non-Goals

**Goals:**
- `games_manual` 納入 Alembic，約束與 ADR 0003 一致。
- 提供 `rules_ingest` 的 model 與 repository，包含依 `(games_id, page)` 覆蓋寫入。

**Non-Goals:**
- 任何 HTTP 端點、service、權限檢查（後續 change）。
- 查詢、列出、編輯、刪除規則書頁面。
- OCR、embedding、向量欄位。
- 儲存圖片或 OCR 的審核旗標；表只有 `content`。

## Decisions

**1. 表名與欄位沿用舊表，不改成 `game_id`。**
AGENTS.md §4.4 偏好 `<對象>_id`，但使用者要求沿用，且遠端既有資料與程式已用 `games_id`。代價是與其他表的 `game_id` 不一致，列為已知小瑕疵。替代方案：改名 `game_id`／`rules_ingest_manual_pages`，被否決。

**2. 外鍵不加 `ON DELETE CASCADE`。**
照 ADR 0003。改變是刻意的，與遠端舊表不同。替代方案：保留 cascade，被否決，因為同步刪桌遊會無聲帶走整本規則書。

**3. 用資料庫的 `INSERT ... ON CONFLICT (games_id, page) DO UPDATE`。**
單一語句、不需要先查再寫，沒有競爭條件，同頁重送也是冪等。使用 `sqlalchemy.dialects.postgresql.insert`，repository 沿用既有 `SessionRepository` 的寫法（同 `core/games/repository.py`）。替代方案：先 `select` 再決定新增或更新，被否決，兩個請求同時送同一頁會撞主鍵。

**4. repository 不吞外鍵錯誤，也不做 `games` 存在性檢查。**
「桌遊不存在」由資料庫外鍵擋下，repository 把 `ForeignKeyViolation` 轉成 domain 自己的錯誤（例如 `GameNotFoundError`），service 之後轉成 404。repository 不做商業判斷（§4.2）。

**5. 空字串是合法內容。**
`content` 為 `NOT NULL`，`""` 代表「整頁沒文字」，與「沒有這頁」（沒有列）是兩回事。後續 API 的 `no_text` 由此而來。

**6. model 放 `domains/rules_ingest/models.py`，且不 import 其他 domain。**
`games` 是共用表，外鍵以字串 `"games.id"` 指向，不 import `core/games/models`（避免 model 之間循環依賴，並照 §4.2）。`migrations/env.py` 加上 `rules_ingest` models 的匯入。

## Risks / Trade-offs

- **[共用資料庫的 vector 擴充]** `vector` 一個資料庫只能裝一份。7501 的 `board_game` 裡它已裝在他人的 `tabletop-hub-tw` schema，`0001` 的 `CREATE EXTENSION IF NOT EXISTS` 被略過，`0002` 找不到 `vector` 型別而失敗。 → 另建資料庫 `board_game_ocr`，在自己的 schema `tabletop-hub-tw_ocr` 裝 vector；不改 `0001`／`0002`，也不動他人的 schema。
- **[舊表衝突]** 7500 的 `games` schema 有手動建立的舊 `games_manual`（0 筆）。 → 新環境不使用 7500；若要把舊環境改成 migration 管理，先 drop 舊表。
- **[欄位命名不一致]** `games_id` 與其他表的 `game_id` 不同。 → 已知，沿用。
- **[先實作後補測試]** 偏離 AGENTS.md §7.2。 → 測試仍要在 MR 前補齊，specs 的每個 scenario 對應一個測試；MR 說明要註明這是使用者的決定。
- **[schema 名稱含連字號]** `tabletop-hub-tw_ocr` 作為 `search_path` 需加引號。 → 已實測：`DATABASE_URL` 帶 `options=-csearch_path="tabletop-hub-tw_ocr"`，Alembic 正常。現有測試假設 `public`，跑 pytest 時要在 shell 覆蓋成不帶 `options` 的 `DATABASE_URL`。

## Migration Plan

1. 新增 `0003_games_manual.py`，`down_revision = "0002"`。
2. 升級：建立 `games_manual`（`games_id` bigint not null、`page` integer not null、`content` text not null；主鍵 `(games_id, page)`；`games_id` 外鍵參照 `games.id`，無 cascade；`CHECK (page >= 1)`）。
3. 降級：`drop_table("games_manual")`。
4. 回滾：降級到 `0002`；因為本 change 沒有資料搬移，降級會遺失 `games_manual` 內的資料，只用於開發環境。

## Open Questions

- 各 domain 的 model 是否要統一加 `schema`？目前整個後端沒有指定 schema，靠連線的 `search_path`；本 change 維持這個做法。
