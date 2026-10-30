---
name: casa24-discord-activity
description: Casa 24 Wordle as a Discord Activity (play inside Discord with the Embedded App SDK) — the Activity shell (activity.html + activity-shell.js, served at / and /activity, SDK constructed once per launch) hosting the game in a same-origin iframe (/lb/<lang>?embed=1, discord-activity.js bridge), why the top document must never navigate, detection (frame_id/instance_id/platform vs embed=1), window.C24Activity, automatic login (authorize → POST /api/activity/token → authenticate), Bearer header session, language choice (saved device choice → Discord's locale → 2-option fallback picker) and header language window, the "Invite friends" card (openInviteDialog), the live rail at ≥860px, SDK modulepreloads (preload.py) and load times, discordsays.com same-origin, CSP rules (frame-src/child-src, no inline on*/javascript:, no external hosts, nonce), vendored SDK path and version, timeouts, layout mode (PIP/grid), portrait lock, safe areas, the in-game leaderboard window (/api/leaderboard), Developer Portal settings and owner FAQ (dev badge, URL Override, Bot page, verification/Discovery), how to turn it off, tests and SDK updates. Use for any Discord Activity, activity, embedded app SDK, discordsays, URL mapping, iframe, shell, App Launcher or Developer Portal activities question.
---

# Discord Activity

**Rule #1: El servidor es la fuente de verdad de la partida; web y Activity solo la pintan.** (The server owns the game; the website and the Activity only paint it.) Never keep leaderboard progress in the browser, never let the client decide colors, points or "finished", and always repaint from `GET /api/state` (or the `state` carried by a 409/`finished` answer). Sync details: `casa24-leaderboard` ("Sync between devices").

**Rule #2: Never navigate the top document (the shell).** No `location.href = …`, no `<a href>`, no redirect away from it, no form submit in it. Only the iframe inside it changes pages.

Status (2026-10-29): the shell + iframe architecture is live in production (commit `18f167a`). Earlier: vendored assets `d229fcf`, server-synced state `5966e7a`, first Activity version `591c0cc`, SDK `lib/` files tracked `e7fc9a8`. Owner's step-by-step guide (Spanish): `docs/discord-activity-manual.md`. Verified requirements with sources: `docs/discord-activity-checklist.md` (re-verify Discord's docs before big changes; they change often). Best-practice review of the shell design (2026-10-28, with sources): summarized below. Why: `casa24-decisions` ("Discord Activity and sync").

## Why a shell (root cause of the "No pudimos conectar" bug)
The first version was multi-page: `/` redirected to `/lb/es`, and every page built its own `DiscordSDK`. In SDK 2.5.0 `getRPCServerSource()` posts the handshake to `window.parent` with **`document.referrer` as the `targetOrigin`**. After any in-frame navigation the referrer is our own `https://<id>.discordsays.com/...`, not `https://discord.com`, so the browser silently drops the handshake, `READY` never arrives, the 10 s timeout fires. A second handshake after a navigation can't work with this SDK. `location.reload()` keeps the original referrer, so a reload is safe; a navigation is not.

Fix = Discord's own recommendation for non-SPA apps ("how-activities-work": nest your framework inside a top-level SPA; official sample `discord/embedded-app-sdk-examples/nested-messages`): a tiny **shell** that owns the SDK, and the game in a **same-origin iframe**.

## Architecture (one app, one deploy, one game code)
- **Same pages, same Vercel deploy.** Discord loads our site through its proxy `https://1564412150519169067.discordsays.com` (Portal URL Mapping `/` → `casa-24-wordle.vercel.app`). No separate build.
- **Detection (`app.py`, section "DISCORD ACTIVITY"):**
  - `is_activity_launch()`: `frame_id` + `instance_id` + `platform` ∈ `ACTIVITY_PLATFORMS` (`desktop`, `mobile`) → this request is **the shell**.
  - `is_activity_embed()`: `?embed=1` → the game page **inside the shell's iframe**. Its URL has **no** Discord params on purpose (like the sample): nothing in it can mistake itself for the top page or start the SDK.
  - `is_activity()` = either. Context processor `inject_activity()` gives templates `C24_ACTIVITY`, `activity_params`, `activity_client_id` (public ID only), `activity_langs` (`code`, `name_native`; es and en only). Without these params nothing changes on the web and the SDK is never requested.
