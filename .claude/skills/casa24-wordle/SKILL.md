---
name: casa24-wordle
description: How Casa 24 Wordle works — how the daily word is chosen (same word for everyone per day and language), the Casa 24 word tiers, the word files, and how to add, review, validate and test words. Use when answering questions about game behavior or when editing word lists, daily-word logic, or translations in this repo.
---

# Casa 24 Wordle: how the game works

Flask app (`webapp/app.py`) with Vue in the browser (`webapp/static/game.js`). Ten languages: en, es, ar, fr, pt, ru, de, tr, vi, ko. Casa 24 words exist only for **es** and **en**.

## One word per day, the same for everyone

- Each language has **exactly one word per day**. Every player who opens `/es` on the same day gets the same Spanish word, and every player on `/en` gets the same English word. Refreshing never changes it. Spanish and English have different words on the same day.
- The day changes at **midnight Panama time (UTC-5, no daylight saving)**. The countdown in the game counts to that same moment.
- The word is computed from the date only. There is no randomness per visit, no database, no login. Logic: `webapp/daily.py`.
  1. `panama_today()` gives today's date in Panama.
  2. `day_index(date)` gives the puzzle number (days since 1970 minus a fixed offset). It appears in share text, e.g. `#1954`.
  3. `is_casa24_day(lang, idx)` hashes (language, puzzle number). About **1 day in 5** is a Casa 24 day. Spanish and English Casa 24 days fall on different dates.
  4. On a Casa 24 day the word comes from `<lang>_5words_casa24_answers.txt`. Otherwise it comes from `<lang>_5words.txt`, which the app shuffles in a fixed order.
- Changing any answer list changes the schedule from then on. Past days are not stored anywhere.
- Each player's progress and stats live only in their own browser (localStorage). The server keeps nothing.

## Word files (`webapp/data/languages/<lang>/`)

| File | Daily answer? | Valid guess? |
|---|---|---|
| `<lang>_5words.txt` | yes (normal days) | yes |
| `<lang>_5words_supplement.txt` | no | yes |
| `<lang>_5words_casa24_answers.txt` | yes (Casa 24 days) | yes |
| `<lang>_5words_casa24_guesses.txt` (slang, brand names) | no | yes |
| `<lang>_5words_casa24_aliases.txt` (member aliases, git-ignored) | no | only if `CASA24_ENABLE_ALIASES=1` |

Rules (enforced by `scripts/validate_words.py`): exactly 5 letters, lowercase, letters only (a-z, ñ, á é í ó ú ü), no word in two Casa 24 tiers.

Accents: languages with `"accent_insensitive": true` in `language_config.json` (Spanish) let players type without accents. On Enter, `resolveAccents()` in `game.js` turns `cancion` into the real word `canción` and the board shows the accented letters. Typing today's answer without accents counts as a win. Tile and key colors compare letters without accents. `ñ` is never folded into `n`. The Spanish keyboard (`es_keyboard.json`) is QWERTY with Ñ plus a row of á é í ó ú ü; an alphabetical layout is in Settings. Other languages still match exactly.

## Adding words

1. Put words in a CSV with columns `lang,word,decision` (`decision` = `answer`, `guess-only`, `alias`, or `reject`; `lang` = `es`, `en`, or `mixed`).
2. `.venv/bin/python scripts/merge_words.py that.csv` adds them (never removes). A word also goes into the other language when that language's main list already has it (e.g. radio, video).
3. `.venv/bin/python scripts/validate_words.py` then `.venv/bin/python -m pytest -q tests`.
4. To remove a word, delete its line from the casa24 file by hand.

Never add member aliases as `answer`, and never commit the alias files.

## Text and translations

All UI text is in `language_config.json` per language (`text`, `help`, `meta`). Missing keys fall back to English (`t()` macro in `game.html`, `this.text()` in `game.js`). Spanish uses Latin American "tú" form.

## Running

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cd webapp && ../.venv/bin/flask --app app run
```
