"""Input and share bugs: physical keyboard (Shift, shortcuts, focus, Turkish i),
on-screen key focus, the share button firing once, alphabetical keyboards."""

import threading

import pytest
from werkzeug.serving import make_server

import app

VM = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
READY = "document.querySelector('#app') && window.Vue"
GENERATED = [l for l in app.language_codes if l not in ("es", "en")]


def build_keyboard(lang):
    return app.Language(lang, app.language_codes_5words[lang])


# ---------------------------------------------------------------- keyboard order


@pytest.mark.parametrize("lang", GENERATED)
def test_generated_keyboard_is_alphabetical(lang):
    language = build_keyboard(lang)
    assert language.keyboard_layout_name == "alphabetical"
    rows = language.keyboard
    letters = [c for row in rows for c in row if c not in ("⇨", "⌫")]
    assert letters == list(language.characters)  # alphabetical, nothing lost
    assert rows[-1][0] == "⇨" and rows[-1][-1] == "⌫"
    assert sum(r.count("⇨") + r.count("⌫") for r in rows) == 2
    assert max(len(r) for r in rows) <= 11, [len(r) for r in rows]
    assert all(rows), "no empty rows"


def test_spanish_and_english_keep_their_layouts():
    for lang in ("es", "en"):
        assert build_keyboard(lang).keyboard_layout_name != "alphabetical"


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


@pytest.mark.parametrize("lang", ["de", "fr", "tr"])
def test_rendered_keyboard_is_alphabetical(server, page, lang):
    open_game(page, server, lang)
    chars = page.evaluate(
        "Array.from(document.querySelectorAll('button.key[data-char]'), b => b.dataset.char)"
    )
    language = build_keyboard(lang)
    assert chars == [c for row in language.keyboard for c in row]


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


def test_turkish_capital_i(server, page):
    open_game(page, server, "tr")
    for key in ("I", "İ"):  # Turkish: I -> ı, İ -> i
        page.evaluate(f"window.dispatchEvent(new KeyboardEvent('keydown', {{key: '{key}'}}))")
    page.keyboard.press("Shift+C")  # ordinary letters still work
    assert page.evaluate(f"{VM}.tiles[0]") == ["ı", "i", "c", "", ""]


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
