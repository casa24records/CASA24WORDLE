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
cd webapp && ../.venv/bin/flask --app app run      # http://127.0.0.1:5000
```
- Pages: `/` (menu), `/es`, `/en`, plus the other 8 language codes.
- The pages load Vue and Tailwind from CDNs, so they need internet.

## Tests (from the repo root; all must pass before committing)
```
.venv/bin/python -m pytest -q tests
```
| File | Covers |
|---|---|
| `test_words.py` | validator passes, tiers don't overlap, Casa 24 words are valid guesses, aliases off, Spanish plurals accepted, no proper names |
| `test_daily.py` | same date same word, Panama midnight, 1 in 5 Casa 24 days |
| `test_smoke_browser.py` | start screen (10 local links, es/en first, fits a phone, remembers language, "Jugada hoy" after a win), a guess colors tiles in es/en, accents optional in Spanish, `/stats` gone (Playwright) |
| `test_vercel_ready.py` | `webapp.app:app` loads from the repo root behind a proxy, build step copies static files |

`tests/conftest.py` puts `webapp/` and `scripts/` on the import path and changes into `webapp/`.

Also run `.venv/bin/python scripts/validate_words.py` after any word change.

## Screenshots
```
.venv/bin/python scripts/screenshots.py            # -> screenshots/ (git-ignored)
```
This saves 6 phone-size (390×844) images: the menu, es and en, each in light and dark. It types `cosas, jamon` in Spanish and `crane, music` in English, and prints any JavaScript errors. Read the images yourself and describe them to the owner. To save tokens, combine them into one picture with Pillow before viewing.

## Gotchas
- The app prints upstream stats on import. That is noise, not an error.
- `localStorage` is per browser profile. Each Playwright context starts clean.
