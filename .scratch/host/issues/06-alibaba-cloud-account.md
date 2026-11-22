# 註冊阿里雲並確認能呼叫 Qwen 即時語音

Type: task
Status: resolved
Map: [AI 語音主持](../map.md)

## Question

Qwen 要另外註冊阿里雲。帳號由立倫自己開、用自己的額度（2026-11-19 畫地圖時決定）。這張 ticket 要立倫親手做，AI 先查官方註冊文件，給一份逐步的清單。

完成後確認並記錄：

1. 帳號開在哪個站（國際站）與區域（新加坡）。要不要綁信用卡、有沒有免費額度、額度多少。
2. 能不能看到並呼叫 `Qwen-Audio-3.1-Realtime` 的 Flash 與 Plus；要不要另外申請開通。
3. 用官方的最小範例實際連上一次，確認收得到聲音。
4. 設定欄位名稱打算叫什麼（先記提案，正式名稱在 spec 決定）。
5. 新加坡區實際叫得動哪些中文聲線。官方文件沒有列出新加坡可用的清單。
6. 新加坡區的免費額度拿不拿得到、有效到什麼時候。

金鑰只放立倫本機的 `.env`。Answer 只寫欄位名稱、區域、模型名稱與額度，不寫金鑰。這張 ticket 不改 `.env.example`（那是實作階段的事）。

## 操作清單

2026-11-19 依官方文件整理，來源在本節最後，查核日期都是 2026-11-19。第一到第五步要立倫親手做；第六步可以交給 AI。

### 一、註冊國際站帳號 [A1]

1. 開 <https://account.alibabacloud.com/register/intl_register.htm>，帳號類型選 **Individual**。
2. 國家／地區選 **Taiwan**。註冊後不能改（它決定幣別與稅率）。驗證用的手機號碼要和這個地區相符。
3. 填 email 與密碼（8 到 20 字，至少三種字元），輸入驗證碼，同意條款後按 Register。

### 二、補完帳號資料 [A1][A2][A3]

拿免費額度、用付費服務之前都要先做完這一步，沒做完的話下單會被擋。

4. 加安全手機（用 email 註冊的話）或安全 email。
5. 加付款方式：實體信用卡，或已驗證的 PayPal。不收虛擬信用卡。綁卡時可能有一筆驗證用的暫時授權，不會真的扣錢。
6. 稅籍資料可以跳過。身分驗證（護照或駕照）不用做：只有買中國大陸區域的服務、簽線上合約、申請信用額度才需要。

### 三、開通新加坡區的 Model Studio [A3]

7. 開 <https://modelstudio.console.alibabacloud.com/ap-southeast-1>，右上角確認區域是 **Singapore**，讀完並同意服務協議。
8. 免費額度會自動發，不用另外申請，最多約 2 小時才看得到。

### 四、確認模型與額度，打開「只用免費額度」 [A3][A6]

9. 開免費額度頁 <https://modelstudio.console.alibabacloud.com/ap-southeast-1/costing-balance/free-quota> 的 **Free Quota** 分頁，找 `qwen-audio-3.1-realtime-flash` 與 `qwen-audio-3.1-realtime-plus`，記下剩餘額度與到期日。
10. 這兩款都打開 **Free Quota Only**。額度用完時呼叫會回錯誤 `AllocationQuota.FreeTierOnly`，不會扣錢。改完約 30 分鐘才生效。
11. 到模型市集 <https://modelstudio.console.alibabacloud.com/model/market> 打開這兩款的詳細頁，看有沒有「申請」或「開通」的按鈕。官方文件沒寫這兩款要不要另外申請。

### 五、建金鑰，寫進 `.env` [A4][A5]

12. 開 <https://modelstudio.console.alibabacloud.com/ap-southeast-1/settings/api-key>，確認右上角仍是 Singapore，按 **Create API Key**：
    - Workspace：選預設的那個。
    - Permissions：選 **Custom**，可用模型只勾這兩款；找不到這兩款就改選 **All**。IP 白名單不設，因為家裡的 IP 會變。
13. 關掉視窗後就再也看不到金鑰明碼，所以當下複製兩樣東西：金鑰、**API Host**。Workspace ID 是 API Host 開頭 `llm-` 的那一段。
14. 在這個 worktree 的根目錄 `.env` 加兩行（目前還沒有這個檔，新建即可；`.env` 已被 git 忽略）：

    ```
    HOST_REALTIME_API_KEY=<金鑰>
    HOST_REALTIME_WORKSPACE_ID=<llm- 開頭的那段>
    ```

    欄位名稱是提案，正式名稱在 spec 決定。命名照 `RULES_QA_EMBEDDING_*` 的前例：每個 domain 用自己的前綴，不退回全域設定。官方範例用的 `DASHSCOPE_API_KEY` 沒有 domain 前綴，所以不用。區域另有選填的 `HOST_REALTIME_REGION`，預設 `ap-southeast-1`。

