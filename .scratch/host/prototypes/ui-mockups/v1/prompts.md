# imagegen 提示詞與輸入對照

四次呼叫都使用內建 `image_gen`，用途為 `ui-mockup`，背景設定為 `transparent_background: false`。三張圖的文字與版面來自[介面摘要](ui-brief.md)。

## 01　開主持前

輸入圖片：無。採用初稿，成品為 [01-setup.png](01-setup.png)。

```text
Use case: ui-mockup
Asset type: One high-fidelity mobile UI reference artboard, first screen of a Taiwanese tabletop voice host. Flat portrait PNG, exactly 1024 × 1536 px (2:3). Screen fills canvas, head-on, crisp text typesetting. A single page, no phone frame, camera view, status bar, browser bar, navigation bar or watermark.
Style: Scandinavian white-oak café warmth expressed through a matte flat ivory #FAF7F2 canvas. White #FFFFFF cards, warm fine #EAE3DA outlines, dark espresso text #27221E, muted #6B635B, burnt orange #D9531E primary, coral-orange #EA580C selection outline and pale peach #FBEAE2 selected fill. Consistent 16 logical px card corners and 12px button corners. Airy but economical spacing, one common left edge, modern Noto Sans TC for Chinese. Strong hierarchy and evenly sized touch controls, at least 48 logical px high.
Composition and exact screen copy, top to bottom. Only the text inside quotes goes on the image, no quote marks:
• In a slim neutral artboard strip above and outside the UI, center the small note "參考設計稿 · 非定案" with a middle dot.
• Header: a simple back arrow on the left. Title "語音主持" and directly beneath, smaller "血與刃的白薔薇".
• First white card: heading "人數". Center a large "7 人" flanked by a circular minus icon and a circular plus icon. Under the count place "5 到 10 人".
• Second white card: heading "接話方式". Two equal-width options in a row: selected "自動接話" on the left in pale peach with orange border, unselected "按住說話" on the right in white. Under the options: "主持中也可以切換".
• Third white card: heading "聲線". Two equal-width options: selected "男聲", unselected "女聲". Under them: "開始後這場主持不能換".
• One full-width filled burnt-orange primary button at the bottom: "開始主持".
Typeset the 15 quoted strings exactly once each in precise Traditional Chinese, Taiwan orthography. Preserve the spaces around numbers, glyphs and the middle dot. No English, numerals or punctuation outside the specified strings, except the requested minus/plus and back icons. No invented titles, captions, features, decorations or game imagery. No brands, logos, cards, box art, real people, avatars, scores, timers, countdown, player data, outcomes, rules text, chat, history, settings gear, language menu, gradients, neon or glass effects.
```

## 02　主持中，初稿

輸入圖片：Image 1 為[第一張成品](01-setup.png)，提供標題列、色彩、字體與元件樣式。

```text
Use case: ui-mockup
Asset type: One high-fidelity 1024 × 1536 px portrait PNG, full-bleed flat mobile UI, second state of the same Taiwanese tabletop voice host as Image 1.
Input images: Image 1 is the finished setup screen. Use it strictly as style reference. Match its canvas size, tiny centered artboard note, header placement, icon stroke, card outlines, Noto Sans TC letterforms and touch-control geometry. Replace its settings and bottom button with the content below.
Visual direction: Modern white-oak Nordic café warmth, ivory #FAF7F2 ground, white cards with fine #EAE3DA strokes, #27221E primary type and #6B635B supporting text. Burnt orange #D9531E for the main action. Muted sage #486458, light sage #E6EEE9, soft amber #FDF1DC with #8A4B08 and quiet beige #F1ECE4. Flat fills, clean purposeful spacing, button corners 12 and card corners 16 logical px. No effects or ornamental drawings.
Exact visible copy and layout in reading order. Print only the strings in quotes, with no quotation marks or numbering.
• Above the interface, note "參考設計稿 · 非定案". Header left: back arrow with heading "語音主持", subheading "血與刃的白薔薇". Header right: small light sage mode badge "自動接話", followed by plain text action "切換".
• One progress card with large heading "第 2 回合". Below, a horizontal three-stop stepper with aligned, legible labels under plain unnumbered markers. The left completed stop uses a sage check and has the single label "傳金幣、放水晶" on one line. The center active stop uses a distinct orange outlined target with solid center, label "決定出牌". The last stop is an empty neutral ring, label "翻牌結算". No step numbers or status labels.
• Center a modest abstract circular host pictogram containing a few short waveform strokes. Directly beneath it print "正在查規則".
• White card heading "可以這樣說". Show exactly eight small quiet neutral beige pills of plain text, natural width, two tidy rows, easy to read. These are passive examples. Read left to right: first row "等一下", "暫停", "繼續", "下一步"; second row "上一步", "結束了", "白薔薇贏了", "血刃贏了". Make the longer phrases wide enough. No extra characters or icons in the pills.
• At the bottom, three large easy-to-reach equally wide controls in one row. Left outlined "上一步", middle outlined "暫停", right solid burnt-orange "下一步". Below, center the quiet text button "結束主持".
Typeset every specified label, including the correct repeated words in the bottom row, in clear standard Traditional Chinese (Taiwan), no simplified characters. Pay attention to 薔薇、贏、幣、則. Preserve all spaces and punctuation. Include no other copy, Roman letters, numbers, action, player or game data, results, scores, timers, cards, box art, logo, transcript, chat input, settings or navigation. No phone frame, status bar, URL bar, perspective, gradients, neon or glass.
```

