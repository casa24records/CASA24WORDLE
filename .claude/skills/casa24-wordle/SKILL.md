---
name: casa24-wordle
description: Start here for anything about Casa 24 Wordle — what the game is, how it is built, what happens when a player presses Enter (game flow, repeated guesses, win/lose end screen), the one-word-per-day rule, and which casa24-* skill covers words, text/accents, branding/dark mode/Kolo/animations, testing, deployment, git/GitHub, or past decisions.
---

# Casa 24 Wordle (overview)

Casa 24 Records' daily word game, on branch `casa24`. Hosted on Vercel only. The owner is a beginner developer: explain changes in plain language, keep them small, commit after each step.

## What it is
- Flask app `webapp/app.py` + Vue 3.5 (jsdelivr) and Tailwind (Play CDN) from CDNs, no build step of our own, in `webapp/templates/` and `webapp/static/`.
- 10 languages in `webapp/data/languages/`: en, es, ar, fr, pt, ru, de, tr, vi, ko. Casa 24 words only in **es** and **en**.
- **One word per language per day, the same for every player.** It changes at midnight Panama time (UTC-5). About 1 day in 5 the es/en word is a Casa 24 word. Details: `casa24-daily-word`.
- No database, no accounts, no analytics. Player stats live in the browser's localStorage.
- Start screen (`/`): Español/English first (last played, else browser language) with "played today" and streak, then the other 8 languages. No links to other sites.
- **Developer view** (internally "demo"; team only, on when the `DEMO_PASSWORD` env var is set): a "🔒 Developer view" card on `/` → `/demo` (password page, `demo_login.html`, es+en side by side) → signed session cookie (30 days) → `/demo/es` or `/demo/en` (other codes redirect to es). It acts like the real game and opens with the real word of the day; the only extras are two buttons in `.c24-demo-bar`: ↻ Restart goes to `?skip=<word>`, and `demo_game()` in `app.py` then picks a random answer from the daily-word pool, never the same word. ✓ Fill in word (`demoFillAnswer()`) types the answer and presses Enter, so the normal win flow runs. The `DEMO` constant in `game.html` makes `game.js` skip every localStorage save/load, results, stats and `casa24_lang`; the end window is the normal one. Responses are `no-store`, not in the sitemap. No `DEMO_PASSWORD` → no card, `/demo` is 404. Why: `casa24-decisions`; env setup: `casa24-deploy`.

## What happens on Enter (`keyDown` in `webapp/static/game.js`)
1. Row not full: "partial word" notification. Typing is ignored while `game_over` or while tiles flip (`revealing`).
2. `resolveAccents()`: in es/fr/pt, `cancion` becomes `canción` (see `casa24-text-and-languages`).
3. `checkWord()`: is it in the word lists? If not: "not valid" notification.
4. Repeat check: a word already guessed in this game is refused with `notification-repeated`; nothing flips.
5. `updateColors()` sets final colors right away (saved to localStorage at once); `revealRow()` flips the tiles one by one, then the keyboard colors update. A win also runs `bounceRow()`.
6. `gameWon(reveal_ms)` / `gameLost(reveal_ms)` (6th wrong guess): end the game and save the result immediately; after the flip, show the word as a notification, then open the stats window (win: +1600 ms for the bounce, loss: +400 ms).
7. The stats window shows a title (`result_won` / `result_lost`, class `c24-result`), then one random Kolo (`pickKolo()`, saved as `kolo_image`), the emoji grid, the countdown, Share, and the stats numbers. Markup: "stats modal" in `game.html`.
Animations and Kolo pictures: `casa24-branding`.

## Which skill to use
| Task | Skill |
|---|---|
| How the daily word is picked, change the 1-in-5 rate | `casa24-daily-word` |
| Add/remove/review words, tiers, aliases | `casa24-words` |
| UI text, translations, Spanish style, accents, keyboards, languages | `casa24-text-and-languages` |
| Colors, dark mode, Kolo art (end-screen Kolo), fonts, logo, favicons, tile animations | `casa24-branding` |
| Run locally, tests, screenshots | `casa24-test-and-preview` |
| Put it online (Vercel), domain | `casa24-deploy` |
| Commit, push to GitHub, which account, history rules | `casa24-git-and-github` |
| Mobile/desktop layout, screen sizes, zoom, landscape, page speed | `casa24-responsive` |
| Developer view / demo (`/demo`): env var and password `casa24-deploy`, run locally `casa24-test-and-preview`, why `casa24-decisions` (how it works: above) | `casa24-deploy` |
| Why things are the way they are (decisions already made) | `casa24-decisions` |

## Map of the repo
```
webapp/app.py            routes (/, /<lang>, /demo, /demo/<lang>, /sitemap.xml), data loading, Language class (keyboards: _generate_alphabetical_keyboard),
                         template helpers asset() (?v= URLs), asset_version(), json_script()
webapp/daily.py          daily-word schedule (pure functions)
webapp/data/languages/   word lists, language_config.json, keyboards
webapp/templates/        index.html (start screen), game.html (game, also Developer view with demo=True),
                         demo_login.html (Developer view password page)
webapp/static/           game.js, index.js, theme.js, style.css, images/kolo/ (WebP), fonts/, favicon/
scripts/                 merge_words.py, validate_words.py, brand_assets.py, screenshots.py, vercel_build.py, casa24/ (seed word CSVs)
tests/                   pytest + Playwright
vercel.json              year-long caching for /static/ URLs with ?v= (see casa24-deploy)
pyproject.toml, .vercelignore, .python-version   Vercel setup
DEPLOY.md, CREDITS.md, README.md, LICENSE (never delete; see casa24-decisions)
```

Quick commands (from the repo root):
```
.venv/bin/python -m pytest -q tests
cd webapp && ../.venv/bin/flask --app app run --port 5050   (port 5000 is macOS AirPlay)
```
