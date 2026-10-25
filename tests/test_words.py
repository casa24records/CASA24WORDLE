import app
import validate_words


def test_validator_passes():
    counts, errors = validate_words.check()
    assert errors == []


def test_both_languages_have_words():
    for lang in ["es", "en"]:
        assert len(app.language_codes_5words[lang]) > 1000
        assert len(app.casa24_words[lang][0]) > 0


def test_casa24_answers_are_valid_guesses():
    for lang in ["es", "en"]:
        valid = set(app.language_codes_5words[lang]) | set(
            app.language_codes_5words_supplements[lang]
        )
        answers, guesses = app.casa24_words[lang]
        assert set(answers) <= valid
        assert set(guesses) <= valid


def test_tiers_do_not_overlap():
    for lang in ["es", "en"]:
        answers, guesses = app.casa24_words[lang]
        assert not set(answers) & set(guesses)


def test_aliases_off_by_default():
    # An alias that is not a normal word (e.g. "zacko") must not be a valid guess.
    for lang in ["es", "en"]:
        normal = set(app.language_codes_5words[lang]) | set(app.load_supplemental_words(lang))
        valid = normal | set(app.language_codes_5words_supplements[lang])
        for alias in app.load_casa24_words(lang, "aliases"):
            if alias not in normal:
                assert alias not in valid


def test_spanish_plurals_accepted():
    valid = set(app.language_codes_5words["es"]) | set(
        app.language_codes_5words_supplements["es"]
    )
    for word in ["cosas", "notas", "todos", "voces"]:
        assert word in valid


def test_no_proper_names_in_spanish():
    # people, places and abbreviations were removed from the Spanish lists
    valid = set(app.language_codes_5words["es"]) | set(app.language_codes_5words_supplements["es"])
    for name in ["laura", "jesús", "rusia", "ibiza", "pablo", "gómez", "excmo", "world"]:
        assert name not in valid
    assert "chile" in app.language_codes_5words["es"]  # the pepper stays