- **Routes inside the Activity:**
  - `/` and `/activity` with launch params → `activity_shell(lang)` renders **`templates/activity.html`** directly (**no redirect**), `no-store`. `?lang=` (if valid) opens that language right away. With `embed=1` they redirect to `/lb/<lang>` instead, so the shell can never load inside its own iframe. `/activity` without Activity params → `/`.
  - `/lb/<lang>` with launch params (but not `embed=1`) → also the shell, opened on that language.
  - `/lb/<lang>?embed=1` → the game: **empty board** (`daily_word=""`, no cookie travels); after the shell's login `game.js` (`activityFirstLoad`) loads `GET /api/state`. `<html class="c24-embed">`.
  - `/<lang>` (guest game) → `/lb/<lang>`: **no guest mode in Discord**. No Developer view, no login/logout menu.
  - `/leaderboard` inside the Activity is the public table (no "you"); the game instead opens an in-page **leaderboard window** (`openBoard()`, `[data-activity-board]`) fed by `GET /api/leaderboard?tab=`.
- **Shell `webapp/static/activity-shell.js`** (ES module, only page that imports the SDK):
  1. Constructs `new DiscordSDK(client_id)` **once** → `ready()` → `authorize({client_id, response_type:'code', state:'', prompt:'none', scope:['identify']})` → `POST /api/activity/token {code}` (**one retry on 429**, waiting `Retry-After` clamped 1–5 s) → `authenticate({access_token})` → session **in memory only**; the token is dropped.
  2. Starts loading the iframe **in parallel** with the login (the game waits for `C24Activity.ready`).
  3. Exposes **`window.C24Activity`** = `{session (getter), ready (Promise), lang (getter), layout (getter), fetch(url, opts) (adds Bearer, credentials omit), reauth(), setLang(code), invite()}` (plus logging/external-link helpers).
  4. After login, once: subscribes `ACTIVITY_LAYOUT_MODE_UPDATE` (one listener, never per iframe load), `setOrientationLockState({lock_state: PORTRAIT})` only when `sdk.platform === 'mobile'`, `userSettingsGetLocale()` to pick the language on a device with no saved choice (`chooseLanguage()`, see "Language"). All optional, `.catch(()=>{})`.
  5. Applies **safe areas**: `.c24-shell-frame` is `position: fixed` inside `var(--c24-safe-*)` (= Discord's `--discord-safe-area-inset-*`, which exist only on the shell document), shell background = game background.
  6. Forwards iframe errors (`{type:"c24-log"}`) to `console.warn` (the SDK sends the shell's console to Discord's debug logs). Never secrets.
  7. Overlay `#c24-activity-overlay`: `data-state` `loading` | `denied` | `error` | `ready`, `data-step` `connect` ("Conectando…") → `game` ("Cargando juego…", translated). **"Intentar de nuevo / Try again"** retries `authorize`/token/`authenticate` **on the same SDK instance**; `location.reload()` only if `ready()` itself failed (reload keeps the referrer). The shell never navigates.
  8. Theme: follows the game's `casa24_theme` via the `storage` event.
- **Game bridge `webapp/static/discord-activity.js`** (module, loaded by `game.html` only when `in_activity`): **never loads the SDK**. Finds `window.parent.C24Activity` (same origin checked) and exposes its own `window.C24Activity` = `{session, ready, fetch, reauth, log, url, setLang, invite, onParticipants(cb)}` to `game.js`; fires `c24activity`. `fetch` adds the shell's Bearer; a **401** asks the shell to `reauth()` (silent authorize) and retries **once**; if re-login fails the shell shows Try again and reopens the game after it works. Opened outside the shell → `error` state. Still keeps `embed=1` on same-site links/GET forms (`OUR_PARAMS` must equal `ACTIVITY_OWN_PARAMS`: `layout, tab, lang, c24_root, login, deleted, skip, next`); server side `aq()` / `activity_url(path)`.
- **Messages between the two documents:** plain objects only, never arrays (the SDK in the shell also receives messages from our origin and reads arrays as its own opcodes). Both sides check `e.origin === location.origin` and `e.source` (iframe's `contentWindow` / `window.parent`). Types: `c24-lang {code}` (game → shell), `c24-invite` (game → shell), `c24-layout {mode}` (shell → game), `c24-participants {participants}` (shell → game), `c24-layout-request` (answered with layout and participants), `c24-log {message}`.
- **The iframe:** `<iframe id="c24-game" allow="clipboard-write">`, **no `sandbox`** (it would break `parent.C24Activity`). Focused after each load so the keyboard types into the board; Tab/Esc never captured.
- **Never add `X-Frame-Options` or `frame-ancestors`**: Discord frames the shell, the shell frames us.

## Language (owner decision, 2026-10-29; es and en only)
- **Rule (`chooseLanguage()` in `activity-shell.js`):** 1) the choice saved on this device, localStorage **`c24_activity_lang`** (try/catch), wins; 2) else **Discord's own language** after the login: `userSettingsGetLocale()` (works with `identify`), `localeLang()`: `es…` (es-ES, es-419) → Español, anything else → English; 3) only if that call fails, returns nothing or takes more than **3 s** (`LOCALE_MS`), the **2-option picker** (`#c24-picker`, title from `activity_pick_title`) asks. This **supersedes** the earlier "picker on first launch" decision (same day): with two languages a picker is just one more tap.
- **Changing it:** the game header in Discord is a button **"Casa 24 ES ▾"** (`.c24-lang-btn`, `openLang()`, aria-label `activity_lang_button`) that opens an in-page language window (`[data-activity-langs]`, `chooseLang()`). Choosing posts `c24-lang` → the shell saves it and swaps the iframe with **`contentWindow.location.replace(url)`** (no history entry), the Discord connection stays.
- Tests: `test_browser_first_launch_follows_discord_locale`, `test_browser_locale_timeout_shows_picker`, `test_browser_remembered_language_on_relaunch`, `test_browser_picker_small_screens`.

