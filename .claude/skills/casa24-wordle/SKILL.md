---
name: casa24-wordle
description: Start here for anything about Casa 24 Wordle — what the game is, how it is built, guest vs leaderboard (Discord) modes and their routes, the live view (who is playing today), what happens when a player presses Enter (game flow, repeated guesses, win/lose end screen), the one-word-per-day rule, and which casa24-* skill covers words, text/accents, branding/dark mode/Kolo/animations, testing, deployment, git/GitHub, or past decisions.
---

# Casa 24 Wordle (overview)

Casa 24 Records' daily word game. Published from `main`; feature work happens on its own branch (see `casa24-git-and-github`). Hosted on Vercel only. The owner is a beginner developer: explain changes in plain language, keep them small, commit after each step.

## What it is
- Flask app `webapp/app.py` + Vue 3.5 (jsdelivr) and Tailwind (Play CDN) from CDNs, no build step of our own, in `webapp/templates/` and `webapp/static/`.
- 10 languages in `webapp/data/languages/`: en, es, ar, fr, pt, ru, de, tr, vi, ko. Casa 24 words only in **es** and **en**.
- **One word per language per day, the same for every player.** It changes at midnight Panama time (UTC-5). About 1 day in 5 the es/en word is a Casa 24 word. Details: `casa24-daily-word`.
- **Two ways to play:**
  - **Guest** (default, all 10 languages): no account, nothing sent to the server. Stats live in the browser's localStorage.
  - **Leaderboard** (es and en only): sign in with Discord (scope `identify`; the Discord ID, username and avatar hash are stored). The server checks and colors every guess, keeps the score in a Postgres database, and ranks players. The browser never gets the answer until the game is over. Off (all its routes 404) unless the Discord env vars, `SECRET_KEY` and a store are there. Details, scoring, privacy and storage: `casa24-leaderboard`. While playing, a **live view** shows the other leaderboard players of today's word (avatar, @username, a mini board of colors only): `casa24-live-view`.
