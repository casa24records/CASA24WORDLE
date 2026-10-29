---
name: casa24-deploy
description: Put Casa 24 Wordle online — Vercel setup that already exists (pyproject entrypoint, build step, vercelignore, vercel.json caching with ?v= asset URLs), vendored Vue/Discord SDK and the Tailwind rebuild (scripts/build_css.py), first deploy steps, env vars (Discord, SECRET_KEY, Neon DATABASE_URL, optional PUBLIC_URL), GitHub auto-deploys, Discord Developer Portal settings (redirect URIs, Activity URL mapping, Enable Activities), costs, adding a casa24records.com subdomain at GoDaddy, and troubleshooting. Vercel is the only host. Use for any hosting, domain, or deployment question. Never deploy or touch DNS without the owner's explicit go-ahead.
---

# Deploy

**Current state (2026-10-26):** **live** at **https://casa-24-wordle.vercel.app** (the older alias `casa24-wordle-seven.vercel.app` may still exist and point to the same project). Vercel account **casa24records**, team **Casa 24** (scope `casa-24`, Hobby plan), project **casa24-wordle**.
- **GitHub is connected:** repo `casa24records/CASA24WORDLE`. A push to **`main` auto-deploys to production**; every other branch gets a preview URL like `casa24-wordle-git-<branch>-casa-24.vercel.app` (for example `casa24-wordle-git-leaderboard-discord-casa-24.vercel.app`). So **pushing to `main` is a production deploy**: only with the owner's OK. The CLI (`vercel deploy --prod --scope casa-24`) still works.
- **Database:** Neon Postgres `casa24-wordle-db`, created through the Vercel Marketplace and connected to casa24-wordle (all environments). It is only for this game; the kanban project has its own Neon/Upstash, never share them. Tables are created by the app on first use (`casa24-leaderboard`).
- No custom domain yet. Previews may be behind Vercel login: check them with `vercel curl <path> --deployment <url> --scope casa-24`.
- **Known issue:** the `vercel.json` year-long cache rule is not applied (static files come back `cache-control: no-cache`); harmless, just slower repeat visits. To investigate: whether the Python/Flask preset ignores `headers` for `public/`, or whether the `has: query` condition is the problem.
- Never deploy to the personal "fer's projects" account (an empty `casa24-wordle` project was created there by mistake on 2026-10-26). Only deploy or touch DNS when the owner asks.

## What is already set up
- `pyproject.toml`:
  - `[tool.vercel] entrypoint = "webapp.app:app"`, which is Vercel's zero-config Flask detection with a custom module
  - Python `>=3.12` (plus `.python-version`)
  - dependencies `flask>=3.1` and `psycopg[binary]>=3.2` (Postgres driver for the leaderboard; also in `requirements.txt`)
  - `[tool.vercel.scripts] build = "python scripts/vercel_build.py"`
- `scripts/vercel_build.py` copies `webapp/static/` to `public/static/`. Vercel serves `public/` from its CDN, so `/static/...` requests never reach Flask. Locally Flask serves `webapp/static/` itself; never run the build by hand (`public/` is git-ignored).
- `webapp/app.py`:
  - absolute data paths (`APP_DIR`)
  - `ProxyFix(x_proto=1, x_host=1)`
  - no https redirect in the app: Vercel already forces https
- **`vercel.json`** has one rule: files under `/static/` are cached for a year (`Cache-Control: public, max-age=31536000, immutable`) **only when the URL has a `?v=` query**. Without `?v=`, Vercel's default applies (browsers re-check every time).
- **`asset(path)`** in `webapp/app.py` (available in every template) returns `/static/<path>?v=<first 10 characters of the file's SHA-1>`. When a file changes, its URL changes, so visitors get the new copy at once even with year-long caching. Fallbacks if a file can't be read: the deploy's git commit (`VERCEL_GIT_COMMIT_SHA`), then a hash of all of `static/`, then the start time. `asset_version(folder)` hashes a whole folder (used for `ASSET_V`, which `game.js` adds to each Kolo picture URL).
  - **Rule:** every static link in a template must use `{{ asset('…') }}`, never `url_for('static', …)` or a hand-written `/static/…` (only exception: the `KOLO_BASE` folder prefix). `test_vercel_ready.py` fails otherwise. An unversioned URL would either never be cached long, or, if someone widened the rule, keep an old copy for a year.
  - `og:image` uses `request.url_root.rstrip('/')` + `asset('images/kolo/kolo-hero.png')`.