## Invite friends (owner, 2026-10-29)
- First card of the live rail / sheet, **inside the Activity only** (`.c24-live-invite`, `data-live-invite`, text `activity_invite`); since 2026-10-29 the same 147×80 size as a player card, with a 64px green circle (`test_activity_phone_sheet_has_invite_card_same_size`).
- Flow: `inviteFriends()` (`game.js`) → `C24Activity.invite()` (`discord-activity.js`) → `postMessage {type: "c24-invite"}` → the shell's `invite()` calls **`sdk.commands.openInviteDialog()`**. **No new OAuth scope** (still `identify` only). Does nothing before the handshake. Tested in `test_activity_shell_language_rule_and_invite_bridge` (`tests/test_languages.py`).

## Friends joining show at once (owner, 2026-10-30)
- The shell's `extras()` calls `getInstanceConnectedParticipants()` once and subscribes to **`ACTIVITY_INSTANCE_PARTICIPANTS_UPDATE`** (no extra OAuth scope). `onParticipants` keeps only `{id, username, avatar}` (id digits ≤20, avatar hash checked, max 50), leaves **yourself** out (`selfId` from the `authenticate` result) and posts `c24-participants` to the iframe (also on iframe load and on `c24-layout-request`).
- The bridge validates again and calls `C24Activity.onParticipants(cb)` listeners (a late subscriber gets the last list).
- `game.js` `applyParticipants`: someone not in `/api/live` yet gets a card at once (`live_participants` → computed `live_cards`, class `is-pending`, empty board, avatar built like `lb_avatar_url`), and `/api/live` is asked right away. Leaving the Activity removes a pending card; server cards stay (they played today).
- Only covers people in **the same Activity instance** (same call / channel). Others show through polling (3 s).
- Test: `test_browser_friend_joining_pops_up_in_live_view` (`tests/test_activity.py`, emits the event on the SDK mock).

