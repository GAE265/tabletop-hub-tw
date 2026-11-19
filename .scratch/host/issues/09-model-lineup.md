# 用 Flash 還是 Plus、要不要轉交思考模型

Type: grilling
Status: resolved
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

## Answer

2026-11-19 立倫決定：

1. **即時語音模型用 Flash**（`Qwen-Audio-3.1-Realtime` Flash，新加坡區）。試聽時音色、速度聽不出和 Plus 的差別；自己答規則題 Flash 不輸 Plus；主持人說話的費用 Plus 約是 13 倍，Flash 另有免費額度。答題品質靠轉交補，不靠升級 Plus。
2. **難題轉交思考模型**：
   - 名稱：spec 與程式都叫「思考模型」（`thinking model`）。不叫「裁判」，`GLOSSARY.md` 把「裁判」列為「主持人」要避免的詞。它只在後端，不是遊戲用語，不進 `GLOSSARY.md`。
   - 哪些題轉交：由即時語音模型自己判斷（試聽時只有難題被轉交），用工具呼叫交給後端。
   - 用哪個模型：預設 Azure `gpt-5.6-luna`，透過現有的 `integrations/llm` 呼叫，不接 Qwen 文字模型。之後可能換成更高階的 Sol：真的要換時，再確認 Foundry 的部署名稱並實測速度（要對照第 4 點的 15 秒）。
   - 設定：新增選填的 `HOST_THINKING_MODEL`，留空就用 `LLM_MODEL`（照 `LLM_BATCH_MODEL` 的先例）。推理強度沿用 `LLM_REASONING_EFFORT`。host 不改任何全域的 `LLM_*` 設定。
3. **等待時說什麼**（固定台詞，由指令要求模型照唸，字句可能略有出入）：
   - 查規則：「我翻一下規則」。
   - 轉交思考模型：「讓我來好好的想一想～」。一題要轉交時只說這句，不先說「翻規則」那句。
   - 轉交後第 8 秒還沒回來：補一句「這題比較複雜，再等我一下」，整段等待只補這一句。
4. **等太久**：從開始轉交算起 15 秒沒回來就放棄，改用查規則已查到的內容回答，最後補「這題我沒把握，大家可以再翻規則書確認」。Azure 回錯誤時也走這條路。
5. **等待中玩家又開口**：
   - 問了新問題：新問題取代舊問題，舊題作廢，舊答案晚到也不唸。主持人不特別交代，直接處理新問題，需要時照第 3 點重新等。
   - 說「算了」「不用了」：一樣作廢舊題，主持人只回「好」。
   - 現有的 Azure 呼叫不能中途取消，作廢的舊題會在背景跑完，答案丟掉，但那次呼叫照樣計費（金額小）。
6. **備案**（Azure `gpt-realtime-2.1`、或「語音轉文字 → 文字模型 → 文字轉語音」）：試聽結果算理想，不用決定。spec 只記一行候選。
7. **偏離 AGENTS.md §4.2 的地方**：思考模型走 `integrations/llm`，符合規定；Qwen 即時語音要一條長時間開著、同時收音和播音的連線，現有的 `respond()` 做不到，要另一個管連線的介面，這裡偏離規定。**要寫 ADR**，在地圖「整合層介面與 fake」那一項處理時寫（要等「[聲音怎麼從瀏覽器連到模型](12-audio-connection-path.md)」與「[選哪個 Agent 框架、它負責什麼](10-agent-framework-choice.md)」定案，才知道介面放哪），MR 說明 @ 瑋鋐（`integrations/llm` 的擁有者）請他同意。

影響：
- 「[選哪個 Agent 框架、它負責什麼](10-agent-framework-choice.md)」解鎖。框架如果要負責呼叫思考模型，也要透過 `integrations/llm`，不能讓框架直接連 Azure。
- 第 3、5 點的「第 8 秒補話」與「晚到的答案不唸」需要後端主動讓主持人開口或丟掉結果，和「[主持人怎麼撐完一局：記性上限與 180 秒斷線](17-keep-host-alive-through-a-match.md)」第 5 題（後端讓主持人開口被拒時怎麼重送）是同一件事。
- 沒有新增術語。
