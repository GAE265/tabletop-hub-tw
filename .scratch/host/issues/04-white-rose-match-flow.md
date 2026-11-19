# 《血與刃的白薔薇》一局的流程

Type: research
Status: open
Map: [AI 語音主持](../map.md)

## Question

主持人要帶《血與刃的白薔薇》（Blades & Rose，BGG 編號 400566）的流程。先整理出一局怎麼進行，後面才能決定主持人每個階段說什麼。用 AGENTS.md §10.2 的用詞（局、輪、回合、階段），不用「次」。

1. 開局前：人數範圍、怎麼分陣營、發什麼牌、誰知道什麼。
2. 一局的結構：有幾個階段、每個回合依序做哪些事、誰先出牌、什麼時候換下一個回合。
3. 隱藏資訊：哪些事只有部分玩家知道（例如陣營）。主持人如果知道了會不會破壞遊戲。
4. 結束條件與勝負：什麼情況這一局結束、哪個陣營獲勝。
5. 對照 `matches` 的回合紀錄欄位（`backend/app/domains/matches/game_definitions.py` 的 `WhiteRoseTurnData`：出牌座位、雙刃、暗刃、巨刃、忠誠的數量、有沒有白薔薇；幽魂不記）。說明每個欄位在流程中代表什麼、在哪個時間點才知道。
6. 玩家最常問的規則問題或最容易搞錯的地方（有來源才寫）。

來源：

- 規則影片：YouTube 影片編號在 `backend/app/dev/lesson_videos.py`。
- 本機資料庫裡 `rules_qa` 的規則片段（如果已入庫）。
- BoardGameGeek 的遊戲頁與出版社的官方說明。

**規則書原文不進 repo（AGENTS.md §2 第 2 點）。** 結果只能用自己的話摘要，不貼原文段落，每項註明出自哪個來源。來源之間互相矛盾、或查不到的地方，列成「要問立倫」的清單。

結果寫在 `.scratch/host/research/white-rose-match-flow.md`。
