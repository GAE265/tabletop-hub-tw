# imagegen 提示詞與輸入對照

四張圖皆使用內建 `image_gen`。每次呼叫都使用 `ui-mockup`，背景設為不透明（`transparent_background: false`）。以下保留送出時的提示詞全文。

## 01　手機開主持前

從文字生成，沒有輸入圖片。初稿採用為 [01-setup.png](01-setup.png)，重試 0 次。

```text
Use case: ui-mockup
Create one finely typeset high-fidelity flat mobile web UI design proof, 1024 × 1536 portrait 2:3. Edge-to-edge canvas, absolutely straight-on. Taiwan Traditional Chinese. This is a shared-table voice host for a nocturnal mystery game. Develop a restrained dark editorial design: matte deep ink navy (#141923), flat surfaces, warm ivory high-contrast type, a muted light apricot (#efb58e) primary fill with very dark text, fine slate dividers. Confident contemporary Taiwanese sans-serif with accurate Noto Sans TC glyphs and a distinct hierarchy. Generous side margins and large reachable controls. No visual noise, no ornamental badges. Enough contrast for the small notes too. This is the setup view, before hosting.
Copy exact strings below using correct printed Traditional Chinese glyphs, including 薔薇 and the spaces around ·. Never print the instructions, numbering or quotation marks. Only this content:
• In a slim separate proof caption band ABOVE the interface: "參考設計稿 · 非定案".
• Header inside interface: back arrow icon, title "語音主持", smaller subtitle "血與刃的白薔薇".
• First block: "人數". A large "7 人" between a minus icon button and a plus icon button. Helper text "5 到 10 人".
• Second block: "接話方式"; two wide side-by-side choices "自動接話" selected, "按住說話" unselected. Helper text "主持中也可以切換".
• Third block: "聲線"; two choices "男聲" selected, "女聲" unselected. Helper text "開始後這場主持不能換".
• Bottom primary button, wide, solid light apricot and dark text: "開始主持".
Use the same visual treatment for both selected options, e.g. an apricot outline and a small filled radio. Fine dividers and negative space separate blocks. Keep headings, helpers and controls aligned. All listed strings appear exactly once. No other text or controls. No content beyond this one screen. No status bars, device bezel, browser chrome, nav bars, player portraits, characters, cards, game art, logos, timer, avatars, chat, illustrations, neon, gradients or casino motifs.
```

## 02　手機主持中，初次生成

輸入圖片 1 為[第 1 張成品](01-setup.png)，提供字體、底色、標題與按鍵樣式。初稿的八句提示帶有外框，容易被看成按鍵，「切換」也離模式名稱較遠。

```text
Use case: ui-mockup
Image 1 is the accepted design reference for typography, colors, header, divider details and buttons ONLY. Generate a NEW screen in the same set, keeping the native dark navy and cream/apricot visual system but replacing all setup fields with the active host interface below. Portrait mobile, edge-to-edge, 1024 × 1536. No device or browser. Polished flat layout. Simplify lines and use empty space for calmness. Keep all type crisp and high-contrast, including inactive steps.
Copy deck in top-to-bottom order. Every quoted string prints verbatim in Taiwan Traditional Chinese, without quote marks. Do not print instructions, add numbering, or abbreviate.
1. Separate slim proof caption strip above interface: "參考設計稿 · 非定案".
2. Header: back arrow; "語音主持" over "血與刃的白薔薇". Beneath header, a small mode label "自動接話" beside a distinct text control "切換".
3. Large round title "第 2 回合". Three phase names in order as a connected vertical progression: small check mark beside "傳金幣、放水晶" for completed; filled apricot marker and large bold warm ivory "決定出牌" for current; outlined circle and secondary light gray text "翻牌結算" for upcoming. No other step text or numbers.
4. A restrained, distinct little horizontal acoustic waveform made of vertical apricot/ivory bars in a single cluster, and the single readable status "正在查規則". No microphone button or avatar.
5. "可以這樣說" above eight passive speech suggestions, lightweight typographic tags, flat and visibly unlike the large action buttons. Arrange in TWO ROWS with four labels per row, sufficient horizontal space, no outer heavy box, no quote marks or commas. First row, from left to right: "等一下" / "暫停" / "繼續" / "下一步". Second row: "上一步" / "結束了" / "白薔薇贏了" / "血刃贏了". Printed slash separators not needed. Use exact detailed characters for 薔、薇、贏、刃.
6. Large bottom action controls in exactly one row: outlined "上一步", outlined "暫停", solid light apricot primary "下一步". Beneath this, one quiet yet legible text action "結束主持". Leave safe margin below it.
Only these elements. The three strings 暫停, 下一步, 上一步 each appear twice: once in the hint area and once on a button. All other strings occur once. No extra copy, steps, headings, characters, cards, scenery, logos, analog dials, transcript, scores, records, navigation or timer.
```