- No analytics.
- Start screen (`/`): Español/English cards first (last played, else browser language) with "played today" and streak, then the other 8 languages. No links to other sites. When the leaderboard is on (owner rule: less text, the UI speaks for itself):
  - **Logged out:** the official Discord sign-in button (Blurple, server-rendered so it shows at once) above the cards, plus a small "ⓘ Privacidad" link that opens a `<dialog>` (the full privacy text lives only there). The cards play the guest game.
  - **Logged in:** the cards go to `/lb/es`, `/lb/en` (trophy icon on the card); a small switch "Jugar como invitado (no cuenta)" sends them to the guest game instead, remembered as `casa24_mode=guest` in localStorage.
  - **Header top-left:** the player's Discord avatar (popover: @username, Ver leaderboard, Cerrar sesión) or, logged out, a small Discord icon; then a line trophy icon linking to `/leaderboard`; then the info button (hidden under 420 px). No 🏆 emoji anywhere.
  - Login failed/cancelled and "data deleted" are short toasts (6 s, ×). Discord texts show in one language (`<html lang>` from Accept-Language, then `index.js` sets the player's language).
- **Developer view** (internally "demo"; team only, on when the `DEMO_PASSWORD` env var is set): a "🔒 Developer view" card on `/` → `/demo` (password page, `demo_login.html`, es+en side by side) → signed session cookie (30 days) → `/demo/es` or `/demo/en` (other codes redirect to es). It acts like the real game and opens with the real word of the day; the only extras are two buttons in `.c24-demo-bar`: ↻ Restart goes to `?skip=<word>`, and `demo_game()` in `app.py` then picks a random answer from the daily-word pool, never the same word. ✓ Fill in word (`demoFillAnswer()`) types the answer and presses Enter, so the normal win flow runs. The `DEMO` constant in `game.html` makes `game.js` skip every localStorage save/load, results, stats and `casa24_lang`; the end window is the normal one. Responses are `no-store`, not in the sitemap. No `DEMO_PASSWORD` → no card, `/demo` is 404. Why: `casa24-decisions`; env setup: `casa24-deploy`.

## Routes
- Guest: `/`, `/<lang>`, `/sitemap.xml`. Developer view: `/demo`, `/demo/<lang>`.
- Leaderboard (all 404 when it's off):
  - `/lb/<lang>` (es/en; other codes go to `/lb/es`): the game in leaderboard mode, same `game.html` with `lb=True`, a line trophy badge, the avatar menu and the live view's people button in the header (sidebar instead from 1024px). Not logged in → Discord login first.
  - `/leaderboard?tab=es|en|all`: public ranking page (`leaderboard.html`); compact line under the table (avatar + @username, or the sign-in button) and the privacy link; "Borrar mis datos" is in the avatar popover.
  - `/auth/discord/login?next=…`, `/auth/discord/callback`, `/auth/logout` (POST): Discord login; the signed `c24_lb` cookie holds only the Discord ID. After login the redirect carries `#dc=<avatar hash>`, which the page keeps in localStorage `c24_dc_avatar` for the header; since 2026-10-27 the server also stores the hash for the live view. Cancel → `/?login=cancelled`, other errors → `/?login=failed`.
  - `/api/guess` (POST, JSON `{lang, guess}`): checks and colors one guess.
  - `/api/live?lang=es|en` (GET, logged in): other players today, colors only; polled every 8 s by `game.js`. See `casa24-live-view`.
  - `/api/me/delete` (POST): "Delete my data", removes the player and all results.
  - `/admin/hide` (POST): admins (`ADMIN_DISCORD_IDS`) hide a name on the ranking.

## What happens on Enter (`keyDown` in `webapp/static/game.js`)
1. Row not full: "partial word" notification. Typing is ignored while `game_over` or while tiles flip (`revealing`).
2. `resolveAccents()`: in es/fr/pt, `cancion` becomes `canción` (see `casa24-text-and-languages`).
3. `checkWord()`: is it in the word lists? If not: "not valid" notification.
4. Repeat check: a word already guessed in this game is refused with `notification-repeated`; nothing flips.
5. `updateColors()` sets final colors right away (saved to localStorage at once); `commitRow()` moves to the next row and `revealRow()` flips the tiles one by one, then the keyboard colors update. A win also runs `bounceRow()`.
6. `gameWon(reveal_ms)` / `gameLost(reveal_ms)` (6th wrong guess): end the game and save the result immediately; after the flip, show the word as a notification, then open the stats window (win: +1600 ms for the bounce, loss: +400 ms).
7. The stats window shows a title (`result_won` / `result_lost`, class `c24-result`), then one random Kolo (`pickKolo()`, saved as `kolo_image`), the emoji grid, the countdown, Share, and the stats numbers. Markup: "stats modal" in `game.html`.
Animations and Kolo pictures: `casa24-branding`.

**Leaderboard mode** (`LB` is true in `game.html`; the page has no answer, `todays_word` is empty):
1. Row not full: same "partial word" notification. Typing also waits while a guess is on its way (`lb_busy`).
2. `submitLb()`: the repeat check runs in the browser first (same notification). Then `POST /api/guess`.
3. The server resolves accents, checks the word, refuses repeats/finished games, saves the guess and returns the colors (and, once the game is over, the answer, points and rank). Errors become the usual notifications (`invalid_word`, `repeat`); `login` sends the player to Discord again; anything else shows `lb_error`.
4. `applyLbGuess()` puts the server's spelling and colors in the row, then calls the same `commitRow()` as a guest game, so the flip, keyboard colors, bounce and `gameWon`/`gameLost` are identical.
5. Nothing goes to localStorage. A reload rebuilds the board from the server (`restoreLb()` with the `c24-lb-state` JSON). The end window shows rank and points as big numbers (`.c24-lb-big`) and a trophy "View leaderboard" link instead of the local stats. A finished guest es/en game shows a small, dismissible hint: a trophy link to `/lb/<lang>` when logged in, else short text + the Discord sign-in button.

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
| Leaderboard: Discord login, scoring, ranking, storage (Neon Postgres), privacy, admin hide | `casa24-leaderboard` |
| Live view: who is playing today, sidebar/sheet, mini boards, polling, `/api/live` | `casa24-live-view` |
| Developer view / demo (`/demo`): env var and password `casa24-deploy`, run locally `casa24-test-and-preview`, why `casa24-decisions` (how it works: above) | `casa24-deploy` |
| Why things are the way they are (decisions already made) | `casa24-decisions` |

## Map of the repo
```
webapp/app.py            routes (/, /<lang>, /demo, /demo/<lang>, /sitemap.xml, plus the leaderboard routes above), data loading, Language class (keyboards: _generate_alphabetical_keyboard),
                         template helpers asset() (?v= URLs), asset_version(), json_script()
webapp/daily.py          daily-word schedule (pure functions)
webapp/discord_auth.py   Discord OAuth (identify only): login URL, code -> ID + username + avatar hash
webapp/leaderboard.py    leaderboard rules (pure): server-side colors, accent resolving, points, streaks
webapp/store.py          leaderboard storage: Postgres when DATABASE_URL is set, in-memory store locally/tests; live() for /api/live
webapp/data/languages/   word lists, language_config.json, keyboards
webapp/templates/        index.html (start screen), game.html (game, also Developer view with demo=True; live view aside in lb mode),
                         demo_login.html (Developer view password page), leaderboard.html (/leaderboard),
                         _discord.html (shared Discord macros: sign-in button, logo, trophy, avatar, header menu,
                         privacy link + dialog, toasts, #dc= avatar script; imported by index/game/leaderboard)
webapp/static/           game.js, index.js, theme.js, style.css, images/kolo/ (WebP), fonts/, favicon/
scripts/                 merge_words.py, validate_words.py, brand_assets.py, screenshots.py, vercel_build.py, casa24/ (seed word CSVs)
tests/                   pytest + Playwright
vercel.json              year-long caching for /static/ URLs with ?v= (see casa24-deploy)
pyproject.toml, .vercelignore, .python-version   Vercel setup
.env.example             names of the env vars (no values); copy to .env.local (git-ignored) for local runs
DEPLOY.md, CREDITS.md, README.md, LICENSE (never delete; see casa24-decisions)
```

Quick commands (from the repo root):
```
.venv/bin/python -m pytest -q tests
cd webapp && ../.venv/bin/flask --app app run --port 5050   (port 5000 is macOS AirPlay)
```
