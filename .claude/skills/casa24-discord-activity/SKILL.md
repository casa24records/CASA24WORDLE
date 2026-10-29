---
name: casa24-discord-activity
description: Casa 24 Wordle as a Discord Activity (play inside Discord with the Embedded App SDK) — detection by frame_id/instance_id/platform, the thin discord-activity.js layer (window.C24Activity), automatic login (authorize → POST /api/activity/token → authenticate), Bearer header session, discordsays.com same-origin, CSP rules (no inline on*/javascript:, no external hosts, nonce), vendored SDK path and version, timeouts, layout mode (PIP/grid), portrait lock, safe areas, preserved query params, the in-game leaderboard window (/api/leaderboard), Developer Portal settings (URL mapping, Enable Activities, platforms), how to turn it off, tests and SDK updates. Use for any Discord Activity, activity, embedded app SDK, discordsays, URL mapping, iframe, App Launcher or Developer Portal activities question.
---

# Discord Activity

**Rule #1: El servidor es la fuente de verdad de la partida; web y Activity solo la pintan.** (The server owns the game; the website and the Activity only paint it.) Never keep leaderboard progress in the browser, never let the client decide colors, points or "finished", and always repaint from `GET /api/state` (or the `state` carried by a 409/`finished` answer). Sync details: `casa24-leaderboard` ("Sync between devices").

Status (2026-10-28): code written (not yet pushed when this was written; check `git log`). Vendored assets came in `d229fcf`, server-synced state in `5966e7a`. The Activity is **off** until the owner sets the URL Mapping and ticks Enable Activities in the Portal. Owner's step-by-step guide (Spanish): `docs/discord-activity-manual.md`. Verified requirements with sources: `docs/discord-activity-checklist.md` (re-verify Discord's docs before big changes; they change often). Original plan: `docs/discord-activity-plan.md`. Why: `casa24-decisions` ("Discord Activity and sync").

## Architecture (one app, one deploy, one game code)
- **Same pages, same Vercel deploy.** Discord loads our site through its proxy `https://1564412150519169067.discordsays.com` (Portal URL Mapping `/` → `casa-24-wordle.vercel.app`). No separate build.
- **Detection:** `is_activity()` in `app.py` is true only when the URL has `frame_id`, `instance_id` and `platform` ∈ `ACTIVITY_PLATFORMS` (`desktop`, `mobile`). Context processor `inject_activity()` gives templates `C24_ACTIVITY`, `activity_params`, `activity_client_id` (public ID only), `activity_langs`. Without the params nothing changes on the web and the SDK is never requested.
- **Routes inside the Activity:**
  - `/` → `/lb/<lang>` keeping Discord's query (`?lang=` if valid, else `es` plus `c24_root=1`; `game.js` then switches once to the language this device played last, localStorage `casa24_lang`).
  - `/<lang>` (guest game) → `/lb/<lang>`: **no guest mode in Discord**. No Developer view, no login/logout menu.
  - `/lb/<lang>` renders an **empty board** (`lb_state=None`, no cookie travels); after the login `game.js` (`activityFirstLoad`) loads `GET /api/state`.
  - `/leaderboard` inside the Activity is the public table (no "you"); the game instead opens an in-page **leaderboard window** (`openBoard()`, `[data-activity-board]`) fed by `GET /api/leaderboard?tab=`.
  - Language change: a select in Settings (`#activity-lang-select`, `data-nav-select`).
