---
name: casa24-responsive
description: Make Casa 24 Wordle work well on every screen — small/large phones, landscape, tablets, laptops, big desktops. Layout rules (dvh, board sized from leftover height, square tiles, key sizes, modals that scroll, safe areas), where each layout class lives, what the 2026-10-26 fixes changed and what is still to do (Tailwind compile, WOFF2), NYT Wordle's measured layout, performance (Vue/Tailwind CDN, fonts, WebP, caching) and the sizes to test. Use for any mobile, desktop, responsive, layout, zoom, landscape, or page-speed question.
---

# Responsive layout (phones → desktop)

Research done on 2026-10-26 by measuring 9 screen sizes, reading the code, and reading NYT Wordle's live CSS/JS. Update "Current state" and "Still to do" when you fix things.

## Target layout (what "good" looks like)
Based on NYT Wordle, which was measured directly.
- **One centered column**, max about 500px wide, on every screen. No side panels on desktop; empty space is fine.
- **Page height `100dvh`** (with a `100vh` fallback first), never plain `100vh` / `h-screen`. Otherwise mobile browser bars hide the bottom keyboard row. Use `dvh` only on the outer container, not on tiles.
- **Header → board → keyboard**, as a flex column. The board area is `flex:1; min-height:0`. The board is **sized from the leftover height**: `width = min(350px…420px, area width, area height × 5/6)`, with `aspect-ratio: 5/6`. Tiles use `aspect-ratio: 1`, so they are always square. Do it with CSS container queries (`container-type:size` + `cqw/cqh`), or a ResizeObserver like NYT.
- **Keys:**
  - `flex:1 1 0; min-width:0`, height about `clamp(44px, 7dvh, 58px)`, gap about `clamp(3px,1vw,6px)`.
  - Enter and Backspace are wider (`flex:1.5`).
  - Never narrower than 24px (WCAG 2.2 minimum). 44px is Apple's guideline, 48dp Material's.
  - Big keyboards (vi has 9 rows, ko 7) get shorter keys, never sideways scrolling.
- **Landscape phone** (`orientation:landscape and max-height:500px`): shrink or hide the header and use shorter keys. Optionally put the board and keyboard side by side. Orientation can't be locked in a browser.
- **Modals:**
  - `max-height: calc(100dvh - 32px); overflow:auto; overscroll-behavior:contain`, width `min(500px, 100% - 32px)`.
  - Close with Esc, and make the close button at least a 44px tap target.
  - On small phones, shrink the Kolo picture.
- **Viewport meta:** `width=device-width, initial-scale=1, viewport-fit=cover`. **No `user-scalable=no`**: let low-vision players pinch-zoom. Stop double-tap zoom on keys with `touch-action: manipulation`.
- **Safe areas:** `padding-bottom: max(8px, env(safe-area-inset-bottom))` on the keyboard, `env(safe-area-inset-top)` on the header, plus left and right insets in landscape.
- **Touch vs mouse:** put hover styles inside `@media (hover:hover) and (pointer:fine)` so they don't stick on phones. Add `-webkit-tap-highlight-color`, `user-select:none` on keys, a `:focus-visible` outline on keys, and `overscroll-behavior:none` on html/body (no pull-to-refresh).
- **Physical keyboard:**
  - Lowercase `event.key`, so Shift and Caps Lock letters work (locale-aware for Turkish).
  - Ignore Ctrl/Meta/Alt and `isComposing`.
  - Blur the on-screen button after a click, so a physical Enter doesn't re-press the last tapped key.
- **theme-color:** light and dark meta tags (`media="(prefers-color-scheme: …)"`), plus `color-scheme: light dark`. Install settings belong in `site.webmanifest`; `apple-mobile-web-app-capable` is deprecated.

