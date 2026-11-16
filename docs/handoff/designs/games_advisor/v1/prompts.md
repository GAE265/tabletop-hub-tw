# imagegen 提示詞與輸入對照

使用內建 `image_gen`，`transparent_background: false`。原截圖是內容與功能參考，第一張生成稿提供後續視覺參考；所有提示屬於參考設計探索。

## 01 · 開始新對話

輸入：`docs/handoff/images/games_advisor/empty.png`

```text
Use case: ui-mockup (restyle the provided working screenshot into a new design-reference artboard).
Asset type: ONE polished raster UI design reference for a Taiwanese board-game web platform, "遊任有娛", feature "桌遊推薦". This is a discussion draft for designer 永傑, NOT an approved brand system or an implemented page.
Artboard: portrait 4:5, approximately 1280 × 1600 pixels, high resolution, front-on flat UI, full-screen interface with a slim neutral artboard label above it. No device mockup, no perspective or browser address bar.
Brand/style direction: a warm, approachable, calm gathering around a board-game table. Retain the project's existing forest-teal seed #2E7D6B as the main interactive color; off-white/ivory main canvas, pale mint containers, deep green-black text, subtle thin neutral borders, very soft restrained shadows, generous intentional spacing, elegant modern Traditional Chinese sans-serif similar to Noto Sans TC. Teal-filled primary controls, coherent 14–18px corner radii, clear readable type hierarchy. Board-game charm only through sparse small abstract dice/meeple/board-tile forms in the welcome illustration; no illustration on populated conversation screens. Maintain a mature useful community-tool feeling.
Shared chrome: header with plain text brand "遊任有娛", secondary section label "桌遊推薦", right-aligned "開始新對話" button, single centered conversation column around 760px wide in the logical layout. Add a slim artboard label "參考設計稿 · 方向探索" above the UI, not as an interactive product element.
Functional invariants: this remains conversational recommendations, not a shop or a dashboard. Preserve screenshot message content and order; improve hierarchy, spacing and layout only. At bottom, keep a clearly separated persistent composer, rounded multiline input, send icon/button, exact 500-character counter, help "Enter 送出 · Shift+Enter 換行" and a quiet disabled link "想問規則或玩法？到規則問答". Keep the composer within the screen and do not cover cards.
Constraints: remove only the development/test-account strip, DEBUG ribbon, and prototype wording from the screenshots. Do not add game-cover images, because image data is not part of this feature. No navigation sidebar, history, filters, preference chips not already present, login, purchase/booking buttons, star ratings, favorites, fabricated user accounts, sources/URLs or invented testimonials. No casino/poker imagery, neon gaming aesthetic, heavy gradients, glassmorphism or formal new logo. All interface labels in accurate Traditional Chinese (Taiwan). English only for actual English review excerpts. All important controls and text legible with strong contrast.

Input images: Image 1 is the working empty-state screenshot, a functional/content reference and restyle target, not a final visual-style reference.
Primary request: create artboard 01, "開始新對話", the welcome state with NO conversation bubbles and NO game recommendations yet.
Composition: compact header, then balanced large welcome whitespace. In the main center place a tasteful small soft matte illustration of a die, two meeples and a few abstract board tiles in the existing teal/ivory family. It is a generic tabletop decoration, not a game cover or mascot. Under it a prominent heading "我幫你挑桌遊。" and supporting text "告訴我幾個人、想玩多久、喜歡什麼感覺。" Then exactly THREE text-only outlined rounded example buttons in a considered clean stack, all equal width and easily clickable:
"我們 4 個人，想輕鬆聊天"
"2 個人約會玩"
"6 個人，30 分鐘內玩完"
Keep all three verbatim, without added tags or extra options.
Empty-state "開始新對話" and the send button are disabled with clearly recognizable subdued styling. Composer placeholder verbatim: "例如：我們 4 個人，想玩 1 小時內、輕鬆聊天的". Counter "0 / 500 字". The welcome content should look welcoming and refined, not sparse default Material prototype UI. Do not add a second redundant chat title above the welcome heading.
```

## 02 · 對話追問

輸入：Image 1：`docs/handoff/images/games_advisor/follow-up.png`；Image 2：第一張生成稿（成品 `01-start.png`）

