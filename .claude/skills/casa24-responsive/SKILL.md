---
name: casa24-responsive
description: Make Casa 24 Wordle work well on every screen — small/large phones, landscape, tablets, laptops, big desktops. NYT-style game layout (2-area header, capped centered board, keyboard under it, NYT proportions from one tile unit --t on tablets/desktops, left rail of 147×80 player cards that never moves the board; decided and refined 2026-10-29), layout rules (dvh, board sized from leftover height, square tiles, key sizes, modals that scroll, safe areas, focus ring), where each layout class lives (including the live view's rail/bottom-sheet breakpoints), measured sizes, what the 2026-10-26 fixes changed and what is still to do (WOFF2), the Discord Activity inside Discord (safe areas applied by the shell around the game iframe, PIP/grid shows the board only, fallback language picker, portrait lock), NYT Wordle's measured layout, performance (self-hosted Vue, compiled Tailwind, fonts, WebP, caching) and the sizes to test. Use for any mobile, desktop, responsive, layout, zoom, landscape, Activity layout, or page-speed question.
---

# Responsive layout (phones → desktop)

Research done on 2026-10-26 by measuring 9 screen sizes, reading the code, and reading NYT Wordle's live CSS/JS. **Reworked 2026-10-29 to NYT's structure with Casa 24's look** (plan and sources: `docs/plan-layout-es-en.md`; tests: `tests/test_layout.py`). Update "Current state" and "Still to do" when you fix things.

## NYT layout principles (owner, 2026-10-29)
- **One centered column** (~500px) for header actions, board and keyboard; nothing else competes on screen.
- **Header: brand left, icons right**, slim (48/52/60px).
- **Board sized from the leftover height**, square tiles, capped (350px desktop, 330px phones), so it never balloons on big screens.
- **Keyboard right under the board** on wide screens (at the bottom, for thumbs, on phones); keys up to ~58px tall, Enter/⌫ 1.5× wide.
- **NYT proportions from 481px wide (refined 2026-10-29, owner: "las dimensiones no son iguales, tiene que verse como New York Times"):** everything comes from one tile unit `--t` (max 62px): board 5t+20 wide, keys 0.66t × 0.87t, keyboard ≈1.41× the board, 0.38t between them. Details under "Where things live".
- **The social panel lives outside the column** (a fixed left rail of cards in the gutter), so it never steals width from or moves the board.
- Same `game.html` / `style.css` for the website and the Discord Activity; Discord only adds classes (`c24-embed`, `c24-plat-*`, `c24-pip`).

## Target layout (what "good" looks like)
Based on NYT Wordle, which was measured directly.
- **One centered column**, max about 500px wide, on every screen. The only side panel is the leaderboard game's live view rail (≥860px wide: web when taller than 500px, Discord desktop at any height; see below), which sits in the left gutter and never moves the column; otherwise empty space is fine.
- **Page height `100dvh`** (with a `100vh` fallback first), never plain `100vh` / `h-screen`. Otherwise mobile browser bars hide the bottom keyboard row. Use `dvh` only on the outer container, not on tiles.
- **Header → board → keyboard**, as a flex column. The board area is `flex:1; min-height:0`. The board is **sized from the leftover height**: `width = min(cap, area width, area height × 5/6)` (cap 350px desktop, 330px phones), with `aspect-ratio: 5/6`. Tiles use `aspect-ratio: 1`, so they are always square. Do it with CSS container queries (`container-type:size` + `cqw/cqh`), or a ResizeObserver like NYT.
- **Keys:**
  - `flex:1 1 0; min-width:0`, height `clamp(44px, 7dvh, 58px)`, gap 6px (4px under 360px).
  - Enter and Backspace are wider (`flex:1.5`).
  - Never narrower than 24px (WCAG 2.2 minimum). 44px is Apple's guideline, 48dp Material's.
- **Landscape phone** (`orientation:landscape and max-height:500px`): shrink or hide the header and use shorter keys. Optionally put the board and keyboard side by side. Orientation can't be locked in a browser.
- **Modals:**
  - `max-height: calc(100dvh - 32px); overflow:auto; overscroll-behavior:contain`, width `min(500px, 100% - 32px)`.
  - Close with Esc, and make the close button at least a 44px tap target.
  - On small phones, shrink the Kolo picture.
- **Viewport meta:** `width=device-width, initial-scale=1, viewport-fit=cover`. **No `user-scalable=no`**: let low-vision players pinch-zoom. Stop double-tap zoom on keys with `touch-action: manipulation`.
- **Safe areas:** `padding-bottom: max(8px, env(safe-area-inset-bottom))` on the keyboard, `env(safe-area-inset-top)` on the header, plus left and right insets in landscape. Inside the Discord Activity, Discord's own insets win (next section).
- **Touch vs mouse:** put hover styles inside `@media (hover:hover) and (pointer:fine)` so they don't stick on phones. Add `-webkit-tap-highlight-color`, `user-select:none` on keys, a `:focus-visible` outline on keys, and `overscroll-behavior:none` on html/body (no pull-to-refresh).
- **Physical keyboard:**
  - Lowercase `event.key`, so Shift and Caps Lock letters work; accented letters fold to the plain key (`normalizeKey`).
  - Ignore Ctrl/Meta/Alt and `isComposing`.
  - Blur the on-screen button after a click, so a physical Enter doesn't re-press the last tapped key.
- **theme-color:** light and dark meta tags (`media="(prefers-color-scheme: …)"`), plus `color-scheme: light dark`. Install settings belong in `site.webmanifest`; `apple-mobile-web-app-capable` is deprecated.

## Inside Discord (Activity)
Inside Discord the top page is the small **Activity shell** (`templates/activity.html`); the game page (`/lb/<lang>?embed=1`) runs in a full-size same-origin `<iframe>` inside it (`casa24-discord-activity`). Extra layout rules:
- **Safe areas are applied in the shell, not in the game.** Discord's mobile app sets `--discord-safe-area-inset-{top,bottom,left,right}` **only on the shell document**. `style.css` `:root` defines `--c24-safe-{top,right,bottom,left}` = `var(--discord-safe-area-inset-*, env(safe-area-inset-*))`; the shell's `.c24-shell-frame` is `position: fixed` inside those insets (shell background = game background `--c24-bg`). The game page inside gets `<html class="c24-embed">`, which sets every `--c24-safe-*` to **`0px`** so insets are never applied twice. On the web the same `--c24-safe-*` rules still apply normally; keep using them (not bare `env()`) in new layout CSS.
- **Layout modes:** focused (0, normal), **PIP** (1, small floating window) and **grid** (2, tile in a call grid). The shell subscribes once and passes the mode to the game (`postMessage {type:"c24-layout"}`); both documents get class `c24-pip` (and `data-layout-mode`) on `<html>`; `style.css` then hides header, keyboard, demo bar, live view, modals and toasts, so **PIP shows only the board** (tested at 240×180).
- **Fallback language picker** (`.c24-picker`, in the shell; only when Discord's language can't be read, 2 options since 2026-10-29): grid of 48px buttons that fits a 390×844 phone without scrolling; under 420px tall (landscape, PIP) no logo, auto-fill columns, 40px buttons, scrolls inside.
- **Orientation:** the Portal locks phones and tablets to **portrait** before the page loads; landscape rules still matter for the web and desktop.
- **Desktop Activity window** can be small and any shape (Discord publishes no fixed sizes): the dvh/container-query layout handles it; our own test set is PIP 240×180, 640×360, 875×400 and 400×700. The live rail shows from 860px wide (`:root.c24-embed:not(.c24-plat-mobile)`); Discord phones keep the facepile + bottom sheet.
- Accessibility: Tab and Escape must not be captured (Discord uses them).
- Test in real Discord: `docs/discord-activity-manual.md` (Paso 15).

## Where things live
All layout CSS is in the "LAYOUT" section of `webapp/static/style.css`; the class names are used in `game.html` / `index.html`.
- `--vh`: `1vh`, or `1dvh` where the browser has it. Write `calc(var(--vh) * N)`, not `vh`.
- `.c24-game`: the game page column (header, board, keyboard). `height: calc(var(--vh) * 100)`, max 500px wide, side safe areas.
- **Game header `.c24-header-bar` (2026-10-29): a 2-area flex bar.** Brand left (`.c24-header-title`: Kolo + "Casa 24" (`.c24-title-text`) + language badge; in the Activity the "Casa 24 ES ▾" language button `.c24-lang-btn`). Actions right (`.c24-header-end`), in order: people/facepile (`.c24-live-btn`, narrow screens), help `[data-help-open]`, trophy (`[data-lb-trophy]` link on the web / `[data-activity-board-open]` button in the Activity), stats `[data-stats-open]`, settings, then the Discord avatar slot. Height **52px**, **48px ≤480px**, **60px from 768px** (full width), plus the top safe area; 44px tap targets (40px wide under 360px). **Only the "Casa 24" text steps aside** when space is short: `/lb/` pages ≤480px, Activity ≤419px (shown again in Discord desktop ≥860px), guest game with leaderboard on ≤359px, plain guest ≤339px (the four `.c24-title-text` rules after `.c24-header-bar`). Kolo, badge and every button stay.
- Menu and `/leaderboard` headers still use `.c24-header` (3-column grid `1fr auto 1fr`). **Menu header when the leaderboard is on** (`.c24-header-side`): Discord avatar/icon (`dc.header_slot`), trophy link, then the info button (`.c24-hide-narrow`, hidden under 420px); `.c24-header-menu-lb` shortens the title to "Casa 24" under 480px (`.c24-title-extra` hidden). The avatar popover `.c24-dc-pop` has `max-width: calc(100vw - 16px)`; in the game bar it opens to the left (avatar at the right end).
- `.c24-board-area` (the `<main>`): takes the leftover height, `container-type: size`.
- `.c24-board` (`role="grid"`, rows `role="row"` with `board_row` labels): `--w: min(var(--cap), 100cqw - 20px, (100cqh - var(--bpad) - 5*gap) / 1.2 + 4*gap)`, `--cap` 350px (330px ≤480px), gap 5px. Phones (<481px portrait) and landscape phones use this and keep the keyboard at the bottom.
- **NYT unit `--t` (2026-10-29), from 481px wide** (`@media (min-width: 481px) and (min-height: 501px), (min-width: 481px) and (orientation: portrait)`; and always in Discord desktop, `:root.c24-embed:not(.c24-plat-mobile)`). Set on `.c24-game` ("NYT proportions" block in LAYOUT): `--t = min(62px, --t-h1, --t-h2, --t-w)`. Height-fit `--t-h1`/`--t-h2` = what fits under the header (`--hdr`: 48/52/60px, 40px in short landscape) minus bottom padding `--padb`; `--t-h2` is the form used when keys hit their 24px floor. Width-fit `--t-w` = a 10-key row fits the column minus 16px. Then: board `--w: 5t + 20px`, board area `6t + 25px` tall with `0.25t` above it (right under the header, not centered in a gap); keyboard `width: max-content` (as wide as its keys, ≈1.41× the board), centered, `0.38t` under the board, no padding, row gap `--krow` 8px (6px short landscape); key width `--kw: max(26px, 0.66t)`, height `--kh: max(24px, 0.87t)`, ⇨/⌫ `1.5 × --kw`; key fonts `max(12px, 0.3t)`, ⇨/⌫ `max(16px, 0.36t)`. Test: `test_nyt_proportions_on_tablets_and_desktops` (`tests/test_layout.py`). The board size is reserved before Vue mounts (no layout shift, `test_board_size_is_reserved_before_vue`). Tiles are square; their font follows the tile size (`main .grid-cols-5 > div`: 62% of a tile, at least 14px).
- `.c24-keyboard` (`role="group"`, `keyboard_label`; ⇨/⌫ labelled `key_enter`/`key_backspace`) with `style="--rows: N"` and one `.c24-key-row` per row, max 500px wide. **Phones and landscape phones** (from 481px the `--t` rules above win): key height `--kh` = **`max(26px, min(clamp(44px, 7dvh, 58px), --kfit))`**, where `--kfit` = the rows' share (`--kshare`, 33% of the height; 28% in short Discord panels). Gap `--kgap` 6px (4px under 360px). Keys `flex: 1 1 0`; ⇨ and ⌫ get `flex-grow: 1.5`. The 10-key Spanish rows still give ≥26px keys at 320px. Bottom padding `max(8px, safe area)`.
- **Focus ring** (keys, icon buttons, close): 3px Casa 24 orange outline + a 2px inner ring in the text color (`box-shadow`), so it shows on cream too. `test_accessibility_basics`, `test_focus_order_brand_actions_board_keyboard`.
- Landscape phones, `@media (orientation: landscape) and (max-height: 500px)`: 40px header on top, board left, keyboard right (CSS grid), max 900px wide.
- **Developer view** (internally "demo", `/demo/es|en`): `.c24-game.c24-demo` adds `.c24-demo-bar` (only ↻ Restart and ✓ Fill in word; wraps on narrow phones) between header and board. In landscape it gets its own grid row: `grid-template-rows: auto auto minmax(0, 1fr)`, bar in row 2 spanning both columns, board and keyboard in row 3. Styles are in the "demo mode" section at the end of `style.css` (not in LAYOUT), including the password page (`.c24-demo-login*`, input 16px so iOS doesn't zoom).
- Modals: `.c24-modal-wrap` (fixed, centered, safe areas) holds `.c24-modal` (`width: min(500px, 100% - 32px)`, `max-height: calc(100dvh - 32px - safe areas)`, scrolls inside). `.c24-modal-sm` is 420px. `.c24-close` is the 44px ×. Esc closes every modal.
- `.c24-kolo` (end-screen picture): at most `min(160px, 22dvh)` tall. `.c24-hero-kolo` (menu): 150px, 96px on screens under 700px tall.
- Start screen: `.c24-start`, `.c24-primary` holds **the two language cards** Español/English (`.c24-play`, one column on phones, 2 columns at ≥640px; the last played first); the dashed "🔒 Developer view" card `.c24-play-demo` comes last and spans the full row (only when `DEMO_PASSWORD` is set). Card name and status sit in one row with a 0.75rem gap: the status never wraps (`white-space: nowrap`), the name may wrap (`overflow-wrap: anywhere`).
- **Leaderboard** (styles in the "leaderboard" section of `style.css`, not in LAYOUT; details of the feature: `casa24-leaderboard`):
  - Menu: `.c24-dc-area` above the cards. Logged out: the full-width Discord button `.c24-dc-btn` (48px) + the small privacy link `.c24-dc-privacy-link` (44px tall). Logged in: the guest switch `.c24-guest-toggle` (44px row, 40×24 `.c24-switch`) + privacy link. Short on purpose (owner: less text), but it still makes the start screen taller, so recheck the phone height after changes (the < 2000px test runs with the leaderboard off).
  - Privacy: native `<dialog class="c24-privacy">`, `width: min(26rem, 100% - 32px)`, `max-height: calc(100dvh - 32px)`, Esc/backdrop/Close (44px) close it.
  - Toasts `.c24-dc-toast` (login failed/cancelled, data deleted): `position: fixed` at the bottom center, `width: min(26rem, 100% - 32px)`, above the safe area, gone after 6 s or on ×. They are **the one allowed exception to "nothing overlaps"**: they float over the page for a moment on purpose.
  - Game `/lb/<lang>` uses the normal game layout; only the end window differs (`.c24-lb-end`: `.c24-lb-stats` with two big VT323 numbers `.c24-lb-big` side by side, then the link). A guest es/en end window may show the hint `.c24-lb-hint` with a Discord button.
  - `/leaderboard` (`leaderboard.html`) is a **standalone page**: it loads `style.css` but **not Tailwind or Vue**, so the end of the leaderboard section has its own small reset (`.c24-lb-page` margins, buttons, links, `.uppercase`). Use `c24-*` classes there, not Tailwind classes. One column `.c24-lb`, max 40rem; it scrolls normally (`min-height` full screen, not fixed height).
  - Table `.c24-lb-table`: rank, player (long names cut with …), points always shown. **Wins** (`.c24-lb-opt1`) appear from **400px** wide, **streak and best streak** (`.c24-lb-opt2`) from **520px**, so a 320px phone never scrolls sideways.
  - Under the table: one compact centered line `.c24-dc-signed` (avatar + @username, wraps long names) or the Discord button `.c24-lb-login` (max 20rem), then the privacy link.
  - **Live view** on `/lb/<lang>` (styles: "live view" section of `style.css`; feature: `casa24-live-view`):
    - **≥860px wide and ≥501px tall** on the web (`@media (min-width: 860px) and (min-height: 501px)`), and **≥860px at any height in Discord desktop**: `<aside class="c24-live">` is a fixed **left rail of NYT cards** (refined 2026-10-29), one column `--c24-card-w` (147px) wide, **16px from the left, 10px under the header** (`--c24-rail-top`: 60px + 10px; in Discord 40px + 10px on panels ≤500px tall), bottom 8px; it scrolls inside when long (scrollbar hidden). The old `--c24-rail-w`/`--c24-rail-x` are gone. At 860px the rail ends at 163px and the column starts at 180px: the centered column **never shrinks or moves** (`test_rail_never_moves_or_shrinks_the_board`). Cards 147×80 (avatar + mini board only; look: `casa24-branding`); the "Jugando hoy" heading is visually hidden on the rail. Inside Discord the first card is "Invite friends" (same size). The people button, × and backdrop are hidden.
    - **Everywhere else** (phones, tablets, landscape phones, Discord phones): the header gets a **people button** `.c24-live-btn` (badge `.c24-live-badge`); when someone is playing it shows a **facepile** of 3 avatars (22px, −8px overlap; **2 under 400px**) and grows wider (`.has-faces`, min 44px); empty → the 44px people icon, and the list opens as a **bottom sheet** (`.c24-live.is-open`) with the **same 147×80 cards in a wrapping grid** (two side by side at 390px): `width: min(500px, 100%)`, `max-height: min(70% of height, 100% − 48px − top safe area)`, list scrolls inside, side and bottom safe areas, backdrop `.c24-live-backdrop`. Esc, ×, backdrop or the button close it.
    - Tested at 320×568, 390×844, 844×390, 768×1024, 860×600, 1024×768, 1366×768, 1920×1080 (`test_live_layout_fits_without_overlap`), in `tests/test_layout.py` and `tests/test_live_rail.py` (card sizes, rail position, sheet grid): no page scroll, no overlap.
  - **Tabs (3 since 2026-10-29: Combinado, Español, English):** `.c24-lb-tabs` is **one row of equal buttons**, no scrolling, at every width (`test_leaderboard_page_tabs_one_row`).
  - Tabs, buttons, Back link and the Discord button are at least 44px tap targets (the admin-only Hide button is 32px). Side padding is `max(16px, safe area)`.
- Hover styles only inside `@media (hover: hover) and (pointer: fine)`.
- Viewport meta: `width=device-width, initial-scale=1, viewport-fit=cover` (pinch-zoom allowed). theme-color: light `#f4efe6`, dark `#0f1a12`.
- Physical keys: `keyDown()` / `normalizeKey()` in `game.js` (rules in `casa24-text-and-languages`).

## Current state (fixed on 2026-10-26)
From the audit (before → now):
- Landscape 844×390 was unplayable (page 545px tall on a 390px screen, keys off-screen, tiles 62×32). Now the board and keyboard sit side by side, all visible, tiles square.
- Modals were cut off (stats by 87px at 320×568, 136px in landscape). Now they fit and scroll inside.
- `h-screen` (100vh) replaced with `dvh` plus safe areas.
- Tiles were not square on short phones (56×36 at 320×568). Now always square. (2026-10-26 the cap went up to 420px; 2026-10-29 back to an NYT-like 350px/330px cap, with board + keyboard centered together so no big gaps.)
- Tile text was always 24px. Now it scales with the tile.
- Keys were 27–34px wide on phones, header icons 24px. Now keys are at least 24px wide, icons and close buttons 44px, Enter/Backspace 1.5× wide.
- Header title overlapped the icons at 320/375. Then a 3-column grid; since 2026-10-29 the 2-area bar (only the "Casa 24" text hides when narrow).
- `user-scalable=no` removed.
- Bugs fixed (tested in `tests/test_input_bugs.py`): Shift/Caps Lock letters, Ctrl/Cmd shortcuts and IME typing, typing in Settings fields, a physical Enter re-pressing the last tapped key, the share button firing many times per tap.

Performance done:
- Vue is the pinned production build `vue@3.5.13`, **self-hosted** at `static/vendor/vue.global.prod.js` since `d229fcf` (was jsdelivr; before that the 2020 dev build 3.0.2 from unpkg), with `defer`.
- **Tailwind is compiled** (done 2026-10-28, `d229fcf`): `static/tailwind.css` (v3.4.17, minified) built by `scripts/build_css.py` with the standalone CLI; no more Play CDN, no unstyled flash. Rebuild after adding classes (`casa24-deploy`). Pixel-diffed: no visual change.
- Kolo pictures are WebP only, with width/height set; the end-screen Kolo has `loading="lazy"`.
- Word lists and config are raw UTF-8 JSON in `<script type="application/json" id="c24-data">` (`json_script()` in `app.py`, smaller than `\uXXXX` escapes for the accented Spanish words). The HTML itself can't be cached (it holds the daily word).
- Every static URL has `?v=<hash>` (`asset()` in `app.py`) and `vercel.json` caches those for a year. Details: `casa24-deploy`.
- VT323 is preloaded; its `@font-face` is inline in both templates' `<head>` so it uses the same versioned URL.

## Still to do
- Check the Activity in real Discord on phones (notch, Android buttons, PIP): `docs/discord-activity-manual.md`.
- **VT323 is still TTF** (about 150 KB). WOFF2 needs `fontTools` and `brotli` in `.venv`. **Waiting for the owner's OK to install them.**
- **The start screen may still scroll a little on phones** (about 780–886px of content at 375–390px wide). If the owner wants it on one screen, tighten `.c24-start` gaps and the `.c24-hero-kolo` height.
- The index stats modal is English-only.
- Targets (Core Web Vitals, mobile): LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1. Check with Lighthouse in mobile mode.

## Measured sizes (2026-10-29, tile / key width × height)
| Screen | Tile | Key |
|---|---|---|
| 320×568 phone | 54.5px | 27.6 × 44 |
| 390×844 phone | 62px | 32 × 58 |
| 844×390 landscape | 50.8px | 34.8 × 52 |
| 768×1024, 1366×768, 1600×813 (NYT unit) | 62px | 40.9 × 53.9 (keyboard 1.40× board) |
| Activity 1000×493 | 44.1px | 29.1 × 38.4 |
| Activity 400×700 | 50px | — |
| Activity 875×400 | 34.1px | 26px wide (width floor) |
| Activity 640×360 | 29.8px | 26px wide (width floor) |
| Discord PIP 240×180 | 26px | (board only) |

## Sizes to test
**Owner rule: nothing may overlap** (header icons vs brand, popover, Discord area, cards, end-window numbers) and the game must fit **without vertical scroll** at **320, 375, 390, 844×390 landscape, 768 and 1366** wide; check these on every leaderboard/Discord UI change, logged in and logged out, on `/`, `/lb/es`, `/lb/en` and `/leaderboard`. On `/lb/es` also check 860×600 (the rail's first size) and 1024×768 and open the live sheet on phones, with the facepile showing. Only the toasts may cover content (see above).

Full list: 320×568, 375×667, 390×844, 430×932, 844×390 (landscape), 768×1024, 1024×768, 1366×768, 1920×1080, plus Activity-embed PIP 240×180, 640×360, 875×400, 400×700. Use `is_mobile`/`has_touch` for phones and tablets.
- Check in light and dark mode, with es (10-key QWERTY-Ñ rows; also the Alfabético layout from Settings) and en.
- **`tests/test_layout.py` automates this** (Playwright, fake store): at many sizes it checks no page scroll, header/board/keyboard don't overlap, square tiles, key sizes (≥26px wide), NYT proportions from 481px (`test_nyt_proportions_on_tablets_and_desktops`), the rail never moving the board, the Activity desktop and phone modes, the board reserved before Vue, aria labels and focus order, the Settings layout choice, and the 3 leaderboard tabs in one row. Run it after any layout change: `.venv/bin/python -m pytest -q tests/test_layout.py`.
- `scripts/screenshots.py` only shoots 390×844. For pictures at other sizes, write a short throwaway Playwright script in the scratchpad and combine the screenshots into one contact sheet with Pillow to save tokens.

## Keyboards (rows × keys)
| Lang | Layout | Keys per row (⇨ and ⌫ included) |
|---|---|---|
| es | QWERTY + Ñ (default, `es_keyboard.json`, 2026-10-29) | 10/10/9 |
| es | Alfabético (Settings) | 10/10/9 |
| en | qwerty (`en_keyboard.json`) | 10/9/9 |

No accent keys (accents are optional and colors ignore them, `casa24-text-and-languages`).

## Sources
NYT Wordle live CSS/JS (Oct 2026); docs.discord.com Activities → Mobile and Layout guides; web.dev/blog/viewport-units; MDN viewport meta, env(), ScreenOrientation.lock; dequeuniversity target-size (WCAG 2.5.8); web.dev/learn/design/interaction; vercel.com/docs/frameworks/backend/flask and caching docs; web.dev font and preload guides.

- **Discord Activity, desktop (2026-10-29):** inside Discord on desktop the game is always stacked (board above keyboard), never the landscape side-by-side layout, at panel heights down to ~360px, sized with the same NYT unit `--t` as the web; from 768px wide the header spans the full panel (a rule after the landscape-phone one, which used to shrink it to the column on short panels like 1000×493); the live rail shows from 860px wide at any height. PIP overrides the unit: the board alone fills the tile. Scoped to `:root.c24-embed:not(.c24-plat-mobile)`; website and mobile unchanged. Details: `casa24-discord-activity`.
