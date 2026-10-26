---
name: casa24-git-and-github
description: Commit and push Casa 24 Wordle to GitHub — the public repo casa24records/CASA24WORDLE, working branch casa24 pushed to main, which GitHub account to use, what must never be published, and history rules (no force-push without asking). Use whenever the owner says commit, push, subir, GitHub, or a push fails.
---

# Git and GitHub

## Where things are
- GitHub repo: https://github.com/casa24records/CASA24WORDLE. It is **PUBLIC**, and its default branch is `main`.
- Local work happens on branch `casa24`. It is published as `main`:
  ```
  git push origin casa24:main
  ```
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
- To check that a push worked, `git ls-remote --heads origin` should show the same hash as `git rev-parse casa24`.

## History rules
- **Never force-push or rewrite published history without the owner's explicit OK.** It was done once, on 2026-10-26, to make the first commit authored by Casa 24 instead of Hugo (see `casa24-decisions`).
- Every commit is authored by `Fer <casa24records@gmail.com>`. Hugo's name may appear only in `LICENSE`, which the law requires.
- If a push fails with `did not receive expected object` / `index-pack failed`, the history points at a commit that isn't present locally (a shallow clone). Check with `git rev-parse --is-shallow-repository`. Ask before fixing it, because the fix rewrites history.
- A local branch `backup-before-author-fix` may exist from that rewrite. Delete it only if the owner agrees.

## Vercel
Vercel can be connected to this repo for automatic deploys from `main`. Do that only with the owner's go-ahead. See `casa24-deploy`.
