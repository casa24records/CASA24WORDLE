---
name: casa24-responsive
description: Make Casa 24 Wordle work well on every screen — small/large phones, landscape, tablets, laptops, big desktops. Layout rules (dvh, board sized from leftover height, square tiles, key sizes, modals that scroll, safe areas), where each layout class lives (including the live view's sidebar/bottom-sheet breakpoints), what the 2026-10-26 fixes changed and what is still to do (WOFF2), the Discord Activity inside Discord (safe areas applied by the shell around the game iframe, PIP/grid shows the board only, language picker, portrait lock), NYT Wordle's measured layout, performance (self-hosted Vue, compiled Tailwind, fonts, WebP, caching) and the sizes to test. Use for any mobile, desktop, responsive, layout, zoom, landscape, Activity layout, or page-speed question.
---

# Responsive layout (phones → desktop)

Research done on 2026-10-26 by measuring 9 screen sizes, reading the code, and reading NYT Wordle's live CSS/JS. Update "Current state" and "Still to do" when you fix things.

## Target layout (what "good" looks like)
Based on NYT Wordle, which was measured directly.
- **One centered column**, max about 500px wide, on every screen. The only side panel is the leaderboard game's live view sidebar (≥1024px, see below); otherwise empty space is fine.
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
- **Safe areas:** `padding-bottom: max(8px, env(safe-area-inset-bottom))` on the keyboard, `env(safe-area-inset-top)` on the header, plus left and right insets in landscape. Inside the Discord Activity, Discord's own insets win (next section).
- **Touch vs mouse:** put hover styles inside `@media (hover:hover) and (pointer:fine)` so they don't stick on phones. Add `-webkit-tap-highlight-color`, `user-select:none` on keys, a `:focus-visible` outline on keys, and `overscroll-behavior:none` on html/body (no pull-to-refresh).
- **Physical keyboard:**
  - Lowercase `event.key`, so Shift and Caps Lock letters work (locale-aware for Turkish).
  - Ignore Ctrl/Meta/Alt and `isComposing`.
  - Blur the on-screen button after a click, so a physical Enter doesn't re-press the last tapped key.
- **theme-color:** light and dark meta tags (`media="(prefers-color-scheme: …)"`), plus `color-scheme: light dark`. Install settings belong in `site.webmanifest`; `apple-mobile-web-app-capable` is deprecated.

## Inside Discord (Activity)
Inside Discord the top page is the small **Activity shell** (`templates/activity.html`); the game page (`/lb/<lang>?embed=1`) runs in a full-size same-origin `<iframe>` inside it (`casa24-discord-activity`). Extra layout rules:
- **Safe areas are applied in the shell, not in the game.** Discord's mobile app sets `--discord-safe-area-inset-{top,bottom,left,right}` **only on the shell document**. `style.css` `:root` defines `--c24-safe-{top,right,bottom,left}` = `var(--discord-safe-area-inset-*, env(safe-area-inset-*))`; the shell's `.c24-shell-frame` is `position: fixed` inside those insets (shell background = game background `--c24-bg`). The game page inside gets `<html class="c24-embed">`, which sets every `--c24-safe-*` to **`0px`** so insets are never applied twice. On the web the same `--c24-safe-*` rules still apply normally; keep using them (not bare `env()`) in new layout CSS.
- **Layout modes:** focused (0, normal), **PIP** (1, small floating window) and **grid** (2, tile in a call grid). The shell subscribes once and passes the mode to the game (`postMessage {type:"c24-layout"}`); both documents get class `c24-pip` (and `data-layout-mode`) on `<html>`; `style.css` then hides header, keyboard, demo bar, live view, modals and toasts, so **PIP shows only the board** (tested at 240×180).
- **First-launch language picker** (`.c24-picker`, in the shell): 2-column grid of 48px buttons that fits a 390×844 phone without scrolling; under 420px tall (landscape, PIP) no logo, auto-fill columns, 40px buttons, scrolls inside.
- **Orientation:** the Portal locks phones and tablets to **portrait** before the page loads; landscape rules still matter for the web and desktop.
- **Desktop Activity window** can be small and any shape: the existing dvh/container-query layout handles it; test at ~640×360 and ~400×700 too.
- Accessibility: Tab and Escape must not be captured (Discord uses them).
- Test in real Discord: `docs/discord-activity-manual.md` (Paso 15).

## Where things live
All layout CSS is in the "LAYOUT" section of `webapp/static/style.css`; the class names are used in `game.html` / `index.html`.
- `--vh`: `1vh`, or `1dvh` where the browser has it. Write `calc(var(--vh) * N)`, not `vh`.
- `.c24-game`: the game page column (header, board, keyboard). `height: calc(var(--vh) * 100)`, max 500px wide, side safe areas.
- `.c24-header`: 3-column grid (`1fr auto 1fr`), 52px + top safe area, so the title never covers the icons. `.c24-header-title` font is `clamp(1.25rem, …, 2.25rem)`. `.c24-icon-btn`: 44×44 icon buttons.
- **Header left group when the leaderboard is on** (`.c24-header-side`, flex row): menu = Discord avatar button or small Discord icon (`dc.header_slot`), then the trophy link to `/leaderboard`, then the info button; leaderboard game = avatar/icon then help; `/leaderboard` = back arrow then avatar/icon. Three 44px icons don't fit next to the title on narrow phones, so the menu's info button has `.c24-hide-narrow` and is **hidden under 420px** (`@media (max-width: 419px)`). With the leaderboard on, the menu header (`.c24-header-menu-lb`) also shortens the title to **"Casa 24" under 480px** (`.c24-title-extra` = " Wordle" is hidden). The avatar popover `.c24-dc-pop` opens below the avatar, `max-width: calc(100vw - 16px)`, long usernames cut with ….
- `.c24-board-area` (the `<main>`): takes the leftover height, `container-type: size`.
- `.c24-board`: `--w: min(420px, 100cqw - 20px, (100cqh - 20px - 5*gap) / 1.2 + 4*gap)`, i.e. as big as fits, max 420px. Tiles are square; their font follows the tile size (`main .grid-cols-5 > div`: 62% of a tile, at least 14px).
- `.c24-keyboard` with `style="--rows: N"` (set in `game.html` from the row count) and one `.c24-key-row` per row. Key height `--kh` = `clamp(24px, …, 58px)`: about 7dvh, less when there are many rows (all rows share about 42dvh). Keys `flex: 1 1 0`; ⇨ and ⌫ get `flex-grow: 1.5`. Bottom padding `max(8px, env(safe-area-inset-bottom))`.
- Landscape phones, `@media (orientation: landscape) and (max-height: 500px)`: 40px header on top, board left, keyboard right (CSS grid), max 900px wide.
- **Developer view** (internally "demo", `/demo/es|en`): `.c24-game.c24-demo` adds `.c24-demo-bar` (only ↻ Restart and ✓ Fill in word; wraps on narrow phones) between header and board. In landscape it gets its own grid row: `grid-template-rows: auto auto minmax(0, 1fr)`, bar in row 2 spanning both columns, board and keyboard in row 3. Styles are in the "demo mode" section at the end of `style.css` (not in LAYOUT), including the password page (`.c24-demo-login*`, input 16px so iOS doesn't zoom).
- Modals: `.c24-modal-wrap` (fixed, centered, safe areas) holds `.c24-modal` (`width: min(500px, 100% - 32px)`, `max-height: calc(100dvh - 32px - safe areas)`, scrolls inside). `.c24-modal-sm` is 420px. `.c24-close` is the 44px ×. Esc closes every modal.
- `.c24-kolo` (end-screen picture): at most `min(160px, 22dvh)` tall. `.c24-hero-kolo` (menu): 150px, 96px on screens under 700px tall.
- Start screen: `.c24-start`, `.c24-primary` holds **all 10 language cards** (`.c24-play`, one column on phones, 2 columns at ≥640px: es/en first, then the other 8; owner 2026-10-28, the `.c24-chips` grid is gone); the dashed "🔒 Developer view" card `.c24-play-demo` comes last and spans the full row (only when `DEMO_PASSWORD` is set). Card name and status sit in one row with a 0.75rem gap: the status never wraps (`white-space: nowrap`), the name may wrap (`overflow-wrap: anywhere`). 10 big cards make the menu scroll on phones; that is expected (`test_smoke_browser.py` still checks the page is < 2000px tall).
- **Leaderboard** (styles in the "leaderboard" section of `style.css`, not in LAYOUT; details of the feature: `casa24-leaderboard`):
  - Menu: `.c24-dc-area` above the cards. Logged out: the full-width Discord button `.c24-dc-btn` (48px) + the small privacy link `.c24-dc-privacy-link` (44px tall). Logged in: the guest switch `.c24-guest-toggle` (44px row, 40×24 `.c24-switch`) + privacy link. Short on purpose (owner: less text), but it still makes the start screen taller, so recheck the phone height after changes (the < 2000px test runs with the leaderboard off).
  - Privacy: native `<dialog class="c24-privacy">`, `width: min(26rem, 100% - 32px)`, `max-height: calc(100dvh - 32px)`, Esc/backdrop/Close (44px) close it.
  - Toasts `.c24-dc-toast` (login failed/cancelled, data deleted): `position: fixed` at the bottom center, `width: min(26rem, 100% - 32px)`, above the safe area, gone after 6 s or on ×. They are **the one allowed exception to "nothing overlaps"**: they float over the page for a moment on purpose.
  - Game `/lb/<lang>` uses the normal game layout; only the end window differs (`.c24-lb-end`: `.c24-lb-stats` with two big VT323 numbers `.c24-lb-big` side by side, then the link). A guest es/en end window may show the hint `.c24-lb-hint` with a Discord button.
  - `/leaderboard` (`leaderboard.html`) is a **standalone page**: it loads `style.css` but **not Tailwind or Vue**, so the end of the leaderboard section has its own small reset (`.c24-lb-page` margins, buttons, links, `.uppercase`). Use `c24-*` classes there, not Tailwind classes. One column `.c24-lb`, max 40rem; it scrolls normally (`min-height` full screen, not fixed height).
  - Table `.c24-lb-table`: rank, player (long names cut with …), points always shown. **Wins** (`.c24-lb-opt1`) appear from **400px** wide, **streak and best streak** (`.c24-lb-opt2`) from **520px**, so a 320px phone never scrolls sideways.
  - Under the table: one compact centered line `.c24-dc-signed` (avatar + @username, wraps long names) or the Discord button `.c24-lb-login` (max 20rem), then the privacy link.
  - **Live view** on `/lb/<lang>` (styles: "live view" section of `style.css`; feature: `casa24-live-view`):
    - **≥1024px wide and ≥501px tall** (`@media (min-width: 1024px) and (min-height: 501px)`): `<aside class="c24-live">` is a fixed **left sidebar**, 240px wide (280px from 1280px, mini squares 11px instead of 10px). The game column stays centered; at 1024px it starts at 262px, so it never touches the sidebar. The people button, × and backdrop are hidden.
    - **Everywhere else** (phones, tablets, landscape phones): the header gets a **people button** `.c24-live-btn` (badge `.c24-live-badge`); when someone is playing it shows a **facepile** of 3 avatars (22px, −8px overlap; **2 under 360px** so Kolo, the language badge and trophy keep their room) and grows wider (`.has-faces`, min 44px); empty → the 44px people icon, and the list opens as a **bottom sheet** (`.c24-live.is-open`): `width: min(500px, 100%)`, `max-height: min(70% of height, 100% − 48px − top safe area)`, list scrolls inside, side and bottom safe areas, backdrop `.c24-live-backdrop`. Esc, ×, backdrop or the button close it.
    - **Header side columns:** `.c24-header-lb` uses `minmax(max-content, 1fr) auto minmax(max-content, 1fr)`, so a side column is **never narrower than its icons** (with the facepile the title shifts a little off-center rather than overlapping).
    - **Header < 420px:** the leaderboard game header (`.c24-header-lb`) has 2 icons left + 3 right, so it uses `grid-template-columns: auto minmax(0, 1fr) auto` and **hides the "Casa 24" text** (`.c24-title-text`); Kolo's face and the badges stay. Guest games keep the text. The owner may revisit this.
    - Tested at 320, 390, 844×390 and 1366 (`test_live_layout_fits_without_overlap`): no page scroll, no overlap.
  - **Tabs (11: 10 languages + Combinado, 2026-10-28):** under 600px `.c24-lb-tabs` is **one row that scrolls sideways** (flex, `overflow-x: auto`, scroll snap, hidden scrollbar, faded edges via `mask-image`); a small inline script in `leaderboard.html` centers the active tab on load without scrolling the page. **From 600px: a 6-column grid** (2 rows), no scrolling, long names cut with ….
  - Tabs, buttons, Back link and the Discord button are at least 44px tap targets (the admin-only Hide button is 32px). Side padding is `max(16px, safe area)`.
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
- Vue is the pinned production build `vue@3.5.13`, **self-hosted** at `static/vendor/vue.global.prod.js` since `d229fcf` (was jsdelivr; before that the 2020 dev build 3.0.2 from unpkg), with `defer`.
- **Tailwind is compiled** (done 2026-10-28, `d229fcf`): `static/tailwind.css` (v3.4.17, minified) built by `scripts/build_css.py` with the standalone CLI; no more Play CDN, no unstyled flash. Rebuild after adding classes (`casa24-deploy`). Pixel-diffed: no visual change.
- Kolo pictures are WebP only, with width/height set; the end-screen Kolo has `loading="lazy"`.
- Word lists and config are raw UTF-8 JSON in `<script type="application/json" id="c24-data">` (`json_script()` in `app.py`): ar page 381 → 172 KB, ko 347 → 208 KB. The HTML itself can't be cached (it holds the daily word).
- Every static URL has `?v=<hash>` (`asset()` in `app.py`) and `vercel.json` caches those for a year. Details: `casa24-deploy`.
- VT323 is preloaded; its `@font-face` is inline in both templates' `<head>` so it uses the same versioned URL.

## Still to do
- Check the Activity in real Discord on phones (notch, Android buttons, PIP): `docs/discord-activity-manual.md`.
- **VT323 is still TTF** (about 150 KB). WOFF2 needs `fontTools` and `brotli` in `.venv`. **Waiting for the owner's OK to install them.**
- **The start screen may still scroll a little on phones** (about 780–886px of content at 375–390px wide). If the owner wants it on one screen, tighten `.c24-start` gaps and the `.c24-hero-kolo` height.
- The index stats modal is English-only.
- Targets (Core Web Vitals, mobile): LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1. Check with Lighthouse in mobile mode.

## Sizes to test
**Owner rule: nothing may overlap** (header icons vs title, popover, Discord area, cards, end-window numbers) at **320, 375, 390, 844×390 landscape, 768 and 1366** wide; check these on every leaderboard/Discord UI change, logged in and logged out, on `/`, `/lb/es` and `/leaderboard`. On `/lb/es` also check 1024×768 (the live sidebar's first size) and open the live sheet on phones. Since all 10 languages have the leaderboard, also check `/lb/ar` (RTL), `/lb/ko` and `/lb/vi` (tall keyboards) with the facepile showing, and `/leaderboard?tab=ar` / a far-right tab (tabs scroll on phones). Only the toasts may cover content (see above).

Full list: 320×568, 375×667, 390×844, 430×932, 844×390 (landscape), 768×1024, 1024×768, 1366×768, 1920×1080. Use `is_mobile`/`has_touch` for phones and tablets.
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
NYT Wordle live CSS/JS (Oct 2026); docs.discord.com Activities → Mobile and Layout guides; web.dev/blog/viewport-units; MDN viewport meta, env(), ScreenOrientation.lock; dequeuniversity target-size (WCAG 2.5.8); web.dev/learn/design/interaction; vercel.com/docs/frameworks/backend/flask and caching docs; web.dev font and preload guides.

- **Discord Activity, desktop (2026-10-29):** inside Discord on desktop the game is always stacked (board above keyboard), never the landscape side-by-side layout, at panel heights down to ~360px; the live sidebar shows from 860px wide at any height. Scoped to `:root.c24-embed:not(.c24-plat-mobile)`; website and mobile unchanged. Details: `casa24-discord-activity`.