```text
Use case: ui-mockup (restyle the provided working screenshot into a new design-reference artboard).
Asset type: ONE polished raster UI design reference for a Taiwanese board-game web platform, "遊任有娛", feature "桌遊推薦". This is a discussion draft for designer 永傑, NOT an approved brand system or an implemented page.
Artboard: portrait 4:5, approximately 1280 × 1600 pixels, high resolution, front-on flat UI, full-screen interface with a slim neutral artboard label above it. No device mockup, no perspective or browser address bar.
Brand/style direction: a warm, approachable, calm gathering around a board-game table. Retain the project's existing forest-teal seed #2E7D6B as the main interactive color; off-white/ivory main canvas, pale mint containers, deep green-black text, subtle thin neutral borders, very soft restrained shadows, generous intentional spacing, elegant modern Traditional Chinese sans-serif similar to Noto Sans TC. Teal-filled primary controls, coherent 14–18px corner radii, clear readable type hierarchy. Board-game charm only through sparse small abstract dice/meeple/board-tile forms in the welcome illustration; no illustration on populated conversation screens. Maintain a mature useful community-tool feeling.
Shared chrome: header with plain text brand "遊任有娛", secondary section label "桌遊推薦", right-aligned "開始新對話" button, single centered conversation column around 760px wide in the logical layout. Add a slim artboard label "參考設計稿 · 方向探索" above the UI, not as an interactive product element.
Functional invariants: this remains conversational recommendations, not a shop or a dashboard. Preserve screenshot message content and order; improve hierarchy, spacing and layout only. At bottom, keep a clearly separated persistent composer, rounded multiline input, send icon/button, exact 500-character counter, help "Enter 送出 · Shift+Enter 換行" and a quiet disabled link "想問規則或玩法？到規則問答". Keep the composer within the screen and do not cover cards.
Constraints: remove only the development/test-account strip, DEBUG ribbon, and prototype wording from the screenshots. Do not add game-cover images, because image data is not part of this feature. No navigation sidebar, history, filters, preference chips not already present, login, purchase/booking buttons, star ratings, favorites, fabricated user accounts, sources/URLs or invented testimonials. No casino/poker imagery, neon gaming aesthetic, heavy gradients, glassmorphism or formal new logo. All interface labels in accurate Traditional Chinese (Taiwan). English only for actual English review excerpts. All important controls and text legible with strong contrast.

Input images: Image 1 is the functional follow-up screenshot and restyle target. Image 2 is the generated welcome-state reference: match its header dimensions, exact brand lettering, teal/ivory/mint colors, typeface, composer, controls, gentle material treatment and portrait artboard size closely, so both images belong to ONE interface.
Primary request: artboard 02, "對話追問". Build the populated conversational state from Image 1 in the same design as Image 2. Keep the background free of decorative illustrations now, leaving calm whitespace beneath the short exchange. Do not show welcome example buttons.
Conversation: right-aligned player bubble in forest teal with readable white text, followed by a left-aligned pale-mint assistant message with a small abstract generic board-game icon. Render these exact lines in Traditional Chinese:
Player: "我們 4 個人，想輕鬆聊天"
Assistant:
"4 人，想要輕鬆聊天的氛圍。你比較偏好哪一種？"
"1. 派對歡樂、容易大笑"
"2. 需要互相描述與猜測，邊玩邊聊天"
"3. 溫馨療癒、節奏輕鬆"
"也可以直接回「都可以」。"
The numbered preferences must remain ordinary text inside ONE assistant message, not interactive buttons, chips or form controls. No game cards yet.
"開始新對話" is now enabled: light mint button, dark readable text, consistent with welcome screen's header position.
Bottom composer matches Image 2 exactly; empty input and disabled send control. Placeholder: "例如：我們 4 個人，想玩 1 小時內、輕鬆聊天的". Counter "0 / 500 字". Help "Enter 送出 · Shift+Enter 換行"; disabled quiet link "想問規則或玩法？到規則問答".
```

## 03 · 推薦結果與心得，初次生成

輸入：Image 1：`docs/handoff/images/games_advisor/cards-expanded.png`；Image 2：第一張生成稿（成品 `01-start.png`）

