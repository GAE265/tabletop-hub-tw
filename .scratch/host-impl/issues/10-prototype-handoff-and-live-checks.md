# 10：參考畫面、交接說明、流程圖；試聽定稿與手動檢查

Status: ready-for-human
Blocked by: 08, 09
Spec: [spec](../../host/spec.md) §4.1、§13.6、§14.4、§14.5、§14.6、§15
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

分兩段。第一段 AI 自己做完，然後停下來；第二段要立倫在場。

### 第一段：AI 做

1. 參考畫面 `frontend/lib/prototypes/host/`，路由 `/proto/host`（spec §14.4）。只用 Flutter 預設元件，不套主題。元件照設計稿 [v2](../../host/prototypes/ui-mockups/v2/README.md) 的清單。提醒的字句照 spec §14.5。
2. 交接說明 `docs/handoff/host.md`，照 `docs/handoff/_template.md`（spec §14.6）。
3. 流程圖：LangGraph 輸出的 Mermaid 文字輸出一次，放 `docs/handoff/host.md` 的最後一節，並在 ADR 0004 連過去（spec §13.6）。
4. 手動檢查清單：把 spec §15.2 的表寫成可以照著做的步驟，改自原型的 [`auto_checks.py`](../../host/prototypes/listen-test/auto_checks.py)。清單放本檔的 Comments。
5. 用筆電開本機網址，真的後端加真的模型，自己先走一遍開主持到結束，確認連得起來。截圖放進交接說明。

做完第一段就停下來，告訴立倫可以試聽了。

### 第二段：立倫在場

1. 固定台詞與提醒的字句定稿：用真的後端試聽 18 句固定台詞、簡短版規則要點、主持人的指令與人設（原「[主持人的人設與台詞](../../host/issues/18-host-persona-and-script-lines.md)」的題目）。改定的字句寫回 `content.py`。
2. 照手動檢查清單跑一遍，結果記在本檔的 Comments，之後貼進 PR 說明。真人多人桌邊閒聊那一項要有組員在場。
3. 量到新的同音字，加進語音指令「也接受」的清單（spec §5.1），並補測試。
4. 片段辨識文字等 0.3 秒夠不夠（spec §5.2）；不夠就改數字並更新 spec。
5. 手機實測：要先有 HTTPS，由立倫準備。沒有就只用筆電測，在 Comments 記「手機沒測」。
6. ADR 0004 請瑋鋐與組員同意後，把 `status` 從 `proposed` 改掉。

手動檢查不擋合併（spec §15.1）。

## 要動的檔案

- `frontend/lib/prototypes/host/`（新）
- `frontend/lib/app/router.dart`（加 `/proto/host`）
- `docs/handoff/host.md`（新）、`docs/handoff/images/`
- `docs/adr/0004-host-realtime-voice-and-langgraph.md`
- `backend/app/domains/host/content.py`（字句定稿）
- `.scratch/host/spec.md`（只有數字或說法清單改了的時候）

## 動到別人的地方

- `frontend/lib/app/router.dart`：加一條 `/proto/host` 路由。擁有者永傑。`dev` 的其他參考畫面也是這樣掛的。PR 說明 @ 永傑。
- PR 要加 `needs-ui` 標籤並 @ 永傑（AGENTS.md §5.4）。標籤由立倫自己加。

## 驗收條件

- [ ] 參考畫面有 spec §14.4 兩張表的每一個元件，以及 spec §14.5 的每一種提醒
- [ ] 參考畫面只呼叫 `state/` 的方法，沒有直接呼叫 API（AGENTS.md §5.3）
- [ ] `/proto/host` 只在 `SHOW_PROTOTYPES=true` 時出現
- [ ] 交接說明照範本寫完，有截圖、設計稿 v1 與 v2 的連結、流程圖
- [ ] `flutter analyze`、`flutter test` 通過；後端三項檢查通過
- [ ] 立倫試聽後，固定台詞與提醒的字句已定稿
- [ ] 手動檢查的結果記在 Comments
- [ ] 01 到 09 都是 `resolved`；spec 11 組情境表格的 140 行都有對應的測試（AGENTS.md §7.4）
- [ ] PR 說明草稿存在 `docs/mr_info/feature-host.md`（AGENTS.md §9），情境表格之外 500 個中文字以內
- [ ] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`
