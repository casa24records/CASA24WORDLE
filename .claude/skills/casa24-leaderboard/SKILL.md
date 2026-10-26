---
name: casa24-leaderboard
description: Casa 24 Wordle's guest mode and Discord leaderboard — what players see, Discord login (OAuth, sign in, identify only), the data we store and never store, anti-cheat (server-checked guesses), points, tiebreaks and streaks, the Neon Postgres database (tables, cleanup, MemoryStore), routes and error codes, env vars, tests, and how to delete my data, hide user, add an admin or change points. Use for any leaderboard, ranking, Discord, login, sign in, OAuth, points, streaks, database, Neon, Postgres, delete my data, hide user or anti-cheat question.
---

# Guest mode + Discord leaderboard

Built 2026-10-26 on branch `leaderboard-discord` (commits `dfb5dea` backend, `ad8610f` UI, then the storage moved from Redis to Neon Postgres). Why it was built this way: `casa24-decisions`. Hosting and env vars: `casa24-deploy`.

Files:
- `webapp/app.py`, section "DISCORD LEADERBOARD": routes, cookies, checks
- `webapp/discord_auth.py`: Discord login (stdlib `urllib`)
- `webapp/leaderboard.py`: pure rules (points, coloring port, streaks)
- `webapp/store.py`: storage (`PostgresStore`, `MemoryStore`, `get_store()`)
- `webapp/templates/index.html` + `static/index.js` (menu choice), `game.html` + `static/game.js` (leaderboard game), `templates/leaderboard.html`
- texts: `lb_*` keys in `webapp/data/languages/{es,en}/language_config.json`

## What players see
- **Menu (es/en area):** a two-option switch, **Jugar como invitado / Play as guest** and **🏆 Jugar con leaderboard (Discord) / Play for the leaderboard (Discord)**. The choice is remembered in localStorage `casa24_mode` (`guest` default, or `lb`). It decides where the Español/English cards go:
  - guest → `/es`, `/en`: exactly the old game, nothing leaves the browser
  - leaderboard → `/lb/es`, `/lb/en`; when not logged in, the card says "Entrar con Discord" and goes through `/auth/discord/login?next=/lb/es`
  - the other 8 languages are always guest only
  - below: "🏆 Ver leaderboard" link, and when logged in "Conectado como @usuario" + "Cerrar sesión"
  - notices: `/?login=failed` (login failed) and `/?deleted=1` (data deleted); the URL is cleaned so a reload doesn't show them again
  - **The switch and links only appear when the leaderboard is enabled** (see `lb_enabled` below).
- **Leaderboard game `/lb/<lang>`:** same `game.html` with a 🏆 badge. The answer is **not** in the page. Every Enter sends the word to the server, which answers with the colors; the flip animation and keyboard colors work as usual. Progress is restored from the server (another device works too), and nothing is saved in localStorage. End window adds **"Tu puesto: #N"**, **"+N puntos"** and a "Ver leaderboard" link. Other language codes redirect to `/lb/es`.
- **Guest end window (es/en, only when enabled):** a dismissible hint "Juega con leaderboard para entrar al ranking" (dismissal saved in localStorage `casa24_lb_hint_off`).
- **`/leaderboard`** (public, `?tab=es|en|all`, default `all` = "Combinado"): top 50 with rank, @username, points, wins, current streak (🔥), best streak. Your own row is highlighted ("Tú"); if you are outside the top 50, "Tu posición: #N" shows below. Page language follows the tab (`all` uses the browser language). Logged out: "Entrar con Discord" button. Logged in: "Cerrar sesión" and **"Borrar mis datos"** (asks for confirmation).
- **Privacy note** (menu leaderboard option and `/leaderboard`): Discord handles the login, we never see password or email; we store Discord ID, username and results to show the ranking; guest games don't count.
- **Delete my data:** removes the player row, all results and saved games, and the rate counter, then logs out and shows the "deleted" notice. Logging in again later starts from zero.
- **Admin hide:** Discord user IDs in `ADMIN_DISCORD_IDS` see an "Ocultar" button on each row. A hidden player disappears from every ranking but can still play (their results keep being recorded).

