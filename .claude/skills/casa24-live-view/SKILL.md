---
name: casa24-live-view
description: Casa 24 Wordle's live view in leaderboard mode — who else is playing today's word, in all 10 languages, shown as a desktop sidebar or a header facepile/"people" button + bottom sheet, with Discord avatar, @username, live dot, ✓/✗ and a 6×5 mini board of colors only. Covers who appears and who can see it, privacy (never words or the answer), the GET /api/live contract, polling and backoff, the DB index and avatar column, files, tests and common tasks. Use for any live view, who is playing, jugando hoy, sidebar, mini boards, polling or /api/live question.
---

# Live view: "Jugando hoy" / "Playing today"

Built 2026-10-27 on branch `live-view`, like NYT Wordle's Discord activity. Owner decisions (record: `casa24-decisions`): **Discord avatars shown** (so the avatar hash is now stored), **colors only, never letters**, **Discord players only**. Login, storage and anti-cheat basics: `casa24-leaderboard`. Layout rules: `casa24-responsive`. Look: `casa24-branding`.

## What players see
- **Where:**
  - **≥1024px wide and >500px tall** (`@media (min-width: 1024px) and (min-height: 501px)`): an always-visible fixed **left sidebar** (240px; 280px from 1280px), next to the centered game. No button and no sheet.
  - **Everywhere else** (phones, tablets, landscape phones): a header button in the leaderboard game (right side, before stats) with an orange count badge (`99+` max). **With players (owner, 2026-10-28): a facepile** of the first **3** avatars (22px, overlapping by 8px, `.c24-facepile` / `.c24-face`, `data-live-faces`; only **2 under 360px**) so it's visible without hunting; **with nobody yet: the "people" SVG icon**. The button grows (`.c24-live-btn.has-faces`, min 44px). It opens a **bottom sheet** (max 500px wide, max 70% of the height) over a backdrop. Esc, the × button, a tap on the backdrop, or the button again closes it.
- **Each card:** round avatar (34px, `loading=lazy`, `referrerpolicy=no-referrer`), `@username` (ellipsis), a green **"en vivo" / "live" dot** when the last guess was ≤5 minutes ago, **✓** (won) or **✗** (lost) once the player is done, and a **6×5 mini grid of colored squares** using the tile color tokens. **Nothing is written in the squares.**
- **Empty state:** "Nadie más está jugando ahora" / "No one else is playing right now" (`lb_live_empty`), shown after the first answer.
- Title "Jugando hoy" with the count.

## Who appears
Leaderboard players with a game **today** (Panama date) in the **same language** (any of the 10 since 2026-10-28):
- not hidden (admin hide also hides them here);
- not yourself;
- with **at least 1 guess**;
- **most recent activity first** (`wordle_games.updated_at DESC`);
- **up to 30** (`LIVE_LIMIT`).

Guests never appear: guest games never leave the browser.

## Who can see it
Only **logged-in leaderboard players**, on the `/lb/<lang>` pages. The guest game (`/<lang>`) has no live markup at all. `/api/live` returns 401 without the `c24_lb` cookie.

## Privacy
- The server reads the stored words but sends **only colors**, computed with `leaderboard.color_guess(word, answer)`. **Never words, never the answer.** A test inspects the JSON for letters, the answer and Discord IDs.
- No `discord_id` field in the response. **But** `avatar_url` (`https://cdn.discordapp.com/avatars/<id>/<hash>.png?size=64`) **contains the player's Discord ID**. The owner accepted this (2026-10-27): Discord IDs are public in Discord anyway. To avoid it, serve the images through a proxy route on our domain.
- The default avatar URL (`embed/avatars/<(id>>22)%6>.png`) does not expose the ID.
- The avatar hash is stored in `wordle_players.avatar` (only if it matches `^(a_)?[0-9a-f]{32}$`, else NULL), refreshed at every login. "Borrar mis datos" removes it with the player row.
- Players who logged in before this feature show the default avatar until their next login.
- The privacy texts (`lb_privacy`, `lb_avatar_note`) say this: ID, username, profile picture and results are stored; others see only your colors.

## API: `GET /api/live?lang=<lang>` (any code in `LB_LANGS`)
- 200 JSON: `{"players": [{"username", "avatar_url", "rows": [[5 colors], ...], "done", "won", "live"}], "count": N}`. Colors are `correct`, `semicorrect`, `incorrect`.
- Errors, JSON `{"error": code}`:
  - `disabled` 404 (leaderboard off)
  - `login` 401
  - `bad_lang` 400
  - `rate` 429
  - `store` 503
- **Rate limit:** its own bucket, **20 per minute** per player (`LIVE_RATE_LIMIT_PER_MINUTE`), stored in `wordle_rate` under the key `"<id>:live"`. So polling never uses up the 30/minute guess budget.
- `Cache-Control: no-store`.
- Code: `api_live`, `_live_player`, `lb_avatar_url` in `webapp/app.py`; `store.live()` in `webapp/store.py`.
- `done` / `won` also cover a game that was won or used 6 guesses but has no result row yet.

## Polling (`game.js`)
- The first request goes out right after the board renders, then one **every 8 s** (`LIVE_EVERY`).
- **Paused while the tab is hidden** (`visibilitychange`); it asks again right away when the tab is visible again.
- **429, 5xx or a network error:** the wait doubles, up to **60 s** (`LIVE_MAX`). It goes back to 8 s after a success.
- **401, 404 or 400:** polling stops for this page.
- **Arabic (RTL):** `livePlayer(p, rtl)` reverses each mini-board row so it reads right to left like the big board (`applyLive` passes `this.right_to_left`).
- The client also checks the data: `avatar_url` must match a Discord CDN pattern (else default avatar), username is cut to 32 characters, and unknown colors become empty cells.
- Why polling: Vercel serverless has no WebSockets, and one indexed query every 8 s is cheap.

