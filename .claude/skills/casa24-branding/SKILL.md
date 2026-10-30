---
name: casa24-branding
description: Change Casa 24 Wordle's look — brand colors, light/dark mode, Kolo mascot art (including the random end-screen Kolo), logo slot, fonts and their licenses, favicons, tile animations, the NYT-style game header, live view look (rail cards, invite card). Use when editing style.css, theme.js, the tile animations in game.js, images, fonts, or when the owner shares new brand assets.
---

# Branding and themes

## Theme in one place: `webapp/static/style.css`
- **Brand colors** (top `:root`):
  - Kolo orange `#ff7944`
  - hoodie green `#1f5a33`
  - forest `#163119`
  - cream `#f4efe6`
  - sand `#cfc5b6`
  - ink `#0a0b09`
- **Tile colors:**
  - correct: green, white text
  - wrong spot: orange, **dark** text, because white on orange fails contrast
  - absent: gray
- **Share grid:** 🟩 🟧 ⬜, set in `game.js` `emoji_board`.
- **Surface tokens** (`--c24-bg`, `--c24-surface`, `--c24-text`, `--c24-subtle`, `--c24-line`, `--c24-key-bg`, ...): light values are in `:root`. Dark values appear **twice** and must stay identical:
  - `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` (automatic)
  - `:root[data-theme="dark"]` (forced)
- The original Tailwind classes (`bg-white`, `text-neutral-500`, `border-gray-300`, ...) are remapped to tokens in the "base" section. A newly used Tailwind color class needs a mapping there, or it will look wrong in dark mode.
- **Browser bar color** (`theme-color` meta in both templates): light `#f4efe6` (cream), dark `#0f1a12`. Change them together with `--c24-bg` if the background changes.
- **Hover** styles go only inside `@media (hover: hover) and (pointer: fine)` at the end of `style.css`, so they don't stick after a tap on phones.
- **`--c24-live`** (was the green "en vivo" dot of the live view; **unused since 2026-10-29**, when the cards lost their visible status): light `#1f8a46`, dark `#4cc477`. It is in **all three theme blocks** (`:root`, the dark media query, `:root[data-theme="dark"]`); keep the two dark values identical.
- **Dark-mode keys:** unused keys (`#5d6d61`) must be *lighter* than ruled-out letters (`#2b312d`), or players can't tell them apart.