- `json_script()` in `app.py` puts the word lists into the page as raw UTF-8 JSON (much smaller Arabic/Korean pages). The HTML itself is never cached long, because it holds the daily word.
- **No CDNs since `d229fcf` (2026-10-28):** everything is served from our own origin (required inside the Discord Activity, whose CSP blocks other hosts; also faster). Sources and SHA-256 in `CREDITS.md`.
  - **Vue 3.5.13**: `webapp/static/vendor/vue.global.prod.js` (deferred, via `asset()`).
  - **Discord Embedded App SDK 2.5.0**: `webapp/static/vendor/discord-embedded-app-sdk-2.5.0/` (ESM, ~70 `.mjs` importing each other **without `?v=`**: the folder name carries the version; a new version = a new folder, never overwrite). Loaded only inside the Activity (`casa24-discord-activity`).
  - **Tailwind v3.4.17, compiled** to `webapp/static/tailwind.css` (committed). **After adding Tailwind classes to a template or `static/*.js`, run `.venv/bin/python scripts/build_css.py`** and commit the new CSS: Vercel does **not** run it. The script downloads the pinned standalone CLI once into `.cache/tailwind/` (git-ignored), checks its SHA-256, and reads `tailwind.config.js` (content globs + a `safelist` for classes built in JS) and `webapp/static/src/tailwind.input.css`. Class missing on the page after a change → you forgot to rebuild, or the class is built from strings in JS (add it to `safelist`).
