"""Browser smoke test: "/" opens the game, /es and /en load, a valid guess colors the tiles.

Needs: pip install playwright pytest-playwright && python -m playwright install chromium
Needs internet (the pages load Vue and Tailwind from public CDNs).
"""

import threading
from urllib.parse import urlparse

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


def test_root_opens_the_game(server, page):
    # no start page since 2026-11-04: "/" goes straight into the guest game, in the
    # computer's language (Playwright's Chromium says en-US)
    page.goto(server + "/")
    assert page.title()
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    assert urlparse(page.url).path in ("/es", "/en")


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


def test_root_remembers_the_language_played(server, page):
    """The game sets the c24_lang cookie: "/" opens the last language played."""
    for lang in ("es", "en", "es"):
        page.goto(f"{server}/{lang}")
        page.wait_for_function("document.querySelector('#app') && window.Vue")
        page.goto(server + "/")
        page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
        assert urlparse(page.url).path == "/" + lang


def test_stats_page_removed(server, page):
    page.goto(server + "/stats")
    assert urlparse(page.url).path in ("/es", "/en")  # via "/", into the game


def pick_accent_case(lang="es"):
    """An answer with an accented vowel, plus a valid plain (ASCII) guess that has
    the plain vowel in that same spot and does not fold-match the answer (so
    resolveAccents leaves it alone)."""
    answers = app.language_codes_5words[lang]
    valid = set(answers) | set(app.language_codes_5words_supplements[lang])
    for answer in answers:
        for i, ch in enumerate(answer):
            plain = fold(ch)
            if plain == ch or not plain.isascii():
                continue
            for guess in sorted(valid):
                if guess.isascii() and guess[i] == plain and fold(guess) != fold(answer):
                    return answer, guess, i, ch, plain
    raise AssertionError(f"no accent test case found for {lang}")


def press_key(page, key):
    # page.keyboard.press doesn't know "ñ"; a keydown event is what the game reads
    page.evaluate("k => window.dispatchEvent(new KeyboardEvent('keydown', {key: k}))", key)


def test_plain_vowel_greens_accented_answer(server, page):
    """2026-10-29 rule: a plain "o" counts for "ó" (and back); the plain key gets the color."""
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
    assert " correct" in " " + row.nth(i).get_attribute("class")  # plain vowel = accented one
    key = page.locator(f'button.key[data-char="{plain}"]').get_attribute("class")
    assert "correct" in key.split()
    assert page.locator(f'button.key[data-char="{accented}"]').count() == 0  # no accent keys


def test_enye_word_typed_plain_wins_and_shares_colors_only(server, page):
    """An answer with ñ and an accent, typed on a physical keyboard without the accent:
    it wins, the board shows the real spelling, and the share text has no letters."""
    words = app.language_codes_5words["es"]
    answer = next((w for w in words if "ñ" in w and fold(w) != w), None) or next(w for w in words if "ñ" in w)
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    vm = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
    page.evaluate(f"w => {{ {vm}.todays_word = w; }}", answer)
    for c in fold(answer):
        press_key(page, c.upper())  # Shift/Caps Lock, Ñ included
    press_key(page, "Enter")
    page.wait_for_function(
        "JSON.parse(localStorage.getItem('game_results') || '{}').es?.slice(-1)[0]?.won === true",
        timeout=5000,
    )
    assert page.evaluate(f"{vm}.tiles[0].join('')") == answer
    saved = page.evaluate("JSON.parse(localStorage.getItem('es')).tiles[0].join('')")
    assert saved == answer
    board = page.evaluate(f"{vm}.getEmojiBoard()")
    assert board.startswith("🟩🟩🟩🟩🟩") and set(board) <= set("🟩🟧⬜\n"), board


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
    assert "/kolo/win/" in src and src.split("?v=")[0].endswith(".webp"), src
    # the end window (Explained.pdf): date, green score, Kolo + clean grid; no "You won!" line
    assert page.locator("[data-stats-score]").inner_text().strip() == "1/6"
    assert "is-won" in page.locator("[data-stats-score]").get_attribute("class")
    assert page.locator(".c24-result").count() == 0
    assert page.locator(KOLO_IMG).count() == 1
    assert_clean_result_grid(page, 1)
    saved = page.evaluate("JSON.parse(localStorage.getItem('en') || '{}').kolo_image")
    assert saved and src.split("?v=")[0].endswith("/kolo/" + saved), (saved, src)  # saved, not re-picked

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
    assert "/kolo/lose/" in src and src.split("?v=")[0].endswith(".webp"), src
    assert page.locator("[data-stats-score]").inner_text().strip() == "X/6"
    assert "is-won" not in page.locator("[data-stats-score]").get_attribute("class")
    assert page.locator(KOLO_IMG).count() == 1
    assert_clean_result_grid(page, 6)
    assert errors == []


