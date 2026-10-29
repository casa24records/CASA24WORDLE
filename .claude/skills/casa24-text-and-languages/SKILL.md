---
name: casa24-text-and-languages
description: Change any visible text or translation in Casa 24 Wordle (buttons, notifications, end-screen result title, help), follow the Spanish style guide, work with accent-insensitive typing, flexible-vowel colors and the Spanish QWERTY-Ñ keyboard, or the es/en-only language list. Use when editing language_config.json, keyboards, hard-coded strings in templates/JS, or the list of languages.
---

# Text, translations, accents, languages

## Where text lives
- **Only two languages: es and en** (since 2026-10-29). Each: `webapp/data/languages/<lang>/language_config.json`
  - `meta`: page description
  - `text`: buttons, notifications, settings, stats
  - `help`: the how-to-play popup
  - also `language_code`, `name`, `name_native`, and `accent_insensitive` (es only). The old `right_to_left` key and Settings toggle are gone.
- Templates: use `{{ t('key', 'English fallback') }}` (macro at the top of `game.html`).
- `game.js`: use `this.text("key", "English fallback")`.
- Missing keys fall back to the English text in the code.
- The start screen (`index.html`) is bilingual on purpose: Spanish and English side by side in `lang="es"`/`lang="en"` spans. The Play/Jugar and "Jugada hoy"/"Played today" card labels come from `label(code, key)` in `index.js`: each card speaks its own language. Card names are each language's `language_name_native`. **Exception: the Discord pieces** (sign-in button, guest toggle, privacy link and dialog, toasts, header menu labels) use the `L1(key, es, en)` macro: both languages are in the page, but CSS on `data-l` shows only the one matching `<html lang>` (set from Accept-Language by the server, then to the player's language by `index.js`). `aria-label`/`title` attributes stay bilingual.
- `index.html` and `leaderboard.html` get `texts` from `app.py`, like `demo_login.html`: `index.html` the es and en `text` blocks, `leaderboard.html` es and en (`LB_TEXT_FALLBACK`). `index.html` uses the macros `tx(lang, key, fallback)` and `bi(key, es, en)` (both languages side by side); `leaderboard.html` uses `L(key, es, en)` and shows **one** language: the tab's language on ES/EN, the browser's es/en choice on Combinado (`all`). Missing keys fall back to the inline es/en text. The menu's Discord pieces stay es/en only (`data-l`). Both keep inline es/en fallbacks, so they still render if `texts` is missing. Change the JSON **and** the inline fallback together.

**Rule:** never hard-code a user-visible string. Add the key to **both** es and en configs, with an English fallback in the code.

Current `text` keys:
- Words and game: `next_word`, `no_attempts`, `share`
- End-screen title (class `c24-result`, above the Kolo): `result_won`, `result_lost`
- Notifications: `notification-copied`, `notification-partial-word`, `notification-not-valid`, `notification-share-unsupported`, `notification-repeated` (same word guessed twice in one game)
- Settings: `settings`, `keyboard_layout`, `easy_mode`
- Accessibility labels (2026-10-29, NYT-style layout): `help_label`, `stats_label` (header icon buttons), `board_label` (board `role="grid"`), `board_row` ("Fila"/"Row" + number), `keyboard_label`, `key_enter`, `key_backspace` (⇨ / ⌫ keys), `activity_invite` ("Invitar amigos"/"Invite friends" card, Discord only)
- Stats: `stats_games`, `stats_win_percentage`, `stats_current_streak`, `stats_best_streak`
- Theme: `theme`, `theme_auto`, `theme_light`, `theme_dark`
- Developer view (internally "demo", team only; **es and en only**): `demo_restart`, `demo_fill`, `demo_title` ("Vista de desarrollador" / "Developer view"), `demo_intro`, `demo_password`, `demo_enter`, `demo_wrong_password`. The password page (`demo_login.html`) reads the es and en keys together and shows them side by side, so both files need every `demo_*` key. (The start-screen card "🔒 Developer view" is in `index.html`.)