## Header
**Game pages (2026-10-29, NYT structure with Casa 24's look):** `.c24-header-bar`, a 2-area bar. **Brand left:** Kolo logo `.c24-logo` + "Casa 24" (`.c24-title-text`, VT323) + language badge `.c24-badge` (and the trophy badge on `/lb/`); inside the Discord Activity the brand is the "Casa 24 ES ▾" language button `.c24-lang-btn`. **Actions right**, all `.c24-icon-btn` (44px, line SVG icons): people/facepile, help, trophy (leaderboard), stats, settings, then the Discord avatar. 48/52/60px tall; only the "Casa 24" text hides when narrow (Kolo and badge stay). Layout details and breakpoints: `casa24-responsive`.
**Menu and `/leaderboard`:** `.c24-header` (3 columns: icons, title, icons), `.c24-header-title`.
- **Discord slot, when the leaderboard is on (owner, 2026-10-26/27):** the logged-in player's **round Discord avatar**; logged out, a small Discord-logo icon button. On the menu (top-left) the **trophy icon** (link to `/leaderboard`) follows, then the info button (hidden under 420 px wide); in the game bar the avatar is at the right end. Tapping the avatar opens a small popover (@username, Ver leaderboard, Cerrar sesión, and Borrar mis datos only on `/leaderboard`). The avatar picture comes from Discord's CDN (how: `casa24-leaderboard`).
- **People button on the leaderboard game (where there is no rail):** a **facepile** of up to 3 round avatars (2 under 400px; `.c24-face`, 22px, a 2px `--c24-bg` ring so they separate) when others are playing, else a **"people" line SVG icon** (same stroke style as the other header icons, no emoji); both in `.c24-live-btn` with a small orange count badge, opening the live view sheet (owner, 2026-10-28).
- **Focus ring** (keys, icon buttons): 3px Casa 24 orange + a thin inner ring in the text color, because orange alone is only 2.3:1 on cream.
- **Nothing may overlap** at any width (320, 375, 390, 844×390 landscape, 768, 1366).
- **Discord desktop ≥768px wide (2026-10-29):** the header bar spans the full panel like NYT (also on short panels such as 1000×493).
- **Board and keys (2026-10-29):** from 481px wide (and in Discord desktop) sizes follow NYT's proportions from one tile unit (keys 0.66 × 0.87 of a tile, key font 0.3 of a tile); details in `casa24-responsive`.

## Start screen styles
`.c24-hero-kolo`, `.c24-today`, `.c24-play` / `.c24-play-main` (filled green, the player's language) / `.c24-play-alt` (outlined, the other of Español/English) in `style.css`. **`.c24-section-title` and `.c24-chip` were removed** with the "Más idiomas" chips; don't bring them back. Card names use VT323 (`.c24-play-name`, 2rem, uppercase). `.c24-play-demo` is the dashed, transparent "🔒 Developer view" card (team only, shown when `DEMO_PASSWORD` is set). They only use `--c24-*` tokens, so dark mode works automatically. Developer view's own styles (`.c24-demo-bar`, `.c24-demo-lang`, `.c24-demo-btn`, the password page `.c24-demo-login*`) are in the "demo mode" section at the end of `style.css`, also token-only (the one fixed color is the wrong-password red `#d9534f`). Keep the start screen compact; a test checks the page stays under 2,000 px tall.

## Leaderboard styles
- In the "leaderboard (every language; Discord login)" section of `style.css`, after the start-screen styles, plus a Discord section after it: the menu's Discord area (`.c24-dc-area`: sign-in button + small privacy link), the logged-in "play as guest" switch (`.c24-guest-toggle`, `.c24-switch`), header avatar/popover (`.c24-dc-me`, `.c24-dc-avatar-head` with a thin Blurple ring, `.c24-dc-pop`), toasts (`.c24-dc-toast`, `.c24-dc-toast-warn`), the privacy dialog (`.c24-privacy`),, the game's end-window block (`.c24-lb-end`; rank and points as big VT323 numbers `.c24-lb-big` with small uppercase labels `.c24-lb-small`), the guest hint (`.c24-lb-hint`), and the `/leaderboard` page (`.c24-lb-*`: tabs, table, your own row with the `--c24-hover` background, an orange left mark and an orange "You/Tú" tag, buttons).
- **Trophy icon, not emoji:** leaderboard access and the leaderboard-game marker use a **line trophy SVG** (`dc.trophy()` in `templates/_discord.html`: `stroke="currentColor"`, stroke-width 2, round caps, same style as the other header icons). The 🏆 emoji is not used anywhere; don't bring it back. No "Ver leaderboard" text link in the menu.
- **Official Discord sign-in button** (`dc.button()`, class `.c24-dc-btn`): Discord **Blurple `#5865F2`**, the **white official Discord logo** as inline SVG (`dc.logo()`, `fill="currentColor"`), white text, **48 px** tall, hover **`#4752C4`** (inside the hover media query). This fixed brand color is an **allowed exception** to the tokens-only rule; keep it the same in light and dark mode. Don't recolor or redraw the Discord logo.
- **Less text:** notices are short auto-dismiss toasts (`.c24-dc-toast`), privacy is a small "ⓘ Privacidad" link opening a dialog (`.c24-privacy`), the end window shows rank/points as big numbers, "Borrar mis datos" is secondary (only in the avatar popover on `/leaderboard`).
- **Tokens only** (`--c24-*`), so dark mode works with no extra rules. The only fixed colors are Discord Blurple (above), white text on the green active tab and on the Blurple button, the white knob of the guest switch (`.c24-switch`), and the "Delete my data" red `#d9534f` (same red as the Developer view's wrong-password message).
- The `/leaderboard` title `.c24-lb-title` is VT323. The 3 tabs (Combinado, Español, English) are one row of equal pill buttons in the body font.
- `/leaderboard` loads `style.css` and `theme.js` but not Tailwind, so it uses no Tailwind classes; it has the same header, logo slot and moon/sun theme button as the menu.

## Live view styles
The "live view" section of `style.css` (after the leaderboard styles; feature: `casa24-live-view`, layout: `casa24-responsive`). Token-only:
- `.c24-live` (rail ≥860px: transparent, floating in the left gutter, 16px from the edge, no title shown; otherwise a bottom sheet on `--c24-surface` with rounded top corners, a shadow and the title), `.c24-live-backdrop` (black, 35%).
- **Cards `.c24-live-card` = NYT "Playing now" (refined 2026-10-29, team: "solo el profile y el grid"), same in rail and sheet:** 147×80 (`--c24-card-w`, `--c24-card-h` on `.c24-live`), transparent, 1px `--c24-line` border, 8px radius, 9px apart (`--c24-card-gap`; the sheet wraps them in a grid). Inside: a **64px round avatar** `.c24-live-avatar` (`--c24-hover` while loading) and the mini board, **nothing else visible**. The @name and live/won/lost status are in the visually hidden `.c24-live-info` (screen readers) plus `title="@name"`. **The live dot and ✓/✗ badges are gone** (`.c24-live-dot`, `.c24-live-result` styles removed); the `--c24-live` token is still defined in the three theme blocks but no longer used.
- **Invite card** (Discord only, first in the rail/sheet, 2026-10-29): `.c24-live-invite`, **same size and border as a player card**, a 64px green circle `.c24-live-invite-icon` (`--c24-correct-bg`, 30px line icon) and the label `activity_invite` (12px, bold, uppercase, up to 2 lines); `--c24-hover` on hover.
- Title `.c24-live-title` (small uppercase, `--c24-subtle`) with a count pill `.c24-live-count` (`--c24-hover`), sheet only.
- Mini board `.c24-live-grid`: 6×5 squares of 9px (gaps 2px × 1.75px, 1px radius), using the tile tokens `--c24-correct-bg`, `--c24-present-bg`, `--c24-absent-bg`; empty cells are outlined at 70% opacity. In dark mode the absent squares get a `--c24-line-strong` border so they stand out. **Never put letters in them.**
- Header button badge `.c24-live-badge`: orange (`--c24-orange`) with ink text.

## Dark mode: `webapp/static/theme.js`
- Loaded in `<head>` of every page (menu, game, `/leaderboard`), before anything renders, so there is no flash.
- Stores `casa24_theme` in localStorage as `auto`, `light` or `dark`. `auto` follows the device.
- Settings in the game has a "Tema/Theme" picker (`#theme-select`). The menu has a moon/sun button that calls `casa24ToggleTheme()`.

## Kolo and images
- Brand pack from the owner (Drive download): `KOLO/` (mascot), `Habitantes/` (member logos), `Fonts/`.
- **Kolo pictures are WebP only** (owner's decision, 2026-10-26). The PNGs were deleted. In `webapp/static/images/kolo/`:
  - `kolo-face.webp`: Kolo Face, the **logo slot** in both headers (source of the favicons too)
  - `kolo-hero.webp`: Young Kolo, on the menu
  - `kolo-hero.png`: the **only PNG left**, for link previews (`og:image` / `twitter:image`), because some sites' crawlers want PNG/JPEG. Don't delete it.
  - `win/` and `lose/`: the end-of-game window shows **one Kolo picked at random per game** (decided 2026-10-26).
    - All `.webp`. Win (any number of guesses), 12 pictures: `car` (Car Kolo), `chill` (Chill Kolo), `dj` (DJ Kolo), `face` (Kolo Face), `hoodie` (Hoodie Kolo), `montuno` (Montuno), `pizza` (Pizza Kolo), `prod` (Prod by Kolo), `rap-battle` (Rap Battle Kolo), `ross` (Kolo Ross (Stained)), `young` (Young Kolo), `young-cropped` (Cropped - Young Kolo).
    - Loss, 2 pictures: `baby` (Baby Kolo), `toilet` (Kolo Toilet).
    - Win pictures are at most 300 px tall, loss pictures 240 px.
    - Shown in the stats window under the won/lost title (`.c24-result`, VT323 2rem; text keys in `casa24-text-and-languages`). The picture uses `.c24-kolo` (max 160 px tall on screen).
    - In `game.js`, `pickKolo()` chooses one in `gameWon()` / `gameLost()`. The choice is saved as `kolo_image` (for example `win/pizza.webp`) in localStorage, so reloading the page that day shows the same Kolo. `kolo_url()` builds the address (`/static/images/kolo/win/pizza.webp?v=…`) and turns an old saved `.png` name into `.webp`.
- Favicons in `webapp/static/favicon/`: `favicon.ico` (holds 16, 32 and 48 px), `apple-touch-icon.png`, `android-chrome-192x192.png`, `android-chrome-512x512.png`, `site.webmanifest`. There are no separate 16/32 px pngs.
- Rebuild or swap with `.venv/bin/python scripts/brand_assets.py "<brand pack folder>"` (the folder that has `KOLO/` inside). It writes:
  - every Kolo picture as WebP (quality 85, transparency kept): `IMAGES` (logo, menu), `WIN`, `LOSE`
  - a PNG copy only for the names in `ALSO_PNG` (just `kolo-hero.webp` → `kolo-hero.png`)
  - the favicons (PNG/ICO, Kolo's face on cream)
  Edit `IMAGES` to change the logo or menu art. Output is reproducible.
- In templates, always link pictures with `{{ asset('images/kolo/…') }}` (adds `?v=`; see `casa24-deploy`). Set `width`/`height` on `<img>` so the page doesn't jump.
- **To add or remove an end-screen Kolo:**
  1. Add or remove the line in `WIN` or `LOSE` in `scripts/brand_assets.py` (new file name ending in **`.webp`** -> original file name in `KOLO/`).
  2. Rerun the script above (delete a removed picture's file from `win/` or `lose/` yourself).
  3. Add or remove the same `.webp` name in `KOLO_WIN` or `KOLO_LOSE` at the top of `game.js`.
  4. Run the tests: `tests/test_kolo.py` checks that the lists, the folders and `brand_assets.py` all match, and that no PNG is back except `kolo-hero.png`.
- **Don't use:** "Kolo ft. Pikachu" (trademark), anywhere, ever. A test checks for it. The owner allowed the alcohol art (Chill Kolo, DJ Kolo) and Kolo Toilet on 2026-10-26. Never draw or invent new Kolo art.
- **Member logos:** not used. Using them needs each member's OK, and HEISEN's logo contains a swear word.
- Kolo art is © Casa 24 Records. It is listed in `CREDITS.md` and is not MIT-licensed.

## Fonts
- **VT323** (pixel font, SIL OFL) is used for titles and tiles. It covers Spanish and English (á é í ó ú ü ñ). If a non-Latin language is ever added, its text in VT323 spots needs a `:lang()` rule to the body font. It is committed, with `VT323-OFL.txt`. Its `@font-face` and a `<link rel="preload">` are in the `<head>` of `index.html` and `game.html` (not in `style.css`), so both use the same `?v=` URL. Still TTF; WOFF2 is pending the owner's OK (`casa24-responsive`).
- **Gilroy** is commercial. Its files are in `webapp/static/fonts/` locally but **git-ignored** (and in `.vercelignore`), so production falls back to the system font. Only commit them if the owner confirms a **webfont** license.
- Fonts are defined by `--c24-font-body` and `--c24-font-display`.

## Animations (tiles)
- **What happens:** a letter "pops" when typed, tiles flip one by one on Enter, and the winning row bounces (each tile 100 ms after the last).
- **Where it lives:**
  - `style.css`: keyframes `c24-pop`, `c24-flip`, `c24-bounce` and classes `.pop` (100 ms), `.flip` (500 ms), `.bounce` (1000 ms). The bounce delays are the `.bounce-d1`…`.bounce-d4` lines (`bounceRow()` adds them left to right).
  - `game.js`: `addChar` adds `.pop`; `revealRow()` does the flip; `bounceRow()` the win bounce.
- **Timing knobs** (in `revealRow()`): `STAGGER = 300` (wait between tiles) and `FLIP = 500` (one tile's flip). To change the flip speed, change `FLIP` **and** `.flip` in `style.css` to the same number, or colors change at the wrong moment. The win/lose pop-up waits for the reveal; the win waits 1600 ms more for the bounce (in `gameWon()`). If you make the bounce longer, raise that too.
- **Only the picture is animated.** `tile_classes_visual` is what the screen shows and is animated. `tile_classes` (saved in localStorage) gets the final colors right away, and the result is saved right away too. So a reload in the middle of a flip still shows the full, correct game. Never delay saving to match an animation.
- **Typing is blocked while tiles flip** (`revealing` / `revealing_row`). On-screen keyboard colors update after the flip, so they don't give the answer away early.
- **Reduced motion:** if the device asks for less motion, the `@media (prefers-reduced-motion: reduce)` block in CSS turns animations off and `reduceMotion()` in JS skips them; colors appear at once. Keep both when adding a new animation.
- **Tests:** after Enter, browser tests must call `wait_reveal(page, rows)` (in `tests/test_smoke_browser.py`) before typing the next word, or the typing is ignored.

## Checking a visual change
Run `.venv/bin/python scripts/screenshots.py`. It saves menu and game screenshots in light and dark mode at phone size to `screenshots/`. Look at them and check contrast before committing.
