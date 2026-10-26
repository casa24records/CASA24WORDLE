---
name: casa24-git-and-github
description: Commit and push Casa 24 Wordle to GitHub — the public repo casa24records/CASA24WORDLE, feature branches merged into main, main auto-deploys to Vercel production (other branches get preview URLs), which GitHub account to use, what must never be published, and history rules (no force-push without asking). Use whenever the owner says commit, push, subir, GitHub, or a push fails.
---

# Git and GitHub

## Where things are
- GitHub repo: https://github.com/casa24records/CASA24WORDLE. It is **PUBLIC**, and its default branch is `main`.
- **Branches** (as of 2026-10-26, check with `git branch -a`):
  - `casa24`: the local main line. There is no local `main`; `casa24` is published as `main` (`git push origin casa24:main`). Right now `casa24` and `origin/main` are the same commit.
  - Feature branches: bigger features get their own branch, for example `leaderboard-discord` (2 commits ahead of `main`, not pushed yet). When the owner OKs it, merge the branch into `casa24` and push that to `main`.
  - `backup-before-author-fix`: see History rules.
- A feature branch can be pushed under its own name for a preview (`git push origin leaderboard-discord`) without touching production, but only when the owner asks.
- There is only one remote, `origin`. The `upstream` remote (the original project) was removed on purpose.

## Before every commit
1. Run `.venv/bin/python -m pytest -q tests`. Everything must pass (see `casa24-test-and-preview`).
2. Keep commits small, one step each, with a clear message. End the message with the Co-Authored-By line from the current session's instructions.
3. Don't commit build output (`public/`), `screenshots/`, `.venv/`, Gilroy fonts or `*_PRIVATE*` files. `.gitignore` covers these. Check `git status` anyway.

## Pushing
- The repo is public, so **anything pushed is public**:
  - Never commit secrets, `.env` files, private word aliases, or fonts without a webfont license.
  - Word lists are fine: they reach the browser anyway.
- Only push when the owner asks. "Commit" alone means commit locally.
- **GitHub account:** this Mac has several `gh` accounts. Only **casa24records** can push.
  - If you get `Permission ... denied to <other user>` (403), the wrong account is active.
  - Ask the owner to run `! gh auth switch --user casa24records`.
  - Don't switch accounts or use their tokens yourself.
- To see what is not on GitHub yet: `git fetch origin && git log origin/main..<branch> --oneline`.
- To check that a push worked, `git ls-remote --heads origin` should show the same hash as `git rev-parse <branch>`.

## History rules
- **Never force-push or rewrite published history without the owner's explicit OK.** It was done once, on 2026-10-26, to make the first commit authored by Casa 24 instead of Hugo (see `casa24-decisions`).
- Every commit is authored by `Fer <casa24records@gmail.com>` (the email is in `~/.gitconfig`; the name comes from the Mac account). Don't change the git identity. Hugo's name may appear only in `LICENSE`, which the law requires.
- If a push fails with `did not receive expected object` / `index-pack failed`, the history points at a commit that isn't present locally (a shallow clone). Check with `git rev-parse --is-shallow-repository`. Ask before fixing it, because the fix rewrites history.
- A local branch `backup-before-author-fix` may exist from that rewrite. Delete it only if the owner agrees.

## Vercel (connected to GitHub)
- **Pushing to `main` publishes to production immediately.** Vercel builds every push to `main` and makes it the live site. So only push `main` with the owner's explicit OK, after tests pass, and after any needed env vars are set in Vercel (the leaderboard needs its Discord vars, `SECRET_KEY` and the database; see `casa24-leaderboard`).
- **Any other branch** pushed to GitHub gets its own preview URL: `casa24-wordle-git-<branch>-casa-24.vercel.app` (for example `casa24-wordle-git-leaderboard-discord-casa-24.vercel.app`). Previews don't change the live site; use them to show the owner a feature first. Preview env vars are set separately in Vercel.
- Deploy setup, env vars and troubleshooting: `casa24-deploy`.
