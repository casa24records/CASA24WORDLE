---
name: casa24-leaderboard
description: Casa 24 Wordle's guest mode and Discord leaderboard — what players see (the live view has its own skill, casa24-live-view), Discord login (OAuth, sign in, identify only), the data we store and never store, anti-cheat (server-checked guesses), points, tiebreaks and streaks, the Neon Postgres database (tables, cleanup, MemoryStore), routes and error codes, env vars, tests, and how to delete my data, hide user, add an admin or change points. Use for any leaderboard, ranking, Discord, login, sign in, OAuth, points, streaks, database, Neon, Postgres, delete my data, hide user or anti-cheat question.
---

# Guest mode + Discord leaderboard

Built 2026-10-26 on branch `leaderboard-discord` (commits `dfb5dea` backend, `ad8610f` UI, then the storage moved from Redis to Neon Postgres). It covered all 10 languages for one day (2026-10-28); **since 2026-10-29 the whole game is es/en only** (see "Spanish and English only" below). Why it was built this way: `casa24-decisions`. Hosting and env vars: `casa24-deploy`. The **live view** (who else is playing today, colors only, `GET /api/live`; added 2026-10-27): **`casa24-live-view`**. Playing **inside Discord** (Activity, same game, same server state, header session): **`casa24-discord-activity`**.

**Rule: the server is the single source of truth for a logged-in player's game; the web page and the Discord Activity only paint it** (see "Sync between devices").

Files:
- `webapp/app.py`, section "DISCORD LEADERBOARD": routes, cookies, checks
- `webapp/discord_auth.py`: Discord login (stdlib `urllib`)
- `webapp/leaderboard.py`: pure rules (points, coloring port, streaks)
- `webapp/store.py`: storage (`PostgresStore`, `MemoryStore`, `get_store()`)
- `webapp/templates/_discord.html` (shared Discord macros), `templates/index.html` + `static/index.js` (menu Discord area, guest toggle), `game.html` + `static/game.js` (leaderboard game), `templates/leaderboard.html`
- texts: `lb_*` keys in `webapp/data/languages/es|en/language_config.json`
- `scripts/purge_languages.py`: deletes the removed languages' rows from Neon (see below)

## What players see
UI rules decided by the owner on 2026-10-26/27 (record: `casa24-decisions`; look: `casa24-branding`). Shared pieces are Jinja macros in **`webapp/templates/_discord.html`** (`dc.button`, `dc.logo`, `dc.trophy`, `dc.avatar`, `dc.header_slot`, `dc.privacy_link`/`dc.privacy_dialog`, `dc.toast`, `dc.script`), imported by `index.html`, `game.html` and `leaderboard.html`.
- **Rules:** less text, the UI speaks for itself. Trophy **line SVG icon** for the leaderboard (never the 🏆 emoji). Official Discord button (Blurple `#5865F2`, white logo, 48 px). **Nothing overlaps at any size** (check 320, 375, 390, 844×390 landscape, 768, 1366).
- **Header, top-left (menu, leaderboard games, `/leaderboard`):** logged in → the player's **round Discord avatar**; tapping it opens a small popover with @username, "Ver leaderboard", "Cerrar sesión" (and "Borrar mis datos" on `/leaderboard`). Logged out → a small Discord-logo icon that starts the login. On the menu a **trophy icon** link to `/leaderboard` sits right after it (no "Ver leaderboard" text link). Esc or a tap outside closes the popover.
- **Menu (Discord area above the Español/English cards), server-rendered so nothing jumps:**
  - logged out → the **Discord sign-in button shows immediately** (no mode to pick first) + a small "ⓘ Privacidad" link. All cards play the guest game. The sign-in `next` is `/lb/<last language played>` (localStorage `casa24_lang`, es/en; a removed code saved there is ignored), else the preferred es/en (`loginLanguage` in `index.js` fixes the href after load; the server renders `/lb/<es|en>` first).
  - logged in → every card goes to `/lb/<code>` (trophy icon on the card; `playHref()` in `index.js`), with a small switch **"Jugar como invitado (no cuenta)"** that sends them to the guest game instead. localStorage `casa24_mode` = `guest` only when that switch is on; otherwise mode is `lb`.
  - guest → `/<code>`: exactly the old game, nothing leaves the browser.
  - **No privacy paragraph on the menu.** The full privacy text lives only in the "ⓘ Privacidad" dialog (`<dialog id="c24-privacy">`).
  - Notices are **short toasts that close themselves** (~6 s, × to close): `/?login=failed`, `/?login=cancelled` (gentle, not a warning), `/?deleted=1`. The URL is cleaned so a reload doesn't show them again.
  - **Everything above appears only when the leaderboard is enabled** (see `lb_enabled` below).
