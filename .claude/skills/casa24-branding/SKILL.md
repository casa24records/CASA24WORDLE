---
name: casa24-branding
description: Change El Wordle by Casa 24's look — the dark-only palette (no light mode), the El Wordle title image, hoodie Kolo and Casa 24 door in the header (_brand.html), the lime language button, leaderboard medals and tabs, the header's top-left Discord slot (no landing since 2026-11-04), Kolo mascot art (including the random end-screen Kolo), fonts and their licenses, favicons and og image (brand_assets.py --rebrand), tile animations, live view look (rail cards, invite card). Use when editing style.css, theme.js, _brand.html, the tile animations in game.js, images, fonts, or when the owner or designer shares new brand assets.
---

# Branding (El Wordle by Casa 24)

**Rebrand 2026-11-04 (owner):** the game is **"El Wordle by Casa 24"** (short "El Wordle"; was "Casa 24 Wordle"). Main reference: the designer's guide **Explained.pdf** (not in the repo: its screenshots show real Discord usernames; the owner keeps it in `~/Downloads/v1.1 01_10_26/`). If a plan and the PDF disagree, the PDF wins. Plan and decisions: `docs/rebrand-el-wordle.md`.

## Dark only
- **No light mode, no theme picker or toggle** (owner, 2026-11-04). `webapp/static/theme.js` only sets `data-theme="dark"` on `<html>` (and removes the old `casa24_theme` localStorage key), plus the `select[data-nav-select]` helper. Every template already has `<html … data-theme="dark">`, `<meta name="color-scheme" content="dark">` and `theme-color` `#0f1a12`; `site.webmanifest` uses `#0f1a12` too.
- Old light/dark blocks (`:root[data-theme="dark"] …`, `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) … }`) still exist in places and keep applying, because the page is always `data-theme="dark"`. New rules don't need them: write them once with the tokens.
- `casa24ToggleTheme()`, `#theme-select` and the old menu's moon/sun button are gone; don't bring them back.