## Speed
- `activity.html` emits `<link rel="modulepreload">` for all **69 SDK modules** (`webapp/preload.py` `sdk_modulepreloads()`: static BFS of relative imports from `index.mjs`, `lru_cache`, `SDK_VERSION` constant) so they download in parallel instead of an import waterfall through Discord's proxy.
- Also preloads the game's own files with the **same `?v=` URLs** as `game.html` (`vue.global.prod.js`, `tailwind.css`, `game.js`, modulepreload `discord-activity.js`), so the iframe reuses them.
- `vercel.json` marks the versioned SDK folder `immutable` (the proxy strips cache headers only from `text/html`).
- Measured locally with 150 ms simulated proxy latency: first launch **~1.9 s → ~1.1 s**, relaunch **~0.6 s**.
- If proxy latency still dominates: bundle the SDK into one ESM file at vendoring time (idea, not done).

## CSP rules (Discord's proxy; observed 2026-10-28)
`default-src 'self'; script-src 'self' 'unsafe-eval' 'nonce-…' blob:; style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data: https://cdn.discordapp.com https://media.discordapp.net; font-src 'self' data:; connect-src 'self' https://discord.com …; frame-src https://<id>.discordsays.com/ wss://<id>.discordsays.com/ https://discord.com/embeds/video-frame …; child-src https://<id>.discordsays.com/ wss://<id>.discordsays.com/ blob:` (full copy: checklist §4-B). The trailing `/` allows framing any path of our own origin, so the iframe is allowed. The iframe's HTML also passes through the proxy (own CSP + nonce, `no-store`).
- **No `onclick=`/`onchange=`/`onsubmit=`… and no `javascript:` URLs** in any template or rendered page. Use `addEventListener`/delegation (`theme.js`, `discord.js`, `leaderboard.js`). Tests scan sources and rendered pages. `activity.html` has no inline JS (JSON block `#c24-shell` only).
- **No `confirm()`, `alert()` or `window.open`** in static JS (test).
- **No external hosts**: no CDN, no Google Fonts, no absolute `https://casa-24-wordle.vercel.app/...` URLs. Everything relative, from `/static`. `cdn.discordapp.com` images are allowed.
- Vue's in-browser template compiler is fine (`'unsafe-eval'`); inline styles are fine. No Service Workers, WebRTC or WebTransport. `patchUrlMappings` not used.

## Vendored files
- SDK: `webapp/static/vendor/discord-embedded-app-sdk-2.5.0/` (npm `@discord/embedded-app-sdk@2.5.0` ESM: `index.mjs` + relative `.mjs`, deps bundled under `lib/`, `mock.mjs`). Imported only by `activity-shell.js` as `./vendor/discord-embedded-app-sdk-2.5.0/index.mjs` (`DiscordSDK`, `Common`). Its files import each other **without `?v=`**, so the **folder name carries the version** and is never rewritten. Source + SHA-256: `CREDITS.md`.
- Vue `static/vendor/vue.global.prod.js` (3.5.13); compiled `static/tailwind.css` (`scripts/build_css.py`, see `casa24-deploy`).
- **Do not use the 3.0.0 beta.** Stable is 2.5.0 (2026-05-05).

