# 難題轉交後端思考模型

## 三行結論

1. 可行，OpenAI 有正式委派文件與 Chat-Supervisor 範例，Qwen 也提供工具呼叫的接回流程，能證明這是官方支援的架構，查不到業界採用比例。[S1][S2][S3]
2. 專案現有 Azure 文字介面可作為後端候選，但實際部署模型未知，不能宣稱現在就能直接使用，先講等待語也不代表裁決已經完成。[L1][S4][S5]
3. 查不到 Plus 提供可控制的深度思考開關，也查不到它能取代後端裁決的比較證據，先保留兩種方案，等規則題測試再決定。[S3][S6]

查核日期一律為 **2026-11-19**。每個來源的文件日期或版本列在文末，文中的來源編號可直接開啟原頁。本次只讀文件與指定程式，沒有使用金鑰、呼叫付費 API，以下均非本機效能實測。

## 1. 怎麼轉交，是否是常見做法

OpenAI 的官方 Chat-Supervisor 範例，讓即時語音模型接待、收集資訊，再用工具把較難的工作交給文字模型。文件舉的是 `gpt-4.1`，所以「委派」本身不要求對方一定是深度思考模型。GPT-Live 的正式文件也把對話與後端推理分開，允許應用程式自行選後端模型或框架。[S1][S2]

這足以證明它是有官方範例的設計模式。查不到跨公司的採用率調查，因此不把「業界普遍使用」當成已證實事實。

Qwen 的官方流程是：用 `session.update` 登記工具，收到完整的 `response.function_call_arguments.done` 後，由應用程式執行。完成後送回 `function_call_output`，帶原來的 `call_id`，再發 `response.create` 讓語音模型回答。工具內容可由後端自行決定，不必是一般資料查詢。[S3]

套到本專案的研究建議如下，尚未實作，也不是已定案的 API：

1. 主持人遇到規則裁決問題，發出一個唯讀的「請後端判讀規則」工具請求。
2. `host.service` 檢查身分與局況，透過 `rules_qa.service` 取得規則依據，再視需要交給文字模型推理。
3. 回傳短答案、來源與「資料不足」狀態，語音模型只把可公開的結論說出來。
4. 工具呼叫使用相同的 `call_id` 對回結果，後端另追蹤這是哪個問題、哪份局況，避免玩家改問後仍播舊答案。

第 2 步的分層依據是專案 AGENTS.md §4.2，這裡沒有查驗 `rules_qa` 現有實作，不能據此保證其契約已足夠。[L2] 第 4 步後半是本研究提出的狀態管理需求，並非 Qwen 自動提供的保證。

## 2. 後端可以用哪些思考模型

### 2.1 Qwen 的雲端文字候選

以下列官方目前推薦的三個文字輸出候選，沒有把歷史別名、所有快照與開源版本全部展開。它們能接受其他輸入類型，不影響只送文字的用法。官方把 Plus 定位在能力與成本平衡、Max 偏重品質、Flash 偏重成本，這是廠商定位，尚未證明誰最會裁決本遊戲的規則。[S7]

| 候選名稱／版本 | 思考、工具、固定格式 | 已核對的區域與價格 |
| --- | --- | --- |
| `qwen4-max`，無日期別名 | 支援思考與 function calling，JSON Schema 支援清單有列出 | Singapore／International，單次輸入不超過 1M tokens：輸入 $1.50、輸出 $4.50／百萬 tokens |
| `qwen3.7-plus`，目前對應 `qwen3.7-plus-2026-05-26` | 支援思考與 function calling，JSON Schema 支援清單有列出 | Singapore／International，採固定快照牌價：輸入不超過 256K 時 $0.40／$1.60，超過 256K 至 1M 時 $1.20／$4.80，依序為輸入／輸出每百萬 tokens |
| `qwen3.8-flash`，無日期別名 | 支援思考與 function calling，JSON Schema 支援清單有列出 | Singapore／International，單次輸入不超過 1M tokens：輸入 $0.15、輸出 $0.47／百萬 tokens |

