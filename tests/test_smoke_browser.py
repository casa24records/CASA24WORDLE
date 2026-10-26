"""Browser smoke test: menu loads, /es and /en load, a valid guess colors the tiles.

Needs: pip install playwright pytest-playwright && python -m playwright install chromium
Needs internet (the pages load Vue and Tailwind from public CDNs).
"""

import threading

import pytest
from werkzeug.serving import make_server

import app

pytest.importorskip("playwright")


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def a_valid_non_answer(lang):
    today = app.Language(lang, app.language_codes_5words[lang]).daily_word
    return next(w for w in app.language_codes_5words[lang] if w != today and w.isascii())


def test_menu_loads(server, page):
    page.goto(server + "/")
    assert page.title()


@pytest.mark.parametrize("lang", ["es", "en"])
def test_guess_colors_tiles(server, page, lang):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": 390, "height": 844})  # phone size
    page.goto(f"{server}/{lang}")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    word = a_valid_non_answer(lang)
    for letter in word:
        page.keyboard.press(letter)
    page.keyboard.press("Enter")
    wait_reveal(page)
    assert page.locator(BOARD_COLORED).count() == 5
    assert errors == []


def fold(word):
    import unicodedata

    return "".join(
        c if c == "ñ" else unicodedata.normalize("NFD", c)[0] for c in word
    )


# colored tiles on the board only (the help modal has example tiles too)
BOARD_COLORED = "main .grid-cols-5 > .correct, main .grid-cols-5 > .semicorrect, main .grid-cols-5 > .incorrect"


def wait_reveal(page, rows=1):
    """Wait until `rows` guesses have finished their letter-by-letter flip."""
    page.wait_for_function(
        f"document.querySelectorAll('{BOARD_COLORED}').length >= {5 * rows}"
        " && !document.querySelector('.flip')",
        timeout=5000,
    )


def type_word(page, word):
    for letter in word:
        page.keyboard.press(letter)
    page.keyboard.press("Enter")


def test_spanish_accents_optional(server, page):
    today = app.Language("es", app.language_codes_5words["es"]).daily_word
    accented = next(
        w for w in app.language_codes_5words["es"]
        if "ó" in w and fold(w) != fold(today)
        and fold(w) not in {fold(x) for x in app.language_codes_5words["es"] if x != w}
    )
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, fold(accented))  # e.g. "jamon"
    wait_reveal(page)
    assert "Ó" in page.locator("#app").inner_text()  # board shows "JAMÓN"

    type_word(page, fold(today))  # today's word typed without accents still wins
    page.wait_for_function(
        "JSON.parse(localStorage.getItem('game_results') || '{}').es?.slice(-1)[0]?.won === true",
        timeout=5000,
    )


def test_start_screen(server, page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(server + "/")
    page.wait_for_function("document.querySelector('.c24-play')")
    links = page.locator("a[data-lang]")
    codes = [links.nth(i).get_attribute("data-lang") for i in range(links.count())]
    assert len(codes) == 10 and set(codes[:2]) == {"es", "en"}
    hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
    assert all(h.startswith("/") for h in hrefs)  # nothing points to other sites
    assert page.evaluate("document.body.scrollHeight") < 2000
    assert "#" in page.locator(".c24-today").inner_text()


def test_start_screen_remembers_language_and_played_today(server, page):
    today = app.Language("es", app.language_codes_5words["es"]).daily_word
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, fold(today))
    page.wait_for_function(
        "JSON.parse(localStorage.getItem('game_results') || '{}').es?.slice(-1)[0]?.won === true"
    )
    page.goto(server + "/")
    page.wait_for_function("document.querySelector('.c24-play')")
    first = page.locator(".c24-play").first
    assert first.get_attribute("data-lang") == "es"
    assert "Jugada hoy" in first.inner_text()


def test_stats_page_removed(server, page):
    page.goto(server + "/stats")
    assert page.url.rstrip("/") == server
