# Flutter Web 怎麼收音與即時播音

## 三行結論

1. Flutter Web 能即時收音與播音：可用 `record` 收 PCM，再用 Web Audio 或 Flutter Sound 播放，WebRTC 是另一條路線，須配合伺服器支援。[S1][S3][S5][S7]
2. 玩家插話後，前端要自己停播、清空待播資料，並拒收舊回覆，套件有停止介面，但手機上的實際停播時間仍待驗證。[S8][S9]
3. 首版建議使用 HTTPS、由玩家點「開始主持」啟用聲音，並保持頁面在前景，鎖屏持續雙向語音不能當成已確認能力。[S10][S11][S12][S13]

查核日期為 2026-11-19，全文的外部事實均以此日查得的一手文件為依據，來源版本與更新日期列在文末。這是文件研究，未安裝套件、未錄音、未跑手機瀏覽器或模型 API，文中的建議尚未定案。

## 1. 收音：取得即時音訊串流

有兩條可行方向，聲音都能在玩家還沒說完時持續送出。

| 方向 | 官方提供的能力 | 對本案的判斷 |
|---|---|---|
| `record` | `AudioRecorder.startStream()` 可輸出 PCM16。6.2.1 與 7.2.0 的矩陣都列 Web、Android、iOS 支援 PCM16 串流，Android 不含 legacy recorder。[S1][S2] | 可先列為跨平台收音候選，但不負責播音或模型連線。 |
| 直接用瀏覽器 API | `getUserMedia({audio: ...})` 取得持續的 `MediaStream`，AudioWorklet 可在音訊處理執行緒處理低延遲音訊，Dart 可用 `package:web` 與 JS interop 存取瀏覽器 API。[S6][S7][S15] | 需要精細控制時可採用，但 PCM 轉換、分段與平台替換都要自行處理。 |

回音消除可在音訊 constraints 要求 `echoCancellation: true`，降噪可要求 `noiseSuppression: true`。一般的 `true` 是盡力符合，不保證成功，不認識的 constraint 可能被忽略。`noiseSuppression` 在 MDN 仍標為有限支援。[S16][S17]

建議啟動後檢查 `getSupportedConstraints()`，再用音軌 `getSettings()` 查看實際設定，取樣率與聲道也應讀回核對，不能只看送出的設定值。是否需要重取樣，等模型連線 ticket 確認輸入格式後再決定。[S16][S17][S18]

`MediaRecorder.start(timeslice)` 也能分段送出 Blob，並非一定要等錄完，但分段間隔不精準，手機可能延後交付。因此本案若要傳原始 PCM，建議優先評估 PCM 串流或 AudioWorklet，避免把 Blob 當成固定大小的 PCM 封包。[S12]

## 2. 播音：邊收邊播，以及插話停播

Flutter Sound 9.30.0 有 `startPlayerFromStream()`，接受 PCM16 或 Float32，須指定取樣率、聲道與 buffer 等參數，`stopPlayer()` 提供停止介面。官方 PCM 指南稱 Web、iOS 的串流已完成，Android 的 Float32 與非交錯聲道格式尚不完整。若走這套，建議先試單聲道 PCM16。[S4][S8][S32]

直接使用 Web Audio 時，可把收到的 PCM 轉成 `AudioBuffer`，用多個 `AudioBufferSourceNode` 排定連續播放，並保留每個節點的參照以便呼叫 `stop()`，也可用 AudioWorklet 自行管理待播資料。這是依 API 能力提出的實作方向，尚未驗證播放平順度。[S7][S9]

不要把任意收到的壓縮音訊片段直接交給 `decodeAudioData()`，MDN 明確說它需要完整音訊檔案資料，不接受檔案碎片。原始 PCM 應依格式建立音訊 buffer，不能當成完整 WAV 或 MP3 解碼。[S19]

建議插話處理分成下列步驟，這是待寫入 spec 的行為建議：