能力依據為 [S7][S8][S9]，價格與區域依據為 [S10]。金額都是美元牌價，不含促銷、快取及其他工具費，輸出價格包含思考內容。這是已核對的共同區域，不表示其他區域不能用。[S8][S10]

固定格式要分清楚：JSON Object 只保證合法 JSON，JSON Schema 才約束欄位與型別。官方結構化輸出頁上方的比較表仍寫「只限部分 qwen-plus」，下方支援清單卻已列出上表各系列，文件有內部不一致。本表採詳細支援清單與模型能力表交叉核對，但「開思考＋工具迴圈＋嚴格格式」整套仍待實際整合測試，不能用單項支援代替通過驗證。[S7][S9]

### 2.2 專案既有 Azure 介面

本次只讀 `backend/app/integrations/llm/` 與 `.env.example` 的欄位名稱，沒有讀取任何 `.env`，也沒有查詢 Azure 帳戶。[L1]

| 已從程式確認 | 對這個做法的意思 |
| --- | --- |
| `CloudLLMProvider` 使用 Azure 的 OpenAI v1 Responses API，一個實例綁一個部署 | 既有 Azure 轉接層可當文字後端的起點 |
| `generate_json()` 要求嚴格 JSON Schema | 可回傳適合後端處理的固定欄位 |
| `respond()` 支援工具、工具結果與 `previous_response_id`，工具迴圈由呼叫方 service 控制 | 可接多步驟查規則，整合層不會自行完成整個工作 |
| `_create()` 會送出 `reasoning.effort` | 已有思考程度設定入口，但部署模型仍須支援該參數 |
| 呼叫採同步寫法，沒有串流方法或取消方法，建構式預設 timeout 是 30 秒 | 整合即時語音時，必須另安排背景執行與逾時處理，不能讓同步等待堵住收音事件 |
| `respond()` 回傳輸入、輸出 token 總數，沒有單獨回傳思考 token 數 | 現有資料不足以細分裁決花多少思考成本 |