## Robustness
- **Timeouts are ours** (the SDK has none and never reconnects): `READY_MS` 10 s, `AUTHORIZE_MS` 5 min, `TOKEN_MS` 15 s, `AUTHENTICATE_MS` 10 s, `LOCALE_MS` 3 s. Timeout → `error` + Try again. Authorize refused → `denied`.
- **Server side** `POST /api/activity/token`: `exchange_code(code, None)` (**no `redirect_uri`**), `fetch_me`, `upsert_player` → `{access_token, session, user:{username}}`. Errors: 404 `disabled`, 403 `forbidden`, 400 `bad_request`, 429 `rate` (global bucket `activity:token`, 120/min), 400 `discord`, 503 `store`. Token never stored or logged. `session` = same signed value as the `c24_lb` cookie (30 days).
- **Header session:** `_lb_session_value()`: an `Authorization` header wins (Bearer), else the `c24_lb` cookie. Never switch web cookies to `SameSite=None`. `_same_origin()` accepts our host or exactly `https://<DISCORD_CLIENT_ID>.discordsays.com`. Identity only from the server (`fetch_me`), never from SDK `auth.user` or query params.
- **Layout mode:** `layout_mode` 0 focused / 1 PIP / 2 grid → class **`c24-pip`** + `data-layout-mode` on both documents; in PIP/grid **only the board** shows. `subscribeToLayoutModeUpdatesCompat` **does not exist in 2.5.0** despite the docs.
- **Orientation:** Portal default lock Portrait (phone + tablet) plus the mobile-only call in the shell.
- **Safe areas:** applied by the shell; the iframe gets `0px` (`:root.c24-embed` sets `--c24-safe-*: 0px`). See `casa24-responsive`.
- **Lifecycle:** close + reopen = new `instance_id`; nothing keyed by instance; the game comes from `/api/state`, also on focus/visibility.
- **Console:** never log code, token or session (test).
- **Sharing inside Discord:** clipboard only; fallback window with text to copy (`openShareText`). Links use `public_url()`, never the discordsays origin.

## Files
| File | Role |
|---|---|
| `webapp/templates/activity.html` | the shell: modulepreloads, `#c24-shell` JSON, iframe `#c24-game`, picker `#c24-picker`, overlay |
| `webapp/static/activity-shell.js` | SDK (once), login, 429 retry, timeouts, language rule + fallback picker, invite dialog, iframe swap, layout/orientation, `C24Activity`, log forwarding |
| `webapp/static/discord-activity.js` | game-side bridge in the iframe: borrows the shell's session, 401 → reauth once, `setLang`, `invite`, layout from the shell, `embed=1` on links |
| `webapp/preload.py` | `sdk_modulepreloads()` |
| `webapp/app.py` | `is_activity_launch`/`is_activity_embed`/`is_activity`, `activity_params`, `activity_url`/`aq`, `activity_shell()`, `inject_activity`, routes `/`, `/activity`, `/<lang>`, `/lb/<lang>`; `_lb_session_value`, `_same_origin`; `POST /api/activity/token`; `GET /api/leaderboard` |
| `webapp/templates/game.html` | `in_activity`: `c24-embed` class, header language button + language window, overlay, bridge module, leaderboard window, no login menu |
| `webapp/static/game.js` | `ACTIVITY`, `lbFetch`, `activityReady`, `activityFirstLoad`, `activityWatchdog`, `activityReauth`, `openBoard`, `openLang`/`chooseLang`, share |
| `webapp/static/style.css` | `--c24-safe-*`, `.c24-shell*`, `.c24-picker*`, `.c24-lang-*`, `.c24-pip`, `.c24-activity-overlay` |
| `vercel.json` | `immutable` for `?v=` assets and the versioned SDK folder |

## Tests
- `tests/test_activity.py`: detection, query keeping, web unchanged, `/` renders the shell (no redirect), shell never inside its own iframe, shell off when the leaderboard is off, game page in embed mode, Activity texts in es and en, token endpoint + errors, Bearer + 401s, discordsays origin, `/api/leaderboard`, no inline JS / `confirm` / secrets, SDK pinned, `test_vendored_sdk_fully_tracked`. Playwright (a `DiscordSDKMock` shim routed over `index.mjs`): **one SDK for the whole launch** (language swaps included), remembered language on relaunch, first launch follows Discord's locale, locale timeout → picker, Bearer through the shell, leaderboard window + share, refused → Try again (in page, no reload), ready timeout, **Discord CSP test** (real CSP with `frame-src`/`child-src` + nonce on shell and iframe, zero violations), mobile PIP + safe areas, picker at phone and 240×180.
- `tests/test_vercel_ready.py`: `test_vercel_json_caches_versioned_sdk`, `test_sdk_modulepreloads`.
- Recipes: checklist §4. Only real Discord can show: checklist §3 and the manual's last table.

