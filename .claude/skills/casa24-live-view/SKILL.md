---
name: casa24-live-view
description: Casa 24 Wordle's live view in leaderboard mode — who else has today's word open (Spanish or English), shown as an NYT-style left rail of 147×80 cards on desktop (plus an "Invite friends" card inside Discord) or a header facepile/"people" button + bottom sheet with the same cards; each card shows only the Discord avatar and a 6×5 mini board of colors (the @username, live and won/lost status are screen-reader text and a tooltip). Covers who appears (presence from opening the game, 0-guess players for 5 minutes) and who can see it, privacy (never words or the answer), the GET /api/live contract, polling and backoff, the DB index and avatar column, files, tests and common tasks. Use for any live view, who is playing, jugando hoy, sidebar, mini boards, polling or /api/live question.
---

# Live view: "Jugando hoy" / "Playing today"

Built 2026-10-27 on branch `live-view`, like NYT Wordle's Discord activity. Owner decisions (record: `casa24-decisions`): **Discord avatars shown** (so the avatar hash is now stored), **colors only, never letters**, **Discord players only**. Login, storage and anti-cheat basics: `casa24-leaderboard`. Layout rules: `casa24-responsive`. Look: `casa24-branding`.

## What players see
- **Where:**
  - **≥860px wide and >500px tall** on the web (`@media (min-width: 860px) and (min-height: 501px)`), and **≥860px at any height in Discord desktop** (`:root.c24-embed:not(.c24-plat-mobile)`): an always-visible fixed **left rail** (refined 2026-10-29), one column of cards 147px wide (`--c24-card-w`), **16px from the left edge, 10px under the header** (`--c24-rail-top`), scrolling inside when long. It **never shrinks or moves the centered board/keyboard** (`test_rail_never_moves_or_shrinks_the_board`). No button and no sheet; the "Jugando hoy" heading stays only for screen readers. (Earlier the same day: from 1024px with a variable width `--c24-rail-w`; removed.)
  - **Inside Discord only, the first card is "Invitar amigos / Invite friends"** (`.c24-live-invite`, `data-live-invite`, text `activity_invite`): `inviteFriends()` in `game.js` → `C24Activity.invite()` → the shell opens Discord's invite window (see `casa24-discord-activity`).
  - **Everywhere else** (phones, tablets, landscape phones): a header button in the leaderboard game (first of the right-hand actions, before help) with an orange count badge (`99+` max). **With players (owner, 2026-10-28): a facepile** of the first **3** avatars (22px, overlapping by 8px, `.c24-facepile` / `.c24-face`, `data-live-faces`; only **2 under 400px**) so it's visible without hunting; **with nobody yet: the "people" SVG icon**. The button grows (`.c24-live-btn.has-faces`, min 44px). It opens a **bottom sheet** (max 500px wide, max 70% of the height) over a backdrop, with the **same cards in a wrapping grid** (two per row at 390px). Esc, the × button, a tap on the backdrop, or the button again closes it.
- **Each card (NYT "Playing now" style, 2026-10-29; team: "solo el profile y el grid"):** 147×80, 1px border, 8px radius, 9px apart; a **64px round avatar** (`loading=lazy`, `referrerpolicy=no-referrer`, `alt=""`) and the **6×5 mini grid** of 9px colored squares using the tile color tokens. **Nothing else is visible:** no @name, no live dot, no ✓/✗, no title. **Nothing is written in the squares.**
- **Accessible name:** a visually hidden `<p class="c24-live-info">` inside each card holds "@name, en vivo, ganó" (`.c24-live-name`, `.c24-live-now` when last guess or visit ≤5 minutes ago, `.c24-live-result` `is-won`/`is-lost` once done, texts `lb_live_now`, `lb_live_won`, `lb_live_lost`); the `<li>` points to it with `aria-labelledby="c24-live-p<n>"` and has `title="@name"` (mouse tooltip).
- **Empty state:** "Nadie más está jugando ahora" / "No one else is playing right now" (`lb_live_empty`), shown after the first answer.
- Title "Jugando hoy" with the count (shown on the sheet; visually hidden on the rail).

