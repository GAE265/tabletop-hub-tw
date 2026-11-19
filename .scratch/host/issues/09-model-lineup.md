# 用 Flash 還是 Plus、要不要轉交思考模型

Type: grilling
Status: open
Blocked by: 01, 02, 07
Map: [AI 語音主持](../map.md)

## Question

模型的首選方向是 `Qwen-Audio-3.1-Realtime`，但立倫想考慮「會思考」的做法，保留兩個選項（2026-11-19 畫地圖時決定）：

- a. 改用比 Flash 更強的 Plus 版。
- c. 即時語音模型只負責聽和說，難題轉交後端的文字思考模型。

依規格、轉交做法的研究結果，以及立倫試聽的感受，決定：

1. 即時語音模型用 Flash 還是 Plus。
2. 要不要轉交思考模型。要的話：用哪一個模型（Qwen 的文字模型，或專案現有的 Azure 模型）、哪些問題才轉交、等待時主持人說什麼。
3. 試聽結果不理想時怎麼辦：改用備案 Azure `gpt-realtime-2.1`，或退回「語音轉文字 → 文字模型 → 文字轉語音」。這一題只在試聽不理想時才問。
4. 這個選擇偏離 AGENTS.md §4.2「LLM 一律透過 `integrations/llm` 的介面」的地方有哪些，要不要寫 ADR、請組員同意。
