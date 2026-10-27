---
name: casa24-text-and-languages
description: Change any visible text or translation in Casa 24 Wordle (buttons, notifications, end-screen result title, help), follow the Spanish style guide, work with accent-insensitive typing and keyboards, or add/remove a language. Use when editing language_config.json, keyboards, hard-coded strings in templates/JS, or the list of languages.
---

# Text, translations, accents, languages

## Where text lives
- Each language: `webapp/data/languages/<lang>/language_config.json`
  - `meta`: page description
  - `text`: buttons, notifications, settings, stats
  - `help`: the how-to-play popup
  - also `language_code`, `name`, `name_native`, `right_to_left` (`"true"`/`"false"`), and `accent_insensitive` (es, fr, pt only)
- Templates: use `{{ t('key', 'English fallback') }}` (macro at the top of `game.html`).
- `game.js`: use `this.text("key", "English fallback")`.
- Missing keys fall back to English, so the 8 other languages still work.
- The start screen (`index.html`) is bilingual on purpose: Spanish and English side by side in `lang="es"`/`lang="en"` spans. The Play/Jugar and "Jugada hoy"/"Played today" labels are in the template's Vue expressions. **Exception: the Discord pieces** (sign-in button, guest toggle, privacy link and dialog, toasts, header menu labels) use the `L1(key, es, en)` macro: both languages are in the page, but CSS on `data-l` shows only the one matching `<html lang>` (set from Accept-Language by the server, then to the player's language by `index.js`). `aria-label`/`title` attributes stay bilingual.
- `index.html` and `leaderboard.html` get `texts` (the es and en `text` blocks) from `app.py`, like `demo_login.html`. `index.html` uses the macros `tx(lang, key, fallback)` and `bi(key, es, en)` (both languages side by side); `leaderboard.html` uses `L(key, es, en)` and shows **one** language: Spanish on the `es` tab, English on `en`, the browser's choice on `all`. Both keep inline es/en fallbacks, so they still render if `texts` is missing. Change the JSON **and** the inline fallback together.

**Rule:** never hard-code a user-visible string. Add the key to **both** `es` and `en` configs, with an English fallback in the code. If every player sees it (like the end-of-game result), add it to **all 10** languages.

Current `text` keys:
- Words and game: `next_word`, `no_attempts`, `share`
- End-screen title (class `c24-result`, above the Kolo): `result_won`, `result_lost`
- Notifications: `notification-copied`, `notification-partial-word`, `notification-not-valid`, `notification-share-unsupported`, `notification-repeated` (same word guessed twice in one game)
- Settings: `settings`, `right_to_left`, `keyboard_layout`, `easy_mode`
- Stats: `stats_games`, `stats_win_percentage`, `stats_current_streak`, `stats_best_streak`
- Theme: `theme`, `theme_auto`, `theme_light`, `theme_dark`
- Developer view (internally "demo", team only; **es and en only**): `demo_restart`, `demo_fill`, `demo_title` ("Vista de desarrollador" / "Developer view"), `demo_intro`, `demo_password`, `demo_enter`, `demo_wrong_password`. The password page (`demo_login.html`) reads the es and en keys together and shows them side by side, so both files need every `demo_*` key. Don't add them to the other 8: Developer view only exists in es/en. (The start-screen card "🔒 Developer view" is in `index.html`.)