- Leaderboard (Discord mode; the game reads them with `this.text`/`t()`, the menu and `/leaderboard` through `texts`):
  - Sign-in and account: `lb_signin` (Discord button and header icon: "Entrar con Discord" / "Sign in with Discord"), `lb_account` (aria label of the avatar button), `lb_view` (popover item and trophy icon label), `lb_logout`, `lb_play_guest` (logged-in switch "Jugar como invitado (no cuenta)")
  - Privacy dialog: `lb_privacy_title` (the small "ⓘ Privacidad" link and the dialog title), `lb_privacy` (what Discord and we see/store), `lb_avatar_note` (where your Discord picture is shown), `lb_guest_note` (guest games don't count). **Changed 2026-10-27** for the live view: `lb_privacy` now says we store ID, username, profile picture and results "para mostrar el ranking y quién está jugando hoy" and that others see only your colors; `lb_avatar_note` no longer says the photo stays in your browser. The fallback strings in `index.html` / `leaderboard.html` still have the old wording (only used if a key is missing).
  - Toasts and errors: `lb_login_failed`, `lb_login_cancelled`, `lb_deleted`, `lb_dismiss` (× / Close label), `lb_error`
  - Live view (`casa24-live-view`): `lb_live_title` ("Jugando hoy" / "Playing today"), `lb_live_empty` ("Nadie más está jugando ahora"), `lb_live_now` ("en vivo" / "live", next to the dot), `lb_live_open` (aria-label of the header people button)
  - Game end window: `lb_rank_label` ("Puesto"/"Rank", under the big "#N"), `lb_points_label` / `lb_point_label` ("puntos"/"punto", under "+N"; singular when exactly 1), `lb_hint` (pointer shown after a guest game)
  - `/leaderboard` page: `lb_title`, `lb_tab_all` ("Combinado"; the language tabs show each `name_native`, so `lb_tab_es` / `lb_tab_en` exist but are unused), `lb_col_player`, `lb_col_points`, `lb_col_wins`, `lb_col_streak`, `lb_col_best`, `lb_you`, `lb_my_position`, `lb_empty`, `lb_delete`, `lb_delete_confirm`, `lb_hide`, `lb_back`
  - Removed: `lb_rank`, `lb_points`, `lb_point_one` (the numbers are now plain "#N" / "+N" with a label). Also removed with the mode switch: `lb_mode_label`, `lb_mode_guest`, `lb_mode_lb`, `lb_logged_in_as` (`lb_login` is still used by `index.html`).
  - No `lb_*` key has placeholders any more (`lb_my_position` is followed by ": #N" in the template).
- Discord Activity:
  - `activity_pick_title` ("Elige tu idioma" / "Choose your language"): the Activity shell's 2-option language picker, shown only when Discord's language can't be read (see `casa24-discord-activity`). The shell shows **es and en together** (`activity_shell()` reads them into `pick`; inline fallbacks in `app.py`).
  - `activity_loading_game` ("Cargando juego…" / "Loading game…"): shell overlay while the game iframe loads, shown in the chosen language (`langs[].loading` in the shell JSON).
  - `activity_lang_button` ("Cambiar idioma" / "Change language"): aria-label of the game header's "Casa 24 ES ▾" button and title of the language window (`game.html`, `t()`).
  - The shell's "Conectando…", permission and error texts are hard-coded es + en side by side in `templates/activity.html` (the language isn't known yet).

- `next_word`, `no_attempts` and `share` are read in `game.html` **without** a fallback, so they must exist in es and en.
- Both have the full `help` block (`title`, `text_1_1_1` … `text_2_3`, `close`).
- History: from 2026-10-28 to 2026-10-29 every key was also translated into 8 more languages (superseded: those languages were removed).

Edit JSON with Python (`json.load`, then `json.dump(..., ensure_ascii=False, indent=4)`) so accents stay readable.

## Spanish style guide
- Natural Latin American, Panama-friendly Spanish, in the **tú** form: "Escribe", "Pulsa", "Puedes".
- Use these words: Compartir (not "Cuota"), intento (not "conjetura"/"supongo"), casillas (not "azulejos"), Ajustes, Partidas, Racha, "% ganadas".
- Keep labels short. Stats labels sit four in a row on a 390 px wide phone.
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
- **Spanish (2026-10-29): QWERTY + Ñ**, `q…p` / `a…l ñ` / `⇨ z…m ⌫`, **no accent keys**. The alternative **"Alfabético"** stays in Settings (owner asked), also without accents, ñ right after n. English is unchanged.
- The letters a player can type are the keyboard's letters: `input_characters()` in `app.py` puts them in the page (`c24_data.input_characters`), and `inputCharacters()` / `acceptable_characters` in `game.js` use them (folded).
- **Physical keyboard** (`keyDown()` / `normalizeKey()` in `game.js`):
  - `normalizeKey()`: NFC, lowercase, then `foldAccents`, so Shift/Caps Lock letters work and a physical accented key (á, Ü) types the plain letter; Ñ types ñ.
  - Ctrl/Cmd/Alt shortcuts and IME composition (`isComposing`) are ignored; AltGr still types.
  - Typing inside a Settings field (input/select/textarea) is not a guess.
  - Tapping an on-screen key (`keyClick()`) blurs it, so a physical Enter afterwards submits the word.
  - Esc closes every window.

## Languages
- **Only es and en** (owner, 2026-10-29). `SUPPORTED_LANGS = ("es", "en")` in `app.py` is the list (menu, leaderboard, sitemap, hreflang); the folders no longer define it.
- `RETIRED_LANGS` (ar, de, fr, ko, pt, ru, tr, vi): `/<code>` and `/lb/<code>` redirect 302 (query kept) to es or en by the browser's Accept-Language (default es); the APIs answer 400 `bad_lang`. Tested in `tests/test_languages.py`.
- Other unknown codes such as `/it` redirect to `/`.
- **Adding a language back** is a real project now (data folder, keyboard JSON, every text key, add it to `SUPPORTED_LANGS`, tests, layout check). Ask the owner first; the decision is es/en only.
- Removed languages can't be restored with one command any more (the `upstream` remote was removed). It would mean adding the original project back as a remote by hand. Ask the owner first.
- New keys (2026-10-29): `legal_terms`, `legal_privacy` and `lb_cancel` (was missing; inline fallback only).
