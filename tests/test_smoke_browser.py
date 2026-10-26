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


def pick_accent_case(lang="es"):
    """An answer with an accented vowel, plus a valid guess that has the plain
    vowel in that same spot (and nowhere else), shares an exact letter with the
    answer, and does not fold-match it (so resolveAccents leaves it alone)."""
    answers = app.language_codes_5words[lang]
    valid = set(answers) | set(app.language_codes_5words_supplements[lang])
    for answer in answers:
        for i, ch in enumerate(answer):
            plain = fold(ch)
            if plain == ch or not plain.isascii():
                continue
            if plain in answer:  # answer must not also have the plain vowel
                continue
            for guess in sorted(valid):
                if (
                    guess.isascii()
                    and guess[i] == plain
                    and guess.count(plain) == 1
                    and fold(guess) != fold(answer)
                    and any(g == a for g, a in zip(guess, answer))
                ):
                    return answer, guess, i, ch, plain
    raise AssertionError(f"no accent test case found for {lang}")


def test_spanish_colors_respect_accents(server, page):
    answer, guess, i, accented, plain = pick_accent_case("es")
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    # Vue 3.0.2 has no app._instance; reach the root component through its vnode
    vm = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
    page.evaluate(f"w => {{ {vm}.todays_word = w; }}", answer)
    assert page.evaluate(f"{vm}.todays_word") == answer
    type_word(page, guess)
    wait_reveal(page)

    row = page.locator("main .grid-cols-5").first.locator("> div")
    assert row.nth(i).inner_text().strip().lower() == plain  # resolveAccents kept the guess
    assert "incorrect" in row.nth(i).get_attribute("class")  # plain "a" never counts for "á"
    exact = [j for j in range(5) if guess[j] == answer[j]]
    assert any(" correct" in " " + row.nth(j).get_attribute("class") for j in exact)

    def key_class(c):
        return page.locator(f'button.key[data-char="{c}"]').get_attribute("class")

    assert "incorrect" in key_class(plain)
    accented_cls = key_class(accented)
    assert not any(k in accented_cls.split() for k in ("correct", "semicorrect", "incorrect"))
    assert key_class(plain) != accented_cls


@pytest.mark.parametrize("lang", ["fr", "pt"])
def test_accents_optional(server, page, lang):
    words = app.language_codes_5words[lang]
    valid = set(words) | set(app.language_codes_5words_supplements[lang])
    today = app.Language(lang, words).daily_word
    accented = next(
        w for w in words
        if not w.isascii() and fold(w).isascii() and fold(w) != fold(today)
        and fold(w) not in valid
        and fold(w) not in {fold(x) for x in valid if x != w}
    )
    page.goto(f"{server}/{lang}")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, fold(accented))
    wait_reveal(page)
    board = page.locator("main .grid-cols-5").first.inner_text()
    letter = next(c for c in accented if not c.isascii())
    assert letter.upper() in board, (accented, board)


KOLO_IMG = "img.c24-kolo"
KOLO_LOADED = (
    f"(() => {{ const i = document.querySelector('{KOLO_IMG}');"
    " return i && i.offsetParent !== null && i.complete && i.naturalWidth > 0; })()"
)


def kolo_src(page):
    page.wait_for_function(KOLO_LOADED, timeout=8000)  # stats modal opens after the flip
    return page.locator(KOLO_IMG).get_attribute("src")


def test_kolo_after_win(server, page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    today = app.Language("en", app.language_codes_5words["en"]).daily_word
    page.goto(f"{server}/en")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, today)
    src = kolo_src(page)
    assert "/kolo/win/" in src and src.endswith(".png"), src
    assert page.locator(KOLO_IMG).count() == 1
    saved = page.evaluate("JSON.parse(localStorage.getItem('en') || '{}').kolo_image")
    assert saved and src.endswith("/kolo/" + saved), (saved, src)  # saved, not re-picked

    page.reload()
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    assert kolo_src(page) == src  # the same Kolo comes back
    assert errors == []


def test_kolo_after_loss(server, page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    words = app.language_codes_5words["es"]
    today = app.Language("es", words).daily_word
    guesses = [w for w in words if w.isascii() and fold(w) != fold(today)][:6]
    assert len(guesses) == 6
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    for n, word in enumerate(guesses, 1):
        type_word(page, word)
        wait_reveal(page, n)
    src = kolo_src(page)
    assert "/kolo/lose/" in src and src.endswith(".png"), src
    assert page.locator(KOLO_IMG).count() == 1
    assert errors == []
