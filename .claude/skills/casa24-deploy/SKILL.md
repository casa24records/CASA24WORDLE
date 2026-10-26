---
name: casa24-deploy
description: Put Casa 24 Wordle online — Vercel setup that already exists (pyproject entrypoint, build step, vercelignore, vercel.json caching with ?v= asset URLs), first deploy steps, costs, adding a casa24records.com subdomain at GoDaddy, and troubleshooting. Vercel is the only host. Use for any hosting, domain, or deployment question. Never deploy or touch DNS without the owner's explicit go-ahead.
---

# Deploy

**Current state:** not deployed, no domain chosen. Vercel is the only host (there is no Docker or other backup setup). **Never run `vercel deploy`, link a project, or change DNS unless the owner explicitly asks in that conversation.** Full guide: `DEPLOY.md`.

## What is already set up
- `pyproject.toml`:
  - `[tool.vercel] entrypoint = "webapp.app:app"`, which is Vercel's zero-config Flask detection with a custom module
  - Python `>=3.12` (plus `.python-version`)
  - dependency `flask>=3.1`
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
- Outside libraries: **Vue 3.5.13** production build from `cdn.jsdelivr.net` (deferred). **Tailwind still comes from the Play CDN** (`cdn.tailwindcss.com`, development-only); compiling it in `scripts/vercel_build.py` with the Tailwind CLI is pending the owner's OK to download the CLI (see `casa24-responsive`).
- `.vercelignore` excludes tests, `.venv`, `.claude`, helper scripts (all of `scripts/` except `vercel_build.py`), the **private alias files**, and the Gilroy fonts (commercial).
- Environment variables: none needed. Keep `CASA24_ENABLE_ALIASES` unset.
- Share links, meta tags and `/sitemap.xml` use the visitor's own address (`request.url_root`, `window.location.origin`), so no domain setting is needed.

## First deploy (only when asked)
1. `npm i -g vercel@latest`. The installed CLI is outdated.
2. `vercel login`, then `vercel link` from the repo root.
3. `vercel deploy` for a preview. Check `/`, `/es`, `/en`, a guess, and dark mode.
4. `vercel deploy --prod` for production. Alternatively, connect the GitHub repo `casa24records/CASA24WORDLE` (branch `main`) for automatic deploys. This needs the owner's go-ahead too.

## Cost
- Hobby is free, but only for **non-commercial** use. Casa 24 is a label, so flag that Pro may be required.
- The game is one small function plus static files. There is no database.

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
| Different daily word than local | language load order changed. The sort in `app.py` must stay |

Before any deploy, run `.venv/bin/python -m pytest -q tests`. `test_vercel_ready.py` simulates the Vercel import.
