"""Input and share bugs: physical keyboard (Shift, shortcuts, focus, accented
and ñ keys), on-screen key focus, the share button firing once, the es/en
keyboard layouts and the layout setting."""

import threading

import pytest
from werkzeug.serving import make_server

import app

VM = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
READY = "document.querySelector('#app') && window.Vue"
KEYS_JS = "Array.from(document.querySelectorAll('button.key[data-char]'), b => b.dataset.char)"
ES_LETTERS = set("abcdefghijklmnñopqrstuvwxyz")


def build_keyboard(lang, layout=None):
    return app.Language(lang, app.language_codes_5words[lang], layout)


# ---------------------------------------------------------------- keyboard order


def test_spanish_and_english_default_to_qwerty():
    for lang in ("es", "en"):
        assert build_keyboard(lang).keyboard_layout_name == "qwerty"


@pytest.mark.parametrize("layout", ["qwerty", "alphabetical"])
def test_spanish_layouts_have_enye_and_no_accent_keys(layout):
    rows = build_keyboard("es", layout).keyboard
    letters = [c for row in rows for c in row if c not in ("⇨", "⌫")]
    assert sorted(letters) == sorted(ES_LETTERS)  # 26 letters + ñ, each once
    assert letters.index("ñ") == letters.index("l" if layout == "qwerty" else "n") + 1
    assert rows[-1][0] == "⇨" and rows[-1][-1] == "⌫"


# ---------------------------------------------------------------- browser

pytest.importorskip("playwright")


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def open_game(page, server, lang):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server}/{lang}")
    page.wait_for_function(READY)
    return errors


def row0(page):
    return page.evaluate(f"{VM}.tiles[0].join('')")


@pytest.mark.parametrize("lang", ["es", "en"])
def test_rendered_keyboard_matches_layout(server, page, lang):
    open_game(page, server, lang)
    language = build_keyboard(lang)
    assert page.evaluate(KEYS_JS) == [c for row in language.keyboard for c in row]


@pytest.mark.parametrize("how", ["query", "cookie"])
def test_spanish_alphabetical_setting(server, page, how):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    if how == "query":
        page.goto(f"{server}/es?layout=alphabetical")
    else:
        page.context.add_cookies([{"name": "keyboard_layout_es", "value": "alphabetical", "url": server}])
        page.goto(f"{server}/es")
    page.wait_for_function(READY)
    keys = [c for c in page.evaluate(KEYS_JS) if c not in ("⇨", "⌫")]
    assert len(keys) == 27 and set(keys) == ES_LETTERS
    assert keys[:3] == ["a", "b", "c"] and keys.index("ñ") == keys.index("n") + 1
    assert page.locator("#keyboard-layout-select").input_value() == "alphabetical"
    press_key(page, "ñ")
    assert row0(page) == "ñ"
    assert errors == []


def test_shift_letter_types_lowercase(server, page):
    errors = open_game(page, server, "en")
    page.keyboard.press("Shift+A")
    page.keyboard.press("B")  # Caps Lock style
    page.keyboard.press("c")
    assert row0(page) == "abc"
    assert errors == []


@pytest.mark.parametrize("shortcut", ["Control+r", "Meta+r", "Alt+r", "Control+a"])
def test_shortcuts_do_not_type(server, page, shortcut):
    open_game(page, server, "en")
    page.evaluate("window.__same_page = true")
    page.keyboard.press("c")
    page.keyboard.press(shortcut)
    page.wait_for_timeout(200)
    assert page.evaluate("window.__same_page === true")
    assert row0(page) == "c"


def test_typing_in_a_form_field_is_not_a_guess(server, page):
    open_game(page, server, "en")
    page.evaluate(
        "() => { const i = document.createElement('input'); i.id = 'probe';"
        " document.body.appendChild(i); i.focus(); }"
    )
    page.keyboard.press("a")
    assert row0(page) == ""
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("a")
    assert row0(page) == "a"


def press_key(page, key):
    page.evaluate("k => window.dispatchEvent(new KeyboardEvent('keydown', {key: k}))", key)


def test_physical_enye_and_accented_keys(server, page):
    errors = open_game(page, server, "es")
    press_key(page, "ñ")
    press_key(page, "Ñ")          # Shift/Caps Lock
    press_key(page, "á")          # accented keys type the plain letter
    press_key(page, "U\u0308")    # decomposed Ü -> u
    press_key(page, "n\u0303")    # decomposed ñ stays ñ
    assert page.evaluate(f"{VM}.tiles[0]") == ["ñ", "ñ", "a", "u", "ñ"]
    assert errors == []


def test_dead_keys_and_unknown_keys_are_ignored(server, page):
    open_game(page, server, "es")
    for key in ("Dead", "´", "¨", "1", "ß"):
        press_key(page, key)
    page.keyboard.press("o")
    assert row0(page) == "o"


def test_english_accented_key_types_plain_letter(server, page):
    open_game(page, server, "en")
    press_key(page, "é")
    assert row0(page) == "e"


def test_physical_enter_after_tapping_a_key(server, page):
    open_game(page, server, "en")
    page.click("button.key[data-char='c']")
    focused_key = page.evaluate(
        "!!(document.activeElement && document.activeElement.classList.contains('key'))"
    )
    assert not focused_key
    page.keyboard.press("Enter")  # partial word: a notice, not a second "c"
    page.wait_for_timeout(100)
    assert row0(page) == "c"


STUB_SHARE = """
window.__shares = [];
Object.defineProperty(navigator, 'share', {configurable: true,
    value: async (data) => { window.__shares.push(data.text); }});
"""
STUB_CLIPBOARD = """
window.__shares = [];
Object.defineProperty(navigator, 'share', {configurable: true, value: undefined});
Object.defineProperty(navigator, 'clipboard', {configurable: true,
    value: {writeText: async (text) => { window.__shares.push(text); }}});
"""


@pytest.mark.parametrize("stub", [STUB_SHARE, STUB_CLIPBOARD], ids=["share", "clipboard"])
def test_share_fires_once_per_tap(server, page, stub):
    page.add_init_script(stub)
    errors = open_game(page, server, "en")
    today = build_keyboard("en").daily_word
    for letter in today:
        page.keyboard.press(letter)
    page.keyboard.press("Enter")
    button = page.locator("#copy_button")
    button.wait_for(state="visible", timeout=8000)
    page.wait_for_timeout(3500)  # the countdown re-renders the modal every second
    button.click()
    page.wait_for_timeout(300)
    shares = page.evaluate("window.__shares")
    assert len(shares) == 1, shares
    assert shares[0].startswith("Casa 24 Wordle EN #") and "1/6" in shares[0]
    assert "🟩🟩🟩🟩🟩" in shares[0]
    button.click()
    page.wait_for_timeout(300)
    assert len(page.evaluate("window.__shares")) == 2
    assert errors == []