## 02　區分語音提示與操作鍵，最終採用

輸入圖片 1 為[第 1 張成品](01-setup.png)，輸入圖片 2 是本機第 2 張初稿 `~/.codex/generated_images/01a1fe96-c00a-77a0-846b-2c6b0f9e6f43/exec-e336370a-fbca-4786-bcf5-15751aaa3e6b.png`。重試 1 次，移除八句提示的外框，並把「切換」移到模式名稱旁。採用為 [02-hosting.png](02-hosting.png)。

```text
Use case: ui-mockup
Image 1 is style reference only (mobile setup). Image 2 is the exact edit target (mobile active host). Retain portrait 1024 × 1536 and all the printed Traditional Chinese text exactly, in the current order. Keep all visual elements of image 2 except for these refinements to the distinction between labels and controls.
• Eight passive suggestions below 可以這樣說: remove the capsule shapes/outlines completely. Typeset the eight phrases as two orderly, evenly spaced rows of PLAIN text with a narrow aligned left dash or tiny typographic marker if necessary. No individual background, outline, pill or box behind these eight phrases. Make them look like a printed reference list. The bottom row of three large action buttons must KEEP its current strong button styling; only the command suggestions above them need this change.
• In the mode row, bring the unboxed, underlined apricot text action 切換 immediately beside the compact 自動接話 mode label, leaving the rest of the row quiet. Only once each.
Keep precisely these strings in their established regions: separate caption 參考設計稿 · 非定案; back arrow, 語音主持, 血與刃的白薔薇; mode 自動接話, 切換; 第 2 回合; 傳金幣、放水晶, 決定出牌, 翻牌結算; waveform and 正在查規則; 可以這樣說; passive row one 等一下 / 暫停 / 繼續 / 下一步 and row two 上一步 / 結束了 / 白薔薇贏了 / 血刃贏了; bottom action row 上一步 / 暫停 / 下一步 then 結束主持. Slashes and semicolons here separate instructions; never print them. No new text or controls. Keep the same step markers, primary button, colors, type and margins.
```

## 03　手機暫停中，按住說話

輸入圖片 1 為[第 1 張成品](01-setup.png)，供配色、字體與按鍵樣式參考。輸入圖片 2 為[第 2 張成品](02-hosting.png)，供回合、階段與底部按鍵的位置參考。初稿採用為 [03-paused-push-to-talk.png](03-paused-push-to-talk.png)，重試 0 次。