## Where things live
All layout CSS is in the "LAYOUT" section of `webapp/static/style.css`; the class names are used in `game.html` / `index.html`.
- `--vh`: `1vh`, or `1dvh` where the browser has it. Write `calc(var(--vh) * N)`, not `vh`.
- `.c24-game`: the game page column (header, board, keyboard). `height: calc(var(--vh) * 100)`, max 500px wide, side safe areas.
- `.c24-header`: 3-column grid (`1fr auto 1fr`), 52px + top safe area, so the title never covers the icons. `.c24-header-title` font is `clamp(1.25rem, …, 2.25rem)`. `.c24-icon-btn`: 44×44 icon buttons.
- `.c24-board-area` (the `<main>`): takes the leftover height, `container-type: size`.
- `.c24-board`: `--w: min(420px, 100cqw - 20px, (100cqh - 20px - 5*gap) / 1.2 + 4*gap)`, i.e. as big as fits, max 420px. Tiles are square; their font follows the tile size (`main .grid-cols-5 > div`: 62% of a tile, at least 14px).
- `.c24-keyboard` with `style="--rows: N"` (set in `game.html` from the row count) and one `.c24-key-row` per row. Key height `--kh` = `clamp(24px, …, 58px)`: about 7dvh, less when there are many rows (all rows share about 42dvh). Keys `flex: 1 1 0`; ⇨ and ⌫ get `flex-grow: 1.5`. Bottom padding `max(8px, env(safe-area-inset-bottom))`.
- Landscape phones, `@media (orientation: landscape) and (max-height: 500px)`: 40px header on top, board left, keyboard right (CSS grid), max 900px wide.
- **Developer view** (internally "demo", `/demo/es|en`): `.c24-game.c24-demo` adds `.c24-demo-bar` (only ↻ Restart and ✓ Fill in word; wraps on narrow phones) between header and board. In landscape it gets its own grid row: `grid-template-rows: auto auto minmax(0, 1fr)`, bar in row 2 spanning both columns, board and keyboard in row 3. Styles are in the "demo mode" section at the end of `style.css` (not in LAYOUT), including the password page (`.c24-demo-login*`, input 16px so iOS doesn't zoom).
- Modals: `.c24-modal-wrap` (fixed, centered, safe areas) holds `.c24-modal` (`width: min(500px, 100% - 32px)`, `max-height: calc(100dvh - 32px - safe areas)`, scrolls inside). `.c24-modal-sm` is 420px. `.c24-close` is the 44px ×. Esc closes every modal.
- `.c24-kolo` (end-screen picture): at most `min(160px, 22dvh)` tall. `.c24-hero-kolo` (menu): 150px, 96px on screens under 700px tall.
- Start screen: `.c24-start`, `.c24-primary` (two big buttons side by side at ≥640px), `.c24-chips` (2 columns, 4 at ≥640px); the dashed "🔒 Developer view" card `.c24-play-demo` spans the full row under them (only when `DEMO_PASSWORD` is set).
- **Leaderboard** (styles in the "leaderboard" section of `style.css`, not in LAYOUT; details of the feature: `casa24-leaderboard`):
  - Menu: `.c24-mode` guest/leaderboard switch (2 equal columns, each option at least 44px tall, Spanish line over a smaller English line), `.c24-notice` boxes (44px ×), `.c24-lb-links` (View leaderboard, logged-in name, Log out). When the leaderboard is on, these make the start screen taller, so recheck the phone height after changes (the < 2000px test runs with the leaderboard off).
  - Game `/lb/<lang>` uses the normal game layout; only the end window differs (`.c24-lb-end`: rank, points, link).
  - `/leaderboard` (`leaderboard.html`) is a **standalone page**: it loads `style.css` but **not Tailwind or Vue**, so the end of the leaderboard section has its own small reset (`.c24-lb-page` margins, buttons, links, `.uppercase`). Use `c24-*` classes there, not Tailwind classes. One column `.c24-lb`, max 40rem; it scrolls normally (`min-height` full screen, not fixed height).
  - Table `.c24-lb-table`: rank, player (long names cut with …), points always shown. **Wins** (`.c24-lb-opt1`) appear from **400px** wide, **streak and best streak** (`.c24-lb-opt2`) from **520px**, so a 320px phone never scrolls sideways.
  - Tabs, buttons, Back link and Log in are at least 44px tap targets (the admin-only Hide button is 32px). Side padding is `max(16px, safe area)`.
- Hover styles only inside `@media (hover: hover) and (pointer: fine)`.
- Viewport meta: `width=device-width, initial-scale=1, viewport-fit=cover` (pinch-zoom allowed). theme-color: light `#f4efe6`, dark `#0f1a12`.
- Physical keys: `keyDown()` / `normalizeKey()` in `game.js` (rules in `casa24-text-and-languages`).

## Current state (fixed on 2026-10-26)
From the audit (before → now):
- Landscape 844×390 was unplayable (page 545px tall on a 390px screen, keys off-screen, tiles 62×32). Now the board and keyboard sit side by side, all visible, tiles square.
- Modals were cut off (stats by 87px at 320×568, 136px in landscape). Now they fit and scroll inside.
- `h-screen` (100vh) replaced with `dvh` plus safe areas.
- Tiles were not square on short phones (56×36 at 320×568). Now always square, and the board grows up to 420px (was a fixed 350px that left big gaps on desktop).
- Tile text was always 24px. Now it scales with the tile.
- Keys were 27–34px wide on phones, header icons 24px. Now keys are at least 24px wide, icons and close buttons 44px, Enter/Backspace 1.5× wide.
- Header title overlapped the icons at 320/375. Now a 3-column grid.
- `user-scalable=no` removed.
- Bugs fixed (tested in `tests/test_input_bugs.py`): Shift/Caps Lock letters, Ctrl/Cmd shortcuts and IME typing, typing in Settings fields, Turkish I/İ, a physical Enter re-pressing the last tapped key, the share button firing many times per tap, de/fr/tr alphabetical keyboards out of order.

Performance done:
- Vue is the pinned production build `vue@3.5.13` from jsdelivr, with `defer` (was the 2020 dev build 3.0.2 from unpkg).
- Kolo pictures are WebP only, with width/height set; the end-screen Kolo has `loading="lazy"`.
- Word lists and config are raw UTF-8 JSON in `<script type="application/json" id="c24-data">` (`json_script()` in `app.py`): ar page 381 → 172 KB, ko 347 → 208 KB. The HTML itself can't be cached (it holds the daily word).
- Every static URL has `?v=<hash>` (`asset()` in `app.py`) and `vercel.json` caches those for a year. Details: `casa24-deploy`.
- VT323 is preloaded; its `@font-face` is inline in both templates' `<head>` so it uses the same versioned URL.

## Still to do
- **Tailwind Play CDN** (`cdn.tailwindcss.com`) is development-only; it builds the CSS in the browser on every load. Fix: run the Tailwind standalone CLI in `scripts/vercel_build.py` to write one minified CSS file (no Node needed). **Waiting for the owner's OK to download the Tailwind CLI.** Until then the script tag must stay synchronous (no `defer`), or the page flashes unstyled.
- **VT323 is still TTF** (about 150 KB). WOFF2 needs `fontTools` and `brotli` in `.venv`. **Waiting for the owner's OK to install them.**
- **The start screen may still scroll a little on phones** (about 780–886px of content at 375–390px wide). If the owner wants it on one screen, tighten `.c24-start` gaps and the `.c24-hero-kolo` height.
- The index stats modal is English-only.
- Targets (Core Web Vitals, mobile): LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1. Check with Lighthouse in mobile mode.

## Sizes to test
320×568, 375×667, 390×844, 430×932, 844×390 (landscape), 768×1024, 1024×768, 1366×768, 1920×1080. Use `is_mobile`/`has_touch` for phones and tablets.
- Check in light and dark mode, and with es, vi (9 key rows), ko (7 rows), ar (RTL) and de/fr/tr (11-key rows).
- For each size, measure:
  - no vertical or horizontal page scroll on the game
  - square tiles
  - key width at least 24px
  - modal fully visible or scrollable
- `scripts/screenshots.py` only shoots 390×844. For other sizes, write a short throwaway Playwright script in the scratchpad: open `/es` (and `/vi`, `/ko`) per size, then read `document.documentElement.scrollHeight` vs `innerHeight`, `scrollWidth` vs `innerWidth`, a tile's `getBoundingClientRect()` (width = height) and the narrowest `.key` width. Combine the screenshots into one contact sheet with Pillow to save tokens.

## Keyboards per language (rows × keys)
| Lang | Layout | Keys per row (⇨ and ⌫ included) |
|---|---|---|
| es | qwerty + accent row (`es_keyboard.json`) | 6/10/10/9 |
| en | qwerty (`en_keyboard.json`) | 10/9/9 |
| de | alphabetical | 11/11/10 |
| fr | alphabetical | 11/11/10/10 |
| tr | alphabetical | 11/10/10 |
| ar | alphabetical | 10/10/9/9 |
| pt | alphabetical | 10/10/10/10 |
| ru | alphabetical | 9/9/8/8 |
| ko | alphabetical | 7 rows (10/10/10/10/9/9/9) |
| vi | alphabetical | 9 rows of 10 |

Only es and en have keyboard files; the rest are built by `_generate_alphabetical_keyboard()` in `app.py`. Key height shrinks with `--rows`, so vi and ko still fit (keys never go below 24px tall).

## Sources
NYT Wordle live CSS/JS (Oct 2026); tailwindcss.com/docs/installation/play-cdn; web.dev/blog/viewport-units; MDN viewport meta, env(), ScreenOrientation.lock; dequeuniversity target-size (WCAG 2.5.8); web.dev/learn/design/interaction; vercel.com/docs/frameworks/backend/flask and caching docs; web.dev font and preload guides.
