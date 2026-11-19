# 註冊阿里雲並確認能呼叫 Qwen 即時語音

Type: task
Status: open
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

## Comments

- 2026-11-19：「[Qwen 即時語音模型的官方規格](01-qwen-realtime-facts.md)」已結案，細節在[結果檔](../research/qwen-realtime-facts.md)。和這張有關的事實：
  - 模型名稱是 `qwen-audio-3.1-realtime-flash` 與 `qwen-audio-3.1-realtime-plus`。新加坡與北京都可用，金鑰要用對應區域與 workspace 的。
  - 官方價格頁寫新加坡區兩款各有 100 萬 tokens 的免費額度，有效 90 天，有條件；沒有登入確認過立倫的帳號符不符合。
  - 官方的快速開始範例用 Python 的 `websockets` 與 `pyaudio`。`dashscope` 套件（2.1.0）沒有查到明列支援這兩款模型的範例。
  - 平台預設保留推論資料最多 30 天。接不接受由「[接不接受阿里雲保留玩家的聲音最多 30 天](14-voice-data-retention.md)」決定；這張只用立倫自己的聲音測。