1. 按鍵或語音活動偵測觸發後，立即停止本機播放，不等待遠端取消完成。
2. 清空應用程式的待播資料，停止已排程的播放節點，若使用 AudioWorklet，通知它清空自己的佇列。
3. 將目前回覆標為失效，之後到達的舊音訊也丟棄，避免它重新進入播放器。
4. 同時通知後端或模型取消回覆。取消事件與回覆識別方式，交由連線決策 ticket 查核。

以上步驟以本機停止 API 與可控制佇列為基礎，但文件沒有保證「零毫秒停播」，實際喇叭停止時間須量測。[S8][S9]

WebRTC 收到的是遠端音軌，可透過 `MediaStreamTrack.enabled = false` 靜音，這個屬性只保證輸出靜音，不代表清空遠端回覆或瀏覽器內部待播資料。本次查不到通用的 WebRTC 接收端「清空全部待播音訊」API，不能把靜音當成完整取消方案。[S20]

## 3. 連線：WebSocket 與 WebRTC 都能用

| 方案 | 已查到的能力與限制 | 本案接下來要決定的事 |
|---|---|---|
| WebSocket | 瀏覽器支援雙向訊息，`web_socket_channel` 對 Web、Android、iOS 提供共用 API。瀏覽器 WebSocket 沒有自動背壓機制，處理不及會累積記憶體。建構式只有 URL 與子協定參數，沒有任意 HTTP header 參數。[S5][S21][S22] | 自訂音訊格式、順序、待播上限、過期音訊丟棄與重連。若供應商要求在握手放 `Authorization`，不能照搬原生或 Python 寫法，須由連線 ticket 決定後端轉送或官方允許的短效驗證方式，長效金鑰不得放前端。 |
| WebRTC | `flutter_webrtc` 的官方功能矩陣列 Web、Android、iOS 都支援音訊與 Data Channel，瀏覽器可把麥克風音軌加到 peer connection。建立連線要交換 SDP 與 ICE 資訊，視網路需要 STUN／TURN。[S10][S14][S23] | 對端必須支援 WebRTC 的媒體與協商流程，不能把 WebRTC 直接接到只收 WebSocket 的端點，工具事件通道、驗證、TURN 與取消方式要另定。 |

WebSocket 的 `wss://` 是加密連線，本案建議與 HTTPS 頁面搭配使用。WebRTC 也不會免除麥克風的 HTTPS 與權限限制。[S6][S10][S22]

研究建議：先依供應商官方協定選傳輸方式，再選套件，不要只因 Flutter 支援 WebRTC，就認定模型端一定能接。這份文件未查核或假設 Qwen 的特定連線協定。

## 4. 手機瀏覽器：權限、自動播放、鎖屏與 HTTPS

| 項目 | iOS Safari | Android Chrome |
|---|---|---|
| 麥克風權限 | WebKit 官方說首次 `getUserMedia()` 會請求授權，使用者也可中途暫停收音，應處理音軌 `mute`／`unmute`。[S10] | 遵循 `getUserMedia()` 的使用者授權，拒絕可能回 `NotAllowedError`，沒有裝置可能回 `NotFoundError`。使用者一直不選時，請求也可能一直等待。[S6] |
| 自動播放 | WebKit 對正在收音或已播放音訊的頁面，允許以 `MediaStream` 為來源的媒體自動播放，開始播放聲音仍有手勢規則。這項例外不能延伸成所有 PCM／Web Audio 都免手勢。[S10] | Chrome 的自動播放政策也涵蓋 Web Audio，建立後可能處於 `suspended`，應在使用者操作時建立或 `resume()`。[S11] |
| 螢幕關閉／背景 | 查不到可保證本案「持續收音＋Web Audio 播音＋連線」全部運作的現行官方承諾。舊 WebKit 問題紀錄顯示 iOS 15.5 曾有鎖屏後麥克風停止問題，但該問題已結案，不能當成今天所有 Safari 都失敗的證據。[S24] | MDN 明列 Android Chrome 鎖屏時可能暫停 MediaRecorder 的 `dataavailable`。這只直接證明 MediaRecorder 的限制，不能據此宣稱所有 AudioWorklet 或 WebRTC 都會停止。Chrome 也說背景頁面可能被凍結或丟棄。[S12][S13] |
| HTTPS | 正式使用須安全來源，WebKit 明列 HTTPS。[S10] | `getUserMedia()` 需要安全來源，MDN 列 HTTPS、localhost 等例外。[S6] |

