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
- Pages: `/` (menu), `/es`, `/en` (only these two since 2026-10-29; old codes like `/fr` redirect to es/en).
- **Developer view** (internally "demo") is off unless `DEMO_PASSWORD` is set. To try it locally, set it just for that run, with the password the owner chose (never write it in a file, test or commit):
  ```
  cd webapp && DEMO_PASSWORD='…' ../.venv/bin/flask --app app run --port 5050
  ```
  Then `/` shows the "🔒 Developer view" card → `/demo` → `/demo/es` or `/demo/en`. Without the variable, `/demo` is a 404 (expected).
- **Leaderboard** (`/lb/es`, `/leaderboard`, the menu's guest/leaderboard switch) is off unless `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` and `SECRET_KEY` are set. Two ways to turn it on locally:
  - The owner runs `vercel env pull .env.local` (see `.env.example`). `app.py` reads `.env.local` on its own when not on Vercel and not under pytest, and never overrides variables already set. With `DATABASE_URL` in it, local play writes to the **real** database, so tell the owner first.
  - Or set the three variables just for that run (values from the owner, never in a file or commit) and leave `DATABASE_URL` out: the app then uses the in-memory store (lost on restart). Real Discord login only works if `http://127.0.0.1:5050/auth/discord/callback` is a redirect URL in the Discord app.
  Details: `casa24-leaderboard`.
- Everything (Vue, compiled Tailwind, fonts, the Discord SDK) is served from our own origin, so pages work offline. After adding Tailwind classes, rebuild with `scripts/build_css.py` (`casa24-deploy`).

## Tests (from the repo root; all must pass before committing)
```
.venv/bin/python -m pytest -q tests
```
**450 tests on 2026-10-29** (about 2 minutes; Playwright tests skip if Chromium isn't installed). Update this number when it changes a lot.
| File | Covers |
|---|---|
| `test_words.py` | validator passes, tiers don't overlap, Casa 24 words are valid guesses, aliases off, Spanish plurals accepted, no proper names |
| `test_daily.py` | same date same word, Panama midnight, 1 in 5 Casa 24 days |
| `test_languages.py` (new 2026-10-29) | only es/en folders, each ships its keyboard, `input_characters`, no right-to-left code left, daily words unchanged, old `/<code>` and `/lb/<code>` links redirect (browser language, query kept), unknown codes unchanged, APIs refuse old codes (400), 3 leaderboard tabs, sitemap and hreflang es/en only, Activity shell lists es/en + language rule + invite bridge, `purge_languages.py` (dry run changes nothing, export, `--execute` needs the approval flag, one transaction, constant parameterized SQL, needs `DATABASE_URL`) |
| `test_accents.py` (new 2026-10-29) | Spanish QWERTY rows (ñ after l), both Spanish layouts = 26 letters + ñ with no accent keys, English unchanged, fold keeps ñ (also decomposed), word lists are NFC, sonar ≠ soñar, every accented answer wins typed plain, accent groups without a plain form, colors fold vowels but not ñ (`game.js` and Python), duplicate letters, share is emoji-only, old saved accent-key colors fold |
| `test_layout.py` (new 2026-10-29) | Playwright size sweep of the NYT-style layout: web game fits with no scroll or overlap at phone/landscape/desktop sizes, phone header with facepile fits, Activity desktop fits, Activity phone keeps the bottom sheet, NYT proportions from 481px (`test_nyt_proportions_on_tablets_and_desktops`: tile unit ≤62px, keys 0.66×0.87 of a tile, keyboard 1.3–1.55× the board, both centered, 0.38t apart), the rail never moves or shrinks the board, rail cards even with nobody playing, board size reserved before Vue (no layout shift), accessibility basics (grid, labels, focus ring), focus order brand → actions → board → keyboard, Settings keyboard-layout choice fits, leaderboard tabs in one row |
| `test_smoke_browser.py` | start screen (2 language cards, fits a phone, remembers language, "Jugada hoy" after a win), a guess colors tiles in es/en, accents optional, a plain vowel greens an accented answer, an ñ word typed plain wins and shares colors only, `/stats` gone, a Kolo from `win/`/`lose/` after a win/loss (its `src` ends `.webp?v=…`), a repeated guess (also typed without accents) is refused (Playwright) |
| `test_input_bugs.py` | es/en default to QWERTY, Spanish layouts have ñ and no accent keys, the rendered keyboard matches the layout, the Alfabético setting; Shift letters type lowercase; Ctrl/Cmd shortcuts don't type; typing in a Settings field isn't a guess; physical ñ and accented keys (fold to the plain letter), dead/unknown keys ignored; physical Enter after tapping a key submits; Share fires once per tap |
| `test_kolo.py` | `KOLO_WIN`/`KOLO_LOSE` in `game.js` match the `win/`/`lose/` folders and `brand_assets.py`, pools don't overlap, no Pikachu, Kolo images are WebP only (only `kolo-hero.png` stays) |
| `test_text.py` | both languages found, new text keys present in es and en |
| `test_demo.py` | Developer view (`/demo`): off without `DEMO_PASSWORD` (no card, 404), login needed, wrong password refused, first open = the real daily word, Restart (`?skip=`) gives a random word that never repeats, other languages redirect to es, a new password logs old sessions out, normal `/es` isn't demo, the password never appears in pages; in the browser, Fill in word wins and nothing is saved to localStorage. Uses a **fake** password via `monkeypatch.setenv`, never the real one |
| `test_leaderboard.py` | leaderboard rules (points, ranking order, streaks, accent folding keeps ñ, server colors), the in-memory store, store choice, SQL is parameterized, Postgres store against a fake connection, `.env.local` loader; routes: off without env, login needed, answer never in the page, guess validation, other-site POST refused, accentless typing, a win counts once, 6 misses, client date ignored, new day, rate limit, guest routes never write, ranking rows and "my position", Combinado = es + en, tabs, delete my data, admin hide. `test_color_and_fold_match_game_js` runs the real `updateColors`/`foldAccents` from `game.js` in **node** and compares with the server's colors; it **skips** when `node` isn't installed |
| `test_discord_auth.py` | Discord login asks only for `identify`, keeps only ID, username and a valid avatar hash, bad/missing state fails, cancel, `next` must be a relative path, logout, tampered cookie ignored |
| `test_leaderboard_ui.py` | menu with/without the leaderboard (2 cards then Developer view, switch, privacy, sign-in lands on the last language), `/lb` page renders the server's state, guest end-window hint, `/leaderboard` table, live view (sidebar/rail, sheet, facepile, polling) against a faked `/api/live`, a full leaderboard game against a faked `/api/guess` |
| `test_live_rail.py` (new 2026-10-29) | NYT "Playing now" cards: avatar + mini grid only (147×80, 64px round avatar, name visually hidden but the accessible name, no live dot), web 1366×768 / 860×600 and Discord 1000×493 in light and dark, rail 16px left and 10px under the header, scrolls inside when long, phone sheet wraps the same cards, Discord phone invite card same size |
| `test_live.py` | `/api/live` and `store.live()`, plus presence (`test_presence_*`; see `casa24-live-view`) |
| `test_sync.py` | web ↔ Discord sync: the 9 owner cases, `attempt`/409, focus/visibility reloads, day rollover |
| `test_activity.py` | Discord Activity: shell, detection, CSP, token login, Bearer session, language rule (saved choice → Discord locale → picker after a timeout), invite, layout modes |
| `test_legal.py` | `/terms` and `/privacy` pages, links, delete my data as JSON |
| `test_vercel_ready.py` | `webapp.app:app` loads from the repo root behind a proxy, sitemap uses the site's own address, build step copies static files, `vercel.json` makes only `?v=` URLs immutable, every `/static/` URL on `/`, `/es`, `/en` has `?v=` |

`tests/lb_testlib.py` holds the leaderboard fixtures: a **fake Discord** (`FakeDiscord`, never calls Discord), the **in-memory store**, fake env values (`FAKE_SECRET_KEY`, never real ones) and a fixed date. Leaderboard tests never touch the real database; `app.py` skips `.env.local` under pytest.

`tests/conftest.py` puts `webapp/` and `scripts/` on the import path and changes into `webapp/`.

Also run `.venv/bin/python scripts/validate_words.py` after any word change.

## Screenshots
```
.venv/bin/python scripts/screenshots.py            # -> screenshots/ (git-ignored)
```
This saves 6 phone-size (390×844) images: the menu, es and en, each in light and dark. It types `cosas, jamon` in Spanish and `crane, music` in English, and prints any JavaScript errors. Read the images yourself and describe them to the owner. To save tokens, combine them into one picture with Pillow before viewing.

**Other screen sizes:** `screenshots.py` only does 390×844 (unchanged). For a layout change, run `tests/test_layout.py` (it measures fit, overlap, square tiles and key sizes at many sizes, web and Discord). For pictures at other sizes, use a throwaway Playwright script in the scratchpad (`is_mobile=True, has_touch=True` for phones); sizes in `casa24-responsive`.

## Gotchas
- `localStorage` is per browser profile. Each Playwright context starts clean.
- **Tile animation:** after Enter, tiles flip one by one for about 1.7 s. Keys typed during the flip are ignored. In browser tests, call `wait_reveal(page, rows)` (in `test_smoke_browser.py`) before asserting colors or typing the next word.
- **Count only board tiles** with the `BOARD_COLORED` selector (`main .grid-cols-5 > …`). The hidden "How to play" window has 3 example tiles that are always in the page.
- **Ending a game fast:** type today's word (win) or six different wrong words (loss). Repeating a word is refused now, so a loss test needs 6 different valid words, with `wait_reveal(page, n)` after each.
- **Forcing today's word in a test:** use `document.querySelector('#app').__vue_app__._container._vnode.component.proxy.todays_word = '…'` (the `VM` constant in the browser tests; still works with Vue 3.5.13). See `test_plain_vowel_greens_accented_answer`.
- **Wait for Vue:** Vue and `game.js` load with `defer`, so wait with `page.wait_for_function("document.querySelector('#app') && window.Vue")` before touching the game.
- **Static URLs end in `?v=…`:** compare with `src.split("?v=")[0]` when checking a file name.
- **Kolo in the end screen** is `<img loading="lazy">`; it only loads once the stats window is open.
- **Reduced motion:** a Playwright context with `reduced_motion='reduce'` gets instant colors with no flip.
