---
name: casa24-test-and-preview
description: Set up, run, test and preview Casa 24 Wordle locally — virtualenv, Flask dev server, pytest suite, Playwright browser tests, phone-size light/dark screenshots. Use before every commit and whenever asked to run, check, or show the game.
---

# Run, test, preview

## Setup (once)
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
```
Never install packages globally. Use `.venv/bin/pip`.

## Run the game
```
cd webapp && ../.venv/bin/flask --app app run --port 5050   # http://127.0.0.1:5050
```
- **Port 5000 is taken by macOS AirPlay on this Mac** (it answers 403). Use `--port 5050` → http://127.0.0.1:5050.
- Pages: `/` (menu), `/es`, `/en`, plus the other 8 language codes.
- **Developer view** (internally "demo") is off unless `DEMO_PASSWORD` is set. To try it locally, set it just for that run, with the password the owner chose (never write it in a file, test or commit):
  ```
  cd webapp && DEMO_PASSWORD='…' ../.venv/bin/flask --app app run --port 5050
  ```
  Then `/` shows the "🔒 Developer view" card → `/demo` → `/demo/es` or `/demo/en`. Without the variable, `/demo` is a 404 (expected).
- The pages load Vue 3.5.13 (jsdelivr) and Tailwind (Play CDN) from the internet, so they need a connection.

## Tests (from the repo root; all must pass before committing)
```
.venv/bin/python -m pytest -q tests
```
| File | Covers |
|---|---|
| `test_words.py` | validator passes, tiers don't overlap, Casa 24 words are valid guesses, aliases off, Spanish plurals accepted, no proper names |
| `test_daily.py` | same date same word, Panama midnight, 1 in 5 Casa 24 days |
| `test_smoke_browser.py` | start screen (10 local links, es/en first, fits a phone, remembers language, "Jugada hoy" after a win), a guess colors tiles in es/en, accents optional in es/fr/pt, colors respect accents (plain a ≠ á), `/stats` gone, a Kolo from `win/`/`lose/` after a win/loss (its `src` ends `.webp?v=…`), a repeated guess (also typed without accents) is refused (Playwright) |
| `test_input_bugs.py` | generated keyboards are alphabetical with ⇨ first and ⌫ last (es/en keep their layouts); Shift letters type lowercase; Ctrl/Cmd shortcuts don't type; typing in a Settings field isn't a guess; Turkish I/İ; physical Enter after tapping a key submits; Share fires once per tap |
| `test_kolo.py` | `KOLO_WIN`/`KOLO_LOSE` in `game.js` match the `win/`/`lose/` folders and `brand_assets.py`, pools don't overlap, no Pikachu, Kolo images are WebP only (only `kolo-hero.png` stays) |
| text-key tests | the result titles and `notification-repeated` exist in all 10 `language_config.json` files |
| `test_demo.py` | Developer view (`/demo`): off without `DEMO_PASSWORD` (no card, 404), login needed, wrong password refused, first open = the real daily word, Restart (`?skip=`) gives a random word that never repeats, other languages redirect to es, a new password logs old sessions out, normal `/es` isn't demo, the password never appears in pages; in the browser, Fill in word wins and nothing is saved to localStorage. Uses a **fake** password via `monkeypatch.setenv`, never the real one |
| `test_vercel_ready.py` | `webapp.app:app` loads from the repo root behind a proxy, sitemap uses the site's own address (no wordle.global), build step copies static files, `vercel.json` makes only `?v=` URLs immutable, every `/static/` URL on `/`, `/es`, `/en`, `/ar`, `/ko` has `?v=` |

`tests/conftest.py` puts `webapp/` and `scripts/` on the import path and changes into `webapp/`.

Also run `.venv/bin/python scripts/validate_words.py` after any word change.

## Screenshots
```
.venv/bin/python scripts/screenshots.py            # -> screenshots/ (git-ignored)
```
This saves 6 phone-size (390×844) images: the menu, es and en, each in light and dark. It types `cosas, jamon` in Spanish and `crane, music` in English, and prints any JavaScript errors. Read the images yourself and describe them to the owner. To save tokens, combine them into one picture with Pillow before viewing.

**Other screen sizes:** `screenshots.py` only does 390×844. For a layout change, check the sizes and measurements listed in `casa24-responsive` ("Sizes to test") with a throwaway Playwright script in the scratchpad (`is_mobile=True, has_touch=True` for phones).

## Gotchas
- `localStorage` is per browser profile. Each Playwright context starts clean.
- **Tile animation:** after Enter, tiles flip one by one for about 1.7 s. Keys typed during the flip are ignored. In browser tests, call `wait_reveal(page, rows)` (in `test_smoke_browser.py`) before asserting colors or typing the next word.
- **Count only board tiles** with the `BOARD_COLORED` selector (`main .grid-cols-5 > …`). The hidden "How to play" window has 3 example tiles that are always in the page.
- **Ending a game fast:** type today's word (win) or six different wrong words (loss). Repeating a word is refused now, so a loss test needs 6 different valid words, with `wait_reveal(page, n)` after each.
- **Forcing today's word in a test:** use `document.querySelector('#app').__vue_app__._container._vnode.component.proxy.todays_word = '…'` (the `VM` constant in the browser tests; still works with Vue 3.5.13). See `test_spanish_colors_respect_accents`.
- **Wait for Vue:** Vue and `game.js` load with `defer`, so wait with `page.wait_for_function("document.querySelector('#app') && window.Vue")` before touching the game.
- **Static URLs end in `?v=…`:** compare with `src.split("?v=")[0]` when checking a file name.
- **Kolo in the end screen** is `<img loading="lazy">`; it only loads once the stats window is open.
- **Reduced motion:** a Playwright context with `reduced_motion='reduce'` gets instant colors with no flip.