手機連電腦的 `http://區網IP:port` 不屬於手機自己的 localhost，因此建議測試環境也準備 HTTPS，這是依安全來源規則得出的部署判斷。[S6]

建議把「開始主持」「麥克風被拒絕」「聲音待啟用」「頁面已暫停」「重新啟用」列為畫面狀態。Screen Wake Lock 可避免自動暗屏或鎖屏，但只適用可見的活動頁面，低電量或系統設定可能拒絕或釋放，它不能保證手動鎖屏後仍有語音服務。[S25]

## 5. 候選套件、版本、授權與維護狀況

### 專案目前的基線

查核來源為本 worktree 的 [`frontend/pubspec.yaml`](../../../frontend/pubspec.yaml) 與 [`frontend/pubspec.lock`](../../../frontend/pubspec.lock)，查核日期同為 2026-11-19。

- `pubspec.yaml`：專案版本 `1.0.0+1`，Dart 限制 `^3.11.1`，Flutter 只寫 SDK dependency，沒有固定實際版本。
- `pubspec.lock`：SDK 限制為 Dart `>=3.11.1 <4.0.0`、Flutter `>=3.41.0`。這是相依套件解出的最低要求，無法證明目前機器安裝哪版 Flutter。
- 已有間接相依 `web 1.1.1`、`web_socket_channel 3.0.3`，尚未在直接 dependencies 宣告，lockfile 沒有 `record`、`flutter_sound`、`flutter_webrtc`。

未執行會更新 Flutter 快取的版本命令，也未跑套件解析或安裝。

下表的「支援」是官方列出的平台能力，不是本專案已編譯或實機驗證。維護欄保留 pub.dev 的相對發布時間，不自行換算成精確發布日。

| 候選／用途 | 版本與授權 | Web | Android | iOS | 維護狀況與版本風險 |
|---|---|---|---|---|---|
| `record`／即時收音 | 候選 `6.2.1`，現行 `7.2.0`，BSD-3-Clause。[S1][S2] | 支援 PCM16 串流。[S1][S2] | 支援 PCM16 串流，legacy recorder 除外。[S1][S2] | 支援 PCM16 串流。[S1][S2] | 6.2.1 頁顯示約 6 個月前，7.2.0 顯示約一週內，changelog 有近期修正。7.x 要 Flutter 3.44／Dart 3.12，超過專案目前宣告的最低基線，6.x changelog 列最低 Flutter 3.24／Dart 3.5。建議先評估 6.2.1，仍須實際解析確認。[S26] |
| `flutter_sound`／收音與播音 | `9.30.0`，MPL-2.0。[S3] | 官方列支援串流。[S4] | 支援，Float32 與非交錯模式不完整。[S4] | 官方列支援串流。[S4] | 版本頁顯示約 10 個月，主頁約 11 個月，快取時間不同，最低 Dart 3.7。README 稱 9.x 是 legacy 且會持續維護，也說維護人力吃緊，不能據此保證維護品質。[S3][S27] |
| `flutter_webrtc`／WebRTC 音訊 | `1.6.3`，MIT。[S14] | README 音訊與 Data Channel 矩陣列支援，pub.dev 頂部平台標籤卻漏列 Web，依矩陣判讀並保留此差異。[S14] | 支援。[S14] | 支援。[S14] | 發布約 23 天，版本頁有多個近期版本，最低 Dart 3.3，實際原生建置與本案整合仍待測。[S28] |
| `web_socket_channel`／傳輸訊息 | `3.0.3`，BSD-3-Clause。[S5] | 支援。[S5] | 支援。[S5] | 支援。[S5] | Dart 團隊發布者，版本頁顯示約 19 個月、最低 Dart 3.3，近期沒有新版不能單獨判成停維護。只管連線，不提供收播音。[S5][S29] |
| `web`／直接存取瀏覽器 API | 專案鎖定 `1.1.1`，BSD-3-Clause，現行 `1.1.2`。[S15][S30] | 支援。[S15] | 不提供原生實作，Android Chrome 屬於 Web。[S15] | 不提供原生實作，iOS Safari 屬於 Web。[S15] | Dart 官方維護。1.1.2 於 2026-10-23 發布，要求 Dart `^3.13.0`，1.1.1 要 Dart `^3.4.0`。不能假設升到最新版仍符合現有最低基線。[S30] |