以上是指定檔案的靜態檢查，不是 Azure 可用性驗證。[L1] `.env.example` 有 `LLM_PROVIDER`、`LLM_ENDPOINT`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_BATCH_MODEL`、`LLM_REASONING_EFFORT`、`LLM_TIMEOUT_SECONDS` 這些欄位，但欄位名稱不會告訴我們實際部署的是哪個模型。[L1]

微軟官方的推理模型表，列出例如 `gpt-6-luna`（2026-09-22）支援 Responses、工具、Structured Outputs 與 reasoning effort。因此 Azure 確有符合這條路線的模型選項，但這不是在說專案已部署它。[S4]

答案是「可以沿用現有介面做起點，是否直接可用仍待確認」。要確認實際部署模型、版本、支援的思考程度與額度，才能判斷是否只需接上 service。若既有部署符合需求，文字後端可繼續用 Azure，毋須再接阿里的文字模型，Qwen 語音仍使用阿里服務。不要為了 host 擅自更改全域 `LLM_*`，是否共用同一部署須留給整合決策。[L1][S4]

## 3. 等待多久，主持人能否先講話

查不到本專案每題裁決的可靠秒數，也查不到這三個 Qwen 候選處理本遊戲中文規則的 p50／p95。官方資料只提供不同情境的線索：

| 官方證據 | 可以怎麼解讀 |
| --- | --- |
| OpenAI Chat-Supervisor 展示中，等待語結束到答案開始約 2 秒 | 這是 `gpt-4.1` 範例片段，不是難題思考的速度保證，也不是玩家講完到答案播完的時間。[S1] |
| 阿里技術報告表 14：全部委派的短任務平均 4.266 秒，多步驟任務平均 38.653 秒 | 只是自家原型測試的量級線索，不能套成桌遊裁決預估。[S6] |
| 阿里深度思考文件說思考會增加時間與 token，可限制 `thinking_budget` | 可控制思考用量，但無法由此保證固定秒數。[S8] |

表 14 用 Qwen-Audio-3.0-Realtime 當前景，並使用合成語音、模擬工具。延遲從使用者說完到必要工具結果達成目標，排除了答案摘要與語音播放，多步驟延遲樣本只有 6 筆工具請求，且只計各路徑都成功的子集。它不是 3.1 Plus 的測試，也不是完整的「聽到答案」延遲。[S6]

先說等待語有官方範例。OpenAI 範例直接要求先說中性的等待語，再呼叫 supervisor 工具，接到結果後照結論回答。[S5] Qwen 的 API 允許同一個 response 同時有一般訊息與工具呼叫，工具呼叫本身不會送去發音，所以協定能容納「先說我查一下，再等工具結果」。但是文件沒有保證每次都先播完等待語，也沒有保證等待期間能持續自然閒聊，必須在 Qwen 原型實測。[S3]

對 host 的研究建議是：先說「我查一下這段規則」，只在確有進度時補充，拿不到依據就說尚無法判定。驗收時分開量「玩家說完到等待語首音」與「玩家說完到有來源的裁決首音」，不能用等待語的速度代表裁決速度。逾時與玩家改問後的舊答案處理也要一起測，門檻尚未定案。

## 4. 已知代價與要補的工作

| 問題 | 已知事實或研究推論 | 後續要驗證什麼 |
| --- | --- | --- |
| 延遲 | 官方委派範例承認增加延遲，深度思考又增加生成量。[S1][S8] | 簡單題是否直答，難題才轉交，分開量等待語與裁決時間 |
| 語氣與內容可能接不順 | OpenAI 官方把 supervisor 輸出寫成能直接朗讀的文字，並要求前景照讀。[S5][S11] 研究推論：兩個模型的文風可能不同，語音模型再次改寫也可能改掉否定或條件 | 相同人設下，結論、例外與來源有沒有被改掉，情感是否自然。查不到這種架構的官方語氣不連貫發生率 |
| 多一層費用 | 阿里文字模型按輸入與輸出收費，思考內容也算輸出。[S8][S10] 研究推論：轉交題會在原有語音用量上，另增加文字推理與往返上下文 | 記每題文字用量與實際語音用量，再比較 Plus 單模型方案，不能先宣稱委派一定較貴或較省 |
| 更難定位錯誤 | OpenAI Realtime 官方要求利用 `call_id` 對應工具結果、利用 `event_id` 對應非同步錯誤。[S12] 研究推論：加文字後端後，又多了模型失敗、格式錯誤及過時局況等失敗點 | 從語音請求一路對到後端模型請求與依據，顯示失敗發生在哪一段 |
| 中斷後仍收到舊答案 | GPT-Live 正式委派文件明列應用程式負責任務狀態與驗證結果。[S2] Qwen 的工具接回流程本身不等於後端任務取消 | 玩家改問、局況改變、斷線或逾時後，舊結果能否被丟棄 |
| 既有介面仍需接線 | 本地 provider 只有同步的單次模型呼叫，沒有即時語音橋接、串流或取消契約。[L1] | 收音不中斷，並限制工具迴圈、總等待與總成本，這些目前都未實作 |

費用可以先用公式比較，毋須編造一局的金額：`新增文字費 = 輸入 tokens × 輸入單價 / 1,000,000 + 輸出 tokens × 輸出單價 / 1,000,000`。輸出要包含思考 tokens，多次工具循環則逐次加總，是否比較省，還要把語音等候、回填文字與重試一起算。[S8][S10]

## 5. 直接用 Realtime Plus，能不能先想再答

動筆前檢查時，`qwen-realtime-facts.md` 尚不存在。**這段和另一張 ticket 重疊，兩邊結果需要對照。** 本題只做最低限度查證，沒有替另一張 ticket 完整盤點語音規格。

結案前已取得[另一張 ticket 的結果](qwen-realtime-facts.md)（2026-11-19），對照其第 6 節，兩邊都查不到 Flash／Plus 分別評測的證據，結論一致。

要分成兩個問題：

- 一般的推理能力：阿里 3.1 技術報告確實介紹 Think、Act、Speak 的架構與語音推理訓練，所以不能說語音模型「完全不會思考」。但該報告沒有把 Flash 與 Plus 分開評測，不能證明 Plus 的裁決能力足夠，也不能用它算 Plus 比 Flash 強多少。[S6]
- 可控制的深度思考模式：在 2026-11-18 更新的 Realtime 使用指南、Client events 與 Plus 模型頁中，查不到 Plus 可用的 `enable_thinking`、`thinking_budget` 或 `reasoning_effort` 規格。文字深度思考文件的候選清單也不能直接移用成 Realtime 的能力保證。因此答案是「查不到 Plus 有這種可控制的模式」，不是「已證明 Plus 沒有任何推理能力」。[S3][S8][S13][S14]

研究建議：把「Plus 單獨回答同一批規則題」與「語音模型＋後端判讀」當成待測選項，對照引用正確性、條件是否完整、裁決等待及成本。查不到能直接替這個遊戲定案的一手比較，不在這張 research ticket 替立倫選定架構。

## 查不到的項目

- 業界採用比例：找到 OpenAI 正式文件與範例、阿里工具流程及研究原型，沒有找到採用率資料。[S1][S2][S3][S6]
- 既有 Azure 的實際部署、版本、區域、額度與價格：允許讀取的程式和設定欄位名稱沒有這些值，沒有讀 `.env` 或登入控制台。[L1]
- 本遊戲的每題延遲、中文裁決正確率、語氣不連貫發生率與每局總費用：查過官方範例、深度思考指南與技術報告，沒有適用的測量。[S1][S6][S8]
- Realtime Plus 的深度思考開關、Plus 對 Flash／委派模型的規則裁決比較：查過 Realtime 使用指南、文字深度思考指南與 3.1 報告，沒有足夠資料。[S3][S6][S8]
- OpenAI 範例的固定 commit SHA：GitHub API 連結透過本次查詢工具無法取得，未繞過，下列範例明確標為 `main` 當日快照，不假造版本。

## 和選型查核報告不一致的地方

對照 2026-11-16 的《AI 語音主持選型查核報告》§04，本題沒有確認到它所列語音牌價的數值衝突，因為那不是本題的價格查核範圍。和本題相關的差異是證據範圍與尚缺的工作：

1. 報告建議「先說我翻一下規則書」來遮住等待。本次確認 OpenAI 有實際範例，Qwen 協定也容許訊息與工具共存，但 Qwen 能否穩定先講、等待時能否繼續對話，仍需測試，不能當成已驗證體驗。[S3][S5]
2. 報告寫現有工具迴圈即可處理。若工具只查資料，這是合理起點，若再加文字思考模型，還要處理第二次模型呼叫、逾時、中斷及舊答案，這些沒有在目前指定介面中完成。[L1]
3. 報告的「原生即時語音首音約 1 秒」不能用作委派裁決的預估。阿里表 14 的委派數據測的是工具結果，且不含語音播放，本題不拿兩者直接比快慢。[S6]
4. 報告沒有證明「Plus 可以取代後端思考模型」，本次也查不到，這仍是後續原型要回答的問題。[S3][S6]

## 來源、查核日期與版本

外部來源均查核於 2026-11-19。日期未揭露的頁面只標示當日快照，不把搜尋引擎抓取時間當成文件更新日。

| 編號 | 一手來源 | 文件更新日／版本 |
| --- | --- | --- |
| S1 | [OpenAI Realtime Agents README：Chat-Supervisor](https://github.com/openai/openai-realtime-agents#agentic-pattern-1-chat-supervisor) | 官方 repo `main`，2026-11-19 快照，SHA 未取得，範例文字模型為 `gpt-4.1` |
| S2 | [OpenAI GPT-Live delegation](https://developers.openai.com/api/docs/guides/live-delegation) | GPT-Live／`gpt-live-1`，頁面未揭露更新日，2026-11-19 快照，僅作架構參考 |
| S3 | [阿里 Qwen-Audio Realtime 使用指南](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-realtime-user-guides) | 更新 2026-11-18，涵蓋 `qwen-audio-3.1-realtime-plus`／`flash` |
| S4 | [微軟 Azure OpenAI reasoning models](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning) | 頁尾更新 2026-11-04，功能表列 `gpt-6-luna` 版本 2026-09-22，頁面快照 2026-11-19 |
| S5 | [OpenAI Chat-Supervisor 語音端指令](https://github.com/openai/openai-realtime-agents/blob/main/src/app/agentConfigs/chatSupervisor/index.ts) | 官方 repo `main`，2026-11-19 快照，SHA 未取得 |
| S6 | [阿里 Qwen-Audio-3.1-Realtime 技術報告](https://arxiv.org/html/2609.25176v2)（[版本日期](https://arxiv.org/abs/2609.25176v2)） | arXiv:2609.25176v2，2026-09-24，§2、§7、表 14，委派原型前景為 3.0 |
| S7 | [阿里文字生成模型能力表](https://www.alibabacloud.com/help/en/model-studio/text-generation-model) | 更新 2026-11-16 |
| S8 | [阿里 Deep thinking](https://www.alibabacloud.com/help/en/model-studio/deep-thinking) | 更新 2026-11-16，Chat Completions／DashScope 文件 |
| S9 | [阿里 Structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output) | 更新 2026-11-16，JSON Object／JSON Schema 支援清單 |
| S10 | [阿里模型價格頁](https://www.alibabacloud.com/help/en/model-studio/model-pricing) | 更新 2026-11-18，Singapore／International 的文字 Max、Plus、Flash 牌價 |
| S11 | [OpenAI Chat-Supervisor 文字端指令](https://github.com/openai/openai-realtime-agents/blob/main/src/app/agentConfigs/chatSupervisor/supervisorAgent.ts) | 官方 repo `main`，2026-11-19 快照，SHA 未取得 |
| S12 | [OpenAI Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations) | Realtime API，頁面未揭露更新日，2026-11-19 快照，Function calling／Error handling |
| S13 | [阿里 Realtime Plus 模型頁](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-3-1-realtime-plus) | 更新 2026-11-10，`qwen-audio-3.1-realtime-plus` |
| S14 | [阿里 Realtime Client events](https://www.alibabacloud.com/help/en/model-studio/fun-audiochat-client-events) | 更新 2026-11-18，Qwen-Audio-Realtime 事件參考 |
| L1 | [base.py](../../../backend/app/integrations/llm/base.py)、[cloud.py](../../../backend/app/integrations/llm/cloud.py)、[factory.py](../../../backend/app/integrations/llm/factory.py)、[types.py](../../../backend/app/integrations/llm/types.py)、[.env.example](../../../.env.example)（僅欄位名稱） | 本地 `docs/host-wayfinder`，2026-11-19 靜態檢查，沒有讀任何 `.env` |
| L2 | [AGENTS.md](../../../AGENTS.md) §4.2 與 [host 地圖 Notes](../map.md) | AGENTS.md 1.11（2026-11-17），地圖方向記錄 2026-11-19 |

[S1]: https://github.com/openai/openai-realtime-agents#agentic-pattern-1-chat-supervisor
[S2]: https://developers.openai.com/api/docs/guides/live-delegation
[S3]: https://www.alibabacloud.com/help/en/model-studio/qwen-audio-realtime-user-guides
[S4]: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
[S5]: https://github.com/openai/openai-realtime-agents/blob/main/src/app/agentConfigs/chatSupervisor/index.ts
[S6]: https://arxiv.org/html/2609.25176v2
[S7]: https://www.alibabacloud.com/help/en/model-studio/text-generation-model
[S8]: https://www.alibabacloud.com/help/en/model-studio/deep-thinking
[S9]: https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output
[S10]: https://www.alibabacloud.com/help/en/model-studio/model-pricing
[S11]: https://github.com/openai/openai-realtime-agents/blob/main/src/app/agentConfigs/chatSupervisor/supervisorAgent.ts
[S12]: https://developers.openai.com/api/docs/guides/realtime-conversations
[S13]: https://www.alibabacloud.com/help/en/model-studio/qwen-audio-3-1-realtime-plus
[S14]: https://www.alibabacloud.com/help/en/model-studio/fun-audiochat-client-events
[L1]: ../../../backend/app/integrations/llm/cloud.py
[L2]: ../../../AGENTS.md
