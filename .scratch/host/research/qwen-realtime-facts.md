# Qwen 即時語音模型官方規格查核

## 三行結論

1. `qwen-audio-3.1-realtime-flash` 與 `qwen-audio-3.1-realtime-plus` 都有 WebSocket、WebRTC、AOQ，可用工具與按住說話，瀏覽器有不暴露長效金鑰的官方接法。[S1][S2][S3][S4]
2. 300 秒是可保留的累計歷史音訊，超過會丟掉較早內容，不能當成連線上限，官方沒有提供 Flash 對 Plus 的中文、工具準確度與速度差距。[S1][S8][S9][S10]
3. 新加坡 Flash 四項單價與選型報告一致，但預設資料保留最多 30 天、含法定及安全例外，目前 ZDR 清單沒有 Realtime，後續須決定是否接受。[S11][S12]

查核日期：2026-11-19，以下全部來源都在當日重新開啟。文件版本或更新日期見文末來源表，各段的來源代號可點開原頁。只做文件查核，沒有開帳號、使用金鑰、呼叫付費 API 或做桌邊測試。以下「官方表示」均是文件或廠商測試的說法，不代表本專案已驗證。

## 1. 連線方式、區域與驗證

兩款模型都支援 WebSocket、WebRTC、AOQ。官方列出新加坡與中國北京，因此「新加坡可用」正確，「只能用新加坡」不正確。[S1][S2][S8][S9]

新加坡端點如下，`{WorkspaceId}` 與 `<model_name>` 都是佔位符，不是真實設定值。[S2][S3]

| 用途 | 端點 |
| --- | --- |
| WebSocket | `wss://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api-ws/v1/realtime?model=<model_name>` |
| WebRTC 的 SDP 交換 | `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1/webrtc/realtime?model=<model_name>` |

北京把主機名稱換成 `{WorkspaceId}.cn-beijing.maas.aliyuncs.com`。WebSocket 官方仍保留舊網域 `dashscope-intl.aliyuncs.com`（新加坡）與 `dashscope.aliyuncs.com`（北京），目前建議改用含 workspace 的網域。驗證為請求標頭 `Authorization: Bearer <API_KEY>`，須使用對應區域與 workspace 的金鑰。[S2][S3]

瀏覽器能直接傳收 WebRTC 媒體與 DataChannel 事件。官方範例讓瀏覽器把 Offer SDP 交給自家後端，後端帶金鑰向阿里雲交換 Answer SDP，再原樣交回瀏覽器，前端不用收到長效金鑰。這只是官方支援的接法，本次沒有測連通。[S3]

短效 API key 確實存在，由安全後端產生，預設有效 60 秒，可設 1 至 1,800 秒，它繼承原金鑰的全部權限限制，不能提前撤銷，只能等過期。這是憑證期限，不是已建立連線的存活時間保證。[S4]

WebSocket 有額外限制：官方要求握手時帶 Authorization，而瀏覽器原生 `WebSocket()` 只有 URL 與 protocols 參數，沒有自訂標頭參數。因此，依這兩份文件推論，不能把官方 Python 握手方式直接搬到瀏覽器，查不到 Qwen 專用的 URL 或子協定帶短效金鑰方法，不能宣稱「拿到短效 key 就一定可直連 WebSocket」。[S2][S5]

AOQ 也有前端連線憑證：後端取得 `aoqTokenForClient`、relay 資訊與 `sidExpiresInSecs`，再交給 SDK。官方回應範例是 7,200 秒，但沒有說這是所有連線的固定或最長期限，不應當成兩小時上限。[S6]

## 2. 音訊格式、回音與降噪