## 02　調整指令標籤，最終採用

輸入圖片：Image 1 為上一節的第二張初稿（生成檔 `exec-93533126-86e4-4ad9-b720-f1401c56d53d.png`），Image 2 為[第一張成品](01-setup.png)。初稿的八個指令標籤接近按鈕大小。這次縮小底色範圍，依文字寬度排列，保留底部三顆操作鍵。成品為 [02-hosting.png](02-hosting.png)。

```text
Use case: ui-mockup
Input images: Image 1 is the edit target, the active hosting screen. Image 2 is the finished setup screen, for the shared header and style only.
Primary request: Fine-tune only the eight passive example labels inside the "可以這樣說" card of Image 1. They currently resemble large clickable rectangular keys. Typeset the eight exact phrases as much smaller, content-width, fully round capsule tags with soft beige #F1ECE4 backgrounds, no outlines, no icons, no shadow, reduced horizontal and vertical padding. Left-align tags in two naturally spaced rows, with open white space remaining at the right edge, like a small reference legend. Keep the text legible. Row one: "等一下" "暫停" "繼續" "下一步". Row two: "上一步" "結束了" "白薔薇贏了" "血刃贏了". Preserve each exact Taiwan Traditional Chinese phrase.
Invariants: Keep every other element and every other glyph, location, font, size, colors, game title, small artboard note, progress graphic, waveform, bottom three real action buttons and end action exactly as in Image 1. Keep 1024 × 1536 portrait. Do not add, drop, relabel or reorder anything. No new icons or words.
```

## 03　按住說話，主持暫停中

輸入圖片：Image 1 為[第一張成品](01-setup.png)，提供共同風格。Image 2 為[第二張成品](02-hosting.png)，提供進度卡片與底部操作區的位置。採用初稿，成品為 [03-paused-push-to-talk.png](03-paused-push-to-talk.png)。

```text
Use case: ui-mockup
Asset type: One high-fidelity 1024 × 1536 px portrait mobile UI artboard, the paused push-to-talk state of the Taiwanese tabletop voice host.
Input images: Image 1 (setup screen) is the master visual style reference. Image 2 (hosting screen) is the layout reference for the shared header, the progress card, and bottom controls. Re-create the very same app. Keep header typography, colors, card shape and alignment close to both images. Content is only the paused state specified below.
Exact content and placement in reading order, no printed quote marks:
• Outside and above the interface, keep the exact small centered note "參考設計稿 · 非定案". Header left back arrow, heading "語音主持" with "血與刃的白薔薇" immediately below. On the right small pale-sage mode badge "按住說話" and text button "切換".
• Immediately beneath header: ONE noticeable pale amber #FDF1DC banner. Its bold main phrase is "主持暫停中" with smaller helper text "暫停中也可以問規則" in the SAME banner. Warm dark amber text #8A4B08. Neither line is a button.
• Next show Image 2's progress card: "第 2 回合", with THREE horizontal unnumbered stops. A completed sage check above "傳金幣、放水晶", an orange current marker above "決定出牌", an empty neutral marker above "翻牌結算". Preserve these captions, positions within the card and unbroken wording exactly as Image 2.
• Main center: ONE very large circular press-to-talk button filled with burnt orange #D9531E, a simple high-contrast white microphone icon inside, and the single caption "按住說話" centered BELOW the circle. Leave room on all sides. No waveform, no lookup status.
• Under that: one compact collapsed white disclosure row with only "可以這樣說" at left and a downward chevron at right. Hide all the phrase tags in this state.
• Bottom exactly like Image 2 in geometry: three equally sized broad real buttons. Left outlined "上一步", MIDDLE SOLID BURNT ORANGE with white "繼續", right white outlined "下一步". Then the low-emphasis plain text action "結束主持" centered below them.
Every quoted string is required exactly as written in clear Taiwan Traditional Chinese, including the proper repeated phrase in the top badge and under the microphone. No numbers or text outside those strings. Use Noto Sans TC style. Warm ivory #FAF7F2 page, white cards, fine #EAE3DA borders, #27221E main type, #6B635B supporting text. Generous tap targets, card corners 16 and button corners 12 logical px. No new actions, brands, logos, avatars, player data, timers, chat, transcription, rules excerpts, card or box art, bottom navigation, device framing, perspective, gradients, neon or glass.
```
