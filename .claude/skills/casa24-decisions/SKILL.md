---
name: casa24-decisions
description: Decisions the Casa 24 owner already made about the Wordle project (scope, languages, words, privacy, branding, hosting) and why. Check this before proposing changes so settled questions are not re-asked or undone.
---

# Decisions already made (October 2026)

Don't re-ask these. If a request seems to conflict with one, mention it in one sentence, then do what the owner asks now.

## Scope and working style
- The owner is the admin at Casa 24 Records (Panama City). They are a beginner developer and watch token usage. Explain in plain language, keep changes small, commit after each step, and don't paste long outputs.
- **Keep the original upstream game and menu.** An early rewrite of the menu as a two-button page was rejected and stashed (`git stash list`). Add Casa 24 things on top instead of rebuilding.
- **Languages:** the 10 most spoken that upstream had: en, es, ar, fr, pt, ru, de, tr, vi, ko. English and Spanish are required.
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
- Accents are **optional when typing** in Spanish, and the board shows the accented word. ñ stays a separate letter.

## Privacy
- The original author's Google Analytics, Bing verification tag and feedback link were removed. **Add no trackers or analytics** without asking.

## Branding
- Kolo, the orange dachshund, is the mascot. The palette comes from his art. Avoid trademarked or alcohol art in the public game. Member logos are not used.
- Gilroy needs a webfont license, so it is git-ignored. VT323 is the pixel font.
- Dark mode exists: it follows the device by default and can be picked in Settings or on the menu.

## Hosting
- Plan for **Vercel**, but **don't deploy yet** and there is **no domain yet**. The subdomain will be decided later, for example `wordle.casa24records.com`. DNS is at GoDaddy, and `shop.` is Shopify.

## Repository
- Work happens on branch `casa24`. `upstream` is https://github.com/Hugo0/wordle (MIT). Keep `LICENSE` and `CONTRIBUTORS.md`.
