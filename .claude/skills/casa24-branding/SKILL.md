---
name: casa24-branding
description: Change Casa 24 Wordle's look — brand colors, light/dark mode, Kolo mascot art (including the random end-screen Kolo), logo slot, fonts and their licenses, favicons, tile animations. Use when editing style.css, theme.js, the tile animations in game.js, images, fonts, or when the owner shares new brand assets.
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
- **Dark-mode keys:** unused keys (`#5d6d61`) must be *lighter* than ruled-out letters (`#2b312d`), or players can't tell them apart.

## Header
Both pages use `.c24-header` (3 columns: icons, title, icons), `.c24-header-title`, the logo `.c24-logo`, the language badge `.c24-badge`, and `.c24-icon-btn` (44 px round icon buttons). Layout details: `casa24-responsive`.

## Start screen styles
`.c24-hero-kolo`, `.c24-today`, `.c24-play` / `.c24-play-main` (filled green, the player's language) / `.c24-play-alt` (outlined), `.c24-section-title`, `.c24-chip` (other languages) in `style.css`. `.c24-play-demo` is the dashed, transparent "🔒 Developer view" card (team only, shown when `DEMO_PASSWORD` is set). They only use `--c24-*` tokens, so dark mode works automatically. Developer view's own styles (`.c24-demo-bar`, `.c24-demo-lang`, `.c24-demo-btn`, the password page `.c24-demo-login*`) are in the "demo mode" section at the end of `style.css`, also token-only (the one fixed color is the wrong-password red `#d9534f`). The start screen must fit one phone screen (a test checks the height is under 2,000 px).

## Leaderboard styles
- All in the "leaderboard (es/en only; Discord login)" section of `style.css`, after the start-screen styles: the menu switch (`.c24-mode`, `.c24-mode-opt.is-active` filled green like the main Play button), notices (`.c24-notice`, `.c24-notice-warn` with an orange border), `.c24-lb-links`, the game's end-window block (`.c24-lb-end`, rank in VT323), the guest hint (`.c24-lb-hint`), and the `/leaderboard` page (`.c24-lb-*`: tabs, table, your own row with the `--c24-hover` background, an orange left mark and an orange "You/Tú" tag, buttons).
- In leaderboard games the header shows a **🏆 badge** (`.c24-badge.c24-badge-lb`, transparent, no padding) right after the language badge, so players can see they are playing for the ranking.
- **Tokens only** (`--c24-*`), so dark mode works with no extra rules. The only fixed colors are white text on the green active tab/option and the "Delete my data" red `#d9534f` (same red as the Developer view's wrong-password message).
- `/leaderboard` loads `style.css` and `theme.js` but not Tailwind, so it uses no Tailwind classes; it has the same header, logo slot and moon/sun theme button as the menu.

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
- **VT323** (pixel font, SIL OFL) is used for titles and tiles. It is committed, with `VT323-OFL.txt`. Its `@font-face` and a `<link rel="preload">` are in the `<head>` of `index.html` and `game.html` (not in `style.css`), so both use the same `?v=` URL. Still TTF; WOFF2 is pending the owner's OK (`casa24-responsive`).
- **Gilroy** is commercial. Its files are in `webapp/static/fonts/` locally but **git-ignored** (and in `.vercelignore`), so production falls back to the system font. Only commit them if the owner confirms a **webfont** license.
- Fonts are defined by `--c24-font-body` and `--c24-font-display`.

## Animations (tiles)
- **What happens:** a letter "pops" when typed, tiles flip one by one on Enter, and the winning row bounces (each tile 100 ms after the last).
- **Where it lives:**
  - `style.css`: keyframes `c24-pop`, `c24-flip`, `c24-bounce` and classes `.pop` (100 ms), `.flip` (500 ms), `.bounce` (1000 ms). The bounce delays are the `.bounce-d1`…`.bounce-d4` lines (`bounceRow()` adds them in reading order, so right-to-left rows bounce from the right).
  - `game.js`: `addChar` adds `.pop`; `revealRow()` does the flip; `bounceRow()` the win bounce.
- **Timing knobs** (in `revealRow()`): `STAGGER = 300` (wait between tiles) and `FLIP = 500` (one tile's flip). To change the flip speed, change `FLIP` **and** `.flip` in `style.css` to the same number, or colors change at the wrong moment. The win/lose pop-up waits for the reveal; the win waits 1600 ms more for the bounce (in `gameWon()`). If you make the bounce longer, raise that too.
- **Only the picture is animated.** `tile_classes_visual` is what the screen shows and is animated. `tile_classes` (saved in localStorage) gets the final colors right away, and the result is saved right away too. So a reload in the middle of a flip still shows the full, correct game. Never delay saving to match an animation.
- **Typing is blocked while tiles flip** (`revealing` / `revealing_row`). On-screen keyboard colors update after the flip, so they don't give the answer away early.
- **Right-to-left languages** flip from right to left (`final.length-1-i` in `revealRow()`).
- **Reduced motion:** if the device asks for less motion, the `@media (prefers-reduced-motion: reduce)` block in CSS turns animations off and `reduceMotion()` in JS skips them; colors appear at once. Keep both when adding a new animation.
- **Tests:** after Enter, browser tests must call `wait_reveal(page, rows)` (in `tests/test_smoke_browser.py`) before typing the next word, or the typing is ignored.

## Checking a visual change
Run `.venv/bin/python scripts/screenshots.py`. It saves menu and game screenshots in light and dark mode at phone size to `screenshots/`. Look at them and check contrast before committing.