此表只列研究候選，未選定或新增相依套件。Flutter Sound 的程式授權與它的文件授權不同，評估套件時應以 MPL-2.0 程式授權為準，不能把同一家族其他套件的授權套過來。[S3]

## 6. 哪些部分要放在 `core/platform/` 後面

現有 [`platform_info.dart`](../../../frontend/lib/core/platform/platform_info.dart)、[`image_picker.dart`](../../../frontend/lib/core/platform/image_picker.dart) 與 [`lesson_video_player.dart`](../../../frontend/lib/core/platform/lesson_video_player.dart) 已採介面加 Riverpod provider 的方式，呼叫端不直接使用平台套件。本機查核日期 2026-11-19，版本是本 worktree 現況。

建議沿用這個方式，以下是設計建議，沒有新增檔案或決定介面名稱：

| 放進平台實作的細節 | 原因／依據 |
|---|---|
| `navigator.mediaDevices`、麥克風權限、constraints、音軌設定與事件 | 都是瀏覽器物件，原生 App 要換成平台錄音能力。[S6][S18] |
| `AudioContext` 的建立／恢復、AudioWorklet 模組、音訊節點、PCM 播放佇列與清除 | Web Audio 與手勢啟用屬於 Web 實作，對上層可提供「開始收音、加入待播資料、停止並清空、釋放」等能力。[S7][S9][S11] |
| DOM 媒體元素、WebRTC 音軌綁定、頁面可見性與 Screen Wake Lock | 不能讓頁面或 host state 直接依賴 DOM，原生 App 生命週期另有實作。[S10][S13][S25] |
| JS interop 與 Web 專用 import | 用條件匯入／匯出隔離，Dart 官方建議 Web API 使用 `package:web` 與 `dart:js_interop`，避免新寫 `dart:html` 路線。[S31] |

host state 可保留「誰的回覆仍有效」「何時打斷」「是否重連」等不依賴瀏覽器的邏輯，測試時換手寫 fake。`web_socket_channel` 是跨平台 API，沒有必要只因用在 Web 就把所有通訊邏輯視為網頁專用，Web 握手限制仍須由轉接層處理。[S5][S22]

## 查不到的項目

- 現行 iOS Safari、Android Chrome 在實際目標手機／平板鎖屏後，能否持續完成本案雙向語音：查過 WebKit WebRTC 文件、WebKit 鎖屏問題紀錄、Chrome Page Lifecycle、MDN MediaRecorder，沒有跨上述收播音路線的現行保證。需分「鎖屏、切 App、來電、回前景」實測。
- 套件在本專案上的相依套件解析、編譯、收音分段大小、實際取樣率、回音消除效果、首音與停播時間：官方平台支援表不能代替本案驗證，本任務也不允許安裝或改程式。
- WebRTC 接收端通用的清空全部待播音訊 API：查過音軌控制與官方套件功能矩陣，只確認靜音能力，沒有取得可滿足完整取消語意的依據。
- `record` 等套件的 pub.dev JSON API 在研究工具回覆不可存取，本機 HTTP 查詢則遇 DNS 解析失敗。已改以可取得的 pub.dev 套件頁、版本頁、changelog 作為依據，不推算精確發布日。`flutter_webrtc` 主頁一度抓取失敗，固定版本頁成功取得，未繞過阻擋。
- Qwen 的輸入／輸出取樣率、取消與歷史修正事件、瀏覽器直連驗證：屬連線／模型 ticket，本次未查核，本報告不把任何特定格式當作已定案。

