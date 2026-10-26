---
name: casa24-deploy
description: Put Casa 24 Wordle online — Vercel setup that already exists (pyproject entrypoint, build step, vercelignore), first deploy steps, costs, adding a casa24records.com subdomain at GoDaddy, and troubleshooting. Vercel is the only host. Use for any hosting, domain, or deployment question. Never deploy or touch DNS without the owner's explicit go-ahead.
---

# Deploy

**Current state:** not deployed, no domain chosen. Vercel is the only host (there is no Docker or other backup setup). **Never run `vercel deploy`, link a project, or change DNS unless the owner explicitly asks in that conversation.** Full guide: `DEPLOY.md`.

## What is already set up
- `pyproject.toml`:
  - `[tool.vercel] entrypoint = "webapp.app:app"`, which is Vercel's zero-config Flask detection with a custom module
  - Python `>=3.12` (plus `.python-version`)
  - dependency `flask>=3.1`
  - `[tool.vercel.scripts] build = "python scripts/vercel_build.py"`
- `scripts/vercel_build.py` copies `webapp/static/` to `public/static/`. Vercel serves `public/` from its CDN, and Flask's `static_folder` should not serve files on Vercel.
- `webapp/app.py`:
  - absolute data paths (`APP_DIR`)
  - `ProxyFix(x_proto=1, x_host=1)`
  - no https redirect in the app: Vercel already forces https
- `.vercelignore` excludes tests, `.venv`, `.claude`, and the **private alias files**.
- Environment variables: none needed. Keep `CASA24_ENABLE_ALIASES` unset.
- Share links and meta tags use the visitor's own address, so no domain setting is needed.

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
| Different daily word than local | language load order changed. The sort in `app.py` must stay |

Before any deploy, run `.venv/bin/python -m pytest -q tests`. `test_vercel_ready.py` simulates the Vercel import.
