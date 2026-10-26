---
name: casa24-responsive
description: Make Casa 24 Wordle work well on every screen — small/large phones, landscape, tablets, laptops, big desktops. Layout rules (dvh, board sized from leftover height, square tiles, key sizes, modals that scroll, safe areas), the measured problems from the 2026-10-26 audit, NYT Wordle's measured layout, performance (Tailwind/Vue CDN, fonts, images, caching) and the sizes to test. Use for any mobile, desktop, responsive, layout, zoom, landscape, or page-speed question.
---

# Responsive layout (phones → desktop)

Research done on 2026-10-26 by measuring 9 screen sizes, reading the code, and reading NYT Wordle's live CSS/JS. Update the "Current state" section when you fix things.

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
  - Lowercase `event.key` (Shift and Caps Lock are dropped today).
  - Ignore Ctrl/Meta/Alt and `isComposing`.
  - Blur the on-screen button after a click, so a physical Enter doesn't re-press the last tapped key.
- **theme-color:** light and dark meta tags (`media="(prefers-color-scheme: …)"`), plus `color-scheme: light dark`. Install settings belong in `site.webmanifest`; `apple-mobile-web-app-capable` is deprecated.

## Current state (audit 2026-10-26, before fixes)
Problems, most important first, measured with Playwright:
1. **Landscape phone 844×390 is unplayable.** The page is 545px tall on a 390px screen, the bottom keyboard rows are off-screen, and tiles are 62×32.
2. **Modals can't scroll.** The stats modal is cut by 87px at 320×568, 37px at 375×667, and 136px in landscape. The help modal is 658px tall. The cause is `fixed top-10 h-full` with no `max-h`/`overflow`.
3. **`h-screen` (100vh)** on the game page (`game.html` body). No `dvh`, no safe areas.
4. **Tiles not square on short phones:** 56×36 at 320×568, 62×53 at 375×667. The board is `max-w-[350px] max-h-[420px]` with no aspect ratio.
5. **Tile text always 24px:** `tiny:text-4xl` does nothing, because the `tiny` breakpoint was never configured.
6. **Touch targets:** keys are 27px wide at 320 and 32–34px at 375/390. Header icons are 24px. Enter and Backspace are as narrow as letters.
7. **Header title overlaps the icons** at 320 and 375 (absolutely centered title).
8. **`user-scalable=no`** on the game page.
9. **Desktop:** the 350px board leaves big empty gaps (183px at 1920×1080).
10. **The start screen scrolls** on small phones (926px at 320×568).

Bugs found along the way:
- The share button adds a new click listener on every Vue `updated()`, so one tap can share many times.
- Physical Shift/Caps Lock letters are ignored.
- `key = event.key` has no `var`.
- The alphabetical keyboard rebalancing in `app.py` scrambles letter order for de, fr and tr (`insert(-1, …)`).
- Invalid classes: `z-1`, `overflow`, `top-50`.
- The index.html charset meta is broken.
- The index stats modal is English-only.

## Performance (fix before launch)
- **Tailwind Play CDN** (`cdn.tailwindcss.com`) is development-only, per Tailwind's docs. It compiles CSS in the browser on every load. Replace it with the **Tailwind standalone CLI**, run in `scripts/vercel_build.py`, which outputs one minified CSS file into `public/static/`. No Node needed.
- **Vue `unpkg.com/vue@3.0.2`** is the 2020 *development* build. Use the pinned production build: `https://cdn.jsdelivr.net/npm/vue@3.5.x/dist/vue.global.prod.js`. It must be the full build, because templates compile in the browser.
- **Fonts:** about 564 KB of TTF. Convert to WOFF2, preload the main one (VT323), and subset if possible.
- **Images:** all PNG with no width/height. Kolo win pictures are 40–108 KB each. Use WebP with a PNG fallback, set width/height, and use `loading="lazy"` on the end-screen Kolo.
- **Page weight:**
  - Word lists are inlined with `tojson`, which escapes non-ASCII as `\uXXXX`. The ar page is 396 KB, ko 362 KB, es 111 KB.
  - Emitting raw UTF-8 (or a separate cacheable JSON file) cuts ar/ko roughly in half.
  - The HTML itself can't be cached, because it holds the daily word.
- **Caching:** Vercel's static default is `max-age=0, must-revalidate`. Use long `immutable` caching in `vercel.json` only once asset URLs carry a version, for example `?v=<git hash>`.
- **Targets (Core Web Vitals, mobile):** LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1. Check with Lighthouse in mobile mode.

## Sizes to test
320×568, 375×667, 390×844, 430×932, 844×390 (landscape), 768×1024, 1024×768, 1366×768, 1920×1080. Use `is_mobile`/`has_touch` for phones and tablets.
- Check in light and dark mode, and with es, vi (9 key rows), ko (7 rows), ar (RTL) and de/fr/tr (11-key rows).
- For each size, measure:
  - no vertical or horizontal page scroll on the game
  - square tiles
  - key width at least 24px
  - modal fully visible or scrollable
- Extend `scripts/screenshots.py` for this. Combine the shots into one contact sheet to save tokens.

## Keyboards per language (rows × keys)
| Lang | Rows | Keys per row |
|---|---|---|
| es (qwerty + accent row) | 4 | 6/10/10/9 |
| en | 3 | 10/9/9 |
| de | 3 | 11/11/10 |
| fr | 4 | 10/11/11/10 |
| tr | 3 | 10/11/10 |
| ar | 4 | 10/10/10/8 |
| pt | 4 | 10 per row |
| ru | 4 | 10/10/10/4 |
| ko | 7 | 7 rows |
| vi | 9 | 9 rows of 10 |

Keyboard height today is rows × 56px + gaps, so vi is about 576px and ko about 440px.

## Sources
NYT Wordle live CSS/JS (Oct 2026); tailwindcss.com/docs/installation/play-cdn; web.dev/blog/viewport-units; MDN viewport meta, env(), ScreenOrientation.lock; dequeuniversity target-size (WCAG 2.5.8); web.dev/learn/design/interaction; vercel.com/docs/frameworks/backend/flask and caching docs; web.dev font and preload guides.
