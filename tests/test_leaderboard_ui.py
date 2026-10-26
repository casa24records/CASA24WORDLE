"""Leaderboard front end: menu choice, leaderboard page, leaderboard game page.

Templates are rendered with the variables the backend contract promises
(lb_enabled, lb_user, lb, lb_state, rows, me_row, is_admin...), so these tests
don't depend on how the backend stores anything. The browser tests serve those
rendered pages through Playwright's request interception and fake /api/guess.
Tests that need a real backend route skip when it isn't there.
"""

import json
import re
import threading

import flask
import pytest
from werkzeug.serving import make_server

import app

LB_ENV = ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY",
          "DATABASE_URL")

ME = {"id": "100000000000000001", "username": "kolo_fan"}


@pytest.fixture
def lb_off(monkeypatch):
    for name in LB_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def lb_on(monkeypatch):
    for name in LB_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DISCORD_CLIENT_ID", "x")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "y")
    monkeypatch.setenv("SECRET_KEY", "z-test-only")


def has_route(rule):
    return any(r.rule == rule for r in app.app.url_map.iter_rules())


def render(template, path="/", **ctx):
    with app.app.test_request_context(path):
        return flask.render_template(template, **ctx)


def render_menu(path="/", **ctx):
    base = dict(languages=app.languages, language_codes=app.language_codes,
                todays_idx=app.get_todays_idx(), demo_enabled=False)
    base.update(ctx)
    return render("index.html", path, **base)


def render_game(lang="es", **ctx):
    language = app.Language(lang, app.language_codes_5words[lang])
    if ctx.get("lb"):
        language.daily_word = ""
    base = dict(language=language, demo=False)
    base.update(ctx)
    return render("game.html", "/" + lang, **base)


