---
name: casa24-text-and-languages
description: Change any visible text or translation in El Wordle by Casa 24 (buttons, notifications, share text, How to play examples, leaderboard tabs EN/ESP/MIX, the "Jugar/Play" back link; no landing texts since 2026-11-04), follow the Spanish style guide, work with accent-insensitive typing, flexible-vowel colors, the keyboards (QWERTY / QWERTY-Ñ plus a hidden alphabetical layout), or the es/en-only language list. Use when editing language_config.json, keyboards, hard-coded strings in templates/JS, or the list of languages.
---

# Text, translations, accents, languages

## Where text lives
- **Only two languages: es and en** (since 2026-10-29). Each: `webapp/data/languages/<lang>/language_config.json`
  - `meta`: page description
  - `text`: buttons, notifications, stats, leaderboard
  - `help`: the How to play window
  - also `language_code`, `name`, `name_native`, and `accent_insensitive` (es only). The old `right_to_left` key is gone, and Settings is gone entirely (2026-11-04).
- Templates: use `{{ t('key', 'English fallback') }}` (macro at the top of `game.html`).
- `game.js`: use `this.text("key", "English fallback")`.
- Missing keys fall back to the English text in the code.
- **No landing since 2026-11-04** (`index.html`/`index.js` deleted; `/` opens the game). The game's Discord pieces (header icon/avatar menu at the top left, toasts) use `t()` in `game.html`, in the game's language.
- `leaderboard.html` gets `texts` from `app.py`, like `demo_login.html`: es and en (`LB_TEXT_FALLBACK`). It uses `L(key, es, en)` and shows **one** language: the tab's language on ESP/EN, the browser's es/en choice on MIX (`all`). Missing keys fall back to the inline es/en text, so it still renders if `texts` is missing. Change the JSON **and** the inline fallback together. Discord texts shown by `_discord.html` in both languages show only one via `data-l` (CSS follows `<html lang>`).

**Rule:** never hard-code a user-visible string. Add the key to **both** es and en configs, with an English fallback in the code.

