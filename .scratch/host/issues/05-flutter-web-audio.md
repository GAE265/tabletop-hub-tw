# Flutter Web 怎麼收音與即時播音

Type: research
Status: resolved
Map: [AI 語音主持](../map.md)

## Question

聲音從桌上的手機或平板進出：開 Flutter Web 頁面，用它的麥克風與喇叭。查清楚 Flutter Web 做得到什麼，之後同一套程式還要出 Android／iOS（AGENTS.md §1）。

1. 收音：Flutter Web 怎麼取得麥克風的即時音訊串流（不是錄完再上傳）。有哪些套件，或要直接用瀏覽器的 API。瀏覽器內建的回音消除、降噪能不能打開。
2. 播音：怎麼邊收到音訊邊播放，又能在玩家插話時立刻停下、丟掉還沒播的部分。
3. 連線：Flutter Web 能用 WebSocket 還是 WebRTC 傳即時音訊，各自的限制。
4. 手機瀏覽器的限制：iOS Safari 與 Android Chrome 對麥克風權限、自動播放、螢幕關閉後的行為。要不要 HTTPS。
5. 套件：每個候選套件的名稱、版本、授權、維護狀況、支援哪些平台（Web、Android、iOS）。專案目前的 Flutter 版本看 `frontend/pubspec.yaml`。
6. 只能在網頁上用的程式碼要包在 `frontend/lib/core/platform/` 的介面後面（AGENTS.md §5.3）。哪些部分會是網頁專用。

只用官方文件、pub.dev、瀏覽器廠商文件（MDN、WebKit、Chrome）等一手來源，每項附連結、查核日期與版本。

結果寫在 `.scratch/host/research/flutter-web-audio.md`。

## Answer

- 查核日期：2026-11-19，六題均已回答，完整來源與版本見[研究結果](../research/flutter-web-audio.md)。
- Web 可即時收 PCM，候選為 `record` 或 `getUserMedia` 加 AudioWorklet，不必等錄完才上傳。
- 播音可用 Flutter Sound 串流或 Web Audio，插話需停播、清空佇列並拒收舊回覆，實際停播時間待測。
- WebSocket 與 WebRTC 都可用，但模型端須支援相同協定，瀏覽器 WebSocket 不能任意設定握手 header。
- 手機使用須考慮 HTTPS、麥克風授權與手勢啟用，鎖屏持續雙向語音查不到完整保證。
- 五個候選套件已逐一列 Web、Android、iOS 支援、授權與維護證據，`record` 7.x 與 `web` 1.1.2 提高 SDK 門檻。
- 網頁物件、音訊節點、JS interop 與頁面生命週期須封裝於 `core/platform/`，現有介面模式可沿用。
- 選型報告的「立刻停播」與「回音消除」需補實作及裝置條件，未改地圖、前端程式或套件設定。