| 傳輸方式 | 已確認規格 |
| --- | --- |
| WebSocket 輸入 | PCM、16 kHz、16-bit、單聲道，放在 `input_audio_buffer.append.audio` 的 Base64 內容 |
| WebSocket 輸出 | PCM、24 kHz、16-bit、單聲道，隨音訊事件逐段接收 |
| WebRTC | 音訊走媒體 track，文字及模型事件走 DataChannel，不把上述 Base64 PCM 欄位當成媒體 track 的線上編碼 |
| AOQ | SDK 負責擷取、編解碼、傳輸與播放，模型事件另走 Data 軌 |

來源：[S7][S3][S6]。查不到 Qwen WebRTC 接入頁承諾的固定線上音訊 codec 與取樣率，因此不自行填 Opus 或 48 kHz。

官方指南建議需要降噪、回音消除與弱網路能力的用戶端優先考慮 AOQ。這是接入方案的能力，不能據此宣稱原生 WebSocket 的模型端會自動消除手機喇叭回音。[S1]

模型另有 speaker enhancement，需要先提供目標說話者的預錄音訊，且只在 `smart_turn`／`smart_turn_v2` 生效。它是排除其他聲音的功能說明，不能當成四位玩家的身分辨識證據，本地圖也已排除身分辨識。[S1][S2]

## 3. 接話、按住說話與插話停播

- `server_vad` 以聲音活動判斷開始與結束，`smart_turn_v2` 同時看聲學與語意，官方建議使用，可減少附和聲、旁聊引起的回應與中斷。[S2]
- 要做按住說話，把整個 `session.turn_detection` 設為 `null`。送完音訊後依序送 `input_audio_buffer.commit`、`response.create`，commit 本身不會產生回答。[S2][S7]
- `turn_detection` 只能在第一段音訊送出前修改，因此不能假設同一條已開始對話的連線可隨時切換自動接話與按住說話。[S7]
- 自動模式判定有人插話時，伺服器取消目前生成，`response.done.status` 為 `cancelled`。前端收到 `input_audio_buffer.speech_started` 就須清空自己的播放緩衝，伺服器取消生成不會替手機清掉已收到的聲音。[S1][S2]
- 按住說話模式由應用程式送 `response.cancel`，同時停止本地播放。若沒有正在生成的回答，送 cancel 會收到錯誤。[S2][S7]

這些事件可作為實作依據，但文件沒有保證桌邊插話一定成功，仍須測手機喇叭、旁聊與重疊說話。

## 4. 工具呼叫與等待中的說話

先用 `session.update.tools` 宣告工具。模型決定呼叫時，官方列的事件順序如下。[S1]

```text
response.created
response.output_item.added                # function_call
conversation.item.created
response.function_call_arguments.delta   # 可有多筆
response.function_call_arguments.done    # 完整 JSON
response.output_item.done
response.done
```

應用程式在完整參數到齊後執行工具，用 `conversation.item.create` 寫回 `function_call_output`，以 `call_id` 對應原呼叫，之後送 `response.create` 讓模型根據結果回答。[S1][S7]

一個 response 可有多個 `function_call`，也可同時含一般訊息，工具呼叫內容本身不會被送去合成語音。因此可有一般話語與工具呼叫並存的回應，但工具要不要同時執行仍由應用程式安排，文件沒有保證每次一定並行。[S1]

「等工具時能不能先講話」要分清楚：同一 response 可含一般訊息，依此推論可設計先說一段提示語，但查不到一手文件保證工具仍未回傳時，模型一定會自動持續說話或可以另開平行生成。官方限制不可在正在生成的 response 中再送一個 `response.create`，工具完成後才觸發第二段推論。把持續接話當成保證仍屬待驗證。[S1][S2][S7]

## 5. 連線時間、歷史與文字接續

| 項目 | Flash | Plus | 來源 |
| --- | --- | --- | --- |
| Context window | 262,144 tokens | 262,144 tokens | [S8][S9] |
| 單次最大輸入 | 245,760 tokens | 245,760 tokens | [S8][S9] |
| 最大輸出 | 16,384 tokens | 16,384 tokens | [S8][S9] |
| 可保留的歷史音訊 | 最多 50 輪、累計 300 秒 | 最多 50 輪、累計 300 秒 | [S1][S8] |
| `max_history_turns` | 1 至 50，預設 20 | 1 至 50，預設 20 | [S7] |