## 和選型查核報告不一致的地方

比對輸入為`AI語音主持選型查核報告.html`§04 的架構圖與具體做法，本機查核日期 2026-11-19。該報告未選 Flutter 音訊套件，沒有相同欄位可直接核對套件版本。

- 報告寫「玩家說等一下 → 本機立刻停播，並丟棄還沒播完的舊回覆」：本研究確認 API 可停止播放，但這是要自己實作的應用行為，還要處理取消後繼續到達的舊資料，不能當成模型或套件已保證的結果。[S8][S9][S20]
- 報告圖中的「回音消除」需要加上裝置與瀏覽器條件：設定 `true` 不保證實際生效，也不保證桌邊喇叭漏音能完全消除。[S16][S17]
- 報告未列手機手勢啟用、鎖屏與 HTTPS 條件，本研究補上限制，這是補缺，不是查出報告某個數字錯誤。[S6][S10][S11][S12]
- 模型的首音、插話停播與費用數字不屬這張 ticket，未拿它們作為 Flutter 可行性證據，也未重新認證。

## 一手來源與版本紀錄

以下全部查核於 **2026-11-19**。未見更新日期的頁面以列出的套件版本或「持續更新文件，本次快照」識別，沒有自行補發布日期。

| 編號 | 來源連結 | 版本／文件更新日期 |
|---|---|---|
| S1 | [record 固定版本與功能矩陣](https://pub.dev/packages/record/versions/6.2.1) | 6.2.1 |
| S2 | [record 現行套件頁](https://pub.dev/packages/record) | 7.2.0 |
| S3 | [Flutter Sound 官方套件頁](https://pub.dev/packages/flutter_sound) | 9.30.0 |
| S4 | [Flutter Sound PCM Dart Streams](https://flutter-sound.canardoux.xyz/tau/guides/guides_live_streams.html) | 文件標題 9.30.0 |
| S5 | [web_socket_channel 官方套件頁](https://pub.dev/packages/web_socket_channel) | 3.0.3 |
| S6 | [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) | 2025-11-30 |
| S7 | [MDN AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet) | 2025-05-09 |
| S8 | [Flutter Sound stopPlayer](https://pub.dev/documentation/flutter_sound/latest/public_flutter_sound_player/FlutterSoundPlayer/stopPlayer.html) | 9.30.0 |
| S9 | [MDN AudioBufferSourceNode](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode) | 2026-09-28 |
| S10 | [WebKit A Closer Look Into WebRTC](https://webkit.org/blog/7763/a-closer-look-into-webrtc/) | 2017-07-03，Safari 11／iOS 11 的政策說明，非現行完整相容性保證 |
| S11 | [Chrome Autoplay policy](https://developer.chrome.com/blog/autoplay/) | 說明 Chrome 66／Web Audio Chrome 71，頁尾標 2017-09-13，與內文提及 2018 有落差，保留原標示 |
| S12 | [MDN MediaRecorder dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event) | 2026-10-26 |
| S13 | [Chrome Page Lifecycle](https://developer.chrome.com/docs/web-platform/page-lifecycle-api) | 2026-10-16 |
| S14 | [flutter_webrtc 固定版本與功能矩陣](https://pub.dev/packages/flutter_webrtc/versions/1.6.3) | 1.6.3 |
| S15 | [web 固定版本](https://pub.dev/packages/web/versions/1.1.1) | 1.1.1 |
| S16 | [MDN echoCancellation](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/echoCancellation) | 2026-10-08 |
| S17 | [MDN noiseSuppression](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/noiseSuppression) | 2026-10-08 |
| S18 | [MDN getSettings](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/getSettings) | 持續更新文件，本次快照 |
| S19 | [MDN decodeAudioData](https://developer.mozilla.org/en-US/docs/Web/API/BaseAudioContext/decodeAudioData) | 2026-09-30 |
| S20 | [MDN MediaStreamTrack.enabled](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/enabled) | 2024-07-26 |
| S21 | [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) | 2026-11-12 |
| S22 | [MDN WebSocket constructor](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/WebSocket) | 2026-06-22 |
| S23 | [MDN WebRTC protocols](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols) | 2026-09-17 |
| S24 | [WebKit issue 241400](https://bugs.webkit.org/show_bug.cgi?id=241400) | iOS 15.5 問題，2022-06-23 結案，不可推論現行版本狀態 |
| S25 | [MDN Screen Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API) | 2026-11-12 |
| S26 | [record changelog](https://pub.dev/packages/record/changelog) | 涵蓋 6.1.0、6.2.1、7.0.0、7.2.0 |
| S27 | [Flutter Sound versions](https://pub.dev/packages/flutter_sound/versions) | 9.30.0，最低 Dart 3.7 |
| S28 | [flutter_webrtc versions](https://pub.dev/packages/flutter_webrtc/versions) | 1.6.3，最低 Dart 3.3 |
| S29 | [web_socket_channel versions](https://pub.dev/packages/web_socket_channel/versions) | 3.0.3，最低 Dart 3.3 |
| S30 | [pub.dev web 套件中繼資料](https://pub.dev/api/packages/web) | 1.1.1：2025-02-26，1.1.2：2026-10-23 |
| S31 | [Dart Migrate to package:web](https://dart.dev/interop/js-interop/package-web) | 持續更新文件，本次快照 |
| S32 | [Flutter Sound startPlayerFromStream](https://pub.dev/documentation/flutter_sound/latest/public_flutter_sound_player/FlutterSoundPlayer/startPlayerFromStream.html) | 9.30.0 |

[S1]: https://pub.dev/packages/record/versions/6.2.1
[S2]: https://pub.dev/packages/record
[S3]: https://pub.dev/packages/flutter_sound
[S4]: https://flutter-sound.canardoux.xyz/tau/guides/guides_live_streams.html
[S5]: https://pub.dev/packages/web_socket_channel
[S6]: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
[S7]: https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet
[S8]: https://pub.dev/documentation/flutter_sound/latest/public_flutter_sound_player/FlutterSoundPlayer/stopPlayer.html
[S9]: https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode
[S10]: https://webkit.org/blog/7763/a-closer-look-into-webrtc/
[S11]: https://developer.chrome.com/blog/autoplay/
[S12]: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event
[S13]: https://developer.chrome.com/docs/web-platform/page-lifecycle-api
[S14]: https://pub.dev/packages/flutter_webrtc/versions/1.6.3
[S15]: https://pub.dev/packages/web/versions/1.1.1
[S16]: https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/echoCancellation
[S17]: https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/noiseSuppression
[S18]: https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/getSettings
[S19]: https://developer.mozilla.org/en-US/docs/Web/API/BaseAudioContext/decodeAudioData
[S20]: https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/enabled
[S21]: https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API
[S22]: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/WebSocket
[S23]: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols
[S24]: https://bugs.webkit.org/show_bug.cgi?id=241400
[S25]: https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API
[S26]: https://pub.dev/packages/record/changelog
[S27]: https://pub.dev/packages/flutter_sound/versions
[S28]: https://pub.dev/packages/flutter_webrtc/versions
[S29]: https://pub.dev/packages/web_socket_channel/versions
[S30]: https://pub.dev/api/packages/web
[S31]: https://dart.dev/interop/js-interop/package-web
[S32]: https://pub.dev/documentation/flutter_sound/latest/public_flutter_sound_player/FlutterSoundPlayer/startPlayerFromStream.html
