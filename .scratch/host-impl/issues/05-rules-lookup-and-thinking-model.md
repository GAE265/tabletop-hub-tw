# 05：rules_qa 只檢索的方法、查規則與思考模型兩個節點

Status: resolved
Blocked by: 03
Spec: [spec](../../host/spec.md) §8.2、§8.3、§8.4、§13.2
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

**開工前**：立倫要先在群組跟永傑說要動 `rules_qa`（spec §13.2）。訊息的草稿由開這張的對話先寫好，立倫貼出去之後才動 `rules_qa` 的檔案。

1. `rules_qa` 的 `service` 加一個只檢索的方法（spec §13.2）：
   - 輸入遊戲與問題的文字；輸出最多 6 段，每段有頁碼與原文。段數沿用現有的 `SEARCH_LIMIT`。
   - 問題轉 embedding、找最像的幾段。不叫 LLM，不檢查使用者，不開成 API。
   - 這款遊戲沒有索引：回空的清單，不回 409。
   - embedding 失敗：照 `rules_qa` 現有的做法丟錯誤。
2. `host` 的圖加「查規則」節點：用 `games.bgg_id` 等於 400566 找到白薔薇，呼叫上面的方法。索引沒建好、找不到遊戲、embedding 失敗都當成空的結果，原因記進紀錄（spec §8.2）。
3. 整局記憶記最近 5 題的問題與查到的頁碼，不記回答的文字。
4. `host` 的圖加「思考模型」節點：後端自己用那個問題再查一次片段，連同問題交給 `integrations/llm`（spec §8.3）。這是圖裡唯一叫 LLM 的節點。
5. `HOST_THINKING_MODEL`：先確認 `integrations/llm` 現有的工廠能不能指定模型。能就不改；不能才改，並記在下面「動到別人的地方」。
6. 等待中的題目編號（spec §8.4）：後端替每一題編號，只交出最新那一題的結果。閒聊與語音指令不會作廢舊題。
7. 同一場主持一次只跑一件事，其他的排隊（spec §8.1）。
8. 查規則或等思考模型時，現況的 `looking_up` 是真。

8 秒、15 秒的計時不在這張，在 [07](07-websocket-and-relay.md)。

## 要動的檔案

- `backend/app/domains/rules_qa/service.py`、`backend/tests/rules_qa/`
- `backend/app/domains/host/graph.py`、`backend/tests/host/`
- `backend/app/integrations/llm/`（只有工廠不能指定模型時）

## 動到別人的地方

- `rules_qa` 的 `service`：加一個方法。擁有者永傑。PR 說明要寫原因並 @ 永傑（AGENTS.md §2 第 3 點）。
- `integrations/llm`：可能要改。擁有者瑋鋐。有改就在 PR 說明 @ 瑋鋐，並附 `uv run pytest -m external` 的結果（AGENTS.md §7.6）。

## 驗收條件

- [x] 立倫已在群組通知永傑
- [x] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [x] `rules_qa` 新方法有自己的測試：有索引回 6 段、沒有索引回空清單、沒有呼叫 LLM
- [x] `rules_qa` 原有的測試全部還是綠的，原有的方法行為不變
- [x] spec §8.5 的 Q-01 到 Q-05、Q-09 到 Q-13 每一行都有測試而且通過
- [x] `host` 的測試用手寫的 fake 取代 `rules_qa` 的新方法與 `integrations/llm`，不連資料庫以外的外部服務（AGENTS.md §7.5）
- [x] `host` 只呼叫 `rules_qa` 的 `service`，沒有用它的 `repository` 或 `models`（AGENTS.md §4.2）
- [x] AGENTS.md §2 第 7 點的後端三項檢查通過
- [x] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`

## Comments

- 2026-11-22：立倫指示「不准再管群組訊息的事，一切以 MR 內容為準」。所以上面「開工前」那一段沒有照做，也沒有寫群組訊息的草稿；驗收條件「立倫已在群組通知永傑」改成「MR 說明已寫明原因並 @ 永傑」，PR #68 的說明已經符合。
- 2026-11-22：`integrations/llm` 沒有改。現有的工廠 `get_llm_provider(name, settings)` 讀 `settings.llm_model`，呼叫端把 `HOST_THINKING_MODEL` 換進一份設定的副本再交給工廠就能指定模型。這一步在接線的那一張（「07：WebSocket 與轉送」）做。
- 2026-11-22：思考模型的呼叫不占那場主持的排隊（`HostGraph.think()`），不然等答案的那幾秒，暫停與下一步都會被卡住。答案回來後再用一件事交回那場主持，由圖判斷是不是最新那一題。
- 2026-11-22：`rules_qa` 新方法回傳的是它現有的 `ChunkHit`（多一個段落的 `id`），沒有另外定義型別。
