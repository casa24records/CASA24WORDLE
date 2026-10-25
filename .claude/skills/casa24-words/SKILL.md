---
name: casa24-words
description: Add, remove, review or validate Casa 24 Wordle words — the answer and guess-only tiers, member aliases, the bigger Spanish guess list, cross-language words, and safety rules (names, brands, offensive words). Use whenever word files under webapp/data/languages/ change.
---

# Words

## Files per language (`webapp/data/languages/<lang>/`)
| File | Daily answer? | Valid guess? | Notes |
|---|---|---|---|
| `<lang>_5words.txt` | yes | yes | upstream list; es had 115 proper names removed |
| `<lang>_5words_supplement.txt` | no | yes | en: upstream; es: FrequencyWords filtered by Hunspell (CC BY-SA 4.0) |
| `<lang>_5words_casa24_answers.txt` | on ~1 in 5 days | yes | Casa 24 vocabulary and everyday words |
| `<lang>_5words_casa24_guesses.txt` | never | yes | house slang (priti, frene, fokop), brand names (canva) |
| `<lang>_5words_casa24_aliases.txt` | never | only with `CASA24_ENABLE_ALIASES=1` | member aliases, **git-ignored, excluded from Vercel** |

Casa 24 files start with a `#` comment line. Words are sorted, one per line.

## Rules (enforced by `scripts/validate_words.py`)
- Exactly 5 letters, lowercase, NFC-normalized, letters only: a-z, ñ, á é í ó ú ü.
- A word lives in only one Casa 24 tier per language.
- es and en main lists and supplements are non-empty, and each has Casa 24 answers.

## Safety rules (apply judgment, not just the validator)
- **No names of people or places as answers.** Members' aliases are never answers, and are off until each member agrees.
- **No brand or trademark names as answers.** At most they can be guess-only, like `canva`.
- **Strong language:** the game is public and may be shown to sponsors. Ask the owner before adding swear words, even as guess-only.
- **Slang** that isn't in a dictionary is guess-only.

## Add words
1. Make a CSV with columns `lang,word,decision`:
   - `lang` is `es`, `en` or `mixed` (both).
   - `decision` is `answer`, `guess-only`, `alias` or `reject`.
2. Run `.venv/bin/python scripts/merge_words.py that.csv`.
   - It only ever **adds** words.
   - A word also goes into the other language when that language's **main** list already has it, like `radio`, `video`, `audio`, `piano` or `canal`.
   - It doesn't use the supplements for this, because the big English list contains Spanish words like `nieve`.
   - `answer` beats `guess-only`: a word marked as both ends up as an answer.
3. Run `.venv/bin/python scripts/validate_words.py`, then `.venv/bin/python -m pytest -q tests`.
4. Commit with a message listing the words added.

The original seed batch is `scripts/casa24/seed_words.csv`, with a `decision` column. The aliases from it are in the git-ignored `scripts/casa24/seed_aliases_PRIVATE.csv`.

## Remove a word
Delete its line from the right file by hand. Also check the other language's Casa 24 files, since shared words appear in both. Then validate and test. If you remove proper names or other words from the main lists, add a few of them to `test_no_proper_names_in_spanish`.

## Upstream lists
- For a bigger, properly licensed list, see how `es_5words_supplement.txt` was made in `CREDITS.md`:
  - take 5-letter words from FrequencyWords seen 20 or more times
  - keep the ones Hunspell `es` accepts, using `spylls`
- Credit any new source in `CREDITS.md`, and **check the license before using it**.
- Any list change reshuffles future daily words. See `casa24-daily-word`.
