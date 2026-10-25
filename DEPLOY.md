# Deploying Casa 24 Wordle

**Status:** not deployed. No domain yet. Everything below is ready for when we want it online.

## Recommended: Vercel

The repo is already set up for Vercel's zero-config Flask support:

| File | What it does |
|---|---|
| `pyproject.toml` | Tells Vercel the app is `webapp/app.py` (`[tool.vercel] entrypoint`), Python ≥ 3.12, and the build step |
| `.python-version` | Python 3.12 |
| `scripts/vercel_build.py` | Build step: copies `webapp/static/` to `public/static/` so the CDN serves images, fonts, CSS, JS |
| `.vercelignore` | Keeps tests, notebooks, the virtualenv and private alias files out of the upload |
| `webapp/app.py` | Uses absolute paths and trusts Vercel's proxy headers, so https works without redirect loops |

No environment variables are needed. Do **not** set `CASA24_ENABLE_ALIASES` until members confirm their aliases.

### First deploy (about 10 minutes)

1. Update the Vercel CLI (the installed one is outdated): `npm i -g vercel@latest`
2. `vercel login` (use the Casa 24 account)
3. From the project folder: `vercel link` (create a new project, e.g. `casa24-wordle`)
4. Preview deploy: `vercel deploy` → opens a `*.vercel.app` link. Check `/`, `/es`, `/en`, dark mode, a guess.
5. Production: `vercel deploy --prod`

Or connect the GitHub repository in the Vercel dashboard. Then every push to the production branch deploys automatically and every other branch gets a preview link.

Test locally the Vercel way (after `vercel link`): `vercel dev`.

### Cost

- **Hobby (free)** is for personal, non-commercial projects. Casa 24 is a record label, so a game used for promotion or shared with sponsors may count as commercial use. Read Vercel's fair-use terms before relying on Hobby.
- **Pro** (per-seat monthly price) is the safe choice for commercial use. Traffic for a small daily game is far below its included limits.
- The game has no database and no background jobs. Each page view is one fast function call, and images and fonts come from the CDN.

### Adding a domain later (GoDaddy DNS)

1. Pick the subdomain, e.g. `wordle.casa24records.com`.
2. Vercel → Project → Settings → Domains → add it. Vercel shows the exact DNS record to create.
3. GoDaddy → DNS for casa24records.com → add a **CNAME** with name `wordle` and the value Vercel shows.
4. Wait for Vercel to show "Valid configuration". HTTPS is automatic.

Nothing in the code needs to change for a domain. Share links and meta tags use whatever address the visitor is on.

## Before going public

- [ ] Gilroy webfont license, or accept the system-font fallback (Gilroy files are not in git)
- [ ] Confirm member aliases before enabling them
- [ ] `.venv/bin/python -m pytest -q tests` passes
- [ ] Look at `/es` and `/en` on a phone in light and dark mode

## Backup: Docker

`Dockerfile` runs the app with gunicorn on port 8000 on any Docker host (Render, Fly.io, Railway, a VPS):

```
docker build -t casa24-wordle . && docker run -p 8000:8000 casa24-wordle
```