def assert_clean_result_grid(page, rows):
    """End window: the result is drawn as flat colored squares (no emoji text);
    Share still uses the emoji version."""
    grid = page.locator("#emoji_board")
    assert grid.inner_text().strip() == ""
    assert grid.locator(".c24-result-row").count() == rows
    cells = grid.locator(".c24-result-row > span")
    assert cells.count() == rows * 5
    classes = set(cells.evaluate_all("els => els.map(e => e.className)"))
    assert classes <= {"is-correct", "is-semicorrect", "is-incorrect"}, classes
    board = page.evaluate(f"{VM}.emoji_board")
    assert grid.get_attribute("aria-label") == board and set(board) <= set("🟩🟧⬜\n")


VM = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
NOTIFICATION = "#app .fixed.top-0 p.font-bold"


def assert_repeat_rejected(page):
    page.wait_for_function(
        f"(() => {{ const n = document.querySelector('{NOTIFICATION}');"
        " return n && n.innerText.includes('Ya probaste esa palabra'); })()",
        timeout=3000,
    )
    page.wait_for_timeout(2000)  # longer than a flip: make sure no reveal starts
    assert page.evaluate(f"{VM}.active_row") == 1
    assert page.locator(BOARD_COLORED).count() == 5  # only the first row is colored
    assert not page.evaluate(f"{VM}.game_over")


def test_repeated_word_rejected(server, page):
    word = a_valid_non_answer("es")
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, word)
    wait_reveal(page)
    type_word(page, word)
    assert_repeat_rejected(page)


def test_repeated_word_rejected_without_accents(server, page):
    words = app.language_codes_5words["es"]
    today = app.Language("es", words).daily_word
    accented = next(
        w for w in words
        if not w.isascii() and fold(w).isascii() and fold(w) != fold(today)
        and fold(w) not in {fold(x) for x in words if x != w}
    )
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, fold(accented))  # e.g. "jamon" -> "jamón"
    wait_reveal(page)
    type_word(page, fold(accented))  # resolves to the same word again
    assert_repeat_rejected(page)


# ---------------------------------------------------------------- rebrand (2026-11-04, Explained.pdf)

def test_stats_icon_after_a_win_shows_the_compact_window(server, page):
    """The end window (opened by itself) has Kolo and the grid; the header icon afterwards
    opens the compact window of the guide: date, green n/6, next word, Share."""
    today = app.Language("en", app.language_codes_5words["en"]).daily_word
    page.goto(f"{server}/en")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    type_word(page, today)
    kolo_src(page)
    page.keyboard.press("Escape")
    page.click("[data-stats-open]")
    page.wait_for_selector("[data-stats-score]", state="visible")
    assert page.locator("[data-stats-score]").inner_text().strip() == "1/6"
    assert "is-won" in page.locator("[data-stats-score]").get_attribute("class")
    assert page.locator("img.c24-kolo").count() == 0 and page.locator("#emoji_board").count() == 0
    assert page.locator("#copy_button").is_visible()
    title = page.locator("#stats-title").inner_text()
    assert title.split(" · ")[0].strip().upper() == title.split(" · ")[0].strip()  # uppercase date
    assert "2" in title and "," in title