超過歷史輪數或累計音訊限制時，較早歷史會自動被捨棄，300 秒不代表 session 在五分鐘後斷線。[S1]

一次 WebSocket／WebRTC 連線的固定最長時間：查不到。查過指南、兩種接入頁、Flash／Plus 模型頁與官方站內關鍵字搜尋，指南只說閒置太久可能斷線，沒有給秒數。AOQ 的 `sidExpiresInSecs` 範例也不能移用成其他協定上限。[S1][S2][S3][S6][S8][S9]

可以把文字摘要放進新連線的上下文：`conversation.item.create` 支援 `message`，`system`／`user` 可帶 `input_text`，官方明說可注入歷史。這只確認「能補文字前情」，沒有官方保證摘要會保留全部遊戲狀態或自動跨 session 記憶，摘要如何產生與驗證仍待後續設計。[S7]

## 6. Flash 與 Plus 差多少

中文語氣、工具準確度、速度的 Flash 對 Plus 官方差距：查不到。已查兩個模型頁、使用指南及技術報告，沒有同條件、分成這兩個 SKU 的評測或首音延遲數字，不能自行認定 Plus 一定更自然、更準或更慢。[S1][S8][S9][S10]

官方技術報告 v2 的數字是 `Qwen-Audio-3.1-Realtime`，未分 Flash／Plus，以下僅供核對選型報告，不能套給其中一款。[S10]

| 測試項目 | Qwen 3.1 | GPT-Realtime-2 | 限制 |
| --- | --- | --- | --- |
| 真實對話同理評分，表 8 | 4.74／5 | 3.54／5 | 廠商測試，非本專案中文盲聽 |
| 背景人聲觸發回應，表 10 | 13% | 72% | FDB v1.5 的背景人聲情境 |
| 對其他人說話時觸發回應，表 10 | 3% | 60% | FDB v1.5 的特定情境 |
| 玩家插話後停播，表 10 | 1.116 秒 | 0.383 秒 | 非首音延遲，非台灣桌邊實測 |
| 工具 Pass@1，表 11 | 54% | 56% | FDB v3.0，不能改稱 3.1 Flash 成績 |
| 工具參數正確率，表 11 | 62.6% | 66% | 同上 |

表中的 GPT 是 `GPT-Realtime-2`，不能改稱 Azure `gpt-realtime-2.1`。4.74 是同理評分，不能據此概括所有中文音質指標。[S10]

有明確數字差距的是價格。以新加坡四項牌價計算，Plus 分別約為 Flash 的 3.48 倍（文字輸入）、6.88 倍（音訊輸入）、9.14 倍（文字輸出）、12.83 倍（音訊輸出），這是本次直接相除的計算，並非整局費用倍數。[S8][S9]

## 7. 語氣、語速與中文聲線

`session.instructions` 可設定角色、回答風格與行為偏好，`enable_speech_emotion` 預設為 `true`，可強化情感變化，`speech_rate` 可設 0.5 至 2.0，預設 1.0。這些是支援的控制欄位，不保證每句都完全照指令表達。[S7]

聲線用 `voice` 選，3.1 兩款預設都是 `longanqian_v3.1`。指南明列可使用 3.1 TTS Plus 與 Flash 聲線清單的聯集，但 voice 只在第一次 `session.update` 生效，後面的同名欄位會被忽略。[S1][S7]

官方中文／方言聲線例子包括女聲 `longanlingxin_v3.1`、`longanhuan_v3.1`、`longanfengyue_v3.1` 與男聲 `xunanchuan_v3.1`。完整清單與試聽在 [S13]，這四個位於多語與方言組，同頁另有 `yuxiaoyun_v3.1`、`anmingyuan_v3.1` 等中文聲線，但該頁把其他類型標為僅北京支援，不能把整張 TTS 表直接當成新加坡可用表。[S13]

