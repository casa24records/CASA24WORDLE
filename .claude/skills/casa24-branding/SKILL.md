---
name: casa24-branding
description: Change Casa 24 Wordle's look — brand colors, light/dark mode, Kolo mascot art, logo slot, fonts and their licenses, favicons. Use when editing style.css, theme.js, images, fonts, or when the owner shares new brand assets.
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

## Checking a visual change
Run `.venv/bin/python scripts/screenshots.py`. It saves menu and game screenshots in light and dark mode at phone size to `screenshots/`. Look at them and check contrast before committing.