## Database
- `CREATE INDEX IF NOT EXISTS wordle_games_lang_day ON wordle_games (lang, day, updated_at DESC)`.
- `ALTER TABLE wordle_players ADD COLUMN IF NOT EXISTS avatar text`.
- Both are in `SQL_SCHEMA` and run automatically on first use (existing Neon databases get them with no manual step).
- Query: `SQL_LIVE` (games JOIN players LEFT JOIN results, parameterized). `MemoryStore.live()` mirrors it.

## Files
- `webapp/app.py`: `/api/live` and the constants `LIVE_RATE_LIMIT_PER_MINUTE`, `LIVE_LIMIT`, `LIVE_RECENT_SECONDS`.
- `webapp/store.py`: `live()`, `clean_avatar`, `AVATAR_HASH_RE`, rate buckets (`RATE_BUCKETS`, `_rate_key`), `SQL_LIVE`, schema.
- `webapp/templates/game.html`: people button (`.c24-live-btn`, `data-live-open`, facepile `data-live-faces` / people icon `v-else`) and `<aside id="c24-live" class="c24-live">`, only `{% if lb %}`.
- `webapp/static/game.js`: `LIVE_*` constants, `liveCells`, `livePlayer`, methods `liveFetch`, `liveSchedule`, `liveVisibility`, `applyLive`, `toggleLive`, `closeLive`.
- `webapp/static/style.css`: section "live view" plus the `--c24-live` token.
- Texts: `lb_live_title`, `lb_live_empty`, `lb_live_now`, `lb_live_open` in all 10 `language_config.json` files.

## Tests
- `tests/test_live.py` (backend):
  - disabled, login and lang checks
  - colors only (no letters, answer or IDs) and filters (self, hidden, other language)
  - live flag, order and limit
  - separate rate bucket
  - 503 on store error
  - `test_live_other_languages`: works for the non-es/en languages
  - delete removes the avatar and the live counter
  - cookie only has the ID
  - avatar rule, `MemoryStore.live`, `PostgresStore` against a fake connection
  - SQL shape and the avatar URL helper
- `tests/test_leaderboard_ui.py` `test_live_*` / `test_*live_view*`:
  - LB game renders the live view; the guest game doesn't
  - text keys exist in es and en
  - Playwright with a faked `/api/live`: desktop sidebar, phone sheet, empty state, polling pauses and backs off
  - layout fits with no overlap at several sizes
  - facepile (2026-10-28): `test_live_facepile_on_phone_opens_sheet_with_loaded_avatars`, `test_live_people_icon_when_nobody_plays`, `test_live_facepile_header_fits` (several languages and sizes; helper `open_lb_mobile`)
- Run: `.venv/bin/python -m pytest -q tests/test_live.py tests/test_leaderboard_ui.py`.

## Common tasks
- **Change the poll interval:** `LIVE_EVERY` (and `LIVE_MAX`) in `game.js`. Keep `LIVE_RATE_LIMIT_PER_MINUTE` in `app.py` above 60 s ÷ interval, with room for tab refreshes.
- **Change how many players show:** `LIVE_LIMIT` in `app.py`. The client also caps the list at 50 in `applyLive`.
- **Change the "en vivo" window:** `LIVE_RECENT_SECONDS` in `app.py` (5 minutes).
- **Hide a player from the live view:** use admin hide (`casa24-leaderboard`). It hides them from the rankings and the live view together. There is no live-only hide.
- **Change the facepile:** markup in `game.html` (`live_players.slice(0, 3)`), styles `.c24-facepile`, `.c24-face`, `.c24-live-btn.has-faces` and the `max-width: 359px` rule (2 faces) in the live section of `style.css`. Re-run `test_live_facepile_header_fits`.
- **Change breakpoints:** the `min-width: 1024px and min-height: 501px` media query in the style.css live section. Then re-run the layout tests (see `casa24-responsive`).

## 320px header change (owner may revisit)
On the leaderboard game, the header has 2 icons on the left and 3 on the right (people/facepile, stats, settings). Its side columns are `minmax(max-content, 1fr)`, so they are never narrower than their icons (with a wide facepile the title moves a little off-center instead of overlapping). So **below 420px wide**, the "Casa 24" title text is hidden: `.c24-header-lb .c24-title-text { display: none }`. Kolo's face, the language badge and the trophy stay, and the logo's `alt` keeps the name. Guest games keep the text. The owner hasn't confirmed this yet. Other options: a smaller logo, or moving an icon into a menu.

- **Your own avatar comes from the server (fixed 2026-10-27):** `lb_current_user()` adds `avatar_url` (from `store.get_avatar`) and `has_avatar`; `_discord.html` renders it directly, and the `c24_dc_avatar` localStorage copy only overrides it when present. Players who signed in before avatars were stored get **one silent pass through Discord** (`lb_avatar_refresh()` on `/lb/<lang>`: redirect to `/auth/discord/login?next=…` with `prompt=none`), guarded by a 1-day `c24_avr` cookie so it never loops (e.g. users with no Discord picture). Tests: `test_avatar_refresh_once_when_no_picture_saved`, `test_no_avatar_refresh_when_picture_saved`; `lb_testlib.login()` sets `c24_avr` to skip it elsewhere.