尚未確認上述 TTS 頁的區域限制如何逐一套到 Realtime 聯集，正式選聲線前須實際驗證，不能保證所有中文聲線都能在新加坡呼叫。TTS 清單的 `instruction`、SSML、`language_hints` 也不能直接當成 Realtime 已支援的同名欄位。[S1][S7][S13]

另外，client events 列有 `response.create.response.voice` 可覆寫單輪聲線，與「後續 session.update 忽略 voice」是不同欄位。官方未清楚說明與首次設定的完整互動，切換聲線的實際行為列為待驗證，不據此承諾一條連線可任意換人聲。[S7]

## 8. 單價、歷史重算與免費額度

以下為美元／100 萬 tokens 的原價，四個欄位依序是文字輸入、音訊輸入、文字輸出、音訊輸出。[S11]

| 區域與模型 | 文字輸入 | 音訊輸入 | 文字輸出 | 音訊輸出 |
| --- | ---: | ---: | ---: | ---: |
| 新加坡 Flash | 0.23 | 0.93 | 0.70 | 1.87 |
| 新加坡 Plus | 0.80 | 6.40 | 6.40 | 24.00 |
| 北京 Flash | 0.212 | 0.848 | 0.636 | 1.696 |
| 北京 Plus | 0.707 | 5.653 | 5.653 | 21.20 |

音訊每秒換算 12.5 tokens，不足 1 秒以 1 秒算。純文字回答按文字輸出算費，文字加音訊回答只收音訊輸出，隨附文字不另收輸出費。[S11]

多輪不是只收新錄音：先前使用者音訊與文字會在後續推論當輸入重算，系統指令也逐輪計費，先前模型文字會成為文字輸入，模型輸出音訊只收輸出一次、不放回上下文計費。因此用「總錄音秒數 × 音訊單價」估整局，可能漏掉歷史成本。[S11]

新加坡 3.1 Flash 與 Plus 在價格表各列 100 萬 tokens 免費額度，有效期從啟用服務、模型發布或申請核准三者較晚的日期起算 90 天，其他區域沒有這份免費額度。這是公開方案，並未登入確認立倫帳號是否符合資格、已使用多少或額度如何在四種 token 間扣抵，不應把它寫成已取得的預算。[S11]

## 9. 音訊保存與訓練

Model Studio 國際站最新資料保留政策說，推論的 prompt 與 response 預設保留不超過 30 天，但法律要求或服務安全必要時可延長，有狀態的對話儲存與檔案則保留到使用者刪除。這不是「完全不保存」。[S12]

官方 FAQ 明說不把客戶資料拿去訓練模型。保存與訓練是兩件事，因此可以同時「不拿去訓練」但「按政策暫存或保留」。[S14]

ZDR 需企業客戶向客戶經理申請，而且只對已適配的模型生效。目前清單有 TTS、ASR、Omni 等系列，沒有列出 `qwen-audio-3.1-realtime-plus` 或 `flash`，清單之外即使從啟用 ZDR 的 workspace 呼叫，也回到標準政策。因此本案不能宣稱已具零保留。[S12]

原始 PCM、轉錄文字、生成音訊各自實際存在哪裡、是否各保留同樣天數，以及連線結束後音訊緩衝何時刪除：查不到 Realtime 專屬明文。以上 30 天是平台推論資料的通則，不能換寫成「所有原始音檔一定在第 30 天刪除」。已查 [S1][S2][S3][S12][S14]。

## 10. Python SDK、版本、授權與同步寫法

要分三條路，避免把相近名稱的 SDK 當成已支援這個模型。