def row(rank, pid, name, points, is_me=False):
    return {"rank": rank, "id": pid, "username": name, "points": points, "wins": points // 3,
            "played": points // 2, "current_streak": 2, "best_streak": 4, "is_me": is_me}


# ---------- menu ----------

def test_menu_without_leaderboard_has_no_choice(lb_off):
    html = app.app.test_client().get("/").get_data(as_text=True)
    assert "data-lb-menu" not in html
    assert "/leaderboard" not in html
    assert "data-mode=" not in html


def test_menu_with_leaderboard_shows_choice_and_privacy():
    html = render_menu(lb_enabled=True, lb_user=None)
    assert 'data-mode="guest"' in html and 'data-mode="lb"' in html
    assert "Jugar como invitado" in html and "Play as guest" in html
    assert "Jugar con leaderboard (Discord)" in html and "Play for the leaderboard (Discord)" in html
    assert 'href="/leaderboard"' in html
    assert "no vemos tu contraseña ni tu correo" in html
    assert "no se suman al ranking" in html
    assert "/auth/logout" not in html  # logged out
    # the other 8 languages stay guest links
    assert 'href="/de"' in html and "/lb/de" not in html


def test_menu_logged_in_shows_user_and_logout():
    html = render_menu(lb_enabled=True, lb_user=ME)
    assert "@kolo_fan" in html
    assert re.search(r'<form method="post" action="/auth/logout"', html)
    assert '"username":"kolo_fan"' in html  # handed to index.js


@pytest.mark.parametrize("query,marker", [("login=failed", "login-failed"), ("deleted=1", "deleted")])
def test_menu_notices(query, marker):
    assert f'data-notice="{marker}"' in render_menu("/?" + query, lb_enabled=True, lb_user=None)
    assert f'data-notice="{marker}"' not in render_menu("/", lb_enabled=True, lb_user=None)


# ---------- game pages ----------

@pytest.mark.parametrize("lang", ["es", "en"])
def test_guest_pages_are_not_leaderboard(lb_off, lang):
    html = app.app.test_client().get(f"/{lang}").get_data(as_text=True)
    assert "const LB = false;" in html
    assert 'id="c24-lb-state">null<' in html
    assert "data-lb-end" not in html
    assert "data-lb-hint" not in html  # leaderboard off: no hint


def test_leaderboard_game_page_renders_server_state():
    state = {"guesses": [{"word": "cosas", "colors": ["correct", "incorrect", "semicorrect", "incorrect", "incorrect"]}],
             "done": False, "won": False, "answer": None, "points": None, "rank": None}
    html = render_game("es", lb=True, lb_state=state, lb_enabled=True, lb_user=ME)
    assert "const LB = true;" in html
    assert 'const todays_word = "";' in html
    data = re.search(r'id="c24-lb-state">(.*?)</script>', html).group(1)
    assert json.loads(data) == state
    assert "data-lb-end" in html and "/leaderboard?tab=es" in html
    assert 'v-model="allow_any_word"' not in html  # no easy mode: the server checks every word


def test_guest_end_window_hint_only_when_enabled():
    assert "data-lb-hint" in render_game("es", lb_enabled=True, lb_user=None)
    assert "/auth/discord/login?next=" in render_game("es", lb_enabled=True, lb_user=None)
    assert 'href="/lb/en"' in render_game("en", lb_enabled=True, lb_user=ME)
    assert "data-lb-hint" not in render_game("de", lb_enabled=True, lb_user=None)  # es/en only
    assert "data-lb-hint" not in render_game("es", demo=True, lb_enabled=True, lb_user=None)


# ---------- /leaderboard page ----------

def test_leaderboard_page_table_and_me():
    rows = [row(1, "1", "alpha", 30), row(2, ME["id"], ME["username"], 20, is_me=True)]
    html = render("leaderboard.html", "/leaderboard?tab=es", tab="es", rows=rows, me_row=rows[1],
                  is_admin=False, lb_user=ME, lb_enabled=True)
    assert html.count('data-tab="') == 3
    assert re.search(r'class="c24-lb-tab is-active"\s+aria-current="page" data-tab="es"', html)
    assert "@alpha" in html and 'class="is-me"' in html
    assert "Jugador" in html  # Spanish tab, Spanish labels
    assert "data-lb-me" not in html  # already in the table
    assert 'action="/api/me/delete"' in html and "window.confirm" in html
    assert 'action="/auth/logout"' in html
    assert 'action="/admin/hide"' not in html
    assert "no vemos tu contraseña" in html


def test_leaderboard_page_admin_empty_and_outside_top():
    html = render("leaderboard.html", "/leaderboard?tab=en", tab="en", rows=[row(1, "1", "alpha", 30)],
                  me_row=row(77, ME["id"], ME["username"], 2, is_me=True), is_admin=True, lb_user=ME, lb_enabled=True)
    assert html.count('action="/admin/hide"') == 1 and 'name="discord_id" value="1"' in html
    assert "data-lb-me" in html and "#77" in html
    assert "Player" in html  # English tab
    empty = render("leaderboard.html", "/leaderboard", tab="all", rows=[], me_row=None,
                   is_admin=False, lb_user=None, lb_enabled=True)
    assert "data-lb-empty" in empty
    assert "/auth/discord/login?next=" in empty and "/api/me/delete" not in empty


def test_leaderboard_route_renders_empty(lb_on):
    if not has_route("/leaderboard"):
        pytest.skip("backend /leaderboard not there yet")
    r = app.app.test_client().get("/leaderboard?tab=es")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "data-lb-empty" in html
    for url in re.findall(r"""/static/[^"'\s)]*""", html):
        assert "?v=" in url, url


def test_menu_route_shows_choice_when_enabled(lb_on):
    if not has_route("/lb/<lang_code>"):
        pytest.skip("backend leaderboard routes not there yet")
    html = app.app.test_client().get("/").get_data(as_text=True)
    assert "data-lb-menu" in html and 'href="/leaderboard"' in html


# ---------- browser ----------

pw = pytest.importorskip("playwright")


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


BOARD_COLORED = "main .grid-cols-5 > .correct, main .grid-cols-5 > .semicorrect, main .grid-cols-5 > .incorrect"


def wait_reveal(page, rows=1):
    page.wait_for_function(
        f"document.querySelectorAll('{BOARD_COLORED}').length >= {5 * rows}"
        " && !document.querySelector('.flip')", timeout=6000)


def test_guest_game_has_no_js_errors(lb_off, server, page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(server + "/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    assert errors == []


def test_menu_mode_switch(server, page):
    html = render_menu(lb_enabled=True, lb_user=None)
    page.route(server + "/menu-lb", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.goto(server + "/menu-lb")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('[data-lang=es]')")
    assert page.get_attribute("a.c24-play[data-lang=es]", "href") == "/es"
    page.click("[data-mode=lb]")
    assert page.get_attribute("a.c24-play[data-lang=es]", "href") == "/auth/discord/login?next=%2Flb%2Fes"
    assert page.is_visible("[data-lb-privacy]")
    assert page.evaluate("localStorage.getItem('casa24_mode')") == "lb"
    page.reload()
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('[data-lang=es]')")
    assert page.get_attribute("a.c24-play[data-lang=en]", "href") == "/auth/discord/login?next=%2Flb%2Fen"


def test_leaderboard_game_flow(server, page):
    """Restore one guess from the server, a refused word, then a winning guess."""
    first = {"word": "cosas", "colors": ["incorrect", "semicorrect", "incorrect", "incorrect", "incorrect"]}
    state = {"guesses": [first], "done": False, "won": False, "answer": None, "points": None, "rank": None}
    html = render_game("es", lb=True, lb_state=state, lb_enabled=True, lb_user=ME)
    calls = []

    def api(route):
        body = json.loads(route.request.post_data)
        calls.append(body)
        if body["guess"] == "zzzzz":
            route.fulfill(status=400, content_type="application/json", body='{"error": "invalid_word"}')
        else:
            route.fulfill(content_type="application/json", body=json.dumps({
                "word": "jamón", "colors": ["correct"] * 5, "done": True, "won": True,
                "answer": "jamón", "points": 5, "rank": 3}))

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route(server + "/lb/es", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.route(server + "/api/guess", api)
    page.goto(server + "/lb/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    assert page.locator(BOARD_COLORED).count() == 5  # restored row
    assert "semicorrect" in page.get_attribute(".key[data-char=o]", "class")

    for c in "zzzzz":
        page.keyboard.press(c)
    page.keyboard.press("Enter")
    page.wait_for_selector("#app .fixed.top-0 p.font-bold")
    assert page.locator(BOARD_COLORED).count() == 5
    for _ in range(5):
        page.keyboard.press("Backspace")
    # the same word again is refused before any request
    for c in "cosas":
        page.keyboard.press(c)
    page.keyboard.press("Enter")
    assert len(calls) == 1
    for _ in range(5):
        page.keyboard.press("Backspace")

    for c in "jamon":
        page.keyboard.press(c)
    page.keyboard.press("Enter")
    wait_reveal(page, 2)
    assert calls[-1] == {"lang": "es", "guess": "jamon"}
    tiles = page.locator("main .grid-cols-5").nth(1).inner_text()
    assert "ó" in tiles.lower()  # server spelling shown
    page.wait_for_selector("[data-lb-end] .c24-lb-rank", state="visible", timeout=6000)
    assert "#3" in page.inner_text("[data-lb-end]")
    assert "+5" in page.inner_text("[data-lb-end]")
    # nothing about the leaderboard game is kept in the browser
    saved = page.evaluate("JSON.stringify(Object.assign({}, localStorage))")
    assert "jam" not in saved and '"es":[{' not in saved
    assert errors == []