- **Query preserved everywhere** (the SDK re-reads `location.search` on every page load; we are multi-page, so each navigation repeats the handshake): server side `aq()` / `activity_url(path)` adds Discord's params (everything except our own `ACTIVITY_OWN_PARAMS`: `layout, tab, lang, c24_root, login, deleted, skip, next`); client side `discord-activity.js` rewrites same-site `<a href>` on click and adds hidden inputs to GET forms; `C24Activity.url(path)`. Keep `OUR_PARAMS` in the JS equal to `ACTIVITY_OWN_PARAMS`.
- **Thin layer `webapp/static/discord-activity.js`** (ES module, `<script type="module">` only when `in_activity` in `game.html`): `new DiscordSDK(client_id)` → `ready()` → login → exposes **`window.C24Activity`** = `{session (getter), ready (Promise), fetch(url, opts) (adds Bearer, credentials omit), reauth(), url(path)}` and fires a `c24activity` event. `game.js` only uses it through `lbFetch()` / `activityReady()`; game logic stays in `game.js`.
- **Automatic login, no login button** (owner decision):
  1. `authorize({client_id, response_type:'code', state:'', prompt:'none', scope:['identify']})` — `identify` only, ever (a new scope re-prompts everyone).
  2. `POST /api/activity/token {code}` → `exchange_code(code, None)` (**no `redirect_uri` field**), `fetch_me`, `parse_me`, `upsert_player(id, username, avatar_hash)` → `{access_token, session, user:{username}}`. Errors: 404 `disabled`, 403 `forbidden`, 400 `bad_request` (code missing / >200 chars), 429 `rate` (one **global** bucket `activity:token`, 120/min, no IPs kept), 400 `discord` (exchange failed), 503 `store`. Token never stored or logged.
  3. `authenticate({access_token})`, then the token is dropped.
  4. `session` = the same signed value as the `c24_lb` cookie (`_serializer("c24-lb")`, 30 days), **in memory only**, sent as `Authorization: Bearer <session>`.
  - Overlay `#c24-activity` (`data-state` = `loading` | `denied` | `error` | `ready`; texts "Conectando con Discord…", the permission message, the error message) with **"Intentar de nuevo / Try again"** — the only button, shown after a refusal or timeout. If the module never runs (blocked/failed), `game.js` `activityWatchdog()` shows the error state.
  - A 401 from `/api/state`, `/api/guess` or `/api/live` → `activityReauth()` → `C24Activity.reauth()` once (silent authorize), never a redirect to `/auth/discord/login`.
  - First launch shows Discord's OAuth modal once; unavoidable.
- **Header session:** `_lb_session_value()` → `lb_player_id()`: if an `Authorization` header is present, **only** it is read (Bearer), else the `c24_lb` cookie. Works for `/api/state`, `/api/guess`, `/api/live`, `/api/leaderboard` (marks your row), `/api/me/delete`. Never switch the web cookies to `SameSite=None`.
- **Same-origin check:** `_same_origin()` accepts our host or exactly `https://<DISCORD_CLIENT_ID>.discordsays.com` (`_discordsays_host()`, no wildcards, https only).
- **Identity only from the server** (`fetch_me`), never from SDK `auth.user` or query params (`test_query_ids_never_choose_the_player`).