| 路線 | 查到的官方資料 | 同步與限制 |
| --- | --- | --- |
| 原生 WebSocket | Qwen Audio 官方快速開始使用 `websockets`、`pyaudio`，範例本身是 async Python，沒有要求用 DashScope 封裝 | 協定可自行實作，但本次查不到官方的 Qwen 3.1 Audio 同步 Python 完整範例，不把範例聲稱成同步 SDK。[S1] |
| DashScope Python SDK | 套件 `dashscope`，PyPI 最新 2.1.0，2026-11-13 發布，Apache 2.0，Python ≥ 3.9 | 有同步 `Client()`，官方 repo 說 duplex WebSocket session 是同步介面，但展示的是 Omni，未找到明列這兩款 Qwen Audio 3.1 的相容範例。[S15][S16] |
| AOQ Linux Python SDK | 模組 `aoq_client_sdk`，官方下載頁列 Linux v1.4.1，2026-11-16 更新，支援 x86_64／arm64 | `connect` 等呼叫搭配 native 執行緒 callback，不是用 `await` 的介面，呼叫回傳不等於連線完成，須處理回呼與執行緒安全。[S17][S18] |

DashScope 的 Apache 2.0 是 SDK 程式碼授權，不是 Qwen 模型權重或付費服務授權。AOQ 下載頁沒有明列開源授權，查不到可自由再散布的授權條件，不能套用 DashScope 的 Apache 2.0。[S15][S17][S18]

DashScope repo 讀的是 2026-11-19 的 `main`，沒有取得該版本對 Qwen Audio 的完整支援證據。嘗試開 PyPI provenance 對應的固定 commit 頁面時工具回傳 `Cache miss`，沒有取得，也沒有下載、安裝或執行套件。Python 版本與同步支援只確認到上表範圍。

## 查不到的項目

- WebSocket／WebRTC 的固定最長連線時間與閒置逾時秒數：查過使用指南、接入頁、模型頁與官方站點搜尋，均未明列。[S1][S2][S3][S8][S9]
- 瀏覽器原生 WebSocket 符合 Qwen 驗證的直接帶短效 key 範例，以及短效 key 過期是否影響既有連線。[S2][S4][S5]
- WebRTC 固定線上 codec、取樣率，以及原生 WebSocket 模型端 AEC／降噪保證。[S1][S3][S7]
- 等工具時自動持續說話的保證、兩款 SKU 分別的中文品質、工具準確度與首音速度差距。[S1][S8][S9][S10]
- Realtime 每個中文聲線在新加坡的可用清單、單輪換聲線的完整行為。[S1][S7][S13]
- 原始音訊與生成音訊各自的具體儲存及刪除時點、Realtime 的 ZDR 明確支援。[S12][S14]
- 明列支援這兩款模型的 DashScope 同步範例，以及 AOQ SDK 的授權條款。[S15][S16][S17][S18]

以上是查核後仍未公開或未取得的項目，不以記憶補答案。一般官方文件可連線，沒有遇到需要繞過網站阻擋的情況。

## 和選型查核報告不一致的地方

對照輸入：地圖 Notes 指定的《AI語音主持選型查核報告》。本次回到它列的官方文件與技術報告，不把該 HTML 當規格來源。

1. 沒有查到可確認的數字矛盾：Flash 新加坡四項價格、12.5 tokens／秒、語速 0.5 至 2.0、歷史音訊 300 秒，以及論文表 8、10、11 的上述數字均一致。[S1][S7][S10][S11]
2. 需修正解讀：報告把「一局超過 60 分鐘要重開 session」和 Qwen 300 秒歷史並列，容易讀成同一種限制，Qwen 的 300 秒只代表歷史音訊容量，沒有找到 Qwen 連線 60 分鐘上限。[S1][S2][S3]
3. 需限制歸屬：報告的中文同理 4.74、停播 1.116 秒、工具 54% 都是未分 SKU 的 3.1 研究結果，不能用來證明 Flash 對 Plus 的差距或 Flash 在本案必達的表現。[S10]
4. 新增官方資訊：北京也可用、WebRTC 後端交換 SDP、短效 API key，以及最新標準資料保留政策。這些是補充，不表示報告原先主張了相反事實。[S1][S2][S3][S4][S12]
5. 報告的一局約 0.12 美元是情境估算，不能當成官方包局價格。後續費用 ticket 須帶入對話輪數、歷史音訊與文字重算，本 ticket 不重建原報告全部假設。[S11]

