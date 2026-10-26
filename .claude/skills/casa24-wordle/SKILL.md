---
name: casa24-wordle
description: Start here for anything about Casa 24 Wordle — what the game is, how it is built, the one-word-per-day rule, and which casa24-* skill covers words, text/accents, branding/dark mode, testing, deployment, or past decisions.
---

# Casa 24 Wordle (overview)

Casa 24 Records' daily word game, on branch `casa24`. Hosted on Vercel only. The owner is a beginner developer: explain changes in plain language, keep them small, commit after each step.

## What it is
- Flask app `webapp/app.py` + Vue 3 / Tailwind from CDNs (no build step) in `webapp/templates/` and `webapp/static/`.
- 10 languages in `webapp/data/languages/`: en, es, ar, fr, pt, ru, de, tr, vi, ko. Casa 24 words only in **es** and **en**.
- **One word per language per day, the same for every player.** It changes at midnight Panama time (UTC-5). About 1 day in 5 the es/en word is a Casa 24 word. Details: `casa24-daily-word`.
- No database, no accounts, no analytics. Player stats live in the browser's localStorage.
- Start screen (`/`): Español/English first (last played, else browser language) with "played today" and streak, then the other 8 languages. No links to other sites.

## Which skill to use
| Task | Skill |
|---|---|
| How the daily word is picked, change the 1-in-5 rate | `casa24-daily-word` |
| Add/remove/review words, tiers, aliases | `casa24-words` |
| UI text, translations, Spanish style, accents, keyboards, languages | `casa24-text-and-languages` |
| Colors, dark mode, Kolo art, fonts, logo, favicons, animations | `casa24-branding` |
| Run locally, tests, screenshots | `casa24-test-and-preview` |
| Put it online (Vercel), domain | `casa24-deploy` |
| Why things are the way they are (decisions already made) | `casa24-decisions` |

## Map of the repo
```
webapp/app.py            routes, data loading, Language class
webapp/daily.py          daily-word schedule (pure functions)
webapp/data/languages/   word lists, language_config.json, keyboards
webapp/templates/        index.html (start screen), game.html (game)
webapp/static/           game.js, index.js, theme.js, style.css, images/, fonts/, favicon/
scripts/                 merge_words.py, validate_words.py, brand_assets.py, screenshots.py, vercel_build.py, casa24/ (seed word CSVs)
tests/                   pytest + Playwright
DEPLOY.md, CREDITS.md, README.md, LICENSE (never delete; see casa24-decisions)
```

Quick commands (from the repo root):
```
.venv/bin/python -m pytest -q tests
cd webapp && ../.venv/bin/flask --app app run
```
