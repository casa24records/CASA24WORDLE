---
name: casa24-branding
description: Change Casa 24 Wordle's look — brand colors, light/dark mode, Kolo mascot art, logo slot, fonts and their licenses, favicons, tile animations. Use when editing style.css, theme.js, the tile animations in game.js, images, fonts, or when the owner shares new brand assets.
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
- **Dark-mode keys:** unused keys (`#5d6d61`) must be *lighter* than ruled-out letters (`#2b312d`), or players can't tell them apart.

## Start screen styles
`.c24-hero-kolo`, `.c24-today`, `.c24-play` / `.c24-play-main` (filled green, the player's language) / `.c24-play-alt` (outlined), `.c24-section-title`, `.c24-chip` (other languages) in `style.css`. They only use `--c24-*` tokens, so dark mode works automatically. The start screen must fit one phone screen (a test checks the height is under 2,000 px).

## Dark mode: `webapp/static/theme.js`
- Loaded in `<head>` of both pages, before anything renders, so there is no flash.
- Stores `casa24_theme` in localStorage as `auto`, `light` or `dark`. `auto` follows the device.
- Settings in the game has a "Tema/Theme" picker (`#theme-select`). The menu has a moon/sun button that calls `casa24ToggleTheme()`.

## Kolo and images
- Brand pack from the owner (Drive download): `KOLO/` (mascot), `Habitantes/` (member logos), `Fonts/`.
- In use, in `webapp/static/images/kolo/`:
  - `kolo-face.png`: Kolo Face, used for the **logo slot** in both headers and the favicons
  - `kolo-hero.png`: Young Kolo, on the menu
  - `kolo-win.png`: Rap Battle Kolo, on the win screen
  - `kolo-lose.png`: Baby Kolo, on the lose screen
- Rebuild or swap with `.venv/bin/python scripts/brand_assets.py "<brand pack folder>"`. Edit its `IMAGES` table to change which art is used. Output is reproducible.
- **Don't use:** "Kolo ft. Pikachu" (trademark), art showing alcohol (Chill Kolo, DJ Kolo), or Kolo Toilet in the public game. Never draw or invent new Kolo art.
- **Member logos:** not used. Using them needs each member's OK, and HEISEN's logo contains a swear word.
- Kolo art is © Casa 24 Records. It is listed in `CREDITS.md` and is not MIT-licensed.

## Fonts
- **VT323** (pixel font, SIL OFL) is used for titles and tiles. It is committed, with `VT323-OFL.txt`.
- **Gilroy** is commercial. Its files are in `webapp/static/fonts/` locally but **git-ignored**, so production falls back to the system font. Only commit them if the owner confirms a **webfont** license.
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