## Who appears
Leaderboard players with a game **today** (Panama date) in the **same language** (es or en):
- not hidden (admin hide also hides them here);
- not yourself;
- **presence (owner, 2026-10-29):** a player shows up **as soon as they open today's leaderboard game**, before any guess. `GET /api/state` or `/api/live` calls `_lb_presence()` → `store.touch()`, which upserts the `wordle_games` row with no guesses (`[]`) or bumps `updated_at`, at most every 20 s (`PRESENCE_MIN_SECONDS`). Players with **0 guesses** are listed only while seen in the last **5 minutes** (`LIVE_RECENT_SECONDS`); players with guesses stay all day. Presence never creates a result, points or streak, stores nothing new, and a store error there never breaks the request. Guest and Developer view pages create no rows;
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

## API: `GET /api/live?lang=<lang>` (es or en, `LB_LANGS`)
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
- The client also checks the data: `avatar_url` must match a Discord CDN pattern (else default avatar), username is cut to 32 characters, and unknown colors become empty cells.
- Why polling: Vercel serverless has no WebSockets, and one indexed query every 8 s is cheap.

## Database
- `CREATE INDEX IF NOT EXISTS wordle_games_lang_day ON wordle_games (lang, day, updated_at DESC)`.
- `ALTER TABLE wordle_players ADD COLUMN IF NOT EXISTS avatar text`.
- Both are in `SQL_SCHEMA` and run automatically on first use (existing Neon databases get them with no manual step).
- Query: `SQL_LIVE` (games JOIN players LEFT JOIN results, parameterized; also `lang = ANY(langs)` so rows of removed languages never show, and 0-guess rows only when `updated_at` is recent). `MemoryStore.live()` mirrors it. Presence: `SQL_GAME_TOUCH` / `touch()` in both stores.

## Files
- `webapp/app.py`: `/api/live` and the constants `LIVE_RATE_LIMIT_PER_MINUTE`, `LIVE_LIMIT`, `LIVE_RECENT_SECONDS`.
- `webapp/store.py`: `live()`, `clean_avatar`, `AVATAR_HASH_RE`, rate buckets (`RATE_BUCKETS`, `_rate_key`), `SQL_LIVE`, schema.
- `webapp/templates/game.html`: invite card (`data-live-invite`, Activity only), people button (`.c24-live-btn`, `data-live-open`, facepile `data-live-faces` / people icon `v-else`) and `<aside id="c24-live" class="c24-live">`, only `{% if lb %}`.
- `webapp/static/game.js`: `LIVE_*` constants, `liveCells`, `livePlayer`, methods `liveFetch`, `liveSchedule`, `liveVisibility`, `applyLive`, `toggleLive`, `closeLive`, `inviteFriends`.
- `webapp/static/style.css`: section "live view" plus the `--c24-live` token.
- Texts: `lb_live_title`, `lb_live_empty`, `lb_live_now`, `lb_live_open`, `lb_live_won` (ganó/won), `lb_live_lost` (perdió/lost; both 2026-10-29), `activity_invite` in the es and en `language_config.json`.

## Tests
- `tests/test_live.py` (backend):
  - disabled, login and lang checks
  - colors only (no letters, answer or IDs) and filters (self, hidden, other language)
  - live flag, order and limit
  - separate rate bucket
  - 503 on store error
  - `test_live_other_languages`: es and en are separate lists
  - presence (`test_presence_*`): opening the game shows an empty board, ends after 5 minutes without guesses, throttled (memory and Postgres fake), hidden players never appear, guest/demo pages create no rows, never a played game, store errors never break `/api/state`, delete my data removes it
  - delete removes the avatar and the live counter
  - cookie only has the ID
  - avatar rule, `MemoryStore.live`, `PostgresStore` against a fake connection
  - SQL shape and the avatar URL helper
