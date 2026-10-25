"""How the daily word is chosen. Same word for everyone on the same day.

1. "Today" is the calendar date in Panama (UTC-5, no daylight saving),
   so the word changes at midnight Panama time.
2. The day number counts days since 1970-01-01, minus a fixed offset
   (kept from the original game, so day numbers look like "#1400").
3. For languages with Casa 24 answer words, a fixed hash of
   (language, day number) decides whether today is a "Casa 24 day".
   That happens on about 1 day in 5. On those days the word comes from the
   Casa 24 answer list; on other days from the normal shuffled list.

Nothing is random per visit: the same date always gives the same word.
Adding or removing words changes the schedule from then on.
"""

import datetime
import hashlib

PANAMA = datetime.timezone(datetime.timedelta(hours=-5), "America/Panama")
EPOCH = datetime.date(1970, 1, 1)
DAY_OFFSET = 18992 - 195  # from the original game's numbering
CASA24_EVERY_N_DAYS = 5


def panama_today(now=None):
    """Today's date in Panama. `now` is an aware datetime (for tests)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return now.astimezone(PANAMA).date()


def day_index(date):
    """The puzzle number for a calendar date."""
    return (date - EPOCH).days - DAY_OFFSET


def _hash(lang, idx):
    digest = hashlib.sha256(f"casa24:{lang}:{idx}".encode()).hexdigest()
    return int(digest, 16)


def is_casa24_day(lang, idx):
    return _hash(lang, idx) % CASA24_EVERY_N_DAYS == 0


def pick_daily_word(lang, idx, base_answers, casa24_answers):
    """Return today's answer for a language."""
    if casa24_answers and is_casa24_day(lang, idx):
        ordered = sorted(casa24_answers)
        return ordered[(_hash(lang, idx) // CASA24_EVERY_N_DAYS) % len(ordered)]
    return base_answers[idx % len(base_answers)]