- `.vercelignore` excludes tests, `.venv`, `.claude`, helper scripts (all of `scripts/` except `vercel_build.py`, including `build_css.py`), the Tailwind inputs (`.cache/`, `tailwind.config.js`, `webapp/static/src/`), the **private alias files**, and the Gilroy fonts (commercial).
- Environment variables (Vercel → Casa 24 → casa24-wordle → Settings → Environment Variables). All of these are set for **Production, Preview and Development** (2026-10-26). **Only the owner types secret values, in the dashboard** (an automated write of secrets from Claude was blocked; don't plan to do it). Never write values in the repo, docs or chat; names only.
  | Name | What | Needed for |
  |---|---|---|
  | `DEMO_PASSWORD` | the password the owner chose for Developer view (`/demo`) | Developer view; unset → no card, `/demo` 404 |
  | `SECRET_KEY` | long random string; signs the leaderboard cookie and the Developer view session | leaderboard (required); Developer view (else derived from `DEMO_PASSWORD`) |
  | `DISCORD_CLIENT_ID` | Discord app "Casa 24 Wordle" client ID (public: `1564412150519169067`) | leaderboard |
  | `DISCORD_CLIENT_SECRET` | that app's client secret | leaderboard |
  | `DATABASE_URL` | Neon pooled connection URL, added by the Neon integration (it also adds `PG*` / `POSTGRES_*` names the app doesn't read) | leaderboard |
  | `ADMIN_DISCORD_IDS` | optional, comma-separated Discord **user** IDs that may hide names (not set yet; it's the owner's user ID, not the app ID) | hiding names |
  | `PUBLIC_URL` | optional, e.g. `https://casa-24-wordle.vercel.app`: the public address used in share links (`public_url()`); unset → the address the visitor used | only if share links ever show a wrong host (e.g. `discordsays.com` inside the Activity) |
  - **The Discord Activity needs no new env vars** (it reuses `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `SECRET_KEY`, `DATABASE_URL`).
  - If any of `SECRET_KEY`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DATABASE_URL` is missing in an environment, the leaderboard is off there (routes 404, no menu switch); the guest game still works.
  - Env changes only apply to **new** deployments: redeploy after editing.
  - Local: the owner runs `vercel env pull .env.local --scope casa-24`; `app.py` reads `.env.local` only when not on Vercel. `.env.local` is git- and Vercel-ignored. `.env.example` lists the names.
  - Keep `CASA24_ENABLE_ALIASES` unset.
- **Discord app redirects** (Discord Developer Portal → Casa 24 Wordle → OAuth2 → Redirects) must list `<domain>/auth/discord/callback` for **every domain people log in from**, exactly. Now:
  - `https://casa-24-wordle.vercel.app/auth/discord/callback`
  - `https://casa24-wordle-git-leaderboard-discord-casa-24.vercel.app/auth/discord/callback`
  - `http://127.0.0.1:5050/auth/discord/callback` (local)
  - plus the placeholder `https://127.0.0.1` that Discord's Activity guide asks for (the Activity's code exchange sends no `redirect_uri`).
  - Adding a custom domain or testing another branch preview → add its callback there first. Scope is `identify` only; no bot.
- **Discord Activity settings** (Developer Portal → Casa 24 Wordle; the owner does them; step-by-step Spanish guide `docs/discord-activity-manual.md`; code side `casa24-discord-activity`):
  - App owned by the Discord Team **Casa 24** (non-distributed Activities open only for the owner and Team members).
  - Installation → **Guild Install only** (scope `applications.commands`, no `bot`), installed in the Casa 24 server.
  - Activities → Settings → Supported Platforms **Web/Desktop, iOS, Android**; Default Orientation Lock **Portrait** (phone, tablet).
  - **The switch, only after the Activity code is on `main`:** Activities → URL Mappings **`/` → `casa-24-wordle.vercel.app`** (no `https://`), then **Enable Activities** (creates the "Launch" command; never delete it).
  - **Turn off without code:** untick Enable Activities (or delete the `/` mapping). The website is unaffected.
  - **Flow (owner, 2026-10-28):** one app, no dev app or preview mapping; the owner configures the Portal first, then says "push"; Claude runs the suite, pushes to `main`, verifies production; then the owner flips the switch.
- **Changing the demo password:** edit `DEMO_PASSWORD` in Vercel, then redeploy (env changes only apply to new deployments). `SECRET_KEY` is set, so people already in Developer view stay logged in (up to 30 days). Changing `SECRET_KEY` logs everyone out of **both** Developer view and the leaderboard.
  - CLI alternative (only when asked): `vercel env rm DEMO_PASSWORD production`, then `vercel env add DEMO_PASSWORD production` (it prompts for the value, so it never lands in shell history), same for `preview`.
- Share links, meta tags and `/sitemap.xml` use the visitor's own address (`request.url_root`, `window.location.origin`), so no domain setting is needed.

## First deploy (only when asked)
1. `npm i -g vercel@latest`. The installed CLI is outdated.
2. `vercel login`, then `vercel link` from the repo root.
3. Add `DEMO_PASSWORD` (and optionally `SECRET_KEY`) for Production and Preview, as above, if the owner wants Developer view on.
4. `vercel deploy` for a preview. Check `/`, `/es`, `/en`, a guess, dark mode, and (if set) `/demo`.
5. `vercel deploy --prod` for production. (Done: GitHub is now connected, so merging/pushing to `main` deploys production automatically.)

## Cost
- Hobby is free, but only for **non-commercial** use. Casa 24 is a label, so flag that Pro may be required.
- The game is one small function plus static files, plus the Neon Postgres free plan for the leaderboard (tiny data: a few rows per player per day).

## Domain (only when asked)
1. Vercel → Settings → Domains → add the subdomain, for example `wordle.casa24records.com`.
2. At GoDaddy DNS for casa24records.com, add a CNAME with name `wordle` and **the value Vercel shows**.
3. Don't touch the records for the main site, `info.`, or `shop.` (Shopify).

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Images/CSS 404 on Vercel | build step didn't run. Check `[tool.vercel.scripts]` and that no Build Command override is set in the dashboard |
| Redirect loop | someone added an http→https redirect back to `app.py`. Remove it; Vercel already does this |
| `FileNotFoundError` for data | a relative path was added. Use `APP_DIR` |
| App not detected | entrypoint string changed, or `app` was renamed |
| Visitors keep an old CSS/JS/picture after a deploy | its URL's `?v=` didn't change with the file (for example a hand-written `?v=`). Link it with `asset()` |
| No Developer view card / `/demo` is 404 on Vercel | `DEMO_PASSWORD` isn't set for that environment (Production vs Preview), or no redeploy since it was added |
| Developer view keeps asking for the password | password changed (derived cookie key), or cookies blocked |
| Different daily word than local | language load order changed. The sort in `app.py` must stay |
| Discord: "Invalid OAuth2 redirect_uri" | that domain's `/auth/discord/callback` is missing from the Discord app's Redirects |
| Leaderboard 404 / no mode switch on one environment | a leaderboard env var (or `DATABASE_URL`) missing for that environment, or not redeployed. More: `casa24-leaderboard` |
| Pushed to `main` and production changed | expected: GitHub auto-deploys `main` |
| A Tailwind class has no effect after a change | `webapp/static/tailwind.css` not rebuilt: run `scripts/build_css.py` and commit (or add JS-built classes to `safelist`) |
| Discord Activity blank / not in App Launcher | Portal URL Mapping or Enable Activities (see `docs/discord-activity-manual.md`, troubleshooting table) |

Before any deploy, run `.venv/bin/python -m pytest -q tests`. `test_vercel_ready.py` simulates the Vercel import.
