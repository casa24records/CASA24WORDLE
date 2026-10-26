---
name: casa24-daily-word
description: How Casa 24 Wordle picks the daily word — same word for everyone, per language, changing at midnight Panama time, with Casa 24 words on about 1 day in 5. Use when someone asks whether players get the same or different words, when the word changes, or wants to change the schedule or Casa 24 frequency.
---

# Daily word

## The rules (answer questions with these)
- **One word per language per day.** Everyone on `/es` today gets the same Spanish word, and everyone on `/en` gets the same English word. Refreshing or replaying never changes it. Spanish and English have different words on the same day.
- **New word at 00:00 Panama time** (UTC-5, no daylight saving). The countdown in the game counts to that moment.
- **No randomness per visit.** The word is computed from the date only. There is no server state.
- **Casa 24 days:** about 1 day in 5 (separately for es and en), the word comes from `<lang>_5words_casa24_answers.txt`. Other days it comes from `<lang>_5words.txt`.
- The other 8 languages have no Casa 24 words and always use their main list.

## Code: `webapp/daily.py`
1. `panama_today(now)` → today's date in Panama.
2. `day_index(date)` → puzzle number = days since 1970-01-01 minus `DAY_OFFSET` (kept from the original game so numbers look like `#1954`; don't change it). Shown in share text.
3. `is_casa24_day(lang, idx)` → `sha256("casa24:{lang}:{idx}") % CASA24_EVERY_N_DAYS == 0`.
4. `pick_daily_word(lang, idx, base_answers, casa24_answers)` → on Casa 24 days, picks from the sorted Casa 24 list with the same hash. Otherwise picks `base_answers[idx % len]`.

`app.py` loads `base_answers` by reading `<lang>_5words.txt` and shuffling it with a fixed seed. Languages load in sorted order, so the shuffle is the same on every machine.

`game.js` `get_time_until_next_day()` uses UTC-5 for the countdown. If the timezone changes, change both files.

## Changing things
- **Frequency:** edit `CASA24_EVERY_N_DAYS` in `daily.py` (5 = about 20%). Update `test_casa24_about_one_day_in_five` in `tests/test_daily.py`.
- **Any word-list edit reshuffles the future schedule.** Past days are not stored, so this is fine before launch. After launch, warn the owner that tomorrow's word may change.
- **Never** add `random` without a fixed seed, use the visitor's local clock on the server, or pick words in the browser. Any of these would give players different words.

## Check today's word (for debugging only, don't spoil it for the owner unprompted)
```
cd webapp && ../.venv/bin/python -c "import app; print(app.Language('es', app.language_codes_5words['es']).daily_word)"
```

Tests: `tests/test_daily.py` covers same date gives the same word, dates differ, the Panama midnight boundary, the 1-in-5 rate, and that Casa 24 days use Casa 24 words.
