"""Spanish accents and ñ (owner decision 2026-10-29): the Spanish keyboard is
QWERTY + Ñ with no accent keys; a plain vowel counts for the accented one (and
back) in colors, ü = u, but ñ is always its own letter. Typing without accents
still resolves to the accented word. Pure Python, plus one browser check."""

import hashlib
import json
import os
import threading
import unicodedata

import pytest

import app
import leaderboard as lb

C, S, I = "correct", "semicorrect", "incorrect"
LANG_DIR = os.path.join(os.path.dirname(app.STATIC_DIR), "data", "languages")
ACCENTED = set("áéíóúüàèìòùâêîôûäëïöÁÉÍÓÚÜ")


def keyboard_json(lang):
    with open(os.path.join(LANG_DIR, lang, f"{lang}_keyboard.json"), encoding="utf-8") as f:
        return json.load(f)


def es_lists():
    return app.language_codes_5words["es"], app.language_codes_5words_supplements["es"]


# ---------------------------------------------------------------- keyboards

def test_spanish_qwerty_rows():
    kb = keyboard_json("es")
    assert kb["default"] == "qwerty"
    assert kb["layouts"]["qwerty"]["rows"] == [
        list("qwertyuiop"), list("asdfghjklñ"), ["⇨"] + list("zxcvbnm") + ["⌫"],
    ]


@pytest.mark.parametrize("layout", ["qwerty", "alphabetical"])
def test_spanish_layouts_are_26_letters_plus_enye(layout):
    rows = keyboard_json("es")["layouts"][layout]["rows"]
    letters = [c for row in rows for c in row if c not in ("⇨", "⌫")]
    assert len(letters) == 27 and set(letters) == set("abcdefghijklmnopqrstuvwxyz") | {"ñ"}
    assert not ACCENTED & set(letters)


def test_no_accent_keys_in_any_spanish_layout():
    for name, layout in keyboard_json("es")["layouts"].items():
        keys = {c for row in layout["rows"] for c in row}
        assert not ACCENTED & keys, name
        assert all(c == unicodedata.normalize("NFC", c) for c in keys), name