## Tokens: top `:root` of `webapp/static/style.css`
| Token | Value | Use |
|---|---|---|
| `--c24-bg` | `#0f1a12` | page (also `theme-color`) |
| `--c24-surface` | `#17241a` | windows, cards |
| `--c24-green` → `--c24-correct-bg` | `#2f7a48` | correct tile (white text) |
| `--c24-amber` → `--c24-present-bg` | `#ffb800` | present tile, text `--c24-ink` `#0a0b09` |
| `--c24-absent-bg` | `#2c302d` | absent tile |
| `--c24-key-bg` | `#5d6d61` | unused keys (must stay lighter than absent) |
| `--c24-lime` | `#efff5e` | language button "EN ▾" (`.c24-badge`), (was also today's number on the removed landing) |
| `--c24-win` | `#32dd65` | stats score when won (`.c24-stats-score.is-won`), green help letter |
| `--c24-accent` | = amber | close ✕, active tab, focus rings |
| `--c24-orange` | `#ff7944` | Kolo's fur: "You/Tú" badge (`.c24-lb-you`), counters (`.c24-live-badge`); a few small accents (legal link underline, warning toast) |
| `--c24-text` / `--c24-subtle` / `--c24-line` | `#f4efe6` / `#b9b0a3` / `#34453a` | text, secondary text, lines |
- The original Tailwind classes (`bg-white`, `text-neutral-500`, `border-gray-300`, ...) are remapped to tokens in the "base" section. A newly used Tailwind color class needs a mapping there.
- **Hover** styles go only inside `@media (hover: hover) and (pointer: fine)`, so they don't stick after a tap on phones.
- **Focus ring** (keys, icon buttons, ✕): 3px `--c24-accent` (amber) + a thin inner ring in the text color.
- `--c24-live` (`#4cc477`) is still defined but unused since 2026-10-29.
- Fixed colors allowed: Discord Blurple (below), the medal colors, white text on green.

## Share grid and end-window grid
- **Share text** (`shareResults()` in `game.js`): `El Wordle by Casa 24 EN #5 3/6` + link + emoji grid 🟩 🟧 ⬜ (`getEmojiBoard()`, only in the copied text).
- **End window result grid: never emoji** (owner, 2026-10-30). Flat 20px squares, 4px apart, 3px radius, in the tile colors (gray ones get a 1px inset line): `#emoji_board.c24-result-grid` in `game.html`, rows from `result_rows`, styles next to `.c24-result` in `style.css`. Test: `assert_clean_result_grid` in `tests/test_smoke_browser.py`.

## Header: `webapp/templates/_brand.html` (every page)
- `brand.lockup(code, arrow=true)`: hoodie Kolo `img.c24-logo.c24-logo-kolo` (`kolo-hoodie.webp`) + the El Wordle title image `img.c24-title-text.c24-titler` (`el-wordle.webp`, alt "El Wordle by Casa 24") + lime `span.c24-badge` with the language code and `span.c24-badge-arrow` "▾". `code=none` (`/leaderboard`, legal) shows no badge.
- `brand.door(cls)`: the Casa 24 door, `a.c24-door-link[data-c24-door]` → https://www.casa24records.com (`target=_blank` on the web; `data-c24-external`, so inside Discord `discord-activity.js` opens it through the SDK's `openExternalLink`). `.c24-door` is a CSS mask of `casa24-door.webp`, so it takes the icon color. It **replaced the Settings button** (right end of the game header) and the light/dark switch on `/leaderboard` and legal pages. Also at the bottom of How to play (`c24-help-door`).
- **Game pages:** `.c24-header-bar`, 2 areas. Left (`.c24-header-start`): on the website (leaderboard on, not Developer view) first the Discord slot (since 2026-11-04), then the lockup inside a button that opens the language window (`.c24-lang-btn`; `data-lang-open` on the web, `data-activity-lang-open` in Discord; a link home in the Developer view). Right, all `.c24-icon-btn`: people/facepile (lb), help, trophy, stats, door.
- **The title image steps aside** only on narrow headers: ≤419px on `/lb/` web pages, ≤379px in the Activity, ≤359px other game pages, ≤339px guest (`.c24-title-text { display: none }` in the header section of `style.css`; was 480/419 for the old "Casa 24" text). Kolo and badge always stay; their narrow-phone sizes are in the "El Wordle brand pieces" section of `style.css`. Layout: `casa24-responsive`.
- **`/leaderboard`:** `.c24-header` (3 columns): back arrow + Discord slot left, lockup in the middle, door on the right.
- **Discord slot** (`dc.header_slot`, leaderboard on; top left on game pages and `/leaderboard`): round Discord avatar (popover `.c24-dc-pop`, opens to the right in the game bar via `.c24-header-bar .c24-dc-pop`: @username, Ver leaderboard, Cerrar sesión, and Borrar mis datos only on `/leaderboard`) or a small Discord icon `.c24-dc-icon` when logged out. Picture from Discord's CDN (`casa24-leaderboard`).
- **People button** (`/lb/` without the rail): facepile of up to 3 avatars (`.c24-face`, 2 under 400px) or a line "people" icon, in `.c24-live-btn` with the orange count badge.
- **Nothing may overlap** at any width (320, 375, 390, 844×390, 768, 1366).

## Windows (Explained.pdf)
- **How to play** (`#HelpModal`, `.c24-help*`): the El Wordle title image, "Examples" (`help.title_2`), three examples with one colored letter each (1st green, 3rd amber, 5th gray; `.c24-help-letter.is-correct/is-semicorrect/is-incorrect`), the door, small Terms · Privacy (`.c24-help-legal`; + "Delete my data" inside Discord). No rule text, no "close" button (✕ only).
- **Stats** (`.c24-stats*`): date title (`stats_date()`, uppercase), big score `[data-stats-score]` n/6 (`.is-won` green; X/6 lost), Next word, timer, Share (`.c24-share-btn`). Opened by itself at the end (`stats_end`) it also shows the random Kolo, the result grid and rank/points (lb) or local stats (guest). The header icon (`toggleStats()`) always opens the compact window.
- **Language window:** same in Discord and on the web (`[data-web-langs]`, `.c24-lang-choice`).

## No landing (2026-11-04)
The landing and its CSS (`.c24-start`, `.c24-hero*`, `.c24-land*`, `.c24-today`, `.c24-menu-app`, `.c24-primary`) were removed: `/` opens the game. `.c24-play` stays (used by `demo_login.html`). The leftover `.c24-play-demo`, `.c24-guest-toggle` and `.c24-demo-langs` rules were deleted too. Developer view styles (`.c24-demo-*`) stay in the "demo mode" section.

## Leaderboard styles
- "leaderboard" and "Discord" sections of `style.css` (sign-in button `.c24-dc-btn`, avatar/popover `.c24-dc-me`/`.c24-dc-pop`, toasts `.c24-dc-toast`, privacy dialog `.c24-privacy`, end-window block `.c24-lb-end` with `.c24-lb-big`/`.c24-lb-small`, table `.c24-lb-table`, own row `tr.is-me` with an orange left mark and the orange `.c24-lb-you` tag).
- **Language window on the web:** its choices are links (`[data-web-langs] a.c24-lang-choice`), centered with flex like the Discord buttons (fixed 2026-11-04).
- **Tabs and medals** ("leaderboard: EN · ESP · MIX tabs and medals" section at the end of `style.css`, used by `/leaderboard` `.c24-lb` and the Discord window `[data-activity-board]`): header row trophy (+ sr-only title), then EN · ESP · MIX as large plain-text tabs, active one amber (`--c24-lb-on`), except **MIX active = green `--c24-win` #32DD65** like the guide (owner 2026-11-04; `[data-tab=all]` / `[data-board-tab=all]`); amber bold ✕ (`.c24-board-close`). Ranks 1–3 are SVG rosette medals `dc.medal(rank)` in `templates/_discord.html` (`.c24-medal.is-1/2/3`: gold `#F5B323`, silver `#B9BEC2`, bronze `#D9622B`; sr-only rank number); plain numbers from 4.
- **Trophy is a line SVG** (`dc.trophy()`), never the 🏆 emoji.
- **Official Discord sign-in button** (`dc.button()`, `.c24-dc-btn`): Blurple `#5865F2`, white official Discord logo (`dc.logo()`), white text, 48px, hover `#4752C4`. Allowed fixed brand color; don't recolor or redraw the logo.
- **Less text:** short auto-dismiss toasts, a small "ⓘ Privacidad" link, rank/points as big numbers.

## Live view styles
"live view" section of `style.css` (feature: `casa24-live-view`, layout: `casa24-responsive`). Token-only, new palette:
- `.c24-live` (rail ≥860px, transparent; else a bottom sheet on `--c24-surface`), `.c24-live-backdrop`.
- **Cards `.c24-live-card`:** 147×80, 1px `--c24-line` border, 8px radius, 64px round avatar `.c24-live-avatar` + mini board, nothing else visible (name/status sr-only `.c24-live-info` + `title`).
- **Invite card** (Discord only): `.c24-live-invite`, same size, 64px **green** circle `.c24-live-invite-icon` (`--c24-correct-bg`), label `activity_invite`.
- Mini board `.c24-live-grid`: 6×5 squares of 9px in the tile tokens; **never letters**.
- Header badge `.c24-live-badge`: orange with ink text.

## Images
- **Rebrand assets** (designer, PNG with transparency): `design/rebrand-v1.1/` — `el-wordle-titler.png`, `hoodie-kolo-cropped.png`, `hoodie-kolo.png`, `casa24-door-white.png`, `icon-1024.png` (opaque Activity icon), `banner-680x240.png`, `banner-alt-480x280.png`.
- **Rebuild:** `.venv/bin/python scripts/brand_assets.py --rebrand design/rebrand-v1.1` (`rebrand()`; `REBRAND_IMAGES`, `REBRAND_OG`, `REBRAND_ICON`). Writes `webapp/static/images/brand/`:
  - `el-wordle.webp` (356×160): header title, How to play, Developer view password page, Activity picker
  - `kolo-hoodie.webp` (160×192): header mascot, Activity loading screen
  - `kolo-hoodie-full.webp` (227×420): was for the removed landing; not shown any more (file and script entry stay)
  - `casa24-door.webp` (height 96): door mask
  - `og-image.png` (from `banner-680x240.png`): `og:image` / `twitter:image` (PNG for crawlers)
  - and the favicons in `webapp/static/favicon/` from `icon-1024.png`: `favicon.ico` (16/32/48), `apple-touch-icon.png`, `android-chrome-192x192.png`, `android-chrome-512x512.png`. The site favicon is the Activity icon (owner, 2026-11-04). Pages link `favicon.ico`, a 192px PNG `rel="icon"` and `apple-touch-icon.png`; `app.py` `root_icons()` also serves `/favicon.ico` and `/apple-touch-icon.png` at the site root (browsers and search engines ask there on their own; before, the catch-all redirect handed them HTML so they kept the old icon). Test: `test_root_favicon_is_the_el_wordle_icon` (`tests/test_vercel_ready.py`).
- **WebP for game images, PNG only for the og image and favicons** (owner, 2026-11-04). The Developer Portal uploads are PNG (`docs/discord-activity-checklist.md` RB1–RB3). The banners may not match the Portal's Cover Art sizes (R13: 16:9 and 13:11, ≥1024px): ask the designer if the Portal rejects them.
- **Old Kolo path:** `.venv/bin/python scripts/brand_assets.py "<brand pack folder>"` (`main()`, folder with `KOLO/`) still writes the Kolo WebPs (`IMAGES`, `WIN`, `LOSE`, `ALSO_PNG`) **and also rewrites the favicons from Kolo's face**: after running it, run `--rebrand` again to restore the El Wordle favicons.
- `webapp/static/images/kolo/`: `kolo-face.webp`, `kolo-hero.webp`, `kolo-hero.png` are no longer shown (the header and og image use `images/brand/`) but stay, because `tests/test_kolo.py` and `tests/test_vercel_ready.py` check them. `win/` and `lose/` are the end-screen Kolos.
- **Random end-screen Kolo** (decided 2026-10-26): one per game, shown only in the window that opens by itself at the end (`.c24-kolo`, max 160px tall).
  - Win (12): `car`, `chill`, `dj`, `face`, `hoodie`, `montuno`, `pizza`, `prod`, `rap-battle`, `ross`, `young`, `young-cropped`. Loss (2): `baby`, `toilet`. All `.webp`; win ≤300px tall, loss ≤240px.
  - `pickKolo()` in `game.js` (lists `KOLO_WIN` / `KOLO_LOSE`), saved as `kolo_image` in localStorage; `kolo_url()` builds the address.
  - **To add or remove one:** edit `WIN`/`LOSE` in `scripts/brand_assets.py`, rerun the old Kolo path (then `--rebrand`), edit `KOLO_WIN`/`KOLO_LOSE` in `game.js`, run `tests/test_kolo.py`.
- In templates, link pictures with `{{ asset('images/…') }}` (adds `?v=`; `casa24-deploy`) and set `width`/`height`.
- **Don't use:** "Kolo ft. Pikachu" (trademark), anywhere, ever (a test checks). Alcohol art and Kolo Toilet are allowed (2026-10-26). Never draw or invent new Kolo art. Member logos are not used.
- Kolo art and the rebrand art are © Casa 24 Records (`CREDITS.md`), not MIT-licensed.

## Fonts
- **VT323** (pixel font, SIL OFL) for tiles and some numbers. Covers es/en. Committed with `VT323-OFL.txt`; `@font-face` + `<link rel="preload">` in the `<head>` of the templates. Still TTF; WOFF2 pending the owner's OK (`casa24-responsive`).
- **Gilroy** is commercial: git-ignored (and in `.vercelignore`), so production uses the system font. Only commit with a confirmed **webfont** license.
- `--c24-font-body`, `--c24-font-display`.

## Animations (tiles)
- A letter pops when typed, tiles flip one by one on Enter, the winning row bounces.
- `style.css`: keyframes `c24-pop`, `c24-flip`, `c24-bounce`; classes `.pop` (100 ms), `.flip` (500 ms), `.bounce` (1000 ms), `.bounce-d1`…`.bounce-d4`. `game.js`: `addChar` adds `.pop`; `revealRow()` flips; `bounceRow()` bounces.
- Knobs in `revealRow()`: `STAGGER = 300`, `FLIP = 500` (change `FLIP` **and** `.flip` together). The win window waits 1600 ms more for the bounce (`gameWon()`).
- **Only the picture is animated:** `tile_classes_visual` animates; `tile_classes` and the saved result are final at once. Never delay saving.
- Typing is blocked while tiles flip (`revealing` / `revealing_row`); keyboard colors update after the flip.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` in CSS and `reduceMotion()` in JS. Keep both for new animations.
- Browser tests call `wait_reveal(page, rows)` (`tests/test_smoke_browser.py`) after Enter.

## Checking a visual change
Run `.venv/bin/python scripts/screenshots.py`: phone-size screenshots of `/` (now the game it redirects to) and both games in `screenshots/`. It still loops over "light" and "dark" device settings, but both now look the same (dark only). Look at them and check contrast before committing.