```text
Use case: ui-mockup
Generate the paused push-to-talk view of a shared-table Taiwan Traditional Chinese voice host. Image 1 is the main style reference (setup). Image 2 is a reference for the same host's round, stage, header and operations layout. Create one finished flat, front-on portrait 1024 × 1536 mobile screen, filling the artboard. Match matte ink navy, warm ivory type, fine hairlines, apricot main controls, generous margins, same type family. Exact typeset Traditional Chinese. No device frame, status bar or browser.
The entire screen must be visible from caption to bottom. Fit a compact header, mode row, pause notice, progress, microphone, collapsed hints, and bottom actions, in that order. Preserve ONLY these strings and elements. No text beyond the quoted strings. Omit quotes:
• Small distinct caption strip above UI: "參考設計稿 · 非定案".
• Header: back arrow, title "語音主持", beneath it smaller "血與刃的白薔薇". Mode label "按住說話" with nearby unboxed underlined text action "切換".
• One prominent wide static pause banner in muted dark plum/russet with bright ivory text, large "主持暫停中" and its smaller helper in the SAME band "暫停中也可以問規則". Clean visual contrast, no other words.
• Large round "第 2 回合". Three vertically linked stage labels: first "傳金幣、放水晶" with small checked circle, second "決定出牌" highlighted in bold and solid apricot marker, third "翻牌結算" with open circle and readable light gray text. No numbers or completion text beside the steps.
• In the middle-lower screen one LARGE CIRCULAR push-to-talk button with a simple microphone pictogram in its center, the single caption "按住說話" directly beneath or inside the button. Keep it very distinct from the banner. This screen has no voice waveform and no rule lookup in progress.
• One collapsed full-width row with ONLY "可以這樣說" and a downward chevron. No visible hints, hint list, or hint chips.
• Three LARGE bottom buttons in a single row in order: outlined "上一步", solid light apricot primary "繼續" with dark text, outlined "下一步". Quiet standalone action "結束主持" below them. Keep space after it.
All text occurs once, except 按住說話 appears twice, once in the mode line and once at the microphone button. Do not reproduce active mode or setup fields from the refs. No other features, screens, characters, portraits, game art, playing cards, logos, timers, chat, transcript, sidebars or navigation.
```

## 04　筆電主持中

輸入圖片 1 為[第 1 張成品](01-setup.png)，供配色與字體參考。輸入圖片 2 為[第 2 張成品](02-hosting.png)，提供同一狀態的元件與文字。初稿採用為 [04-hosting-laptop.png](04-hosting-laptop.png)，重試 0 次。

```text
Use case: ui-mockup
Make a WIDE LANDSCAPE 3:2 artboard, 1536 px wide × 1024 px tall, for the actual full-width laptop web page used in a tabletop demo. Flat UI screenshot-shaped design proof. No actual computer hardware, no monitor frame or browser chrome. Image 1 supplies the approved dark ink-navy/ivory/apricot style, centered header, typography, borders and button corners. Image 2 supplies the EXACT CONTENT of this active host state. Responsively recompose it for a landscape viewport. Use the whole width as ONE page. It must not be a portrait panel in a wide frame, nor two screens, nor a dashboard with navigation.
Top: the same separate slim proof strip spanning the width with "參考設計稿 · 非定案". Below, one header with back arrow at far left, centered title "語音主持", smaller subtitle "血與刃的白薔薇". The mode label "自動接話" and immediately adjacent underlined apricot text button "切換" go together in the top right of the header.
Main content in two balanced editorial columns separated by generous space or a fine vertical rule, no cards around them. Left half: very large "第 2 回合". Directly under it, the same connected vertical stage list: a small checked circle at "傳金幣、放水晶", an apricot dot and largest bold type on the CURRENT stage "決定出牌", an open circle at the upcoming "翻牌結算" in legible soft-gray type. Below list, center a small cluster of apricot sound-wave bars and the status "正在查規則".
Right half: generous heading "可以這樣說", then eight passive typographic labels arranged in a clean two-column list of four rows. Row one "等一下" and "暫停"; row two "繼續" and "下一步"; row three "上一步" and "結束了"; row four "白薔薇贏了" and "血刃贏了". Tiny bullet dashes only, no borders, no pill treatment on the suggestions. Below them place three tall, comfortable buttons in one horizontal row: outlined "上一步", outlined "暫停", filled light apricot with dark text "下一步". Center the quiet action "結束主持" below the buttons. Comfortable edges and bottom margin, all contents visible.
Never add headings, column labels, step numbers, chat, transcript, timer, side menu, navigation bar, logos, game art, players or decorations. No setup fields. Accurate Traditional Chinese as in Image 2, each quoted phrase once except 上一步, 暫停 and 下一步 each twice. Exact characters, no quote marks, no paraphrases. Preserve contrast and visual hierarchy even in the small type.
```