def test_english_keyboard_unchanged():
    kb = keyboard_json("en")
    assert kb["default"] == "qwerty"
    rows = {k: ["".join(r) for r in v["rows"]] for k, v in kb["layouts"].items()}
    assert rows == {
        "qwerty": ["qwertyuiop", "asdfghjkl", "⇨zxcvbnm⌫"],
        "dvorak": ["pyfgcrl", "aoeuidhtns", "⇨qjkxbmwvz⌫"],
        "alphabetical": ["abcdefghij", "klmnopqrst", "⇨uvwxyz⌫"],
    }
    path = os.path.join(LANG_DIR, "en", "en_keyboard.json")
    with open(path, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == (
            "2889db5e9d33a938e5f2b6d14775e24808727fead3d365d7b7e828e93f25279b")


# ---------------------------------------------------------------- fold

def test_fold_keeps_enye():
    assert lb.fold_accents("ñ") == "ñ"
    assert lb.fold_accents("Ñ".lower()) == "ñ"
    assert lb.fold_accents("Ñ") == "Ñ"
    assert lb.fold_accents("ñ") == "ñ"          # decomposed ñ: NFC first
    assert lb.fold_accents("año") == "año"
    assert lb.fold_accents("ü") == "u"
    assert lb.fold_accents("pingüino") == "pinguino"
    assert lb.fold_accents("canción") == "cancion"
    assert lb.fold_accents("ó") == "o"          # decomposed ó


def test_word_lists_are_nfc():
    main, sup = es_lists()
    assert all(w == unicodedata.normalize("NFC", w) for w in list(main) + list(sup))


# ---------------------------------------------------------------- resolve

def test_sonar_and_sonar_with_enye_never_meet():
    main, sup = es_lists()
    for typed, answer in (("sonar", "soñar"), ("soñar", "sonar"), ("sonar", "perro"), ("soñar", "perro")):
        resolved = lb.resolve_accents(typed, answer, main, sup, True)
        assert lb.fold_accents(resolved) == typed, (typed, answer, resolved)


def test_every_accented_answer_wins_typed_plain():
    main, sup = es_lists()
    fold_map = lb.build_fold_map(main, sup)
    accented = [w for w in main if lb.fold_accents(w) != w]
    assert len(accented) > 100
    for w in accented:
        typed = lb.fold_accents(w)
        assert lb.resolve_accents(typed, w, main, sup, True, fold_map) == w, w
        assert lb.color_guess(typed, w) == [C] * 5, w


def test_accent_groups_without_plain_form():
    """Plain spellings shared by several accented words and not a word itself
    (vacío/vació...): typed plain they resolve to the first listed form, unless
    one of them is today's answer."""
    main, sup = es_lists()
    groups = {}
    for w in list(main) + list(sup):
        groups.setdefault(lb.fold_accents(w), set()).add(w)
    no_plain = {k: v for k, v in groups.items() if len(v) > 1 and k not in v}
    assert "vacio" in no_plain and no_plain["vacio"] == {"vacío", "vació"}
    for plain, forms in no_plain.items():
        for answer in forms:
            assert lb.resolve_accents(plain, answer, main, sup, True) == answer


# ---------------------------------------------------------------- colors

def test_colors_fold_vowels_but_not_enye():
    assert lb.color_guess("cancion", "canción") == [C] * 7
    assert lb.color_guess("canción", "cancion") == [C] * 7
    assert lb.color_guess("sonar", "soñar") == [C, C, I, C, C]
    assert lb.color_guess("soñar", "sonar") == [C, C, I, C, C]
    assert lb.color_guess("pingue", "pingüe") == [C] * 6
    # a decomposed ñ in the guess is still ñ
    assert lb.color_guess("soñar", "soñar") == [C] * 5


def test_duplicate_letters_with_accents():
    # "á" and "a" are one letter: the answer has two a's in total
    assert lb.color_guess("aaxxa", "ábaca") == [C, S, I, I, C]
    # only one a in the answer: the green one uses it up
    assert lb.color_guess("aaxxx", "xáxxx") == [I, C, C, C, C]
    assert lb.color_guess("pasas", "papás") == [C, C, I, C, C]


def test_share_text_is_emoji_only():
    """getEmojiBoard builds the share text from tile colors only, never letters."""
    with open(os.path.join(app.STATIC_DIR, "game.js"), encoding="utf-8") as f:
        src = f.read()
    start = src.index("\n        getEmojiBoard()")
    body = src[start:src.index("\n        text(key, fallback)", start)]
    assert "this.tile_classes" in body
    assert "this.tiles" not in body and "todays_word" not in body
    assert "fromCharCode" not in body


# ---------------------------------------------------------------- browser

@pytest.fixture(scope="module")
def server():
    pytest.importorskip("playwright")
    from werkzeug.serving import make_server

    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_old_saved_accent_key_colors_fold(server, page):
    """A guest game saved before 2026-10-29 kept colors on accented keys ("á"):
    they now color the plain key, and nothing breaks."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    today = app.Language("es", app.language_codes_5words["es"]).daily_word
    saved = {
        "tiles": [["", "", "", "", ""] for _ in range(6)],
        "tile_classes": [["border-2 border-neutral-300"] * 5 for _ in range(6)],
        "key_classes": {"á": "correct", "a": "incorrect", "ü": "semicorrect", "ñ": "incorrect"},
        "active_row": 0, "active_cell": 0, "todays_word": today, "game_over": False,
        "game_won": False, "emoji_board": "", "attempts": "0", "full_word_inputted": False,
    }
    page.add_init_script(f"localStorage.setItem('es', {json.dumps(json.dumps(saved))})")
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")

    def cls(c):
        return page.locator(f'button.key[data-char="{c}"]').get_attribute("class").split()

    assert "correct" in cls("a")
    assert "semicorrect" in cls("u")
    assert "incorrect" in cls("ñ") and "incorrect" not in cls("n")
    assert errors == []
