# Plan: NYT-style game layout + Spanish/English only + QWERTY-Ñ keyboard (web and Discord Activity)

## Context
The owner wants three things, all applied to both the website and the Discord Activity. Both already share one `game.html` and one `style.css`; Discord only adds flags, the shell page and a few `c24-embed` rules, so there is no duplicated component to merge.
1. The game screen should feel like NYT Games: a compact top bar, a centered board, the keyboard right under it, and a secondary social panel. It must fit with no vertical scroll, keep Casa 24 colors and fonts, stay accessible and cause no layout shift.
2. Only Spanish and English remain, removed from code, data, tests, docs, skills and the Neon database.
3. The Spanish keyboard becomes plain QWERTY plus Ñ, with no accent keys. Vowels match with or without accents in both directions (o = ó). Ñ always stays its own letter.

This reverses two recorded decisions in `casa24-decisions`: "keep 10 languages" and "colors respect accents" (2026-10-26). The owner is deciding it now, so the skills get updated. The rejected 2-language stash (`stash@{0}`) is **not** reused; it predates the leaderboard and Activity.

**Owner answers (2026-10-29):** flexible vowels (o↔ó both ways). Delete the 8 languages' rows from the database. An "Invite friends" card in the social panel, inside Discord only.

## Research summary (sources go into the delivered docs)
- **Discord Activities** ([layout](https://docs.discord.com/developers/activities/development-guides/layout), [mobile](https://docs.discord.com/developers/activities/development-guides/mobile), [design patterns](https://docs.discord.com/developers/activities/design-patterns), [SDK reference](https://docs.discord.com/developers/developer-tools/embedded-app-sdk), [user object](https://docs.discord.com/developers/resources/user)):
  - Discord publishes no fixed iframe sizes or aspect ratios. The guidance is to scale fluidly, respect `--discord-safe-area-inset-*`, and handle the FOCUSED/PIP/GRID layout modes and orientation lock.
  - Our test sizes are therefore our own: PIP 240×180, desktop 640×360, 875×400 and 400×700.
  - Locale: `userSettingsGetLocale()` already works with `identify`. The `/users/@me` `locale` is also returned. There is no guild locale in the SDK.
  - `openInviteDialog()` needs no extra scope.
- **NYT Wordle principles:**
  - One centered column of about 500px. The header is brand left, icons right.
  - The board is sized from the leftover height with square tiles.
  - The keyboard sits at the bottom with keys of about 58px max height and 1.5× wide Enter/⌫.
  - The social panel lives outside the column (a fixed left rail of cards), so it never steals width from the board.
  - Nothing else competes on screen.

## Approach

### Step 0: Save the plan and take "before" screenshots
- Copy this plan to `docs/plan-layout-es-en.md`, per the owner's memory rule.
- Work on a new local branch `layout-es-en` from `casa24`. Commit locally in small steps. **No push and no merge to main** until the owner reviews.
- Capture "before" screenshots with a throwaway Playwright script in the scratchpad, at these sizes:
  - 320×568, 390×844, 844×390, 768×1024, 1366×768, 1920×1080.
  - Activity-embed 640×360, 400×700, PIP 240×180.
  - es, light and dark, leaderboard page with a fake store.
- Save them to `screenshots/before/` (git-ignored).

### Parallel implementation: 3 agents with non-overlapping file ownership
**Agent A, layout (owns `templates/game.html`, `static/style.css`, `templates/activity.html` markup/CSS only, `static/tailwind.css` rebuild):**
- **Header:** replace the 3-column centered-title grid with a 2-area bar.
  - Brand on the left: Kolo logo, "Casa 24" and the language badge. In Discord, the existing "Casa 24 ES ▾" language button.
  - Actions on the right, in this order: live facepile (narrow only), help, leaderboard trophy, stats, settings, then avatar/Discord slot.
  - Height 52px desktop and 48px phones, plus the top safe area. 44px tap targets. Drop the "hide title under 420px" hack if the 2-area bar fits at 320. Otherwise keep the logo and badge and hide only the text.
- **Board:** keep the existing container-query sizing in `.c24-board-area` (`style.css:305-329`). Cap the width at about 350px desktop and 330px phone, NYT-like. Keep a uniform 5px gap, square tiles and `aspect-ratio` reserved before Vue mounts (no CLS).
- **Keyboard:** directly under the board.
  - `max-width:500px`.
  - `--kh` becomes clamp(44px, 7dvh, 58px), with the existing `--rows` formula as the lower bound for the smallest screens.
  - Enter/⌫ stay 1.5×. A 6px gap, 4px under 360px.
  - Verify that the 10-key Ñ row fits at 320px (needs ≥ 26px keys).
- **Social panel:** restyle `<aside class="c24-live">` (`game.html:197-223`) as a NYT-style left rail of rounded cards.
  - Card 1, inside the Activity only: "Invitar amigos / Invite friends" with a round green icon. It calls the shell bridge, which runs `discordSdk.commands.openInviteDialog()`.
  - Then one card per player: avatar, @name, live dot, ✓/✗ and a mini 6×5 board.
  - Shown as a fixed rail at ≥1024px on the web and ≥860px in Discord desktop (existing breakpoints). The centered column never moves or shrinks; the rail sits in the left gutter.
  - Narrower screens keep the header facepile and bottom sheet.
- **Fit check:** header + board + keyboard ≤ viewport at every size listed in Step 0. The landscape-phone side-by-side grid (`style.css:374`) is kept. PIP keeps board-only.
- **Accessibility:** a visible `:focus-visible` ring on keys and icons (Casa 24 orange), and `aria-label` on every icon button and key (⇨ "Enter", ⌫ "Borrar/Backspace"). The board gets `role="grid"` with row labels. A live region for toasts already exists; check it. Check contrast of the tile colors in both themes.

**Agent B, languages and database (owns `webapp/app.py`, `store.py`, `index.html`, `index.js`, `leaderboard.html`, `activity-shell.js`, `discord-activity.js`, `data/languages/{ar,de,fr,ko,pt,ru,tr,vi}`, `scripts/purge_languages.py` (new), README, CREDITS, `docs/`, tests except keyboard/color tests):**
- **Data and code:**
  - `git rm -r` the 8 language folders.
  - Remove dead code: the tr/az lowercasing and Korean NFD form in `lb_normalize`/`_lb_norm_form` (`app.py:983-1003`), `_is_rtl` (`app.py:280`) and RTL plumbing, `_generate_alphabetical_keyboard` (es/en have keyboard files), and the `:lang(ar|ko|ru|vi)` CSS rules. The CSS edits are handed to Agent A as a short list.
  - Pin `SUPPORTED_LANGS = ("es","en")` as an explicit constant used by `language_codes`, `LB_LANGS` and the leaderboard tabs (Combinado + ES + EN). The folder glob no longer defines the product.
  - Expose `language.input_characters`, the set of letters on the keyboard, for Agent C.
- **Old links and saved languages:**
  - `/ar /de /fr /ko /pt /ru /tr /vi` and `/lb/<those>` → 302 to the same route in es or en, chosen from Accept-Language (default es).
  - `/leaderboard?tab=<old>` → `all`.
  - Other unknown codes keep today's behavior.
  - The menu's `calculateTotalStats` counts only es/en guest stats. `casa24_lang` and `c24_activity_lang` are already validated against the list.
- **Initial language in Discord:** recommendation for the owner's review.
  - Drop the first-launch picker. Pick the language from `userSettingsGetLocale()` (`es*` → es, else en) unless the device has a saved choice.
  - Switching stays in the header "ES ▾" window, now two options.
  - Why: with only two languages a picker is one more tap for no gain, and Discord's locale is reliable. If the owner prefers to keep the picker, it simply shows two cards.
- **Web:** unchanged rule (`casa24_lang`, then the browser language).
- **SEO:**
  - The sitemap shrinks automatically.
  - Add `hreflang` alternates for /es and /en (and x-default) to the game page.
  - The meta description comes from es/en configs only.
- **Database script `scripts/purge_languages.py`:**
  - Default is a dry run. It prints row counts per `lang` in `wordle_results` and `wordle_games`.
  - `--export` writes the rows to be deleted as CSV in the scratchpad, outside git.
  - `--execute` runs `DELETE … WHERE lang NOT IN ('es','en')` on both tables in **one transaction** and prints the deleted counts. Players, rate rows and avatars are untouched: they have no language.
  - Also add `lang = ANY(%(langs)s)` filters to `SQL_RANKED`, `SQL_HISTORIES` and the MemoryStore equivalents, so stray rows can never count.
  - Run order: dry run → show the counts to the owner → `--execute` only after the owner's go-ahead in chat. It needs `DATABASE_URL`, which the owner provides via `vercel env pull .env.local`; there is no `.env.local` now.
- **Tests:** rewrite the 10-language assertions in `test_text`, `test_leaderboard`, `test_leaderboard_ui`, `test_activity`, `test_live`, `test_legal`, `test_demo`, `test_sync`, `test_vercel_ready` and `test_smoke_browser` (menu part) for es/en.
  - Add `tests/test_languages.py`: only es/en exist, old codes redirect correctly, `/api/*` with an old code returns 400, the leaderboard has 3 tabs, the purge SQL is parameterized and filters correctly against the fake connection.

**Agent C, keyboard and accents (owns `static/game.js`, `webapp/leaderboard.py`, `data/languages/es/es_keyboard.json`, `es|en/language_config.json` help texts, `tests/test_input_bugs.py`, the color/accent tests in `test_leaderboard.py` and `test_smoke_browser.py`, new `tests/test_accents.py`):**
- **Keyboard JSON:**
  - es qwerty: `q…p` / `a…l ñ` / `⇨ z…m ⌫`.
  - Alfabético: drop the accent row.
  - en files untouched.
- **Colors:** `updateColors` (`game.js:525-569`) and `color_guess` (`leaderboard.py:65-85`) compare `foldAccents` letters. Ñ is still distinct, ü folds to u. Key colors go to the folded key (`colorKey`, `key_classes`).
- **Input:** `normalizeKey` applies NFC and folds accented physical keys to the plain letter, keeping ñ. `acceptable_characters` comes from the keyboard letters.
- **Board display:** after Enter, tiles keep showing the accented spelling (`resolveAccents`).
- **Saved games:** old localStorage `key_classes` entries for accented keys are ignored harmlessly.
- **RTL:** remove the right-to-left logic in `game.js` (`:77-80, 1003, 1037-1095`) and its Settings toggle. The `game.html` part is handed to Agent A.
- **Help text:** es "Puedes escribir sin tildes: la «o» vale por «ó» y al revés. La ñ es su propia letra." Plus the en equivalent.
- **Tests:**
  - Update `COLOR_CASES` and the game.js↔Python parity test (`test_leaderboard.py:76-131`).
  - Replace `test_spanish_colors_respect_accents` with "plain vowel greens an accented one".
  - Add tests:
    - The es keyboard is exactly 26 letters + ñ after l, with no accented keys.
    - The en layouts are unchanged.
    - `fold("ñ")=="ñ"`, and decomposed `n+U+0303` → ñ via NFC.
    - `sonar` ≠ `soñar`.
    - Each accented answer wins when typed plain.
    - A typed ñ is stored and shared correctly (share is emoji-only).

### Integration (me, after the agents)
- Merge the agents' handed-off edits (CSS list from B, RTL bits in `game.html` from C).
- Rebuild Tailwind (`scripts/build_css.py`).
- Run the full test suite and `scripts/validate_words.py`.
- Run a residual grep across the repo, excluding `.venv` and git history:

  ```
  grep -rniE '\b(ar|de|fr|ko|pt|ru|tr|vi)\b|árabe|arabic|korean|coreano|français|deutsch|русский|türkçe|tiếng|한국어|العربية|português' …
  ```

  Review the hits and report that none remain, or list the false positives such as the word "de".
- Then a **skills agent** updates: decisions (the reversals with date and why), text-and-languages, wordle, leaderboard, live-view, responsive (new header/rail/key sizes and NYT principles), branding (header), daily-word, test-and-preview, deploy, discord-activity (locale auto-pick, invite card), words. Create a new skill only if a gap appears. A likely candidate is `casa24-layout` if the responsive skill grows too big.

## Deliverables
- `docs/plan-layout-es-en.md` holds the plan, the research summary with sources, the decisions, and the risks and items not touched.
- `docs/layout-es-en-manual-steps.md` holds the owner's manual steps:
  1. `vercel env pull .env.local` so the purge script can reach Neon, then approve the delete.
  2. Discord Developer Portal: Discovery description and supported locales changed to es/en, and "10 idiomas" texts updated.
  3. Test the Activity with "Activity URL Override" pointing to the Vercel preview URL, on desktop and phone.
  4. Push and merge to main only when the owner says so.
  5. Optionally delete `stash@{0}`.
- Before/after screenshots at all the sizes, combined into one image per size group.
- **Risks and things not touched:**
  - The Spanish word lists are not edited, so the daily word order is unchanged.
  - 13 accent groups without a plain word resolve to the first listed form.
  - Old browsers keep orphan localStorage keys for removed languages, which are harmless.
  - Discord gives no fixed sizes, so we test our own set.
  - The VT323 WOFF2 conversion is still pending, as before.
  - The Combinado totals drop for anyone who played the other languages.

## Verification
1. Run the full test suite:
   ```
   .venv/bin/python -m pytest -q tests
   .venv/bin/python scripts/validate_words.py
   ```
2. Run a Playwright size sweep (scratchpad script). At each size, assert:
   - `document.scrollingElement.scrollHeight <= innerHeight` during play.
   - Header, board and keyboard don't overlap.
   - Board tiles are square.
   - Keys are ≥ 26px wide and ≥ 40px tall on phones.
   - The rail doesn't change the board width (measure the board with the rail open and closed).
   - CLS = 0 via PerformanceObserver `layout-shift` on load and on resize.
3. Run the same sweep with `?embed=1` and the `c24-embed`/`c24-plat-mobile`/`c24-pip` classes on.
4. Play through Spanish with the physical keyboard (ñ and accented keys typed), and check colors and the share text.
5. Local run of the purge script dry run against the in-memory store and the fake Postgres connection in tests. The real database only with the owner's go-ahead.
6. The owner checks the real Discord Activity on desktop and phone via URL Override on the preview deploy.
