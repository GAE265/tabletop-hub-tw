# 用 Flash 還是 Plus、要不要轉交思考模型

Type: grilling
Status: open
Blocked by: 01, 02, 07, 14
Map: [AI 語音主持](../map.md)

## Question

模型的首選方向是 `Qwen-Audio-3.1-Realtime`，但立倫想考慮「會思考」的做法，保留兩個選項（2026-11-19 畫地圖時決定）：

- a. 改用比 Flash 更強的 Plus 版。研究後要修正前提：官方沒有說 Plus 會「先想再答」，查不到可以打開的思考設定，也沒有 Flash 對 Plus 的比較數字。確定的只有 Plus 比較貴（約 3.5 到 12.8 倍）。Plus 答規則題是不是比較好，只能看試聽結果。
- c. 即時語音模型只負責聽和說，難題轉交後端的文字思考模型。研究確認做得到，但要多處理等待、逾時、玩家中途改問、過期的舊答案。

依規格、轉交做法的研究結果，以及立倫試聽的感受，決定：

1. 即時語音模型用 Flash 還是 Plus。
2. 要不要轉交思考模型。要的話：用哪一個模型、哪些問題才轉交、等待時主持人說什麼、等太久時怎麼辦。候選有兩邊：
   - Qwen 的文字模型：`qwen4-max`、`qwen3.7-plus`、`qwen3.8-flash`。
   - 專案現有的 Azure 文字模型，好處是不用多接一家。games_advisor 的地圖記著立倫的 Foundry 部署了 `gpt-5.6-luna` 與 `gpt-5.6-terra`（[當時的 ticket](../../games-advisor/issues/17-foundry-model-deployments.md)），現在是不是還這樣要立倫確認。host 不擅自改全域的 `LLM_*` 設定。
3. 試聽結果不理想時怎麼辦：改用備案 Azure `gpt-realtime-2.1`，或退回「語音轉文字 → 文字模型 → 文字轉語音」。這一題只在試聽不理想時才問。
4. 這個選擇偏離 AGENTS.md §4.2「LLM 一律透過 `integrations/llm` 的介面」的地方有哪些，要不要寫 ADR、請組員同意。

## Comments

- 2026-11-19：「[Qwen 即時語音模型的官方規格](01-qwen-realtime-facts.md)」與「[難題轉交後端思考模型的做法](02-delegate-to-thinking-model.md)」已結案。和這張有關的事實（細節在 [qwen-realtime-facts](../research/qwen-realtime-facts.md)、[delegate-to-thinking-model](../research/delegate-to-thinking-model.md)）：
  - 新加坡區每 100 萬 tokens 的價格（美元，依序是文字輸入、音訊輸入、文字輸出、音訊輸出）：Flash 0.23、0.93、0.70、1.87；Plus 0.80、6.40、6.40、24.00。每一輪都會把先前的對話重新算一次輸入費用。
  - 廠商的技術報告說模型本身有推理能力，但沒有把 Flash 與 Plus 分開測。
  - 現有的 Azure 文字介面是同步的單次呼叫，沒有取消的方法，預設逾時 30 秒。拿來當思考模型時，等待期間不能卡住收音。
  - 等待語講得快不代表答案來得快。廠商自己的轉交測試用的是舊版原型，而且不含播出聲音的時間，不能拿來預估。
- 2026-11-19：新增相依「[接不接受阿里雲保留玩家的聲音最多 30 天](14-voice-data-retention.md)」。那張的答案如果是不接受，這張的前提（用 Qwen）就要改。
- 2026-11-19：立倫在 ticket 06 看了主控台的即時模型清單後說，選模型先看三件事：有感情、能串接自訂工具、成本。當時順便查的比較（官方文件，沒有存成結果檔）：Qwen3.8-Omni-Flash-Realtime 的 token 單價和 Audio-3.1 Flash 一樣，也有新加坡免費額度，但帶聲音的回覆另收文字輸出費；它的自訂工具和網路搜尋只能二選一，文件沒寫情緒控制。Audio-3.1 的工具和搜尋可以同時開，也有 `enable_speech_emotion`。依這三件事，方向仍是 Audio-3.1 Flash。
- 2026-11-19：「[用真的聲音試聽 Qwen 主持人](07-listen-to-qwen-host.md)」已結案，答案第 2、3、8 題是這張的主要依據：
  - 只比音色，立倫聽不出 Flash 和 Plus 的差別；兩款速度也差不多。
  - 規則題 6 題各跑 1 次。自己答時，Flash 5 題完全對、Plus 4 題；允許轉交裁判（Azure `gpt-5.6-luna`）時，Plus 6 題全對，Flash 有 1 題結論對但理由錯。差別在要把兩條規則串起來的題。
  - 轉交多等約 2 秒（裁判 1.4 到 2.1 秒）。要不要轉交由模型自己判斷，只有難題才轉交。
  - 立倫的阿里雲金鑰叫不到 Qwen 文字模型（403 `Access denied by API-Key restrictions`）。要比 Qwen 文字模型，得先到主控台加權限。
  - 費用線索：`response.done` 會帶 `usage`。歷史塞滿 300 秒音訊時，每一輪的輸入 Flash 約 US$0.0035、Plus 約 US$0.024。
  - 立倫優先用的聲線：`xunanchuan_v3.1`、`longyuan_v3.1`。
