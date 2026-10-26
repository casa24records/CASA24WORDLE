---
name: casa24-decisions
description: Decisions the Casa 24 owner already made about the Wordle project (scope, languages, words, privacy, branding, hosting) and why. Check this before proposing changes so settled questions are not re-asked or undone.
---

# Decisions already made (October 2026)

Don't re-ask these. If a request seems to conflict with one, mention it in one sentence, then do what the owner asks now.

## Scope and working style
- The owner is the admin at Casa 24 Records (Panama City). They are a beginner developer and watch token usage. Explain in plain language, keep changes small, commit after each step, and don't paste long outputs.
- **Keep the full game with its 10 languages.** An early two-language-only rewrite was rejected (stashed, see `git stash list`) because it cut languages.
- **Start screen redesigned** (owner asked for "a better starting screen"): Kolo hero, today's puzzle number and countdown, big Español/English buttons, the other 8 languages as small chips. The original game's **External Links** section (1,264 links to other Wordle sites, which looked like "extra modes that change the colors"), the search box and the `/stats` page were **removed**. Don't bring them back.
- **Languages:** the 10 most spoken that the original game had: en, es, ar, fr, pt, ru, de, tr, vi, ko. English and Spanish are required.
- **Name:** "Casa 24 Wordle".

## Words
- Casa 24 words are daily answers on **about 1 day in 5**, chosen deterministically.
- Words shared by both languages count in both, but only if the other language's main list has them.
- A bigger, licensed Spanish guess list was approved and added (FrequencyWords + Hunspell filter, CC BY-SA 4.0).
- **No proper names.** 115 people, places and abbreviations were removed from Spanish. `chile` (the pepper) stays.
- **Member aliases** (mango, zacko) stay off and out of git until members confirm.
- The **Drive word-mining** idea was dropped ("we don't need the drive"). Don't rebuild it unless asked.

## Text and accents
- Spanish was rewritten in natural tú-form Latin American Spanish.
- Accents are **optional when typing**, and the board shows the accented word. ñ stays a separate letter.
- **Colors respect accents** (decided 2026-10-26): a plain "a" never counts for an "á" in the answer, and only the exact letter's key is colored. Typing today's answer without accents still wins.
- Optional accents are **on for es, fr, pt** and **off on purpose** for the rest, because there the marks make different letters or words: de (alter/älter, ß), tr (akşam/aksam), vi (tones change meaning), ru (й would become и), ar (hamza forms are their own letters). en and ko have nothing to remove. Details in `casa24-text-and-languages`.
- The Spanish help says: "Puedes escribir con o sin tildes, pero los colores sí las cuentan: una «a» no vale por una «á»."

## Privacy
- The original author's Google Analytics, Bing verification tag and feedback link were removed. **Add no trackers or analytics** without asking.

## Branding
- Kolo, the orange dachshund, is the mascot. The palette comes from his art. Member logos are not used.
- **Random Kolo on the end screen** (decided 2026-10-26): each game shows one Kolo picked at random, 12 for a win and 2 for a loss (Baby Kolo, Kolo Toilet). The owner allowed the alcohol art (Chill Kolo, DJ Kolo) and Kolo Toilet; this replaces the earlier "avoid alcohol art" rule. **Kolo ft. Pikachu is never used** (trademark). List and how to change it: `casa24-branding`.
- Gilroy needs a webfont license, so it is git-ignored. VT323 is the pixel font.
- Dark mode exists: it follows the device by default and can be picked in Settings or on the menu.

## Hosting
- Plan for **Vercel**, but **don't deploy yet** and there is **no domain yet**. The subdomain will be decided later, for example `wordle.casa24records.com`. DNS is at GoDaddy, and `shop.` is Shopify.

## Repository
- Work happens on branch `casa24`, published to the **public** GitHub repo `casa24records/CASA24WORDLE` as `main` (`git push origin casa24:main`). Details: `casa24-git-and-github`.
- **Cleanup (2026-10-26): this repo is Casa 24 Wordle only, hosted on Vercel only.** Removed, and don't bring back:
  - Docker and gunicorn files (`Dockerfile`, `.dockerignore`, `Procfile`): Vercel is the only host, so a backup host was just extra to maintain.
  - The original project's notebooks and helper scripts in `scripts/` (and `CONTRIBUTORS.md`): they built the original word lists and are not needed to run or change this game.
  - The `upstream` git remote: we no longer pull changes from the original project.
  - Unused data and settings: old word files, empty keyboard files (the alphabetical keyboard is built automatically when the file is missing), unused `language_config.json` keys, the 16/32 px favicon pngs, dead code.
  - The console log that printed today's word (it spoiled the answer) and the http→https redirects (Vercel already forces https).
  - `requirements.txt` now lists only `flask`. `.python-version` is tracked.
- **Credit is the legal minimum, and only in files:**
  - `LICENSE` (MIT) keeps the original copyright line by Hugo Montenegro and adds a Casa 24 line. **Never delete `LICENSE` or remove that line:** the MIT license requires it.
  - `CREDITS.md` lists the word-list sources and licenses (including the CC BY-SA 4.0 Spanish supplement), VT323 (SIL OFL), and Kolo (© Casa 24 Records).
  - **No credit line or GitHub link in the game itself** (the footer and the Settings "Source code" row were removed on purpose).
- Git history keeps every Casa 24 commit, but the first commit (the imported original code) is now authored by Casa 24, so Hugo doesn't show as a GitHub contributor. His name stays only where the law needs it: `LICENSE`. The old link to the original repo's history was cut, because that history was never downloaded and GitHub refused the push. `main` on GitHub was force-pushed once for this (2026-10-26); don't rewrite published history again without asking.
- The sitemap stays and uses the site's own address, so it works on any domain.
- `DAY_OFFSET` in `daily.py` stays, so puzzle numbers don't jump.