def test_help_is_like_the_guide(server, page):
    page.goto(f"{server}/en")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    page.click("[data-help-open]")
    help_box = page.locator("#HelpModal")
    help_box.wait_for(state="visible")
    assert help_box.locator("#help-title img").get_attribute("alt") == "El Wordle by Casa 24"
    words = help_box.locator(".c24-example").evaluate_all(
        "els => els.map(e => [...e.children].map(c => c.textContent.trim()).join(''))")
    assert words == ["blunt", "farts", "dream"]
    assert help_box.locator(".c24-example .correct").inner_text().strip().lower() == "b"
    assert help_box.locator(".c24-example .semicorrect").inner_text().strip().lower() == "r"
    assert help_box.locator(".c24-example .incorrect").inner_text().strip().lower() == "m"
    door = help_box.locator("[data-c24-door]")
    assert door.get_attribute("href") == "https://www.casa24records.com" and door.get_attribute("target") == "_blank"
    assert help_box.locator("[data-legal-links] a").count() == 2
    assert "how to play" in help_box.inner_text().lower() or help_box.locator(".sr-only").count()


def test_header_door_and_language_window_on_the_web(server, page):
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    assert page.locator("header img.c24-titler").get_attribute("alt") == "El Wordle by Casa 24"
    assert page.locator("header .c24-badge").inner_text().replace(" ", "") == "ES▾"
    assert page.locator("header [data-c24-door]").get_attribute("href") == "https://www.casa24records.com"
    page.click("[data-lang-open]")
    page.wait_for_selector("[data-web-langs]", state="visible")
    links = page.locator("[data-web-langs] a[data-lang-choice]")
    assert [links.nth(i).get_attribute("href") for i in range(links.count())] == ["/es", "/en"]
    assert "c24_lang=es" in page.evaluate("document.cookie")
    page.click("[data-web-langs] a[data-lang-choice=en]")
    page.wait_for_url("**/en")
    assert "c24_lang=en" in page.evaluate("document.cookie")


def test_spanish_help_uses_the_same_examples_for_now(server, page):
    """Owner 2026-11-04: Spanish shows BLUNT / FARTS / DREAM too (with the Spanish lines)."""
    page.goto(f"{server}/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    page.click("[data-help-open]")
    words = page.locator("#HelpModal .c24-example").evaluate_all(
        "els => els.map(e => [...e.children].map(c => c.textContent.trim()).join(''))")
    assert words == ["blunt", "farts", "dream"]
    assert "está en la palabra y en el lugar correcto" in page.locator("#HelpModal").inner_text()


def test_language_window_text_centered_and_mix_tab_green(server, page):
    """Owner 2026-11-04: the website's language buttons center their text; on the
    leaderboard the active MIX tab is green (#32DD65) like the guide, EN/ESP amber."""
    page.goto(f"{server}/en")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    page.click("[data-lang-open]")
    link = page.locator("[data-web-langs] a[data-lang-choice=es]")
    link.wait_for(state="visible")
    box = link.bounding_box()
    text = link.evaluate("e => { const r = document.createRange(); r.selectNodeContents(e);"
                         " const b = r.getBoundingClientRect(); return {y: b.y, h: b.height}; }")
    assert abs((text["y"] + text["h"] / 2) - (box["y"] + box["height"] / 2)) <= 2
    import flask
    tabs = [{"code": c, "name_native": app.language_configs[c]["name_native"]} for c in ("en", "es")] + [
        {"code": "all", "name_native": None}]
    for tab, rgb in (("all", "rgb(50, 221, 101)"), ("es", "rgb(255, 184, 0)")):
        with app.app.test_request_context(f"/leaderboard?tab={tab}"):
            html = flask.render_template("leaderboard.html", tab=tab, lb_tabs=tabs, rows=[], me_row=None,
                                         is_admin=False, lb_user=None, lb_enabled=True)
        body = html
        page.route(server + "/board", lambda r: r.fulfill(body=body, content_type="text/html"))
        page.goto(server + "/board")
        assert page.locator(f".c24-lb-tab.is-active[data-tab={tab}]").evaluate("e => getComputedStyle(e).color") == rgb
        page.unroute(server + "/board")