- `tests/test_leaderboard_ui.py` `test_live_*` / `test_*live_view*`:
  - LB game renders the live view; the guest game doesn't
  - text keys exist in es and en (incl. `lb_live_won`/`lb_live_lost`)
  - Playwright with a faked `/api/live`: desktop sidebar (title tooltip, accessible names like "@heisen, ganó", no `.c24-live-dot`), phone sheet, empty state, polling pauses and backs off
  - layout fits with no overlap at several sizes (`LIVE_SIZES`, incl. 860×600; rail when `width >= 860 and height > 500`)
  - `tests/test_live_rail.py` (new 2026-10-29, 9 tests): cards are avatar + grid only (147×80 ±, 64px round avatar, 30 cells, info visually hidden) at 1366×768 web, 1000×493 Discord and 860×600, light and dark; rail 16px left / 10px under the header; rail scrolls inside when long; phone sheet wraps the same cards; Discord phone invite card same size as a player card
  - rail and invite card: `tests/test_layout.py` (`test_rail_never_moves_or_shrinks_the_board`, `test_rail_shows_cards_even_with_nobody_playing`, `test_activity_phone_keeps_bottom_sheet`)
  - facepile (2026-10-28): `test_live_facepile_on_phone_opens_sheet_with_loaded_avatars`, `test_live_people_icon_when_nobody_plays`, `test_live_facepile_header_fits` (es/en at several sizes; helper `open_lb_mobile`)
- Run: `.venv/bin/python -m pytest -q tests/test_live.py tests/test_leaderboard_ui.py tests/test_layout.py`.

## Common tasks
- **Change the poll interval:** `LIVE_EVERY` (and `LIVE_MAX`) in `game.js`. Keep `LIVE_RATE_LIMIT_PER_MINUTE` in `app.py` above 60 s ÷ interval, with room for tab refreshes.
- **Change how many players show:** `LIVE_LIMIT` in `app.py`. The client also caps the list at 50 in `applyLive`.
- **Change the "en vivo" window:** `LIVE_RECENT_SECONDS` in `app.py` (5 minutes).
- **Hide a player from the live view:** use admin hide (`casa24-leaderboard`). It hides them from the rankings and the live view together. There is no live-only hide.
- **Change the facepile:** markup in `game.html` (`live_players.slice(0, 3)`), styles `.c24-facepile`, `.c24-face`, `.c24-live-btn.has-faces` and the `max-width: 399px` rule (2 faces) next to the header-bar rules in `style.css`. Re-run `test_live_facepile_header_fits`.
- **Change the card look:** `--c24-card-w/-h/-gap` on `.c24-live`, `.c24-live-card`, `.c24-live-avatar`, `.c24-live-grid` in the live section; re-run `tests/test_live_rail.py`.
- **Change breakpoints:** the `min-width: 860px and min-height: 501px` media query in the style.css live section (and the Discord `min-width: 860px` block near the end of the Activity section). Then re-run the layout tests (see `casa24-responsive`).

## Header at narrow widths (2026-10-29)
The leaderboard game uses the 2-area header (brand left, actions right: people/facepile, help, trophy, stats, settings, avatar; see `casa24-responsive`). Where the actions need the room, only the "Casa 24" text hides (`.c24-title-text`; on `/lb/` pages at ≤480px, inside the Activity at ≤419px); Kolo, the badge and all buttons stay. Re-run `test_live_facepile_header_fits` and `tests/test_layout.py` after changes.

- **Your own avatar comes from the server (fixed 2026-10-27):** `lb_current_user()` adds `avatar_url` (from `store.get_avatar`) and `has_avatar`; `_discord.html` renders it directly, and the `c24_dc_avatar` localStorage copy only overrides it when present. Players who signed in before avatars were stored get **one silent pass through Discord** (`lb_avatar_refresh()` on `/lb/<lang>`: redirect to `/auth/discord/login?next=…` with `prompt=none`), guarded by a 1-day `c24_avr` cookie so it never loops (e.g. users with no Discord picture). Tests: `test_avatar_refresh_once_when_no_picture_saved`, `test_no_avatar_refresh_when_picture_saved`; `lb_testlib.login()` sets `c24_avr` to skip it elsewhere.