## CSP rules (Discord's proxy; observed 2026-10-28)
`default-src 'self'; script-src 'self' 'unsafe-eval' 'nonce-…' blob:; style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data: https://cdn.discordapp.com https://media.discordapp.net; font-src 'self' data:; connect-src 'self' https://discord.com https://cdn.discordapp.com https://media.discordapp.net …`
- **No `onclick=`/`onchange=`/`onsubmit=`… and no `javascript:` URLs** in any template or rendered page (handlers can't take the nonce). Use `addEventListener`/delegation: `theme.js` (`data-theme-toggle`, `data-theme-select`, `data-autosubmit`, `data-nav-select`), `discord.js` (avatar menu, privacy dialog, toasts, in-page "delete my data" confirm), `leaderboard.js` (tabs). Tests scan sources and rendered pages.
- **No `confirm()`, `alert()` or `window.open`** in static JS (test).
- **No external hosts**: no CDN, no Google Fonts, no absolute `https://casa-24-wordle.vercel.app/...` URLs. Everything relative, from `/static`. `cdn.discordapp.com` images are allowed (also `/embed/avatars/`).
- Inline `<script>` blocks get the proxy's nonce (seen in published apps, not documented). JSON blocks (`type="application/json"`) are data. If the nonce ever fails, move inline scripts to files.
- Vue's in-browser template compiler is fine (`'unsafe-eval'`); inline styles are fine. No Service Workers, WebRTC or WebTransport. `patchUrlMappings` not used.

## Vendored files
- SDK: `webapp/static/vendor/discord-embedded-app-sdk-2.5.0/` (npm `@discord/embedded-app-sdk@2.5.0` ESM: `index.mjs` + ~70 relative `.mjs`, deps bundled, `mock.mjs`). Imported as `./vendor/discord-embedded-app-sdk-2.5.0/index.mjs` (`DiscordSDK`, `Common`). Its files import each other **without `?v=`**, so the **folder name carries the version** and is never rewritten. Source + SHA-256: `CREDITS.md`.
- Vue `static/vendor/vue.global.prod.js` (3.5.13); compiled `static/tailwind.css` (`scripts/build_css.py`, see `casa24-deploy`).
- **Do not use the 3.0.0 beta.** Stable is 2.5.0 (2026-05-05).

## Robustness
- **Timeouts are ours** (the SDK has none): `READY_MS` 10 s, `AUTHORIZE_MS` 5 min (player may be reading the modal), `TOKEN_MS` 15 s, `AUTHENTICATE_MS` 10 s. Timeout → `error` state + Try again.
- **Optional commands** in `try/catch`, silent on failure (old clients answer 4002/4004): `subscribe('ACTIVITY_LAYOUT_MODE_UPDATE')`, `setOrientationLockState`.
- **Layout mode:** `layout_mode` 0 focused / 1 PIP / 2 grid → class **`c24-pip`** and `data-layout-mode` on `<html>`; in PIP/grid only the board shows (header, keyboard, live view, modals, toasts hidden). `subscribeToLayoutModeUpdatesCompat` **does not exist in 2.5.0** despite the docs.
- **Orientation:** Portal default lock Portrait (phone + tablet); code calls `setOrientationLockState({lock_state: PORTRAIT})` only when `sdk.platform === 'mobile'`.
- **Safe areas:** `style.css` `:root` defines `--c24-safe-{top,right,bottom,left}` = `var(--discord-safe-area-inset-*, env(safe-area-inset-*))`; layout uses those (web too). See `casa24-responsive`.
- **Lifecycle:** close + reopen = new `instance_id`; nothing is keyed by instance; the game comes from `/api/state`, also on focus/visibility.
- **Console:** the SDK forwards `console.*` to Discord; never log code, token or session (test).
- **Sharing inside Discord:** copy to clipboard only (no `navigator.share`, no new windows); if copying fails, a window with the text to copy by hand (`openShareText`). Links use `public_url()` (`PUBLIC_ORIGIN`), never the discordsays origin. `shareLink`/`openExternalLink` are **not used** (possible later).
- **Accessibility:** the global `keydown` never captures Tab or Escape.

## Files
| File | Role |
|---|---|
| `webapp/static/discord-activity.js` | SDK, handshake, login, timeouts, query keeping, layout/orientation, `C24Activity` |
| `webapp/app.py` | section "DISCORD ACTIVITY" (`is_activity`, `activity_params`, `activity_url`/`aq`, `inject_activity`), Activity redirects in `/`, `/<lang>`, `/lb/<lang>`; `_lb_session_value`, `_discordsays_host`, `_same_origin`; `POST /api/activity/token`; `GET /api/leaderboard` + `lb_board()`; `GET /api/state`, `attempt`/409 |
| `webapp/discord_auth.py` | `exchange_code(code, redirect_uri=None)` omits the field when `None`; `parse_me()` |
| `webapp/store.py` | rate bucket `token` (global key `activity:token`) |
| `webapp/templates/game.html` | `in_activity`: `#c24-activity` JSON + overlay, module script, Settings language select, leaderboard window, no login menu |
| `webapp/static/game.js` | `ACTIVITY`, `lbFetch`, `activityReady`, `activityFirstLoad`, `activityWatchdog`, `activityReauth`, `openBoard`, `c24_root` language switch, share |
| `webapp/static/discord.js`, `leaderboard.js`, `theme.js` | former inline scripts/handlers (CSP) |
| `webapp/static/style.css` | `--c24-safe-*`, `.c24-pip`, `.c24-activity-overlay` |

## Tests
- `tests/test_activity.py` (being written alongside the code; check it for the current list) covers: detection, query keeping, web unchanged, Activity redirects, token endpoint and its errors, no `redirect_uri`, Bearer session (and 401s), discordsays origin, `/api/leaderboard`, no inline JS / `confirm` / secrets in console, SDK version pinned; plus Playwright with a `DiscordSDKMock` shim routed over `index.mjs` (auto login, refusal + Try again, timeouts, PIP/safe areas, leaderboard window, share) and the **Discord CSP test** (real CSP header + nonce, foreign requests aborted, zero violations).
- Recipes (mock shim, CSP harness, fake parent): checklist §4. Sync tests: `tests/test_sync.py`.
- Only real Discord can show: checklist §3 and the manual's last table.

## Developer Portal (owner does it; full guide `docs/discord-activity-manual.md`)
- One app **"Casa 24 Wordle"** (`1564412150519169067`), owned by Team **Casa 24**.
- OAuth2 Redirects: the 3 web callbacks + placeholder `https://127.0.0.1`.
- Installation: **Guild Install only**, scope `applications.commands`, no bot.
- Activities → Settings: Supported Platforms Web/Desktop + iOS + Android; Default Orientation Lock Portrait (phone, tablet).
- **The switch, only after the code is on `main`:** Activities → URL Mappings `/` → `casa-24-wordle.vercel.app` (no `https://`), then **Enable Activities** (creates the "Launch" Entry Point command; never delete it).
- **No new env vars** (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `SECRET_KEY`, `DATABASE_URL`; optional existing `PUBLIC_URL` for share links).

## How to turn it off (no code)
Portal → Activities → Settings → untick **Enable Activities** → Save (gone from the App Launcher). Or delete the `/` URL Mapping (opens blank). The website is unaffected either way.

## How to update the SDK version
1. Read the SDK CHANGELOG and Discord's change log since 2.5.0; skip betas. Ask the owner before downloading.
2. Put the new npm tarball's `output/` ESM files in a **new** folder `webapp/static/vendor/discord-embedded-app-sdk-<version>/` (never overwrite the old one: cached a year without `?v=`). Record source URL + SHA-256 in `CREDITS.md`.
3. Change the import in `discord-activity.js` and the version in `tests/test_activity.py` (route patterns, pin test).
4. Check the names we use still exist: `DiscordSDK`, `Common.OrientationLockStateTypeObject`, `ready`, `commands.authorize/authenticate/setOrientationLockState`, `subscribe('ACTIVITY_LAYOUT_MODE_UPDATE')`, `DiscordSDKMock` in `mock.mjs`.
5. Full suite (including the CSP test), then real Discord (manual, Parte C). Delete the old folder in a later commit.

## Gotcha: the `lib/` gitignore rule (fixed 2026-10-29)
The standard Python `.gitignore` has `lib/`, which silently hid the vendored SDK's bundled dependencies (`vendor/discord-embedded-app-sdk-2.5.0/lib/…`: tslib, uuid, zod, …). They existed locally (tests passed) but were never committed, so on Vercel they returned 404, the SDK import failed and the Activity showed "No pudimos conectar con Discord" after the 10 s timeout. `.gitignore` now un-ignores `webapp/static/vendor/**/lib/`, and `tests/test_activity.py::test_vendored_sdk_fully_tracked` fails if any module the SDK imports is not tracked by git. When updating the SDK, run that test before pushing. First debugging step for "stuck connecting": check `vercel logs` for 404s under `/static/vendor/`.
