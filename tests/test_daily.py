import datetime

import daily

UTC = datetime.timezone.utc
BASE = [f"w{i:04d}" for i in range(3000)]
CASA = ["plena", "notas", "voces", "corte", "pieza"]


def word_on(date, lang="es"):
    return daily.pick_daily_word(lang, daily.day_index(date), BASE, CASA)


def test_same_date_same_word():
    d = datetime.date(2026, 11, 3)
    assert word_on(d) == word_on(d)


def test_different_dates_differ():
    words = [word_on(datetime.date(2026, 1, 1) + datetime.timedelta(days=i)) for i in range(30)]
    assert len(set(words)) > 20


def test_panama_midnight_boundary():
    # 04:59 UTC is still 23:59 the previous day in Panama
    before = datetime.datetime(2026, 11, 4, 4, 59, tzinfo=UTC)
    after = datetime.datetime(2026, 11, 4, 5, 0, tzinfo=UTC)
    assert daily.panama_today(before) == datetime.date(2026, 11, 3)
    assert daily.panama_today(after) == datetime.date(2026, 11, 4)


def test_casa24_about_one_day_in_five():
    n = sum(daily.is_casa24_day("es", i) for i in range(5000))
    assert 900 < n < 1100


def test_casa24_days_use_casa24_words():
    for i in range(2000):
        word = daily.pick_daily_word("es", i, BASE, CASA)
        assert (word in CASA) == daily.is_casa24_day("es", i)


def test_no_casa24_words_means_base_list():
    for i in range(100):
        assert daily.pick_daily_word("fr", i, BASE, []) == BASE[i % len(BASE)]


def test_numbering_starts_at_1_on_start_date():
    assert daily.day_index(daily.START_DATE) == 1
    assert daily.day_index(datetime.date(2026, 10, 26)) == 1
    assert daily.day_index(datetime.date(2026, 10, 27)) == 2