## Developer Portal (owner does it; full guide `docs/discord-activity-manual.md`)
- One app **"Casa 24 Wordle"** (`1564412150519169067`), owned by Team **Casa 24**.
- OAuth2 Redirects: the 3 web callbacks + placeholder `https://127.0.0.1`.
- Installation: **Guild Install only**, scope `applications.commands`, no bot.
- Activities → Settings: Supported Platforms Web/Desktop + iOS + Android; Default Orientation Lock Portrait (phone, tablet).
- URL Mappings `/` → `casa-24-wordle.vercel.app` (no `https://`), **Enable Activities** (creates the "Launch" Entry Point command; never delete it).
- The shell change needed **no Portal change** (same `/` mapping). **No new env vars.**

## Owner FAQ (Portal / Discord UI)
- **The "<>" dev badge and "Use Activity URL Override"** appear because the owner has Developer Mode on and/or the app is not distributed. Players don't need them. Removing them for everyone requires **App Verification + Discovery** (Portal → Discovery); Discord will likely ask for **Terms of Service and Privacy Policy URLs** [not verified in docs]. Only if the owner wants public discovery.
- **The "Launch" detail sheet** (description, art, the Launch button) is Discord UI, not our page. Art/description: Portal → Rich Presence / App info (checklist R13).
- **Bot page:** leave every toggle off (no Privileged Intents, no Requires OAuth2 Code Grant). **Public Bot off** for now; turn it on later only if going for Discovery. **Never press "Reset Token"** (we don't use a bot token; resetting is pointless and confusing).

## How to turn it off (no code)
Portal → Activities → Settings → untick **Enable Activities** → Save. Or delete the `/` URL Mapping. The website is unaffected.

## How to update the SDK version
1. Read the SDK CHANGELOG and Discord's change log since 2.5.0; skip betas. Ask the owner before downloading.
2. Put the new npm tarball's `output/` ESM files in a **new** folder `webapp/static/vendor/discord-embedded-app-sdk-<version>/` (never overwrite: cached a year). Record source URL + SHA-256 in `CREDITS.md`.
3. Change the import in **`activity-shell.js`**, `SDK_VERSION` in **`preload.py`**, the folder in the **`vercel.json`** immutable rule, and the version in `tests/test_activity.py` / `tests/test_vercel_ready.py`.
4. Check the names we use still exist: `DiscordSDK`, `Common.OrientationLockStateTypeObject`, `ready`, `commands.authorize/authenticate/setOrientationLockState/userSettingsGetLocale`, `subscribe('ACTIVITY_LAYOUT_MODE_UPDATE')`, `DiscordSDKMock` in `mock.mjs`. Re-check the handshake still uses `document.referrer` (Rule #2 stays either way).
5. Full suite (CSP test, `test_vendored_sdk_fully_tracked`), then real Discord (manual, Parte C). Delete the old folder in a later commit.

## Gotcha: the `lib/` gitignore rule (fixed 2026-10-29)
The standard Python `.gitignore` has `lib/`, which silently hid the vendored SDK's bundled dependencies (`vendor/discord-embedded-app-sdk-2.5.0/lib/…`: tslib, uuid, zod, …). They existed locally (tests passed) but were never committed, so on Vercel they returned 404, the SDK import failed and the Activity showed "No pudimos conectar con Discord" after the 10 s timeout. `.gitignore` now un-ignores `webapp/static/vendor/**/lib/`, and `tests/test_activity.py::test_vendored_sdk_fully_tracked` fails if any module the SDK imports is not tracked by git. When updating the SDK, run that test before pushing. First debugging step for "stuck connecting": check `vercel logs` for 404s under `/static/vendor/`.

## Desktop layout inside Discord (2026-10-29)
Owner prefers board ABOVE keyboard in Discord. On the desktop platform (shell sets `c24-plat-desktop` from the launch `platform` and passes it in the `c24-layout` message; the bridge copies it onto the game `<html>`) the game never uses the website's landscape side-by-side layout: always stacked, square tiles. **Since 2026-10-29 (owner: "tiene que verse como New York Times") it uses the web's NYT tile unit `--t` at every panel size:** board right under the header, keys `max(26px, 0.66t)` × `max(24px, 0.87t)`, keyboard as wide as its keys and centered 0.38t under the board. From **768px wide** the header bar spans the whole panel (overrides the landscape-phone rule that matched short panels like 1000×493). The "Jugando hoy" **left rail** (first card "Invite friends") shows from 860px wide at any height: 147×80 cards (avatar + mini board only), 16px from the left, 10px under the header (40px header on panels ≤500px tall, 60px above), never moving or shrinking the centered board; below 860px and on Discord phones, the header facepile + bottom sheet. Measured: 1000×493 → tiles 44.1px, keys 29.1×38.4; 400×700 → 50px; 875×400 → 34.1px (26px key-width floor); 640×360 → 29.8px; PIP 240×180 → 26px (board only; `.c24-pip` overrides the unit so the board fills the tile). Layout details: `casa24-responsive`. Rules are scoped to `:root.c24-embed:not(.c24-plat-mobile)`; mobile and the website are unchanged. Tests: `test_browser_desktop_panel_stays_stacked_with_sidebar` (rail 140–280px wide, keys ≥24px wide and tall), `test_browser_website_landscape_unchanged`, `test_nyt_proportions_on_tablets_and_desktops` (`act` 1000×493, `tests/test_layout.py`), `tests/test_live_rail.py`.

## Keyboard focus and guesses (fixed 2026-10-29)
Symptom: in Discord a typed word was never sent (no POST /api/guess in the logs). Causes found/guarded:
- Focus on the shell document (after clicking the overlay, picker or the safe-area margin) → keys never reached the game iframe. The shell now forwards every keydown except Tab into the game and refocuses the iframe on load, overlay close and margin clicks.
- Typing no longer waits for the first `/api/state` (`lb_ready`); `attempt` + 409 keeps it safe.
- A guess request aborts after 20 s (`GUESS_MS`) so `lb_busy` can't stick; failures show a toast and `C24Activity.log` sends "guess not saved: <code> <status>" to the shell console (Discord debug logs). Never log secrets.
- In Discord desktop, keys typed before clicking inside the Activity go to Discord's chat box — click the board first.
Sync works both ways (Activity → web, web → Activity, both open with focus refresh); tests in `tests/test_activity.py` (`…physical_keyboard…`, `…on_screen_keys_and_both_sync_directions`, `…web_guess_then_activity_launch`, `…guess_error_is_shown_and_logged`).
Known small issue: if a header button keeps focus after closing its window with Esc, Enter also reopens that window (guess still saved).

## Going public (2026-10-29)
See `docs/discord-publish-guide.md`. Unverified Activities: only the team, App Testers (≤50) and servers under 25 members. App Verification (team owner identity via Stripe + Terms/Privacy URLs + description/icon) lets anyone play; Discovery (art assets, tags, support server) is optional on top. Inside the Activity, Settings has Terms/Privacy (opened with the SDK `openExternalLink` through the shell — never navigate) and "Borrar mis datos" (Bearer DELETE → shell shows "datos borrados" + "Volver a jugar", which signs in again on the same SDK instance), as Discord's Developer Policy requires easy access to the privacy policy and deletion.

## Status 2026-10-29: verified, Discovery in progress
- The owner confirmed in Discord that the Activity works (language picker, guesses, sync web↔Discord) — before the 2026-10-29 es/en + locale change, which still needs a real-Discord check (URL Override on the preview).
- **App Verification: approved** (General Information shows "Verified apps can change their name once every 6 months"). Team members with Developer Mode still see the "<>" badge and "Use Activity URL Override" — that is the developer view; check with Developer Mode off or a non-team account.
- **Discovery Status checklist** (done: slash commands/Entry Point, verified, 2FA, ≥1 tag). Pending for the owner:
  1. Support server must be a **Community** server (Server Settings → Enable Community), then pick it as Support Server.
  2. **Summary** (short), 3. **expanded description**, 4. at least one **locale** (Spanish, English US — the game is es/en only now; remove any "10 idiomas" wording) in Discovery Settings; also fill General Information → Description (was empty).
  Suggested texts are in `docs/discord-publish-guide.md`. After all green: enable Discovery (up to 24 h to appear).