- Leaderboard (Discord mode; **es and en only**, like `demo_*`; the game reads them with `this.text`/`t()`, the menu and `/leaderboard` through `texts`):
  - Sign-in and account: `lb_signin` (Discord button and header icon: "Entrar con Discord" / "Sign in with Discord"), `lb_account` (aria label of the avatar button), `lb_view` (popover item and trophy icon label), `lb_logout`, `lb_play_guest` (logged-in switch "Jugar como invitado (no cuenta)")
  - Privacy dialog: `lb_privacy_title` (the small "ⓘ Privacidad" link and the dialog title), `lb_privacy` (what Discord and we see/store), `lb_avatar_note` (the picture stays in your browser), `lb_guest_note` (guest games don't count)
  - Toasts and errors: `lb_login_failed`, `lb_login_cancelled`, `lb_deleted`, `lb_dismiss` (× / Close label), `lb_error`
  - Game end window: `lb_rank_label` ("Puesto"/"Rank", under the big "#N"), `lb_points_label` / `lb_point_label` ("puntos"/"punto", under "+N"; singular when exactly 1), `lb_hint` (pointer shown after a guest game)
  - `/leaderboard` page: `lb_title`, `lb_tab_es`, `lb_tab_en`, `lb_tab_all`, `lb_col_player`, `lb_col_points`, `lb_col_wins`, `lb_col_streak`, `lb_col_best`, `lb_you`, `lb_my_position`, `lb_empty`, `lb_delete`, `lb_delete_confirm`, `lb_hide`, `lb_back`
  - Removed: `lb_rank`, `lb_points`, `lb_point_one` (the numbers are now plain "#N" / "+N" with a label). Also removed with the mode switch: `lb_mode_label`, `lb_mode_guest`, `lb_mode_lb`, `lb_logged_in_as` (`lb_login` is still used by `index.html`).
  - No `lb_*` key has placeholders any more (`lb_my_position` is followed by ": #N" in the template).

Which languages have which keys:
- **es, en:** all keys above (the `demo_*` and `lb_*` keys only exist here).
- **The other 8** (ar, de, fr, ko, pt, ru, tr, vi): only `next_word`, `no_attempts`, `share`, `notification-copied`, `notification-partial-word`, plus `result_won`, `result_lost`, `notification-repeated` (translated in all 10; a test checks they exist everywhere). Everything else shows the English fallback.
- `next_word`, `no_attempts` and `share` are read in `game.html` **without** a fallback, so they must exist in all 10.
- All 10 have the full `help` block (`title`, `text_1_1_1` … `text_2_3`, `close`).

Edit JSON with Python (`json.load`, then `json.dump(..., ensure_ascii=False, indent=4)`) so accents stay readable.

## Spanish style guide
- Natural Latin American, Panama-friendly Spanish, in the **tú** form: "Escribe", "Pulsa", "Puedes".
- Use these words: Compartir (not "Cuota"), intento (not "conjetura"/"supongo"), casillas (not "azulejos"), Ajustes, Partidas, Racha, "% ganadas".
- Keep labels short. Stats labels sit four in a row on a 390 px wide phone.
- "Leaderboard" stays in English in Spanish text, as used everywhere so far ("Juega con leaderboard", "Ver leaderboard"); the list itself is "el ranking" ("entrar al ranking"), a place is "puesto" (label "Puesto"), a game won is "Ganadas". Discord login is "Entrar con Discord" / "Cerrar sesión" (English: "Sign in with Discord" / "Log out").
- Owner rule for leaderboard/Discord UI: **less text, the UI speaks for itself.** Prefer an icon or a short label; long explanations go in the privacy dialog, not on the page.
- Privacy text is plain and honest: say exactly what is stored (Discord ID, username, results) and what we never see (password, email).
- Show new Spanish strings to the owner before committing big text changes.

## Accents
- Turned on per language with `"accent_insensitive": true` in `language_config.json`. It is on for `es`, `fr` and `pt`.
- **Typing accents is optional, but colors respect them.**
  - `foldAccents()` removes accents but keeps **ñ**. If you ever turn this on for a language with another letter that must stay separate, add it to that keep list.
  - On Enter, `resolveAccents()` maps the typed word to a real word. For example, `cancion` becomes `canción`, and the board shows the accents.
  - If the typed word matches today's answer without accents, it **is** today's answer and counts as a win.
  - `updateColors()` compares letters **exactly**. A plain "a" never counts for an "á" in the answer (it is gray unless the answer also has a plain "a"). An "á" is green or yellow only against an "á". Only the key of the exact letter on the tile gets colored.
  - The repeated-guess check runs on the resolved word, so typing `jamon` after `jamón` is also blocked.
  - When several accented words share one plain spelling, a plain spelling that is itself a word wins; otherwise the first match in the list wins. French has 11 of these groups, Portuguese 82.
- French and Portuguese keyboards are built automatically in alphabetical order (only es and en have a `<lang>_keyboard.json`), so every accented letter has its own key. œ and æ can't be typed without accents, so those words still need the œ/æ key.

| Language | Accents optional? | Why |
|---|---|---|
| es, fr, pt | On | Accents are just marks on the same letter. |
| de | Off | ä/ö/ü make different real words (alter/älter, apfel/äpfel, boden/böden). ß can't be split into a plain letter. |
| tr | Off | ç ğ ı ö ü ş are separate letters (akşam/aksam). |
| vi | Off | Tone marks change the meaning: 116 clashing groups in 738 words. |
| ru | Off | Removing marks turns й into и (заика/зайка would merge). No ё words in the list anyway. |
| ar | Off | It would strip the hamza forms آ أ ؤ إ ئ, which are separate letters with their own keys. |
| en, ko | Off | Nothing to remove. |

- Tested by the accent tests in `tests/test_smoke_browser.py` (for example `test_spanish_accents_optional`).

## Keyboards
- `<lang>_keyboard.json` is optional; only **es** and **en** have one. When it is missing, `_generate_alphabetical_keyboard()` in `app.py` builds one from the letters of the word list, so don't add empty keyboard files. When present, it has `{"default": ..., "layouts": {name: {"label", "rows"}}}`.
- **Generated keyboard rule:** letters in alphabetical order (never reordered), about 10 per row and **never more than 11 per row** (the rows are evened out; earlier rows get the extra key), `⇨` first and `⌫` last on the bottom row. `tests/test_input_bugs.py` checks this for all 8 languages. Row sizes per language: `casa24-responsive`.
- `⇨` is Enter and `⌫` is Backspace.
- The Spanish default is QWERTY with Ñ plus an accent row (á é í ó ú ü). The alternative is "Alfabético", chosen in Settings.
- A key only works if its letter appears in that language's main word list (`Language.characters`).
- **Physical keyboard** (`keyDown()` / `normalizeKey()` in `game.js`):
  - Shift/Caps Lock letters are lowercased: first with the language's own rules (`toLocaleLowerCase(language_code)`, so Turkish `I` → `ı` and `İ` → `i`), then plain `toLowerCase()`.
  - Ctrl/Cmd/Alt shortcuts and IME composition (`isComposing`) are ignored; AltGr still types.
  - Typing inside a Settings field (input/select/textarea) is not a guess.
  - Tapping an on-screen key (`keyClick()`) blurs it, so a physical Enter afterwards submits the word.
  - Esc closes every window.

## Languages
- Kept: en, es, ar, fr, pt, ru, de, tr, vi, ko. These are the 10 most spoken languages that the original game had.
- The menu lists es and en first, set by the sort in `app.py` and the `json.dumps_kwargs` policy that keeps key order.
- Unknown codes such as `/it` redirect to `/`.
- **To remove a language:** `git rm -r webapp/data/languages/<code>`. Nothing else is needed.
- Removed languages can't be restored with one command any more (the `upstream` remote was removed). It would mean adding the original project back as a remote by hand. Ask the owner first.
