# Design

## Context

只動規格用詞，對齊 AGENTS.md 1.8 的 4.4（主鍵預設 UUID，固定小型分類表可用 `bigint` identity）與第 3 節（共用資料表清單）。動機見 proposal.md。現有 `0001_baseline.py` 的兩張表都是 UUID 主鍵，已符合新規則，不需要新增 migration。

## Goals / Non-Goals

**Goals:**
- `database-baseline` 的主鍵需求與 AGENTS.md 1.8 的 4.4 一致。
- Purpose 明確寫出 `auth_users`、`booking_shops` 是第 3 節的共用資料表。

**Non-Goals:**
- 不改程式、model、migration、測試。
- 不新增 `games`、`game_types`、`games_game_types`（由立倫另開 change）。
- 不改 AGENTS.md、`docs/review-guide.md`、`openspec/changes/archive/`。

## Decisions

**D1 用 RENAMED + MODIFIED 改需求。** 需求標題要改，所以 delta 先 RENAMED（FROM/TO），再用新標題 MODIFIED，並貼上完整的需求區塊與原有三個情境。替代方案：REMOVED 舊的再 ADDED 新的——會丟掉原有情境的歷史，不採用。

**D2 Purpose 直接改主 spec。** delta 不能改既有 capability 的 Purpose（會被忽略），所以在 apply 階段直接編輯 `openspec/specs/database-baseline/spec.md` 的 Purpose；需求本身由 archive 套用 delta，避免兩邊重複修改而衝突。

**D3 「參照欄位同為 UUID」限縮為「參照 UUID 主鍵的欄位」。** 放寬後，指向 `bigint` 分類表的外鍵欄位就不該是 UUID，所以只保留對 UUID 主鍵的約束。這比原本指定的文字多了一個限定語，需使用者確認。

**D4 新增一個情境描述 `bigint` 例外。** 目前沒有任何 `bigint` 主鍵的表（`game_types` 尚未建立），所以這個情境是規則層級的說明，現在沒有對應的測試；等 `game_types` 的 migration 出現時再補測試。

## Risks / Trade-offs

- [新情境暫時沒有對應測試] → 測試案例表格寫「不適用：只改文件與規格，行為不變」，`game_types` 建立時再補。
- [用詞放寬後，可能有人把非分類表也改成 `bigint`] → 範圍限定在「固定的小型分類表」，審核者依 AGENTS.md 4.4 把關。