### 六、跑小測試

15. 跟 AI 說「金鑰填好了」，AI 會在 worktree 根目錄跑下面兩個指令，再把結果寫進 Answer。也可以自己跑：

    ```
    uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/qwen-smoke/smoke.py connect
    uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/qwen-smoke/smoke.py voices
    ```

    - `connect`：Flash 與 Plus 各連一次，送一句文字，存下主持人回覆的聲音，用 `afplay <檔案>` 播放。不用麥克風；對著麥克風說話留給「[用真的聲音試聽 Qwen 主持人](07-listen-to-qwen-host.md)」。
    - `voices`：用 Flash 逐一試聲線表上 3.1 的 74 個聲線 [A8]，每個只講一句話，列出新加坡區叫得動哪些。
    - 聲音檔存在系統暫存區，不進 repo。腳本不印金鑰與 Workspace ID，也不裝進專案的套件（`--no-project`）。
    - 費用：兩個指令合計約 76 次短回覆，估計用掉 Flash 免費額度不到 1%。
    - 握手失敗時，官方建議依序查：網域、區域、workspace、金鑰、模型名稱、模型有沒有開通、權限 [A7]。

### 來源

| 代號 | 文件 | 文件更新日期 |
| --- | --- | --- |
| [A1] | [Sign up with Alibaba Cloud](https://www.alibabacloud.com/help/en/account-management/latest/sign-up-with-alibaba-cloud) | 2026-09-21 |
| [A2] | [Payment method FAQs](https://www.alibabacloud.com/help/en/account/support/payment-method-faqs) | 2026-09-21 |
| [A3] | [Free quota for new users](https://www.alibabacloud.com/help/en/model-studio/new-free-quota) | 2026-11-16 |
| [A4] | [Obtain an API key](https://www.alibabacloud.com/help/en/model-studio/get-api-key) | 2026-11-15 |
| [A5] | [Regions and service deployment scopes](https://www.alibabacloud.com/help/en/model-studio/regions) | 2026-11-12 |
| [A6] | [Model pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing) | 2026-11-18 |
| [A7] | [WebSocket access](https://www.alibabacloud.com/help/en/model-studio/audio-realtime-websocket-access) | 2026-11-16 |
| [A8] | [Qwen-Audio-TTS 音色列表](https://www.alibabacloud.com/help/zh/model-studio/qwen-audio-tts-voice-list) | 2026-11-18 |

查不到的項目：

- 台灣發行的信用卡能不能綁：付款方式 FAQ 只說「依國家與地區而定」，指向另一頁，沒有列出發卡國家。
- 這兩款模型要不要另外申請開通：模型頁、免費額度頁、使用指南都沒寫，所以列成第 11 步讓立倫在主控台看。
- 免費額度在文字與音訊 tokens 之間怎麼扣：價格頁沒寫。

## Comments

- 2026-11-19：「[Qwen 即時語音模型的官方規格](01-qwen-realtime-facts.md)」已結案，細節在[結果檔](../research/qwen-realtime-facts.md)。和這張有關的事實：
  - 模型名稱是 `qwen-audio-3.1-realtime-flash` 與 `qwen-audio-3.1-realtime-plus`。新加坡與北京都可用，金鑰要用對應區域與 workspace 的。
  - 官方價格頁寫新加坡區兩款各有 100 萬 tokens 的免費額度，有效 90 天，有條件；沒有登入確認過立倫的帳號符不符合。
  - 官方的快速開始範例用 Python 的 `websockets` 與 `pyaudio`。`dashscope` 套件（2.1.0）沒有查到明列支援這兩款模型的範例。
  - 平台預設保留推論資料最多 30 天。接不接受由「[接不接受阿里雲保留玩家的聲音最多 30 天](14-voice-data-retention.md)」決定；這張只用立倫自己的聲音測。
- 2026-11-19：立倫開好帳號並開通新加坡區，傳來 `qwen-audio-3.1-realtime-flash` 詳細頁的截圖：
  - 部署範圍是 International。免費額度 1,000,000／1,000,000 tokens（剩 100%），到期日 2027/02/18。
  - 截圖當下 Free Quota Only 還是關的。
  - 頁面上只有 Try Now，沒有「申請」或「開通」按鈕。
  - 模型能力欄勾了 Playground、function calling、Web Search；Structured Output、Prefix Continuation、Cache、Batches、Model Fine-tuning 沒勾。
  - Plus 的詳細頁還沒看。
- 2026-11-19：立倫填好 `.env`，AI 跑 `smoke.py`（只測 Flash）：
  - 主控台的 API Host 長這樣：`ws-<一串英數>.ap-southeast-1.maas.aliyuncs.com`。Workspace ID 的開頭是 `ws-`，不是官方區域文件舉例的 `llm-`。立倫把整段 API Host 填進 `HOST_REALTIME_WORKSPACE_ID`，腳本改成兩種寫法都接受。
  - `connect --models flash`：成功。預設聲線 `longanqian_v3.1`，回覆 3.9 秒聲音，逐字稿「歡迎來玩《血與刃的白薔薇》，今晚開戰！」。從送出文字到第一段音訊 836 毫秒；這是文字輸入，不能當成語音對話的首音時間。
  - `voices --model flash`：試了 74 個，54 個成功，`session.updated` 回報的聲線都和要求的一樣。失敗的 20 個都回 `invalid_value: Unsupported voice`，全是 TTS 聲線表上「只在北京」的那一組：`linxiaoling`、`longfeifei`、`longjing`、`longqiang`、`longyan`、`longxiaobai`、`longyue`、`longcheng`、`longlaotie`、`longshao`、`longshu`、`longze`、`longhao`、`longjin`、`longnan`、`longshuo`、`longtian`、`longxiaocheng`、`longke`、`loongbella`（都是 `_v3.1`）。
  - 同一則錯誤訊息附了伺服器接受的 92 個聲線名稱，比 TTS 聲線表多出幾個，例如 `longanlufeng`、`longanxiaoxin`、`longanhuan_v3.6`、`cindy_v3.1`。這些多出來的沒有試。
  - 聲音檔在系統暫存區，沒有進 repo。
  - 主控台的免費額度清單只看得到 Flash，找不到 Plus。
- 2026-11-19：立倫同意試呼叫 Plus 一次（`connect --models plus`）：成功。預設聲線，回覆 2.8 秒聲音，逐字稿「歡迎來玩《血與刃的白薔薇》！」，從送出文字到第一段音訊 1,072 毫秒（文字輸入）。

## Answer

2026-11-19 結案。測試全部用文字輸入，沒有錄任何人的聲音。

1. **站與區域**：國際站（alibabacloud.com）個人帳號，Model Studio 開在新加坡（`ap-southeast-1`）。依官方文件，要先補完帳號資料（安全手機、付款方式）才拿得到免費額度、才能用付費服務；身分驗證不用做。
2. **能不能看到、叫不叫得動**：
   - `qwen-audio-3.1-realtime-flash`：主控台看得到。詳細頁只有 Try Now，沒有「申請」按鈕。實際呼叫成功。
   - `qwen-audio-3.1-realtime-plus`：主控台的免費額度清單找不到，直接呼叫卻成功。
3. **最小範例**：沒有照抄官方範例（它要麥克風與 `pyaudio`），改用自寫的 [`smoke.py`](../prototypes/qwen-smoke/smoke.py)：照官方 WebSocket 事件送一句文字，存下回覆的聲音。Flash 和 Plus 都收得到聲音，細節在 Comments。對著麥克風說話留給「[用真的聲音試聽 Qwen 主持人](07-listen-to-qwen-host.md)」。
4. **設定欄位（提案，正式名稱在 spec 決定）**：
   - `HOST_REALTIME_API_KEY`：金鑰。新版金鑰以 `sk-ws` 開頭。
   - 建議用 `HOST_REALTIME_API_HOST` 放主控台顯示的整段 API Host（`ws-<一串英數>.ap-southeast-1.maas.aliyuncs.com`），不要拆成 Workspace ID 和區域兩個欄位。理由：立倫第一次就整段貼上，而且 API Host 裡已經有區域。這次腳本沿用 `HOST_REALTIME_WORKSPACE_ID`，兩種寫法都接受。
   - 前綴照 `RULES_QA_EMBEDDING_*` 的前例，每個 domain 用自己的前綴，不退回全域設定。
5. **新加坡區的中文聲線**：用 Flash 試了 TTS 聲線表上 3.1 的 74 個，54 個叫得動。失敗的 20 個都是表上「只在北京」的那一組，名單在 Comments。伺服器的錯誤訊息附了它接受的 92 個聲線名稱，比聲線表多幾個，多的那些沒有試。聲音好不好聽由試聽那張判斷。
6. **免費額度**：
   - Flash：拿到了，100 萬 tokens，2027/02/18 到期（開通日起 90 天）。
   - Plus：查不到。價格頁寫有 100 萬 tokens，主控台卻看不到。這次呼叫有沒有收費，要等帳單更新才知道。