## Data
| Stored (Neon Postgres) | Never stored |
|---|---|
| Discord user ID, Discord username (max 32 chars, refreshed on each login), `hidden` flag, created date | Discord access token (lives only inside `discord_auth.identify()`) |
| Per finished leaderboard game: language, Panama date, won, attempts, points, finish time | avatar, email, banner, display name, locale or anything else Discord returns |
| Today's guesses (deleted after 2 days) | IP addresses, user agent |
| Guesses per minute counter (deleted after ~2 minutes) | guest games (never sent, never imported on login) |

No app logging of tokens or IPs. Vercel's own platform request logs exist outside the app.

**Cookies** (both signed with `SECRET_KEY` via itsdangerous, `HttpOnly`, `SameSite=Lax`, `Secure` on https):
- `c24_lb`: **only the Discord ID**, 30 days. Separate from Flask's `session` (that one is only the Developer view flag).
- `c24_oauth`: the login `state` + where to go after, 10 minutes, path `/auth/discord` only.

## Login flow
1. Player clicks "Entrar con Discord" → `GET /auth/discord/login?next=/lb/es`.
2. Server makes a random `state`, puts it (and `next`) in `c24_oauth`, redirects to `https://discord.com/oauth2/authorize` with `scope=identify`, `prompt=none`, `client_id`, and `redirect_uri = <this site>/auth/discord/callback`.
3. Player approves on Discord; Discord sends them to `/auth/discord/callback?code=…&state=…`.
4. Server checks `state` against the cookie (constant-time compare), trades the code for a token (`POST https://discord.com/api/oauth2/token`), calls `GET /api/users/@me`, keeps only `id` and `username`, drops the rest and the token.
5. Upserts the player, sets `c24_lb`, deletes `c24_oauth`, redirects to `next` (only relative paths like `/lb/es`; anything else → `/`).
6. Any error, cancel, bad/missing state → redirect `/?login=failed`. Nothing is logged.
- **Logout:** `POST /auth/logout` clears `c24_lb` and goes to `/`.
- The `redirect_uri` is built from the address the visitor used, so **each domain must be listed in the Discord app's Redirects** exactly.

## Anti-cheat
- In leaderboard mode the **answer is never sent to the browser** until the game is over (`daily_word` is blanked; the server colors guesses).
- `POST /api/guess` checks, in order: leaderboard enabled → same origin → logged in (`c24_lb` valid and player exists) → rate limit (**30 per minute** per player, else 429) → body is `{lang, guess}` with lang `es`/`en`.
- Then: today = **Panama date from `daily.py`** (any date the client sends is ignored), answer = the real daily word, accents resolved on the server (same as the guest game), word must be 5 letters and in the main or supplement list, not already guessed, at most 6 guesses, game not finished.
- The game row is **locked** (`SELECT … FOR UPDATE`) while a guess is processed, so two tabs can't race.
- The result is written once: `INSERT … ON CONFLICT DO NOTHING` on (discord_id, lang, day). **The client never sends points**; the server computes them.
- **Same-origin check** on every POST (`/api/guess`, `/auth/logout`, `/api/me/delete`, `/admin/hide`): if the browser sends `Origin` or `Referer`, its host must equal this site's host, else 403. Plus `SameSite=Lax` cookies.
- The coloring (`color_guess`, `resolve_accents`, `fold_accents`) is a 1:1 Python port of `game.js` (`updateColors`, `resolveAccents`, `foldAccents`). **If you change one, change the other**; a test runs both (needs `node`).

