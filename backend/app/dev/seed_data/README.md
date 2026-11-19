# seed_data：開發用 seed 寫入的桌遊與推薦 Agent 資料

`uv run python -m app.dev.seed` 會讀這個資料夾的兩個檔，讓資料庫的 7 張表和立倫的本機資料庫相同。為什麼放在 repo、有什麼後果，見 [ADR 0004](../../../../docs/adr/0004-seed-data-in-repo.md)。

| 檔案 | 寫入的資料表 | 筆數 |
|---|---|---|
| `games-export.json` | `games`、`game_genres`，以及 `games.id` 的計數器 | 16 款（1–16 號）、類型對應 21 筆、下一個編號 17 |
| `games_advisor_data.sql` | `games_advisor_tags`、`games_advisor_game_tags`、`games_advisor_review_summaries`、`games_advisor_review_excerpts` | 30、114、16、128 |

第 7 張表 `genres`（8 個遊戲類型）由 migration 寫入，不在這裡。

## 來源

- 正本：立倫的本機資料庫（容器 `games_advisor-tables-postgres-1` 的 `tabletop-hub-tw`）。
- 匯出日期：2026-11-19。匯出時正本的資料表版本是 0009；已在版本 0012 的空資料庫驗證，seed 寫入後 7 張表和正本逐表比對相同。
- `games-export.json` 是 `export-games` 指令的輸出，格式和 `sync-games` 讀的匯出檔相同（[ADR 0003](../../../../docs/adr/0003-shared-games-table.md)）。
- `games_advisor_data.sql` 是 `pg_dump --data-only --column-inserts`（16.15）的輸出，去掉連線設定與 psql 專用的指令，只留 INSERT。
- 向量用 text-embedding-3-large 產生，1536 維。`GAMES_ADVISOR_EMBEDDING_DIM` 不是 1536 的資料庫寫不進去。

## 內含第三方內容

**repo 是公開的。** `games_advisor_review_excerpts` 的 128 筆是從公開的桌遊心得文章擷取的原文片段（繁體中文 41 筆、英文 87 筆，來自 62 個網站的 80 篇文章），每筆都有來源網址（`source_url`）與網站名稱（`site_name`）。`games_advisor_review_summaries` 的 16 筆是 LLM 依這些心得寫的摘要。`games-export.json` 的桌遊基本資料（人數、時長、類別、機制、BGG 編號）是請 Codex 整理的（ADR 0003）。

這兩個檔沒有金鑰、密碼或連線字串；更新後提交前要再檢查一次。

## seed 怎麼使用這兩個檔

程式在 `backend/app/dev/games_data.py`，整個步驟是一個交易，失敗就全部退回：

1. 用 `games-export.json` 呼叫 `sync-games` 背後的 service：資料庫的桌遊變得和檔案完全一樣（檔案沒有的桌遊會刪掉），計數器設成檔案的 `next_id`。
2. 清空 4 張 `games_advisor_` 表（不加 CASCADE）。
3. 執行 `games_advisor_data.sql`。

不要手動編輯這兩個檔的資料；要改資料，先改正本再重新產生。

`seed` 有一個選用參數 `--data-dir <資料夾>`，可以改讀別的資料夾裡同名的兩個檔。它是給自動測試用的（`backend/tests/dev/` 用自己編的小型假資料測錯誤情境），平常不用給。

## 更新資料時怎麼重新產生（立倫執行）

正本的資料有變（補 `result_type`、重跑心得管線、新增桌遊）之後，在 Mac 上照下面做。指令都只讀正本，不會改它。

1. 確認正本的容器在執行，並把連線指到正本（`.env` 的 `DATABASE_URL`）。
2. 在 `backend/` 重新匯出共用桌遊資料：

   ```bash
   uv run python -m app.domains.games_advisor.commands export-games --out app/dev/seed_data/games-export.json
   ```

3. 在 `backend/` 重新匯出推薦 Agent 的 4 張表。`sed` 那一行保留檔案開頭的說明（到第一個空行為止），`grep` 去掉 pg_dump 的連線設定與 psql 專用的 `\restrict`、`\unrestrict`：

   ```bash
   F=app/dev/seed_data/games_advisor_data.sql
   sed '/^$/q' "$F" > "$F.new"
   docker exec games_advisor-tables-postgres-1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --column-inserts --no-owner -t games_advisor_tags -t games_advisor_game_tags -t games_advisor_review_summaries -t games_advisor_review_excerpts' \
     | grep -v -e '^\\restrict ' -e '^\\unrestrict ' -e '^SET ' -e "^SELECT pg_catalog\.set_config('search_path'" >> "$F.new"
   mv "$F.new" "$F"
   ```

4. 手動更新 `games_advisor_data.sql` 開頭說明裡的筆數、匯出日期與資料表版本，以及本檔的筆數與「來源」。
5. 筆數變了的話，更新 `backend/tests/dev/test_seed_games_data.py` 的 `SEEDED_COUNTS` 與 `SEEDED_NEXT_GAME_ID`；1–3 號的桌遊換了的話，更新 `test_seed_lesson_videos.py` 的 `SEED_GAME_IDS`。
6. 用全新的資料庫演練並和正本比對，例如另開一個 pgvector 容器：

   ```bash
   docker run -d --name seed-check-pg -e POSTGRES_USER=seedcheck -e POSTGRES_PASSWORD=seedcheck -e POSTGRES_DB=seedcheck -p 5440:5432 pgvector/pgvector:pg16
   export DATABASE_URL='postgresql+psycopg://seedcheck:seedcheck@localhost:5440/seedcheck' AUTH_MODE=dev
   uv run alembic upgrade head
   uv run python -m app.dev.seed      # 結束碼要是 0
   uv run python -m app.dev.seed      # 再跑一次：結束碼 0、筆數不變
   ```

   逐表比對兩邊的筆數與內容（排序後算雜湊）。`game_genres.id` 每次同步都重新產生，只比 `game_id` 與 `genre_id`。比對完移除容器：`docker rm -f seed-check-pg`。
7. 在 `backend/` 跑 `uv run pytest`，確認兩個檔沒有金鑰，再發 MR。組員拉下 `dev` 後重跑 seed 就會拿到新資料。
