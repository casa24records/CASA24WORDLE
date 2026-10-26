---
name: casa24-text-and-languages
description: Change any visible text or translation in Casa 24 Wordle, follow the Spanish style guide, work with accent-insensitive typing and keyboards, or add/remove a language. Use when editing language_config.json, keyboards, hard-coded strings in templates/JS, or the list of languages.
---

# Text, translations, accents, languages

## Where text lives
- Each language: `webapp/data/languages/<lang>/language_config.json`
  - `meta`: page description
  - `text`: buttons, notifications, settings, stats
  - `help`: the how-to-play popup
- Templates: use `{{ t('key', 'English fallback') }}` (macro at the top of `game.html`).
- `game.js`: use `this.text("key", "English fallback")`.
- Missing keys fall back to English, so the 8 other languages still work.
- The start screen (`index.html`) is bilingual on purpose: Spanish and English side by side in `lang="es"`/`lang="en"` spans. The Play/Jugar and "Jugada hoy"/"Played today" labels are in the template's Vue expressions.

**Rule:** never hard-code a user-visible string. Add the key to **both** `es` and `en` configs, with an English fallback in the code.

Current `text` keys:
- Words and game: `next_word`, `no_attempts`, `share`
- Notifications: `notification-copied`, `notification-partial-word`, `notification-not-valid`, `notification-share-unsupported`
- Settings: `settings`, `right_to_left`, `keyboard_layout`, `easy_mode`
- Stats: `stats_games`, `stats_win_percentage`, `stats_current_streak`, `stats_best_streak`
- Theme: `theme`, `theme_auto`, `theme_light`, `theme_dark`

Edit JSON with Python (`json.load`, then `json.dump(..., ensure_ascii=False, indent=4)`) so accents stay readable.

## Spanish style guide
- Natural Latin American, Panama-friendly Spanish, in the **tú** form: "Escribe", "Pulsa", "Puedes".
- Use these words: Compartir (not "Cuota"), intento (not "conjetura"/"supongo"), casillas (not "azulejos"), Ajustes, Partidas, Racha, "% ganadas".
- Keep labels short. Stats labels sit four in a row on a 390 px wide phone.
- Show new Spanish strings to the owner before committing big text changes.

## Accents
- Turned on per language with `"accent_insensitive": true` in `language_config.json`. It is on for `es`, `fr` and `pt`.
- **Typing accents is optional, but colors respect them.**
  - `foldAccents()` removes accents but keeps **ñ**. If you ever turn this on for a language with another letter that must stay separate, add it to that keep list.
  - On Enter, `resolveAccents()` maps the typed word to a real word. For example, `cancion` becomes `canción`, and the board shows the accents.
  - If the typed word matches today's answer without accents, it **is** today's answer and counts as a win.
  - `updateColors()` compares letters **exactly**. A plain "a" never counts for an "á" in the answer (it is gray unless the answer also has a plain "a"). An "á" is green or yellow only against an "á". Only the key of the exact letter on the tile gets colored.
  - When several accented words share one plain spelling, a plain spelling that is itself a word wins; otherwise the first match in the list wins. French has 11 of these groups, Portuguese 82.
- French and Portuguese keyboards are built automatically in alphabetical order (they have no `<lang>_keyboard.json`), so every accented letter has its own key. œ and æ can't be typed without accents, so those words still need the œ/æ key.

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
- `<lang>_keyboard.json` is optional. When it is missing, an alphabetical keyboard is built automatically from the word list, so don't add empty keyboard files. When present, it has `{"default": ..., "layouts": {name: {"label", "rows"}}}`.
- `⇨` is Enter and `⌫` is Backspace.
- The Spanish default is QWERTY with Ñ plus an accent row (á é í ó ú ü). The alternative is "Alfabético", chosen in Settings.
- A key only works if its letter appears in that language's main word list (`Language.characters`).

## Languages
- Kept: en, es, ar, fr, pt, ru, de, tr, vi, ko. These are the 10 most spoken languages that the original game had.
- The menu lists es and en first, set by the sort in `app.py` and the `json.dumps_kwargs` policy that keeps key order.
- Unknown codes such as `/it` redirect to `/`.
- **To remove a language:** `git rm -r webapp/data/languages/<code>`. Nothing else is needed.
- Removed languages can't be restored with one command any more (the `upstream` remote was removed). It would mean adding the original project back as a remote by hand. Ask the owner first.