```text
Use case: ui-mockup (restyle the provided working screenshot into a new design-reference artboard).
Asset type: ONE polished raster UI design reference for a Taiwanese board-game web platform, "遊任有娛", feature "桌遊推薦". This is a discussion draft for designer 永傑, NOT an approved brand system or an implemented page.
Artboard: portrait 4:5, approximately 1280 × 1600 pixels, high resolution, front-on flat UI, full-screen interface with a slim neutral artboard label above it. No device mockup, no perspective or browser address bar.
Brand/style direction: a warm, approachable, calm gathering around a board-game table. Retain the project's existing forest-teal seed #2E7D6B as the main interactive color; off-white/ivory main canvas, pale mint containers, deep green-black text, subtle thin neutral borders, very soft restrained shadows, generous intentional spacing, elegant modern Traditional Chinese sans-serif similar to Noto Sans TC. Teal-filled primary controls, coherent 14–18px corner radii, clear readable type hierarchy. Board-game charm only through sparse small abstract dice/meeple/board-tile forms in the welcome illustration; no illustration on populated conversation screens. Maintain a mature useful community-tool feeling.
Shared chrome: header with plain text brand "遊任有娛", secondary section label "桌遊推薦", right-aligned "開始新對話" button, single centered conversation column around 760px wide in the logical layout. Add a slim artboard label "參考設計稿 · 方向探索" above the UI, not as an interactive product element.
Functional invariants: this remains conversational recommendations, not a shop or a dashboard. Preserve screenshot message content and order; improve hierarchy, spacing and layout only. At bottom, keep a clearly separated persistent composer, rounded multiline input, send icon/button, exact 500-character counter, help "Enter 送出 · Shift+Enter 換行" and a quiet disabled link "想問規則或玩法？到規則問答". Keep the composer within the screen and do not cover cards.
Constraints: remove only the development/test-account strip, DEBUG ribbon, and prototype wording from the screenshots. Do not add game-cover images, because image data is not part of this feature. No navigation sidebar, history, filters, preference chips not already present, login, purchase/booking buttons, star ratings, favorites, fabricated user accounts, sources/URLs or invented testimonials. No casino/poker imagery, neon gaming aesthetic, heavy gradients, glassmorphism or formal new logo. All interface labels in accurate Traditional Chinese (Taiwan). English only for actual English review excerpts. All important controls and text legible with strong contrast.

Input images: Image 1 is the functional "recommendation cards with excerpts expanded" screenshot and restyle target. Image 2 is our generated welcome-state design reference. Match Image 2's artboard size, exact header and brand text, typography family, teal/ivory/mint palette, composer placement, corners and spacing; this is artboard 03 in the SAME design system.
Primary request: artboard 03, "推薦結果與心得". Show the conversation at a later SCROLL POSITION: the earlier welcome and preference-question exchange has scrolled above the viewport. At the top of the conversation area show the latest right-aligned player bubble "都可以", then the small assistant icon and exact reply "以下幾款都適合 4 人一起輕鬆同樂、邊玩邊聊天。". Below, a readable vertical stack of recommendation cards.
Card 1 expanded, exact title "魔法風雲會", metadata "2–6 人 · 20 分鐘 · 13 歲以上 · 難度 3.3 / 5". Strong title, compact quiet metadata, then reason:
"心得提到可以在朋友家或酒吧輕鬆遊玩，適合想隨意聊天、不追求正式競賽的場合。整體也被形容為好玩、適合在餐桌上同樂。"
Then an accordion row "心得片段（2）" with an UP chevron showing it is OPEN. Within a subtly lighter inset panel, show two excerpt paragraphs, each with a small quiet "英文" language label. Retain all the exact English text below with comfortable line height; smaller type than the Chinese main reason but still legible:
"I used to play at friends houses or at the pub casually playing 5 corners or attack left. These were a good way to play really weird or silly decks. One issue here is multiplayer games are usually slower so you end up using decks too slow for a 1 on 1 game. Not a good time to test, but good fun none the less."
"It's a card game I can warmly recommend—for yourself, as a gift, or to coax that lethargic teenager out from behind the monitor for an old-school round at the kitchen table."
Card 2 below, accordion COLLAPSED, exact title "動物疊疊樂", metadata "2–4 人 · 15 分鐘 · 4 歲以上 · 難度 1.0 / 5", reason "命中派對聚會，心得形容非常適合派對，疊出奇妙造型時常會引發驚呼與笑聲，氣氛歡樂輕鬆。", accordion row "心得片段（2）" with DOWN chevron. If needed, show only the upper part of card 2 at the scroll-viewport boundary; the list continues by scrolling. Do NOT compress the first card into tiny unreadable text to fit extra cards.
Use clear white/ivory cards with fine mint border and soft spacing; excerpt panel pale mint, title deep forest. No game box images or star ratings. No source links. No extra card actions. Do not rewrite either game's actual data. "開始新對話" enabled in header.
Keep bottom persistent composer identical to Image 2. It is empty with disabled send, "0 / 500 字", "Enter 送出 · Shift+Enter 換行", and disabled "想問規則或玩法？到規則問答". Do not let the composer obscure any text: end the scrollable card region cleanly above it.
```

## 03 · 一致性修正，最終採用

輸入：Image 1：上一節產生的推薦頁初稿；Image 2：第二張生成稿（成品 `02-follow-up.png`）。僅統一玩家泡泡與 Agent 圖示，最終成品為 `03-recommendations.png`。

```text
Use case: precise-object-edit / ui-mockup.
Asset type: small consistency correction to reference UI artboard 03 for "遊任有娛" tabletop recommendations.
Input images: Image 1 is the edit target, the recommendation results artboard. Image 2 is the style reference, the conversational follow-up artboard from the same set.
Change ONLY these two UI details in Image 1 to match Image 2:
1. The latest player "都可以" bubble: use the exact forest-teal filled rounded bubble with white text from Image 2; remove the small generic person icon outside that player bubble, because Image 2 has no such icon.
2. The assistant avatar to the left of its reply: replace the robot head with the small meeple-and-die line icon inside a pale-mint circular badge used in Image 2.
Critical invariants: keep Image 1's entire composition, header and brand lettering, slim "參考設計稿 · 方向探索" strip, every game title, all Chinese and English text, numbers, recommendation card order, excerpt accordion open/closed states, metadata, card geometry, composer and footer completely unchanged. Retain the exact 4:5 portrait size. Do not rewrite, remove, crop or add any card content. Do not import the follow-up question or alter the page state. This remains a raster discussion draft, not implementation.
```