## Scoring, tiebreaks, streaks
- **Points:** win in 1 guess = 6, 2 = 5, 3 = 4, 4 = 3, 5 = 2, 6 = 1, loss = 0 (`leaderboard.points()`).
- **Ranking order:** total points, then wins, then **who reached that total first** (earlier "last day you scored points"; players with 0 points use their first day), then Discord ID. Computed by SQL each time (`SQL_RANKED` in `store.py`; `MemoryStore._ranked` mirrors it).
- Tabs: `es`, `en` count only that language; `all` (Combinado) adds both.
- **Streaks** (`leaderboard.streaks()`), recomputed from results only for rows on screen:
  - per language: consecutive Panama days with a win; a loss resets to 0
  - combined: consecutive days with a win in **any** language; a loss does not break it, two wins on one day count once
  - the current streak shows 0 once a whole day passes without a win (yesterday's win still counts today)
- "Your rank" at game end is your place in **that language's** tab.
- `leaderboard.score()` is a leftover from the Redis design (not used by the app; still tested).

## Storage
- `get_store()` in `store.py`:
  - `DATABASE_URL` set → `PostgresStore` (Neon, psycopg 3, pooled URL, `prepare_threshold=None`, 5 s connect timeout)
  - not set and not on Vercel → `MemoryStore` (Python dicts; lost on restart; used by tests and local dev)
  - not set on Vercel → `None` → leaderboard off
- Tables, created automatically on first use (`CREATE TABLE IF NOT EXISTS`, guarded by an advisory lock):
  - `wordle_players(discord_id PK, username, hidden, created_at)`
  - `wordle_results(discord_id → players ON DELETE CASCADE, lang, day, won, attempts, points, finished_at, PK(discord_id, lang, day))`
  - `wordle_games(discord_id → players ON DELETE CASCADE, lang, day, guesses jsonb, updated_at, PK(discord_id, lang, day))`
  - `wordle_rate(discord_id, minute, count, PK(discord_id, minute))`
- Cleanup happens during normal use (no cron): saving a guess deletes `wordle_games` rows older than 2 days; the first hit of each minute deletes `wordle_rate` rows older than 2 minutes. Deleting a player cascades results and games, and the rate rows are deleted separately.
- One connection per request, closed at teardown (serverless friendly). DB errors become `StoreError` with no query text; `/api/guess` returns 503 `store`.
- All SQL is constant with parameters (a test checks this).

## Routes
| Route | What | Responses |
|---|---|---|
| `GET /auth/discord/login?next=` | start login | 302 to Discord; 404 if disabled |
| `GET /auth/discord/callback` | finish login | 302 to `next`, or `/?login=failed` |
| `POST /auth/logout` | log out | 302 `/`; 403 other site |
| `GET /lb/<lang>` | leaderboard game (es/en) | page; 302 to login if logged out; 404 if disabled |
| `POST /api/guess` JSON `{lang, guess}` | one guess | 200 `{word, colors[5], done, won, answer, points, rank}` (answer/points/rank only when done, else null) |
| `GET /leaderboard?tab=` | ranking page | page; 404 if disabled |
| `POST /api/me/delete` | delete my data | 302 `/?deleted=1`; 401 JSON `login` if no cookie; 403 other site |
| `POST /admin/hide` form `discord_id`, `hidden` (1/0), `tab` | hide/unhide | 302 `/leaderboard`; 403 not admin; 400 bad id |

`/api/guess` errors are JSON `{"error": code}`: `disabled` 404, `forbidden` 403, `login` 401, `rate` 429, `bad_request` 400, `bad_lang` 400, `invalid_word` 400, `finished` 400, `too_many` 400, `repeat` 400, `store` 503. In `game.js`, `lbError()` handles them: `login` → back through Discord login; `invalid_word`/`repeat` → the usual notices; `finished` → reload; anything else → "Algo salió mal".

Templates get `lb_enabled` and `lb_user` (`{id, username}` or none) from a context processor. **`lb_enabled`** = `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` and `SECRET_KEY` set, and a store exists. If false, every leaderboard route is 404 and the menu shows no choice.

## Env vars
Set in Vercel → casa24-wordle → Settings → Environment Variables, for Production, Preview and Development (details and current state: `casa24-deploy`). Only the owner types secret values there; never write values in the repo or chat.
- `DISCORD_CLIENT_ID` (public; the app's is `1564412150519169067`), `DISCORD_CLIENT_SECRET`, `SECRET_KEY`: all required.
- `DATABASE_URL`: Neon pooled URL, added by the Neon integration (with other `PG*` / `POSTGRES_*` names the app doesn't use).
- `ADMIN_DISCORD_IDS` (optional): comma-separated Discord **user** IDs (not the app ID).
- Locally, `app.py` reads `.env.local` (git- and Vercel-ignored) when not on Vercel and never overrides variables already set. `.env.example` lists the names.

## Tests
- `tests/lb_testlib.py`: shared fixtures. `FakeDiscord` replaces `discord_auth.exchange_code` / `fetch_me` (returns extra fields like email/avatar on purpose); `mem` = a fresh `MemoryStore`; `lb_env` = fake env values + frozen Panama date; helpers `login()`, `guess()`, `answer()`, `wrong_words()`.
- `tests/test_discord_auth.py`: login only asks `identify`, only id + username kept, bad/missing state, cancel, Discord error, `next` must be relative, logout, tampered cookie.
- `tests/test_leaderboard.py`: points, order, streaks, accents, coloring vs `game.js` (node), MemoryStore, `get_store()` choice, SQL parameterized, PostgresStore against a fake connection, `.env.local` loader, disabled without env, guess validation, other-site refused, records once, client date ignored, rate limit, guest makes zero writes, ranking rows, delete, admin hide/unhide.
- `tests/test_leaderboard_ui.py`: rendered menu/game/leaderboard templates, plus Playwright browser tests with a faked `/api/guess`.
- **No test talks to Discord or a real database.**
- Run: `.venv/bin/python -m pytest -q tests` (or just `tests/test_leaderboard.py tests/test_discord_auth.py tests/test_leaderboard_ui.py`).
- **Try it locally without Discord setup:** not possible through the real login (Discord must redirect back). Use the tests, or the real login below.

## Testing the real login
- **Local:** the owner runs `vercel env pull .env.local --scope casa-24` themselves (it writes secrets to a file; don't print it). Then `cd webapp && ../.venv/bin/flask --app app run --port 5050` and open **http://127.0.0.1:5050** (not `localhost`: the Discord redirect is registered for `127.0.0.1:5050`). With `DATABASE_URL` in `.env.local` it uses the **real Neon database**; remove that line to use the MemoryStore.
- **Production / preview:** https://casa-24-wordle.vercel.app (owner approved testing in production), or the branch preview `https://casa24-wordle-git-leaderboard-discord-casa-24.vercel.app`. Previews may be behind Vercel login.

## Common tasks
- **Add an admin:** owner finds their Discord user ID (Discord → Settings → Advanced → Developer Mode, then right-click own name → Copy User ID), adds it to `ADMIN_DISCORD_IDS` in Vercel (comma-separated for more), redeploys.
- **Hide a user:** as admin, "Ocultar" on `/leaderboard`. **Unhide:** there is no button (hidden users aren't listed). Either POST `/admin/hide` with `discord_id=<id>&hidden=0` while logged in as admin, or in the Neon SQL editor: `UPDATE wordle_players SET hidden = false WHERE discord_id = '<id>';`.
- **Change points:** edit `points()` in `webapp/leaderboard.py` and `test_points`. Results already stored keep their old points (they are saved per game); to recompute, run an `UPDATE wordle_results SET points = …` only with the owner's OK.
- **Add another language to the leaderboard** (now es/en only): add it to `LB_LANGS` and `LB_TABS` in `app.py`, add a tab in `leaderboard.html`, add the `lb_*` text keys to that language's `language_config.json`, show the mode switch for it in `index.html`/`index.js` (they currently assume es/en), add a Discord-free test, and check `casa24-text-and-languages` for its accent rules.
- **Delete someone's data on request:** they can use "Borrar mis datos"; otherwise `DELETE FROM wordle_players WHERE discord_id = '<id>';` (cascades) plus `DELETE FROM wordle_rate WHERE discord_id = '<id>';`.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Discord says "Invalid OAuth2 redirect_uri" | this domain's `/auth/discord/callback` isn't in the Discord app's Redirects (exact match, https, no trailing slash) |
| Back on `/?login=failed` | wrong/missing `DISCORD_CLIENT_SECRET` for that environment, secret reset in Discord but not in Vercel, the 10-minute login cookie expired, cookies blocked, or the database is unreachable |
| `/leaderboard`, `/lb/es` are 404 and no mode switch in the menu | `lb_enabled` is false: one of `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `SECRET_KEY` or `DATABASE_URL` is missing **for that environment**, or no redeploy since adding it |
| Everyone got logged out | `SECRET_KEY` changed (this also logs out Developer view) |
| "Algo salió mal" on every guess | database error (503 `store`): check Neon status and `DATABASE_URL` |
| Local login goes to `localhost` and fails | open `http://127.0.0.1:5050`, not `localhost` |
| Leaderboard empty locally after restart | MemoryStore (no `DATABASE_URL`) loses data on restart; that's expected |
| Ranking colors differ from guest game | the Python port and `game.js` drifted; run the node comparison test |
