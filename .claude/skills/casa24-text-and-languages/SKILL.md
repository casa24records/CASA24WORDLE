---
name: casa24-text-and-languages
description: Change any visible text or translation in Casa 24 Wordle, follow the Spanish style guide, work with accent-insensitive typing and keyboards, or add/remove a language. Use when editing language_config.json, keyboards, hard-coded strings in templates/JS, or the list of languages.
---

# Text, translations, accents, languages

## Where text lives
- Each language: `webapp/data/languages/<lang>/language_config.json`
  - `meta`: page title, description, keywords
  - `text`: buttons, notifications, settings, stats
  - `help`: the how-to-play popup
- Templates: use `{{ t('key', 'English fallback') }}` (macro at the top of `game.html`).
- `game.js`: use `this.text("key", "English fallback")`.
- Missing keys fall back to English, so the 8 other languages still work.
- The start screen (`index.html`) is bilingual on purpose: Spanish and English side by side in `lang="es"`/`lang="en"` spans. The Play/Jugar and "Jugada hoy"/"Played today" labels are in the template's Vue expressions.

**Rule:** never hard-code a user-visible string. Add the key to **both** `es` and `en` configs, with an English fallback in the code.

Current `text` keys:
- Words and game: `subheader`, `next_word`, `no_attempts`, `share`
- Notifications: `notification-copied`, `notification-partial-word`, `notification-not-valid`, `notification-share-unsupported`
- Settings: `settings`, `right_to_left`, `keyboard_layout`, `easy_mode`, `source_code`
- Stats: `stats_games`, `stats_win_percentage`, `stats_current_streak`, `stats_best_streak`
- Theme: `theme`, `theme_auto`, `theme_light`, `theme_dark`

Edit JSON with Python (`json.load`, then `json.dump(..., ensure_ascii=False, indent=4)`) so accents stay readable.

## Spanish style guide
- Natural Latin American, Panama-friendly Spanish, in the **tú** form: "Escribe", "Pulsa", "Puedes".
- Use these words: Compartir (not "Cuota"), intento (not "conjetura"/"supongo"), casillas (not "azulejos"), Ajustes, Partidas, Racha, "% ganadas".
- Keep labels short. Stats labels sit four in a row on a 390 px wide phone.
- Show new Spanish strings to the owner before committing big text changes.

## Accents (Spanish)
- Turned on per language with `"accent_insensitive": true` in `language_config.json`. Currently only `es` has it. Don't turn it on for languages where accented letters are separate letters, such as Turkish or Vietnamese.
- In `game.js`:
  - `foldAccents()` removes accents but keeps **ñ**.
  - On Enter, `resolveAccents()` maps the typed word to a real word. For example, `cancion` becomes `canción`, and the board shows the accents.
  - If the typed word matches today's answer without accents, it **is** today's answer and counts as a win.
  - `updateColors()` compares letters without accents. It colors both the base key and the accented key.
- Tested in `tests/test_smoke_browser.py::test_spanish_accents_optional`.

## Keyboards
- `<lang>_keyboard.json` has `{"default": ..., "layouts": {name: {"label", "rows"}}}`.
- `⇨` is Enter and `⌫` is Backspace.
- The Spanish default is QWERTY with Ñ plus an accent row (á é í ó ú ü). The alternative is "Alfabético", chosen in Settings.
- A key only works if its letter appears in that language's main word list (`Language.characters`).

## Languages
- Kept: en, es, ar, fr, pt, ru, de, tr, vi, ko. These are the 10 most spoken languages that upstream had.
- The menu lists es and en first, set by the sort in `app.py` and the `json.dumps_kwargs` policy that keeps key order.
- Unknown codes such as `/it` redirect to `/`.
- **To remove a language:** `git rm -r webapp/data/languages/<code>`. Nothing else is needed.
- **To restore one from upstream:** `git checkout upstream/main -- webapp/data/languages/<code>`, then add the new `text` keys if you want it translated.
