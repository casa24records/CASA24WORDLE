---
name: casa24-decisions
description: Decisions the Casa 24 owner already made about the Wordle project (scope, languages, words, privacy, guest/leaderboard modes, Discord login, Discord Activity, web↔Discord sync, live view, database, branding, hosting) and why. Check this before proposing changes so settled questions are not re-asked or undone.
---

# Decisions already made (October 2026)

Don't re-ask these. If a request seems to conflict with one, mention it in one sentence, then do what the owner asks now.

## Scope and working style
- The owner is the admin at Casa 24 Records (Panama City). They are a beginner developer and watch token usage. Explain in plain language, keep changes small, commit after each step, and don't paste long outputs.
- ~~Keep the full game with its 10 languages~~ — **superseded 2026-10-29:** the owner chose **Spanish and English only** (see "Spanish and English only" below). The old rejected 2-language stash was not reused.
- **Start screen redesigned** (owner asked for "a better starting screen"): Kolo hero, today's puzzle number and countdown, big Español/English cards (the other-language chips/cards are gone since 2026-10-29). The original game's **External Links** section (1,264 links to other Wordle sites, which looked like "extra modes that change the colors"), the search box and the `/stats` page were **removed**. Don't bring them back.
- **Languages: es and en only** (since 2026-10-29; before that the 10 of the original game).
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
- Accents are **optional when typing**, and the board shows the accented word after Enter. ñ stays a separate letter.
- **Flexible vowels (decided 2026-10-29):** for colors, a vowel matches with or without accent, both ways (o = ó), on tiles and keys; ü counts as u; **Ñ is always its own letter** (sonar ≠ soñar). This **reverses** the 2026-10-26 "colors follow the exact accented letter" rule. Details in `casa24-text-and-languages`.
- **Spanish keyboard (2026-10-29): QWERTY + Ñ (after L), no accent keys.** The "Alfabético" layout stays in Settings (owner asked), also without accents, ñ after n. English unchanged.
- **A word can't be guessed twice in one game** (2026-10-26): it shows "Ya probaste esa palabra" and costs no turn.
- **The end screen has a title**, "¡Ganaste!" / "Perdiste", above the Kolo. This text and the repeated-word message are in es and en.
- The Spanish help says (2026-10-29): "Puedes escribir sin tildes: la «o» vale por «ó» y al revés. La ñ es su propia letra." (help key `text_1_2`)

## Developer view for the team (decided 2026-10-26)
- Players see it as **"Developer view" / "Vista de desarrollador"**. Internally it is still "demo": routes `/demo` and `/demo/<lang>`, env `DEMO_PASSWORD`, `demo_*` text keys, `.c24-demo*` classes, `data-demo` attributes. Don't rename those.
- **Why:** the Casa 24 team wants to test and show the game without waiting a day for a new word.
- A "🔒 Developer view" card on the start screen opens `/demo`, a password page. After the right password the browser keeps a signed session cookie for 30 days and plays `/demo/es` or `/demo/en` (chosen inside the start-screen card). **It acts exactly like the real game** (owner, 2026-10-26): it opens with the real word of the day and the same end window. The only differences are two buttons: **↻ Reiniciar** (a random answer from the daily-word pool, never the same word again) and **✓ Poner la palabra** (types the current word and presses Enter, so the real win flow runs).
- **The password lives only in the `DEMO_PASSWORD` environment variable** (Vercel settings, or the shell when running locally), because the repo is public. Never write it in code, tests, docs, skills or commit messages; call it "the password the owner chose". Without `DEMO_PASSWORD` there is no Developer view card and `/demo` is a 404.
- **es and en only.** Other language codes redirect to `/demo/es`.
- **Developer view never touches player data:** no localStorage saves, no results, stats or streaks, no "last language" (`casa24_lang`). The end window is the normal one (countdown, Share, your real stats), but the developer game is not added to them.
- Not in the sitemap, pages are `noindex`/`no-store`. How it works: `casa24-wordle`; setting the password: `casa24-deploy`.