- **Leaderboard game `/lb/<lang>`:** same `game.html`, with the trophy SVG as a badge after the language badge and the avatar in the header. The answer is **not** in the page. Every Enter sends the word to the server, which answers with the colors; the flip animation and keyboard colors work as usual. Progress is restored from the server (another device or the Discord Activity works too) and reloaded without refreshing (see "Sync between devices"); nothing is saved in localStorage. End window shows **rank and points as big numbers** ("#N", "+N", both `.c24-lb-big`, small labels `lb_rank_label` / `lb_points_label` or `lb_point_label` for exactly 1) and a trophy "Ver leaderboard" link. es/en only: a removed language's code redirects 302 to es/en by browser language (query kept), other unknown codes to `/lb/es`.
- **Guest end window (any language, only when enabled):** a dismissible hint (dismissal saved in localStorage `casa24_lb_hint_off`): logged in → a trophy link to `/lb/<lang>`; logged out → short text + the Discord sign-in button.
- **`/leaderboard`** (public, `?tab=all|es|en`, default `all` = "Combinado"; **3 tabs: Combinado, Español, English** in one row; an old `?tab=<removed code>` shows Combinado): top 50 with rank, @username, points, wins, current streak (🔥), best streak. Your own row is highlighted ("Tú") with your avatar; if you are outside the top 50, "Tu posición: #N" shows below. Page language follows the tab (`all` uses the browser's es/en). Below the table: logged out → Discord sign-in button; logged in → avatar + @username. Plus the small "ⓘ Privacidad" link. Cerrar sesión and **Borrar mis datos** (asks for confirmation) are in the avatar popover: delete is secondary, never a big button.
- **Privacy text** (the dialog; `lb_privacy`, `lb_avatar_note`, `lb_guest_note`; changed 2026-10-27): Discord handles the login, we never see password or email; we store Discord ID, username, **profile picture** and results to show the ranking and who is playing today; **other players see only your colors, never your words**; other players see your Discord picture in the live list (the ranking shows only your own); guest games don't count. The old "only shown in your browser, we don't store it" promise is gone (the live view needs the avatar). The inline fallbacks in `index.html` / `leaderboard.html` match the JSON keys; change both together.
- **Delete my data:** removes the player row (with the avatar hash), all results and saved games, and the rate counters (guess, `:live` and `:state` buckets), then logs out, clears `c24_dc_avatar`, and shows the "deleted" toast. Logging in again later starts from zero.
- **Admin hide:** Discord user IDs in `ADMIN_DISCORD_IDS` see an "Ocultar" button on each row. A hidden player disappears from every ranking but can still play (their results keep being recorded).

## Spanish and English only (2026-10-29) — backend notes
- `SUPPORTED_LANGS = ("es", "en")` and `RETIRED_LANGS` (ar, de, fr, ko, pt, ru, tr, vi) in `app.py`. `LB_LANGS = SUPPORTED_LANGS`; `LB_TABS = ("all",) + LB_LANGS` (Combinado first). `/lb/<lang>`, `/api/guess`, `/api/state`, `/api/live` answer 400 `bad_lang` for other codes; `/api/leaderboard` answers 400 `bad_tab`. Old page links: `retired_lang_redirect()` (302, query kept, es/en by Accept-Language, default es).
- `leaderboard.html` gets `lb_tabs` (`lb_tabs()` = Combinado (`lb_tab_all`) + `[{code, name_native}]` for es, en) and `texts` for es + en (`LB_TEXT_FALLBACK`).
- `lb_normalize(lang, typed)` is now just NFC + trim + lowercase (the Korean NFD and Turkish I/İ special cases were removed).
- Accents: es only (`accent_insensitive`). `color_guess` compares letters folded by `fold_accents` (vowels with or without accent match, ñ stays ñ), the same as `game.js` (`casa24-text-and-languages`).
- **Old rows can never count:** `store.py` filters ranking, histories (streaks) and live view by `lang = ANY(langs)` (`SQL_RANKED`, `SQL_HISTORIES`, `SQL_LIVE` and the MemoryStore equivalents).
- **Deleting old rows from Neon:** `scripts/purge_languages.py`. Dry run by default (row counts per language in `wordle_results` and `wordle_games`); `--export DIR` writes the rows to CSV first (they contain Discord IDs: keep private, outside git); `--execute --yes-i-have-owner-approval` deletes `lang <> ALL(('es','en'))` from both tables in **one transaction** (autocommit connection with an explicit transaction). Players, avatars and rate rows are untouched. **Status: NOT run yet.** It needs the owner's `DATABASE_URL` (`vercel env pull .env.local` by the owner, then `--env-file .env.local`) and the owner's go-ahead in chat before `--execute`. Combinado totals drop for anyone who played other languages. Tests: `test_purge_*` in `tests/test_languages.py`. **Run on production 2026-10-29: 0 rows in other languages, nothing deleted.**

## Data
| Stored (Neon Postgres) | Never stored |
|---|---|
| Discord user ID, Discord username (max 32 chars, refreshed on each login), **Discord avatar hash** (`avatar`, only if it matches `^(a_)?[0-9a-f]{32}$`, else NULL; refreshed on each login; owner decision 2026-10-27, for the live view), `hidden` flag, created date | Discord access token (lives only inside `discord_auth.identify()`) |
| Per finished leaderboard game: language, Panama date, won, attempts, points, finish time | email, banner, display name, locale or anything else Discord returns |
| Today's guesses (deleted after 2 days) | IP addresses, user agent |
| Per-minute request counters: guesses (key = ID), live polling (key = `<id>:live`) and state reloads (key = `<id>:state`), plus one global counter of Activity logins (`activity:token`), deleted after ~2 minutes | guest games (never sent, never imported on login) |

No app logging of tokens or IPs. Vercel's own platform request logs exist outside the app.

**Cookies** (both signed with `SECRET_KEY` via itsdangerous, `HttpOnly`, `SameSite=Lax`, `Secure` on https):
- `c24_lb`: **only the Discord ID**, 30 days. Separate from Flask's `session` (that one is only the Developer view flag).
- `c24_oauth`: the login `state` + where to go after, 10 minutes, path `/auth/discord` only.

## Login flow
1. Player clicks the Discord sign-in button → `GET /auth/discord/login?next=/lb/es`.
2. Server makes a random `state`, puts it (and `next`) in `c24_oauth`, redirects to `https://discord.com/oauth2/authorize` with `scope=identify`, `prompt=none` (kept on purpose), `client_id`, and `redirect_uri = <this site>/auth/discord/callback`.
3. Player approves on Discord; Discord sends them to `/auth/discord/callback?code=…&state=…`.
4. **Cancel first:** if the callback has `?error=access_denied` (the player pressed Cancel on Discord), the server deletes `c24_oauth` and redirects to **`/?login=cancelled`** (a gentle notice, not an error). This is checked **before** the state check.
5. Server checks `state` against the cookie (constant-time compare), trades the code for a token (`POST https://discord.com/api/oauth2/token`), calls `GET /api/users/@me`. `discord_auth.identify()` returns only **`(id, username, avatar_hash)`** and drops the rest and the token.
6. Upserts the player (id, username, and the avatar hash if it has Discord's format, else NULL), sets `c24_lb`, deletes `c24_oauth`, redirects to `next` (only relative paths like `/lb/es`; anything else → `/`) with any `#…` in `next` replaced by the avatar fragment:
   - `#dc=<hash>` when the hash matches `^(a_)?[0-9a-f]{32}$`
   - `#dc=` (empty) when the player has no Discord avatar
   - no fragment at all when the hash doesn't match that format
   The redirect body is empty (the hash is only in the `Location` header) and `Cache-Control: no-store`.
7. Any other failure (Discord error, bad/missing state, expired cookie, token/user call failed, database error) → `/?login=failed`. Nothing is logged.
- **Logout:** `POST /auth/logout` clears `c24_lb` and goes to `/`. The page also clears localStorage `c24_dc_avatar`.
- The `redirect_uri` is built from the address the visitor used, so **each domain must be listed in the Discord app's Redirects** exactly.

## Avatar
- **Since 2026-10-27 the server stores the avatar hash** (`wordle_players.avatar`) so the live view can show other players' pictures (`casa24-live-view`). It is still never logged or put in a cookie (`c24_lb` holds only the ID). Your **own** avatar in the header still comes from the login redirect's `#dc=` fragment, as below.
- `/api/live` builds other players' `avatar_url` server-side; that URL contains their Discord ID (accepted by the owner; see `casa24-live-view`).
- The page reads `#dc=` on load, saves localStorage **`c24_dc_avatar` = `{id, hash}`** (id = the logged-in Discord ID from the page), then removes the fragment with `history.replaceState`.
- Picture URL, loaded by the browser straight from Discord: `https://cdn.discordapp.com/avatars/<id>/<hash>.png` (animated hashes start with `a_`). No hash (empty `#dc=`) or a load error → default avatar `https://cdn.discordapp.com/embed/avatars/<(id >> 22) % 6>.png` (compute with `BigInt`, the id is too big for a JS number).
- A stored `c24_dc_avatar` whose `id` differs from the logged-in player is ignored. It is **removed on logout** (and on "Borrar mis datos").

## Sync between devices (web ↔ web ↔ Discord Activity; commit `5966e7a`, 2026-10-28)
- **`GET /api/state?lang=<lang>`** (read-only, the session player only): the same JSON as the page embed `#c24-lb-state`, built by `lb_game_state()`: `{day, puzzle, guesses:[{word, colors}], status: playing|won|lost, attempts, done, won, answer, points, rank}`. `answer`, `points`, `rank` are `null` until the game is done. `Cache-Control: no-store`. Errors: 404 `disabled`, 401 `login`, 400 `bad_lang`, 429 `rate` (own **30/min** bucket `<id>:state`), 503 `store`.
- **`POST /api/guess` takes `attempt`** = the 0-based row the client is filling (= how many guesses it believes exist; optional, int 0–6, else 400 `bad_request`). If the server has a different count (played elsewhere meanwhile) → **409 `{"error":"stale","state":{…}}`** and nothing is saved. `finished` / `too_many` also carry `state`. Checked inside the locked row, so web + Discord pressing Enter together can never save two words for one row. Successful answers now also include `day` and `attempts`.
- **Client (`game.js`), one function each:** `loadState(force)` = `GET /api/state` + `paintState()`; `submitGuess()` = `POST /api/guess` with `attempt`. A 409/`finished` answer repaints from its `state` (no error shown); a game finished elsewhere opens the end window. Reloads: on `focus` / tab visible again (`syncOnReturn`, at most once per 5 s), every **60 s** while visible, and when this device's Panama date changes (new word → empty board). A 401/404/400 from `/api/state` stops the polling (the next guess handles login). `loadState` is skipped while a guess is in flight or tiles flip.
- **Header session (Discord Activity):** cookies don't travel in Discord's iframe, so the Activity sends the same signed value as `c24_lb` in `Authorization: Bearer <session>`; `lb_player_id()` accepts cookie **or** header; the session comes from `POST /api/activity/token` (see `casa24-discord-activity`). `_lb_session_value()`: when an `Authorization` header is present only it is read (Bearer), else the cookie; same signature, salt and 30-day age.
- Guest games: the save key is the path only (`pageKey()`, query ignored), and the guest end window shows `lb_guest_sync` ("Inicia sesión con Discord para continuar esta partida en Discord…"). Share links use `public_url()` (`data-public-origin`, optional env `PUBLIC_URL`), never `window.location.origin`.
- Tests: `tests/test_sync.py` (the 9 owner cases `test_1_…`–`test_9_…`, state errors, attempt validation, browser 409 repaint, finished elsewhere, focus/visibility, day rollover, guest key ignores query).

## Anti-cheat
- In leaderboard mode the **answer is never sent to the browser** until the game is over (`daily_word` is blanked; the server colors guesses).
- `POST /api/guess` checks, in order: leaderboard enabled → same origin (our host, or exactly `https://<DISCORD_CLIENT_ID>.discordsays.com` for the Activity) → logged in (`c24_lb` cookie, or the Activity's `Authorization: Bearer` session, valid and player exists) → rate limit (**30 per minute** per player, else 429) → body is `{lang, guess}` with lang in `LB_LANGS` (es/en).
- Then: today = **Panama date from `daily.py`** (any date the client sends is ignored), answer = the real daily word, the guess normalized to the word lists' form (`lb_normalize`), accents resolved on the server (same as the guest game; es only), word must be 5 letters and in the main or supplement list, not already guessed, at most 6 guesses, game not finished.
- The game row is **locked** (`SELECT … FOR UPDATE`) while a guess is processed, so two tabs (or web + Discord) can't race; with `attempt` a stale client gets 409 instead of adding a second word.
- The result is written once: `INSERT … ON CONFLICT DO NOTHING` on (discord_id, lang, day). **The client never sends points**; the server computes them.
- **Same-origin check** on every POST (`/api/guess`, `/auth/logout`, `/api/me/delete`, `/admin/hide`): if the browser sends `Origin` or `Referer`, its host must equal this site's host, else 403. Plus `SameSite=Lax` cookies.
- The coloring (`color_guess`, `resolve_accents`, `fold_accents`) is a 1:1 Python port of `game.js` (`updateColors`, `resolveAccents`, `foldAccents`). **If you change one, change the other**; a test runs both (needs `node`).

## Scoring, tiebreaks, streaks
- **Points:** win in 1 guess = 6, 2 = 5, 3 = 4, 4 = 3, 5 = 2, 6 = 1, loss = 0 (`leaderboard.points()`).
- **Ranking order:** total points, then wins, then **who reached that total first** (earlier "last day you scored points"; players with 0 points use their first day), then Discord ID. Computed by SQL each time (`SQL_RANKED` in `store.py`; `MemoryStore._ranked` mirrors it).
- Tabs: each language tab counts only that language; `all` (Combinado) adds es + en (rows of removed languages never count).
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
  - `wordle_players(discord_id PK, username, hidden, created_at, avatar)` (`avatar` added 2026-10-27 by `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, run on first use)
  - `wordle_results(discord_id → players ON DELETE CASCADE, lang, day, won, attempts, points, finished_at, PK(discord_id, lang, day))`
  - `wordle_games(discord_id → players ON DELETE CASCADE, lang, day, guesses jsonb, updated_at, PK(discord_id, lang, day))`
  - `wordle_rate(discord_id, minute, count, PK(discord_id, minute))` (`discord_id` is `<id>` for guesses, `<id>:live` for live polling, `<id>:state` for `/api/state`)
  - index `wordle_games_lang_day (lang, day, updated_at DESC)` for the live view
- Cleanup happens during normal use (no cron): saving a guess deletes `wordle_games` rows older than 2 days; the first hit of each minute deletes `wordle_rate` rows older than 2 minutes. Deleting a player cascades results and games, and the rate rows (both buckets) are deleted separately.
- One connection per request, closed at teardown (serverless friendly). DB errors become `StoreError` with no query text; `/api/guess` returns 503 `store`.
- All SQL is constant with parameters (a test checks this).

## Routes
| Route | What | Responses |
|---|---|---|
| `GET /auth/discord/login?next=` | start login | 302 to Discord; 404 if disabled |
| `GET /auth/discord/callback` | finish login | 302 to `next` + `#dc=<hash>`; `/?login=cancelled` on `error=access_denied`; `/?login=failed` otherwise |
| `POST /auth/logout` | log out | 302 `/`; 403 other site |
| `GET /lb/<lang>` | leaderboard game (es/en; a removed language → 302 to es/en, query kept; other unknown → `/lb/es`) | page; 302 to login if logged out; 404 if disabled |
| `POST /api/guess` JSON `{lang, guess, attempt}` | one guess | 200 `{word, colors[5], done, won, answer, points, rank, day, attempts}` (answer/points/rank only when done, else null); 409 `stale` + `state` |
| `GET /api/state?lang=` | today's game for the session player | 200 state (see "Sync"); also marks the player present for the live view (`_lb_presence`); 401 `login`, 400 `bad_lang`, 429 `rate`, 503 `store`, 404 `disabled` |
| `POST /api/activity/token` JSON `{code}` | Discord Activity login (no `redirect_uri`; token never stored) | 200 `{access_token, session, user:{username}}`; 400 `bad_request`/`discord`, 403, 404, 429 `rate` (global 120/min), 503; see `casa24-discord-activity` |
| `GET /api/leaderboard?tab=` | the ranking table as JSON (the Activity's leaderboard window; public, your row marked with a session) | 200 `{tab, rows:[{rank, username, points, wins, played, current_streak, best_streak, is_me}], me}`; 400 `bad_tab`, 503, 404; no Discord IDs |
| `GET /api/live?lang=<lang>` | who else plays today, colors only (`casa24-live-view`) | 200 `{players:[{username, avatar_url, rows, done, won, live}], count}`; 401 `login`, 400 `bad_lang`, 429 `rate` (own 20/min bucket), 503 `store`, 404 `disabled`; `Cache-Control: no-store` |
| `GET /leaderboard?tab=` | ranking page (`all`/`es`/`en`; any other tab shows Combinado) | page; 404 if disabled |
| `POST /api/me/delete` | delete my data | 302 `/?deleted=1`; 401 JSON `login` if no cookie; 403 other site |
| `POST /admin/hide` form `discord_id`, `hidden` (1/0), `tab` | hide/unhide | 302 `/leaderboard`; 403 not admin; 400 bad id |

`/api/guess` errors are JSON `{"error": code}`: `disabled` 404, `forbidden` 403, `login` 401, `rate` 429, `bad_request` 400, `bad_lang` 400, `invalid_word` 400, `finished` 400 (+`state`), `too_many` 400 (+`state`), `stale` 409 (+`state`), `repeat` 400, `store` 503. In `game.js`: a `state` in the answer → `paintState()`; otherwise `lbError()`: `login` → back through Discord login (in the Activity: one silent re-authorize, `activityReauth()`, instead); `invalid_word`/`repeat` → the usual notices; `finished`/`too_many`/`stale` → `loadState(true)`; anything else → "Algo salió mal".

Templates get `lb_enabled` and `lb_user` (`{id, username}` or none) from a context processor. **`lb_enabled`** = `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` and `SECRET_KEY` set, and a store exists. If false, every leaderboard route is 404 and the menu shows no Discord pieces (no button, avatar/Discord icon, trophy, toggle or privacy link).

## Env vars
Set in Vercel → casa24-wordle → Settings → Environment Variables, for Production, Preview and Development (details and current state: `casa24-deploy`). Only the owner types secret values there; never write values in the repo or chat.
- `DISCORD_CLIENT_ID` (public; the app's is `1564412150519169067`), `DISCORD_CLIENT_SECRET`, `SECRET_KEY`: all required.
- `DATABASE_URL`: Neon pooled URL, added by the Neon integration (with other `PG*` / `POSTGRES_*` names the app doesn't use).
- `ADMIN_DISCORD_IDS` (optional): comma-separated Discord **user** IDs (not the app ID).
- Locally, `app.py` reads `.env.local` (git- and Vercel-ignored) when not on Vercel and never overrides variables already set. `.env.example` lists the names.

## Tests
- `tests/lb_testlib.py`: shared fixtures. `FakeDiscord` replaces `discord_auth.exchange_code` / `fetch_me` (returns extra fields like email/avatar on purpose; `FakeDiscord.avatar` defaults to a deliberately invalid hash so no `#dc=` is added, `VALID_AVATAR` is a real-format one); `mem` = a fresh `MemoryStore`; `lb_env` = fake env values + frozen Panama date; helpers `login()`, `guess()`, `answer()`, `wrong_words()`.
- `tests/test_discord_auth.py`: login only asks `identify`, only id + username + valid avatar hash stored, bad/missing state, cancel → `/?login=cancelled`, other Discord error → `/?login=failed`, avatar hash in the store (valid format only) and the `Location` fragment, never in cookies or the body, empty `#dc=` without avatar, no fragment for a malformed hash, `next`'s own fragment replaced, `next` must be relative, logout, tampered cookie.
- `tests/test_leaderboard.py`: points, order, streaks, accents, coloring vs `game.js` (node), MemoryStore, `get_store()` choice, SQL parameterized, PostgresStore against a fake connection, `.env.local` loader, disabled without env, guess validation, other-site refused, records once, client date ignored, rate limit, guest makes zero writes, ranking rows, delete, admin hide/unhide.
- es/en tests (2026-10-29): `test_lb_langs_are_es_and_en`, `test_lb_page_renders_every_language`, `test_guess_colors_and_win_every_language`, `test_combined_sums_es_and_en`, `test_leaderboard_tabs_and_texts` (in `test_leaderboard.py`); `test_leaderboard_game_page_any_language`, `test_menu_two_big_cards_then_developer_view`, `test_menu_logged_in_every_card_goes_to_leaderboard`, `test_menu_sign_in_goes_to_last_language_played` (in `test_leaderboard_ui.py`); redirects, 400s, 3 tabs and the purge script in `tests/test_languages.py`; accent colors in `tests/test_accents.py`.
- `tests/test_leaderboard_ui.py`: rendered menu/game/leaderboard templates, plus Playwright browser tests with a faked `/api/guess` (and live view tests with a faked `/api/live`).
- `tests/test_live.py`: `/api/live` and `store.live()` (see `casa24-live-view`).
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
- **Add another language:** not planned (owner: es/en only, 2026-10-29). It would mean adding it to `SUPPORTED_LANGS` (and out of `RETIRED_LANGS` if it was one), its data folder with keyboard and every text key, and re-checking the layout and tests. Ask the owner first.
- **Purge the removed languages' rows:** owner runs `vercel env pull .env.local`, then `.venv/bin/python scripts/purge_languages.py --env-file .env.local` (dry run), optionally `--export <private dir>`, shows the counts to the owner, and only after the go-ahead `--execute --yes-i-have-owner-approval`.
- **Delete someone's data on request:** they can use "Borrar mis datos"; otherwise `DELETE FROM wordle_players WHERE discord_id = '<id>';` (cascades) plus `DELETE FROM wordle_rate WHERE discord_id IN ('<id>', '<id>:live', '<id>:state');`.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Discord says "Invalid OAuth2 redirect_uri" | this domain's `/auth/discord/callback` isn't in the Discord app's Redirects (exact match, https, no trailing slash) |
| Back on `/?login=cancelled` | the player pressed Cancel on Discord's screen (expected, not a bug) |
| Back on `/?login=failed` | wrong/missing `DISCORD_CLIENT_SECRET` for that environment, secret reset in Discord but not in Vercel, the 10-minute login cookie expired, cookies blocked, or the database is unreachable |
| `/leaderboard`, `/lb/es` are 404 and no Discord button in the menu | `lb_enabled` is false: one of `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `SECRET_KEY` or `DATABASE_URL` is missing **for that environment**, or no redeploy since adding it |
| Everyone got logged out | `SECRET_KEY` changed (this also logs out Developer view) |
| "Algo salió mal" on every guess | database error (503 `store`): check Neon status and `DATABASE_URL` |
| Local login goes to `localhost` and fails | open `http://127.0.0.1:5050`, not `localhost` |
| Leaderboard empty locally after restart | MemoryStore (no `DATABASE_URL`) loses data on restart; that's expected |
| Ranking colors differ from guest game | the Python port and `game.js` drifted; run the node comparison test |

- **Your own avatar comes from the server (fixed 2026-10-27):** `lb_current_user()` adds `avatar_url` (from `store.get_avatar`) and `has_avatar`; `_discord.html` renders it directly, and the `c24_dc_avatar` localStorage copy only overrides it when present. Players who signed in before avatars were stored get **one silent pass through Discord** (`lb_avatar_refresh()` on `/lb/<lang>`: redirect to `/auth/discord/login?next=…` with `prompt=none`), guarded by a 1-day `c24_avr` cookie so it never loops (e.g. users with no Discord picture). Tests: `test_avatar_refresh_once_when_no_picture_saved`, `test_no_avatar_refresh_when_picture_saved`; `lb_testlib.login()` sets `c24_avr` to skip it elsewhere.

## Legal pages and deletion (2026-10-29)
`/terms` and `/privacy` (templates `legal.html`, `terms.html`, `privacy.html`; es/en by Accept-Language or `?lang=`). Contact/operator/date are constants in `app.py`: `LEGAL_CONTACT_EMAIL` (casa24records@gmail.com, owner's choice), `LEGAL_OPERATOR`, `LEGAL_CITY`, `LEGAL_UPDATED` — change them there and in `tests/test_legal.py`. The privacy text must stay true to what we store (ID, username, avatar hash, results; tokens never; guest data only in the browser). Small "Términos · Privacidad" links on the start screen, `/leaderboard` and the game Settings. `/api/me/delete` answers JSON when asked for it (Activity) and still redirects to `/?deleted=1` for the web form. Plain-language texts, not lawyer-reviewed.