Current `text` keys:
- Words and game: `next_word`, `no_attempts`, `share`
- `result_won`, `result_lost`: still in the JSON but **not shown** since 2026-11-04 (the stats window has no won/lost line)
- Notifications: `notification-copied`, `notification-partial-word`, `notification-not-valid`, `notification-share-unsupported`, `notification-repeated` (same word guessed twice in one game)
- Accessibility labels (2026-10-29, NYT-style layout): `help_label`, `stats_label` (header icon buttons), `board_label` (board `role="grid"`), `board_row` ("Fila"/"Row" + number), `keyboard_label`, `key_enter`, `key_backspace` (⇨ / ⌫ keys), `activity_invite` ("Invitar amigos"/"Invite friends" card, Discord only)
- Stats: `stats_games`, `stats_win_percentage`, `stats_current_streak`, `stats_best_streak`
- **Removed 2026-11-04 (no landing):** `landing_tagline`, `landing_or_guest`, `lb_login`, `lb_play_guest` (and earlier the Settings keys `settings`, `theme*`, `easy_mode`, `keyboard_layout`).
- **Removed 2026-11-04** with Settings and light mode: `settings`, `keyboard_layout`, `easy_mode`, `theme`, `theme_auto`, `theme_light`, `theme_dark`. Don't add them back.
- Developer view (internally "demo", team only; **es and en only**): `demo_restart`, `demo_fill`, `demo_title` ("Vista de desarrollador" / "Developer view"), `demo_intro`, `demo_password`, `demo_enter`, `demo_wrong_password`. The password page (`demo_login.html`) reads the es and en keys together and shows them side by side, so both files need every `demo_*` key. (No card: the hidden Ctrl+⌘+D shortcut on the website's game pages opens `/demo`.)

- Leaderboard (Discord mode; the game reads them with `this.text`/`t()`, `/leaderboard` through `texts`):
  - Sign-in and account: `lb_signin` (Discord button and header icon: "Entrar con Discord" / "Sign in with Discord"), `lb_account` (aria label of the avatar button), `lb_view` (popover item and trophy icon label), `lb_logout`
  - Privacy dialog: `lb_privacy_title` (the small "ⓘ Privacidad" link and the dialog title), `lb_privacy` (what Discord and we see/store), `lb_avatar_note` (where your Discord picture is shown), `lb_guest_note` (guest games don't count). **Changed 2026-10-27** for the live view: `lb_privacy` now says we store ID, username, profile picture and results "para mostrar el ranking y quién está jugando hoy" and that others see only your colors; `lb_avatar_note` no longer says the photo stays in your browser. The fallback strings in `leaderboard.html` match the new wording.
  - Toasts and errors: `lb_login_failed`, `lb_login_cancelled`, `lb_deleted`, `lb_dismiss` (× / Close label), `lb_error`
  - Live view (`casa24-live-view`): `lb_live_title` ("Jugando hoy" / "Playing today"), `lb_live_empty` ("Nadie más está jugando ahora"), `lb_live_now` ("en vivo" / "live", next to the dot), `lb_live_open` (aria-label of the header people button)
  - Game end window: `lb_rank_label` ("Puesto"/"Rank", under the big "#N"), `lb_points_label` / `lb_point_label` ("puntos"/"punto", under "+N"; singular when exactly 1), `lb_hint` (pointer shown after a guest game)
  - Tabs (2026-11-04, `/leaderboard` and the Discord window, order EN · ESP · MIX): `lb_tab_en` "EN", `lb_tab_es` "ESP", `lb_tab_all` "MIX" (same in both languages; was Combinado/Combined and the `name_native`s).
  - `/leaderboard` page: `lb_title`, `lb_col_player`, `lb_col_points`, `lb_col_wins`, `lb_col_streak`, `lb_col_best`, `lb_you`, `lb_my_position`, `lb_empty`, `lb_delete`, `lb_delete_confirm`, `lb_hide`, `lb_back` (back link on `/leaderboard`, to `/` = the game: "Jugar" / "Play" since 2026-11-04, was "Menú" / "Menu"; legal pages use the same words inline in `legal.html`)
  - Removed: `lb_rank`, `lb_points`, `lb_point_one` (the numbers are now plain "#N" / "+N" with a label). Also removed with the mode switch: `lb_mode_label`, `lb_mode_guest`, `lb_mode_lb`, `lb_logged_in_as`.
  - No `lb_*` key has placeholders any more (`lb_my_position` is followed by ": #N" in the template).
- Discord Activity:
  - `activity_pick_title` ("Elige tu idioma" / "Choose your language"): the Activity shell's 2-option language picker, shown only when Discord's language can't be read (see `casa24-discord-activity`). The shell shows **es and en together** (`activity_shell()` reads them into `pick`; inline fallbacks in `app.py`).
  - `activity_loading_game` ("Cargando juego…" / "Loading game…"): shell overlay while the game iframe loads, shown in the chosen language (`langs[].loading` in the shell JSON).
  - `activity_lang_button` ("Cambiar idioma" / "Change language"): aria-label of the game header's language button (hoodie Kolo + El Wordle + lime "ES ▾") and title of the language window, in Discord and on the website (`game.html`, `t()`).
  - The shell's "Conectando…", permission and error texts are hard-coded es + en side by side in `templates/activity.html` (the language isn't known yet).

- `next_word`, `no_attempts` and `share` are read in `game.html` **without** a fallback, so they must exist in es and en.
- `help` block (`title`, `title_2`, `text_1_1_1` … `text_2_3`, `close`; `example_1`..`example_3` in es and en). **How to play since 2026-11-04 (Explained.pdf):** El Wordle image (`title` is sr-only), `title_2` ("Examples"), three example words with one colored letter each and `text_2_1`..`text_2_3` under them, the door, Terms · Privacy. Example words: `help.example_1..3` (`blunt`, `farts`, `dream` in both languages for now, owner 2026-11-04; Spanish words can replace them later), else the first three answers. The rule texts `text_1_*` are no longer shown; `close` is only the ✕ aria-label.
- **Share text** (`shareResults()` in `game.js`, not translated): `El Wordle by Casa 24 EN #5 3/6` + link + emoji grid.
- History: from 2026-10-28 to 2026-10-29 every key was also translated into 8 more languages (superseded: those languages were removed).

Edit JSON with Python (`json.load`, then `json.dump(..., ensure_ascii=False, indent=4)`) so accents stay readable.

## Spanish style guide
- Natural Latin American, Panama-friendly Spanish, in the **tú** form: "Escribe", "Pulsa", "Puedes".
- Use these words: Compartir (not "Cuota"), intento (not "conjetura"/"supongo"), casillas (not "azulejos"), Partidas, Racha, "% ganadas".
- Keep labels short. Stats labels sit four in a row on a 390 px wide phone.
- The product name "El Wordle by Casa 24" is not translated.
- "Leaderboard" stays in English in Spanish text, as used everywhere so far ("Juega con leaderboard", "Ver leaderboard"); the list itself is "el ranking" ("entrar al ranking"), a place is "puesto" (label "Puesto"), a game won is "Ganadas". Discord login is "Entrar con Discord" / "Cerrar sesión" (English: "Sign in with Discord" / "Log out").
- Owner rule for leaderboard/Discord UI: **less text, the UI speaks for itself.** Prefer an icon or a short label; long explanations go in the privacy dialog, not on the page.
- Privacy text is plain and honest: say exactly what is stored (Discord ID, username, profile picture, results) and what we never see (password, email), and that other players see only colors.
- Show new Spanish strings to the owner before committing big text changes.

## Accents (flexible vowels, decided 2026-10-29)
- Turned on with `"accent_insensitive": true` in `language_config.json`: **es only** (en has no accents).
- **Typing accents is optional, and colors ignore them too.** This reverses the 2026-10-26 rule where colors followed the exact accented letter.
  - `foldAccents()` (top of `game.js`) and `fold_accents()` (`leaderboard.py`) do the same thing: NFC first (a decomposed n + U+0303 becomes ñ), then remove accent marks, **except ñ/Ñ**. ü folds to u.
  - On Enter, `resolveAccents()` maps the typed word to a real word. For example, `cancion` becomes `canción`, and **the board shows the accented spelling**.
  - If the typed word matches today's answer without accents, it **is** today's answer and counts as a win.
  - Colors: `updateColors()` (guest) and `color_guess()` (server) compare **folded** letters, so a plain "o" is green/yellow for an "ó" and the other way round. **Ñ is always its own letter** (sonar ≠ soñar). Keys are colored by their folded letter (the keyboard has no accent keys).
  - The repeated-guess check runs on the resolved word, so typing `jamon` after `jamón` is also blocked.
  - When several accented words share one plain spelling, a plain spelling that is itself a word wins; otherwise the first match in the list wins (13 Spanish groups have no plain word).
  - Old saved games with colors on accented keys are folded on load (harmless).
- Tested by `tests/test_accents.py` (keyboard shape, fold rules, colors both ways, sonar/soñar, each accented answer wins typed plain) plus the parity cases in `tests/test_leaderboard.py`.

## Keyboards
- Each language has a `<lang>_keyboard.json`: `{"default": ..., "layouts": {name: {"label", "rows"}}}`. (The automatic alphabetical keyboard for languages without a file was removed with the other languages.)
- `⇨` is Enter and `⌫` is Backspace (aria labels `key_enter` / `key_backspace`).
- **Spanish (2026-10-29): QWERTY + Ñ**, `q…p` / `a…l ñ` / `⇨ z…m ⌫`, **no accent keys**. English: QWERTY. **Dvorak was removed 2026-11-04.**
- **Hidden alphabetical layout** (both languages: `alphabetical`, "Alfabético" / "Alphabetical", ñ right after n, no accents): no Settings any more, so **Ctrl+⌘+A** on Mac (Ctrl+Alt+Shift+A elsewhere) toggles QWERTY ↔ alphabetical. `keyDown()` → `switchLayout()` in `game.js` reloads with `?layout=`; the server saves cookie `keyboard_layout_<lang>` (`layout` is in `ACTIVITY_OWN_PARAMS`, so it also works in the Discord iframe). The board has `.c24-keyboard[data-layout]`. Tests: `tests/test_layout.py::test_no_settings_and_hidden_keyboard_shortcut`, `tests/test_activity.py::test_activity_hidden_alphabetical_keyboard_keeps_query`.
- The letters a player can type are the keyboard's letters: `input_characters()` in `app.py` puts them in the page (`c24_data.input_characters`), and `inputCharacters()` / `acceptable_characters` in `game.js` use them (folded).
- **Physical keyboard** (`keyDown()` / `normalizeKey()` in `game.js`):
  - `normalizeKey()`: NFC, lowercase, then `foldAccents`, so Shift/Caps Lock letters work and a physical accented key (á, Ü) types the plain letter; Ñ types ñ.
  - Ctrl/Cmd/Alt shortcuts and IME composition (`isComposing`) are ignored; AltGr still types.
  - Typing inside a form field (input/select/textarea) is not a guess.
  - Tapping an on-screen key (`keyClick()`) blurs it, so a physical Enter afterwards submits the word.
  - Esc closes every window.

## Languages
- **Only es and en** (owner, 2026-10-29). `SUPPORTED_LANGS = ("es", "en")` in `app.py` is the list (games, leaderboard, sitemap, hreflang); the folders no longer define it.
- `RETIRED_LANGS` (ar, de, fr, ko, pt, ru, tr, vi): `/<code>` and `/lb/<code>` redirect 302 (query kept) to es or en by the browser's Accept-Language (default es); the APIs answer 400 `bad_lang`. Tested in `tests/test_languages.py`.
- Other unknown codes such as `/it` redirect to `/`.
- **Adding a language back** is a real project now (data folder, keyboard JSON, every text key, add it to `SUPPORTED_LANGS`, tests, layout check). Ask the owner first; the decision is es/en only.
- Removed languages can't be restored with one command any more (the `upstream` remote was removed). It would mean adding the original project back as a remote by hand. Ask the owner first.
- New keys (2026-10-29): `legal_terms`, `legal_privacy` and `lb_cancel` (was missing; inline fallback only).