## 一手來源與文件版本

全部查核日期：2026-11-19。模型版本均為名稱中的 3.1，文件沒有提供可鎖定的模型快照版本時，不自行補日期尾碼。

| 代號與來源 | 文件更新日期／版本 |
| --- | --- |
| [S1：Qwen Audio 使用指南][S1] | 2026-11-18 |
| [S2：WebSocket 接入][S2] | 2026-11-16 |
| [S3：WebRTC 接入][S3] | 2026-11-16 |
| [S4：短效 API key][S4] | 2026-10-29 |
| [S5：MDN WebSocket constructor][S5] | 2026-06-22 |
| [S6：AOQ 接入][S6] | 2026-11-13 |
| [S7：Client events][S7] | 2026-11-18 |
| [S8：Flash 模型頁][S8] | 2026-11-06 |
| [S9：Plus 模型頁][S9] | 2026-11-10 |
| [S10：官方技術報告][S10] | arXiv 2609.25176v2，2026-09-24 修訂，版本日期由[摘要頁](https://arxiv.org/abs/2609.25176v2)核對 |
| [S11：Model pricing][S11] | 2026-11-18 |
| [S12：Data retention policy][S12] | 2026-11-17 |
| [S13：3.1 TTS 聲線表][S13] | 2026-11-18 |
| [S14：Model Studio FAQ][S14] | 2026-11-15 |
| [S15：DashScope PyPI][S15] | 2.1.0，2026-11-13 發布 |
| [S16：DashScope 官方 repo][S16] | main，2026-11-19 查核，固定 commit 頁未取得 |
| [S17：AOQ Linux Python API][S17] | 2026-10-11 |
| [S18：AOQ SDK 下載][S18] | 文件 2026-11-17，Linux v1.4.1 更新於 2026-11-16 |

[S1]: https://www.alibabacloud.com/help/en/model-studio/qwen-audio-realtime-user-guides
[S2]: https://www.alibabacloud.com/help/en/model-studio/audio-realtime-websocket-access
[S3]: https://www.alibabacloud.com/help/en/model-studio/audio-realtime-webrtc-access
[S4]: https://www.alibabacloud.com/help/en/model-studio/generate-temporary-api-key
[S5]: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/WebSocket
[S6]: https://www.alibabacloud.com/help/zh/model-studio/audio-realtime-aoq-access
[S7]: https://www.alibabacloud.com/help/en/model-studio/fun-audiochat-client-events
[S8]: https://www.alibabacloud.com/help/en/model-studio/qwen-audio-3-1-realtime-flash
[S9]: https://www.alibabacloud.com/help/en/model-studio/qwen-audio-3-1-realtime-plus
[S10]: https://arxiv.org/html/2609.25176v2
[S11]: https://www.alibabacloud.com/help/en/model-studio/model-pricing
[S12]: https://www.alibabacloud.com/help/en/model-studio/data-retention-policy
[S13]: https://www.alibabacloud.com/help/zh/model-studio/qwen-audio-tts-voice-list
[S14]: https://www.alibabacloud.com/help/en/model-studio/faq-about-alibaba-cloud-model-studio
[S15]: https://pypi.org/project/dashscope/2.1.0/
[S16]: https://github.com/dashscope/dashscope-sdk-python
[S17]: https://www.alibabacloud.com/help/zh/model-studio/aoq-linux-python-sdk-reference
[S18]: https://www.alibabacloud.com/help/zh/model-studio/realtime-sdk-download