## Guest mode + Discord leaderboard (decided 2026-10-26)
How it works: `casa24-leaderboard`.
- **Two modes** (es/en; all 10 languages 2026-10-28 → back to es/en 2026-10-29): guest (the old game, nothing leaves the browser) and leaderboard (all-time ranking with Discord username and points). Since 2026-10-26/27 the menu shows the Discord sign-in button right away when logged out (cards play guest); when logged in the cards play the leaderboard game, with a small "Jugar como invitado (no cuenta)" switch. (The old "other languages stay guest only" rule was **superseded 2026-10-28**.)
- **Discord login, scope `identify` only, no bot.** Discord app "Casa 24 Wordle". We never see passwords or email.
- **Minimal data:** Discord ID, username, Discord avatar hash (since 2026-10-27, see "Live view"), a `hidden` flag, per finished game language/date/won/attempts/points, today's guesses (2 days), per-minute counters. **Never** tokens, email or IPs. Privacy text in a small "ⓘ Privacidad" popover (see below), plus "Borrar mis datos".
- **Database: Neon Postgres** through the Vercel Marketplace, a new separate database `casa24-wordle-db`. Not Upstash (the first plan, dropped by the owner), and not GitHub-as-a-database. The kanban project has its own Neon and Upstash: **never share or reuse them**.
- **Points:** win in 1 = 6 … win in 6 = 1, loss = 0. Ranking: points, then wins, then who reached the total first. The server computes everything; the answer never reaches the browser in leaderboard mode.
- **Guest games never count** and are never imported when someone logs in later.
- **Open to anyone with a Discord account.** Members-only (for example a Casa 24 server role) is **phase 2**, not built.
- **Moderation:** admins (`ADMIN_DISCORD_IDS`) can hide offensive names.
- **Testing in production was approved by the owner** (2026-10-26).
- Secrets are entered only by the owner in the Vercel dashboard, never by Claude.

## Discord sign-in UI and avatar (decided 2026-10-26/27)
How it works: `casa24-leaderboard` (login flow, avatar, UI); look: `casa24-branding`.
- **Official Discord sign-in button:** Discord Blurple `#5865F2`, white official Discord logo (inline SVG), 48 px tall, hover `#4752C4`. A fixed brand color is an allowed exception to the tokens-only rule.
- **On the menu the Discord button shows right away** on page load (no need to pick a mode first), and it is **server-rendered**, so nothing jumps when the page loads.
- **Logged in: the player's Discord avatar (round) sits in the top-left of the header, before the trophy icon.** Tapping it opens a small popover: @username, "Ver leaderboard", "Cerrar sesión" (and "Borrar mis datos").
- **Own avatar in the header:** the callback passes the hash in the redirect's URL fragment `#dc=<hash>`; the page keeps it in localStorage `c24_dc_avatar` `{id, hash}`, removes the fragment with `history.replaceState`, and the browser loads the picture from `cdn.discordapp.com`. No hash → Discord's default avatar `embed/avatars/<(id>>22)%6>.png`. Cleared on logout.
- ~~The avatar never touches our server's storage~~ — **superseded 2026-10-27** by the live view: the owner chose to store the avatar hash (see below). It is still never put in cookies or logs.
- **Cancel on Discord is not an error:** `?error=access_denied` → `/?login=cancelled` (a gentle notice); other failures → `/?login=failed`. `prompt=none` stays.
- **Leaderboard access is a trophy line icon (SVG)** in the top-left of the header, not an emoji and not a "Ver leaderboard" text link. The 🏆 emoji is replaced by this SVG everywhere.
- **Less text, UI that speaks for itself:** no privacy paragraph on the menu; the full privacy text lives only in a small "ⓘ Privacidad" popover. Notices are short toasts that close themselves. The end window shows rank and points as big numbers. "Borrar mis datos" is secondary (avatar popover or a small link), never a big button.
- **Nothing may overlap anything at any screen size.** Check at 320, 375, 390, 844×390 (landscape), 768 and 1366 px wide (see `casa24-responsive`).

