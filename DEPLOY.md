# Deploying Casa 24 Wordle

**Status:** not deployed. No domain yet. Everything below is ready for when we want it online.

## Vercel

The repo is already set up for Vercel's zero-config Flask support:

| File | What it does |
|---|---|
| `pyproject.toml` | Tells Vercel the app is `webapp/app.py` (`[tool.vercel] entrypoint`), Python ≥ 3.12, and the build step |
| `.python-version` | Python 3.12 |
| `scripts/vercel_build.py` | Build step: copies `webapp/static/` to `public/static/` so the CDN serves images, fonts, CSS, JS |
| `.vercelignore` | Keeps tests, the virtualenv, helper scripts and private word/alias files out of the upload |
| `webapp/app.py` | Uses absolute paths and trusts Vercel's proxy headers, so https works without redirect loops |

### Environment variables

The game itself needs none. Two are optional, for the team's **Developer view** (internally "demo": the `/demo` page: the same game plus Restart (new random word) and Fill in word buttons):

| Variable | What it does |
|---|---|
| `DEMO_PASSWORD` | Turns Developer view on. The value is the password the owner chose. **Never write it in the repo, this file, or any message:** the repo is public. Not set → no Developer view card on the start screen and `/demo` shows "Not Found". Everything else works the same. |
| `SECRET_KEY` (optional) | A long random string that signs the Developer view login cookie (valid 30 days). If not set, the key is made from `DEMO_PASSWORD`. |

How to set them: Vercel → Project → Settings → Environment Variables → add each one and tick **Production** and **Preview** → redeploy (new values only reach new deployments).

Changing the Developer view password: change `DEMO_PASSWORD` in Vercel, then redeploy.
- Without `SECRET_KEY`: everyone who was logged in to Developer view is logged out and must type the new password.
- With `SECRET_KEY` set: people already logged in stay logged in (up to 30 days). To log everyone out as well, change `SECRET_KEY` too.

Do **not** set `CASA24_ENABLE_ALIASES` until members confirm their aliases.

### First deploy (about 10 minutes)

1. Update the Vercel CLI (the installed one is outdated): `npm i -g vercel@latest`
2. `vercel login` (use the Casa 24 account)
3. From the project folder: `vercel link` (create a new project, e.g. `casa24-wordle`)
4. Optional: add `DEMO_PASSWORD` (and `SECRET_KEY`) as above if you want Developer view on.
5. Preview deploy: `vercel deploy` → opens a `*.vercel.app` link. Check `/`, `/es`, `/en`, dark mode, a guess, and `/demo` if you set the password.
6. Production: `vercel deploy --prod`

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
- [ ] Decide whether Developer view should be on (set `DEMO_PASSWORD` for Production and Preview) or off (leave it unset)