## Live view (decided 2026-10-27)
How it works: `casa24-live-view`.
- **While playing the leaderboard game you see who else is playing today's word** (same language), like NYT Wordle's Discord activity. Since 2026-10-29 each card shows **only the avatar and the mini board** (see "Game layout" below); @username and live/won/lost are screen-reader text and a tooltip.
- **Colors only, never letters.** The server computes the colors; words and the answer are never sent.
- **Discord players only:** only logged-in leaderboard players see it, and only they appear in it. Guest games never leave the browser.
- **Discord avatars are shown, so the avatar hash is now stored** (`wordle_players.avatar`, Discord's format only, refreshed at login, removed by "Borrar mis datos"). This replaces the earlier "we never store your photo" rule.
- **Privacy text updated** (`lb_privacy`, `lb_avatar_note`): we store ID, username, profile picture and results for the ranking and "who is playing today"; others see only your colors.
- **The avatar URL exposes the player's Discord ID** (`cdn.discordapp.com/avatars/<id>/<hash>.png`). Accepted: Discord IDs are public inside Discord. If this ever matters, proxy the images through our domain.
- Live = polling every 8 s (no WebSockets on Vercel serverless). Desktop: a fixed left rail of cards from 860px wide (web: and taller than 500px; Discord desktop: any height; was 1024px on the web until 2026-10-29); a header people button/facepile + bottom sheet elsewhere. The "Casa 24" header text hides on narrow screens to fit the buttons.
- **Presence (owner, 2026-10-29):** players appear as soon as they open today's leaderboard game, even with 0 guesses (shown while seen in the last 5 minutes). Presence never creates a result.

## ~~All languages on the menu and the leaderboard~~ (2026-10-28, superseded 2026-10-29)
History only: for one day all 10 languages had big menu cards, leaderboards and translated `lb_*` texts. Replaced by "Spanish and English only" below. Still valid from that day: the **mobile facepile** (up to 3 avatars, 2 under 400px since 2026-10-29, + count; the people icon only when nobody else plays), the **Developer view card last** on the menu, and the menu title shortening to "Casa 24" under 480px when the leaderboard is on.

## Spanish and English only (decided 2026-10-29)
How it works: `casa24-text-and-languages`, `casa24-leaderboard`; plan and research: `docs/plan-layout-es-en.md`.
- **Only es and en.** ar, de, fr, ko, pt, ru, tr, vi were removed everywhere (data folders, right-to-left code, generated keyboards, tests). `SUPPORTED_LANGS = ("es", "en")` in `app.py` defines the product (not the folder list).
- **Old links keep working:** `/<old code>` and `/lb/<old code>` redirect (302, query kept) to es or en by the browser's language (default es); `/leaderboard?tab=<old>` shows Combinado; the APIs answer 400 `bad_lang` / `bad_tab`.
- **Leaderboard tabs: Combinado, ES, EN.** Ranking, streaks and live view only count es/en rows.
- **Delete the old languages' rows from Neon** (owner said yes): `scripts/purge_languages.py`, dry run by default. **Checked on production 2026-10-29 (owner said "hazlo directo"): the dry run found 0 rows in other languages (only es/en existed), so nothing was deleted.** The script stays for reference.
- Discord sign-in from the menu lands on the last language played (es/en), else the browser's preferred one.

## Game layout (decided 2026-10-29)
How it works: `casa24-responsive`, `casa24-branding`.
- **NYT Wordle structure, Casa 24 look:** a slim 2-area header (brand left, icons right), a capped centered board, the keyboard right under it, and the live view as a **left rail of cards that never shrinks or moves the board**. Same `game.html` / `style.css` for the website and the Discord Activity. Must fit with no vertical scroll from Discord PIP (240×180) to 1920×1080.
- **Refined 2026-10-29: NYT proportions and NYT cards.** Owner: "las dimensiones no son iguales, tiene que verse como New York Times"; a team member: "UI de Playing Now más como el de Wordle, solo el profile y el grid".
  - From 481px wide (tablets, web desktop) and in Discord desktop, board and keyboard come from **one tile unit** (max 62px): keys 0.66 × 0.87 of a tile (Enter/⌫ 1.5 keys), keyboard about 1.4× the board's width, centered just under the board (no longer pinned to the bottom), board just under the header. Phones and landscape phones unchanged; PIP shows the board alone.
  - Discord desktop from 768px wide: the header spans the whole panel, like NYT.
  - Live cards: **only the round profile picture and the 6×5 mini grid** (147×80, 64px avatar); no visible name, live dot, ✓/✗ or "Jugando hoy" title on the rail. The name and status stay for screen readers and as a tooltip. The invite card has the same size. The rail sits 16px from the left, 10px under the header, from **860px wide** (was 1024px on the web). Phones: same cards in the bottom sheet.

## Discord Activity and sync (decided 2026-10-28)
How it works: `casa24-discord-activity`; owner's Portal guide: `docs/discord-activity-manual.md`.
- **Play inside Discord as an Activity** (Embedded App SDK, no bot), from the **same repo, pages and deploy** as the website. Detected by `frame_id` + `instance_id` + `platform`; without them the website is unchanged.
- **One Discord app only, "Casa 24 Wordle"** (`1564412150519169067`). The plan's separate "dev" app and preview URL mapping were **dropped**. The app moves to a Discord Team **Casa 24** so members can test before distribution.
- **Main-only flow, push triggered by the owner:** small commits, the full test suite before every push, straight to `main` (production) **only when the owner says so**; the owner configures the Discord Portal **first** (everything except the switch), then says "push", then turns on URL Mapping + Enable Activities. Production is verified after each push and reverted if something breaks.
- **Automatic login inside Discord** (authorize → server token exchange → authenticate). No login button; the only button is "Intentar de nuevo" after the player cancels Discord's permission modal. Scope stays **`identify` only**. The first-launch Discord modal is accepted as unavoidable.
- **No guest mode inside Discord:** everyone plays with their account and counts for the ranking.
- **Guild Install only** (no User Install). **Individual games** (no shared/multiplayer board).
- **Sync rule: the server is the single source of truth for a logged-in player's game; the website and the Activity only paint it.** Same game across web, other devices and Discord (`GET /api/state`, `attempt`/409, reload on focus/visibility/every minute/Panama midnight). The leaderboard counts a game once.
- **Everything self-hosted** (Vue, Discord SDK pinned to 2.5.0, compiled Tailwind): the owner approved the downloads (done in `d229fcf`). Don't add CDNs or external fonts.
- **No new env vars** for the Activity.
- Turning it off is a Portal action (untick Enable Activities), no code.
- **Shell + iframe architecture (decided 2026-10-29), per Discord's own recommendation** for apps that are not single-page apps (docs "how-activities-work" + official sample `nested-messages`): a small shell page (`/`, `/activity`) builds the Discord SDK **once per launch** and the unchanged game page runs in a same-origin iframe (`/lb/<lang>?embed=1`). Why: the old multi-page version redirected `/` → `/lb/es`; after any in-frame navigation the SDK's handshake goes to the wrong origin (`document.referrer`) and the Activity hung on "No pudimos conectar". **The shell must never navigate**; don't go back to redirects or per-page SDKs. Rejected alternatives: swapping the page's HTML in place (CSP nonces, fragile) and a full SPA rewrite (only if the website ever becomes an SPA too).
- ~~Language inside Discord: picker on first launch~~ (2026-10-29 morning, **superseded the same day**).
- **Language inside Discord (decided 2026-10-29):** the language saved on the device wins; else **Discord's own language** (`es…` → Español, anything else → English); a 2-option picker shows only if Discord doesn't answer (error or more than 3 s). Changing it: the header button **"Casa 24 ES ▾"** opens a language window; the game swaps in place and the Discord connection stays.
- **"Invite friends" card (owner, 2026-10-29):** first card of the live rail, **inside Discord only**; opens Discord's own invite window (no new permission).
- **Developer Portal:** Bot page toggles all off, **Public Bot off** for now (on later only if going for Discovery), never Reset Token. The "<>" dev badge / "Use Activity URL Override" only go away with App Verification + Discovery, which is not planned yet (would need Terms and Privacy URLs).

## Privacy
- The original author's Google Analytics, Bing verification tag and feedback link were removed. **Add no trackers or analytics** without asking.

## Branding
- Kolo, the orange dachshund, is the mascot. The palette comes from his art. Member logos are not used.
- **Random Kolo on the end screen** (decided 2026-10-26): each game shows one Kolo picked at random, 12 for a win and 2 for a loss (Baby Kolo, Kolo Toilet). The owner allowed the alcohol art (Chill Kolo, DJ Kolo) and Kolo Toilet; this replaces the earlier "avoid alcohol art" rule. **Kolo ft. Pikachu is never used** (trademark). List and how to change it: `casa24-branding`.
- Gilroy needs a webfont license, so it is git-ignored. VT323 is the pixel font.
- **Kolo pictures are WebP only** (decided by the owner, 2026-10-26): all Kolo PNGs were deleted. The one exception is `kolo-hero.png`, kept for link previews (og:image). Don't bring PNGs back; `brand_assets.py` writes WebP.
- **Tailwind is compiled** (owner approved, done 2026-10-28 in `d229fcf`; no more Play CDN). **Still pending the owner's OK:** converting VT323 to WOFF2 (needs fontTools + brotli). Ask before installing. Details: `casa24-responsive`.
- Dark mode exists: it follows the device by default and can be picked in Settings or on the menu.

## Hosting
- **Vercel** only, team Casa 24. Live at https://casa-24-wordle.vercel.app; GitHub `main` auto-deploys to production (details: `casa24-deploy`). Still **no custom domain**; the subdomain will be decided later, for example `wordle.casa24records.com`. DNS is at GoDaddy, and `shop.` is Shopify.

## Repository
- Work happens on branch `casa24`, published to the **public** GitHub repo `casa24records/CASA24WORDLE` as `main` (`git push origin casa24:main`). Details: `casa24-git-and-github`.
- **Cleanup (2026-10-26): this repo is Casa 24 Wordle only, hosted on Vercel only.** Removed, and don't bring back:
  - Docker and gunicorn files (`Dockerfile`, `.dockerignore`, `Procfile`): Vercel is the only host, so a backup host was just extra to maintain.
  - The original project's notebooks and helper scripts in `scripts/` (and `CONTRIBUTORS.md`): they built the original word lists and are not needed to run or change this game.
  - The `upstream` git remote: we no longer pull changes from the original project.
  - Unused data and settings: old word files, empty keyboard files (the alphabetical keyboard is built automatically when the file is missing), unused `language_config.json` keys, the 16/32 px favicon pngs, dead code.
  - The console log that printed today's word (it spoiled the answer) and the http→https redirects (Vercel already forces https).
  - `requirements.txt` lists only `flask` (plus `psycopg[binary]` since the leaderboard). `.python-version` is tracked.
- **Credit is the legal minimum, and only in files:**
  - `LICENSE` (MIT) keeps the original copyright line by Hugo Montenegro and adds a Casa 24 line. **Never delete `LICENSE` or remove that line:** the MIT license requires it.
  - `CREDITS.md` lists the word-list sources and licenses (including the CC BY-SA 4.0 Spanish supplement), VT323 (SIL OFL), and Kolo (© Casa 24 Records).
  - **No credit line or GitHub link in the game itself** (the footer and the Settings "Source code" row were removed on purpose).
- Git history keeps every Casa 24 commit, but the first commit (the imported original code) is now authored by Casa 24, so Hugo doesn't show as a GitHub contributor. His name stays only where the law needs it: `LICENSE`. The old link to the original repo's history was cut, because that history was never downloaded and GitHub refused the push. `main` on GitHub was force-pushed once for this (2026-10-26); don't rewrite published history again without asking.
- The sitemap stays and uses the site's own address, so it works on any domain.
- Puzzle numbers are Casa 24's own: **#1 = 2026-10-26** (`START_DATE` in `daily.py`, owner's decision that day; the old "#1955"-style numbering from the original game was dropped before launch). Never change it after launch.

## Going public (2026-10-29)
- Owner chose to make the Activity public: Terms/Privacy pages (contact casa24records@gmail.com, operator Casa 24 Records, Ciudad de Panamá), App Verification done and approved, Public Bot on (required for verified apps), Discovery being completed (Community support server, summary, description, locales). Details and status: `casa24-discord-activity`, `docs/discord-publish-guide.md`.
