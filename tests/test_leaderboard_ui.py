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


DISCORD_PATH = "M20.317 4.3698"  # start of the official Discord logo path (simple-icons)
AVATAR_HASH = "a_" + "0123456789abcdef" * 2
DEFAULT_AVATAR = f"https://cdn.discordapp.com/embed/avatars/{(int(ME['id']) >> 22) % 6}.png"


def main_view(html):
    """The page without the privacy <dialog> and the <head> script."""
    body = html[html.index("<body"):]
    return body[:body.index('<dialog id="c24-privacy"')] if '<dialog id="c24-privacy"' in body else body


def test_menu_logged_out_shows_discord_button():
    html = render_menu(lb_enabled=True, lb_user=None)
    assert "data-dc-area" in html and "data-lb-menu" in html
    assert re.search(r'<a href="/auth/discord/login\?next=/lb/(es|en)" class="c24-dc-btn ', html)
    assert DISCORD_PATH in html
    assert "Entrar con Discord" in html and "Sign in with Discord" in html
    # trophy icon button to the leaderboard (no text link, no emoji)
    assert re.search(r'<a href="/leaderboard" class="c24-icon-btn" data-lb-trophy', html)
    assert "🏆" not in html and "Ver leaderboard</span></a>" not in html
    # no guest/leaderboard switch: cards play as guest, the button signs in
    assert "data-mode=" not in html and "data-guest-toggle" not in html
    # privacy only inside the (i) dialog, not in the main view
    assert "data-dc-privacy" in html and '<dialog id="c24-privacy"' in html
    assert "no vemos tu contraseña" in html and "no se suman al ranking" in html and "nunca tus palabras" in html
    assert "no vemos tu contraseña" not in main_view(html)
    assert "Discord handles your login" not in main_view(html)
    assert "/auth/logout" not in main_view(html) and "data-dc-toggle" not in main_view(html)  # logged out
    # Español and English are big cards (Vue); the old "Más idiomas" chips are gone
    assert "c24-chip" not in html and "Más idiomas" not in html and "more-languages" not in html


def test_menu_logged_in_shows_avatar_menu_and_guest_toggle():
    html = render_menu(lb_enabled=True, lb_user=ME)
    assert "@kolo_fan" in html
    assert "data-dc-toggle" in html and DEFAULT_AVATAR in html
    assert 'data-dc-id="100000000000000001"' in html
    assert re.search(r'<form method="post" action="/auth/logout" data-dc-clear>', html)
    assert "data-guest-toggle" in html
    assert "c24-dc-btn" not in main_view(html)  # no big sign-in button
    assert '"username":"kolo_fan"' in html  # handed to index.js
    assert '<script type="application/json" id="c24-dc-me">"100000000000000001"</script>' in html  # handed to the avatar script


@pytest.mark.parametrize("query,marker", [("login=failed", "login-failed"), ("login=cancelled", "login-cancelled"),
                                          ("deleted=1", "deleted")])
def test_menu_notices(query, marker):
    html = render_menu("/?" + query, lb_enabled=True, lb_user=None)
    assert f'data-notice="{marker}"' in html and "data-c24-toast" in html
    assert f'data-notice="{marker}"' not in render_menu("/", lb_enabled=True, lb_user=None)
    if marker == "login-cancelled":
        assert "Cancelaste el inicio de sesión con Discord." in html


# ---------- game pages ----------

@pytest.mark.parametrize("lang", ["es", "en"])
def test_guest_pages_are_not_leaderboard(lb_off, lang):
    html = app.app.test_client().get(f"/{lang}").get_data(as_text=True)
    assert '"lb":false' in html
    assert 'id="c24-lb-state">null<' in html
    assert "data-lb-end" not in html
    assert "data-lb-hint" not in html  # leaderboard off: no hint


def test_leaderboard_game_page_renders_server_state():
    state = {"guesses": [{"word": "cosas", "colors": ["correct", "incorrect", "semicorrect", "incorrect", "incorrect"]}],
             "done": False, "won": False, "answer": None, "points": None, "rank": None}
    html = render_game("es", lb=True, lb_state=state, lb_enabled=True, lb_user=ME)
    assert '"lb":true' in html
    assert '"todays_word":""' in html
    data = re.search(r'id="c24-lb-state">(.*?)</script>', html).group(1)
    assert json.loads(data) == state
    assert "data-lb-end" in html and "/leaderboard?tab=es" in html
    assert "data-dc-toggle" in html and "@kolo_fan" in html  # avatar menu in the header
    assert "🏆" not in html
    assert 'v-model="allow_any_word"' not in html  # no easy mode: the server checks every word


def test_guest_end_window_hint_only_when_enabled():
    assert "data-lb-hint" in render_game("es", lb_enabled=True, lb_user=None)
    out = render_game("es", lb_enabled=True, lb_user=None)
    assert "/auth/discord/login?next=" in out and "c24-dc-btn" in out and DISCORD_PATH in out
    assert 'href="/lb/en"' in render_game("en", lb_enabled=True, lb_user=ME)
    assert "data-lb-hint" in render_game("en", lb_enabled=True, lb_user=None)
    assert "data-lb-hint" not in render_game("es", demo=True, lb_enabled=True, lb_user=None)


# ---------- /leaderboard page ----------

def test_leaderboard_page_table_and_me():
    rows = [row(1, "1", "alpha", 30), row(2, ME["id"], ME["username"], 20, is_me=True)]
    html = render("leaderboard.html", "/leaderboard?tab=es", tab="es", rows=rows, me_row=rows[1],
                  is_admin=False, lb_user=ME, lb_enabled=True)
    assert html.count('data-tab="') == 3
    assert re.search(r'class="c24-lb-tab is-active"\s+aria-current="page" data-tab="es"', html)
    assert "@alpha" in html and 'class="is-me"' in html
    assert html.count('data-dc-id="') == 4  # header button + its menu + own row + profile line, nobody else
    assert "Jugador" in html  # Spanish tab, Spanish labels
    assert "data-lb-me" not in html  # already in the table
    assert 'action="/api/me/delete"' in html and "data-confirm=" in html and "confirm(" not in html  # in-page dialog (discord.js), never window.confirm
    assert 'action="/auth/logout"' in html
    assert 'action="/admin/hide"' not in html
    assert "no vemos tu contraseña" in html


# what app.py hands the page (lb_tabs): "all" (Combinado), then es, en
LB_TABS_ALL = [{"code": "all", "name_native": None}] + [
    {"code": c, "name_native": app.languages[c]["language_name_native"]} for c in app.language_codes]


def test_leaderboard_page_three_tabs():
    html = render("leaderboard.html", "/leaderboard?tab=en", tab="en", lb_tabs=LB_TABS_ALL, rows=[], me_row=None,
                  is_admin=False, lb_user=None, lb_enabled=True)
    tabs = re.findall(r'data-tab="([a-z]+)"', html)
    assert tabs == ["all", "es", "en"]
    assert re.search(r'class="c24-lb-tab is-active"\s+aria-current="page" data-tab="en"', html)
    assert 'href="/leaderboard?tab=es"' in html and "Español" in html and "English" in html
    assert "next=/leaderboard%3Ftab%3Den" in html  # sign-in comes back to this tab
    assert '<html lang="en">' in html and 'dir="rtl"' not in html
    # page text: the tab's language when its texts are passed
    es = render("leaderboard.html", "/leaderboard?tab=es", tab="es", lb_tabs=LB_TABS_ALL, rows=[], me_row=None,
                is_admin=False, lb_user=None, lb_enabled=True, texts={"es": {"lb_title": "Clasificación"}, "en": {}})
    assert '<html lang="es">' in es and "Clasificación" in es
    # unknown or removed tab → Combinado; no `tabs` from the backend → all/es/en
    for old in ("xx", "de", "ar"):
        bad = render("leaderboard.html", f"/leaderboard?tab={old}", tab=old, lb_tabs=LB_TABS_ALL, rows=[],
                     me_row=None, is_admin=False, lb_user=None, lb_enabled=True)
        assert re.search(r'class="c24-lb-tab is-active"\s+aria-current="page" data-tab="all"', bad)
    old = render("leaderboard.html", "/leaderboard?tab=es", tab="es", rows=[], me_row=None,
                 is_admin=False, lb_user=None, lb_enabled=True)
    assert re.findall(r'data-tab="([a-z]+)"', old) == ["all", "es", "en"]
    # a list without "all" still gets the Combinado tab, first
    no_all = render("leaderboard.html", "/leaderboard", tab="all", tabs=LB_TABS_ALL[1:], rows=[], me_row=None,
                    is_admin=False, lb_user=None, lb_enabled=True)
    assert re.findall(r'data-tab="([a-z]+)"', no_all)[0] == "all" and "Combinado" in no_all


@pytest.mark.parametrize("lang", ["es", "en"])
def test_leaderboard_game_page_any_language(lang):
    html = render_game(lang, lb=True, lb_state=None, lb_enabled=True, lb_user=ME)
    assert '"lb":true' in html and '"todays_word":""' in html
    assert 'id="c24-live"' in html and "data-live-open" in html and "data-live-faces" in html
    assert "data-lb-trophy" in html and "c24-badge-lb" not in html  # trophy is a header action (NYT-style bar)
    assert f"/leaderboard?tab={lang}" in html and "data-lb-end" in html
    assert "data-dc-toggle" in html and '<script type="application/json" id="c24-dc-me">"100000000000000001"</script>' in html  # avatar + its script
    assert "data-lb-hint" not in html  # the hint is only for guest games


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


def open_menu(server, page, html, path="/menu-lb", frag=""):
    page.route(server + path, lambda r: r.fulfill(body=html, content_type="text/html"))
    page.goto(server + path + frag)
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('[data-lang=es]')")


def test_menu_logged_out_cards_and_button(server, page):
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=None))
    page.evaluate("localStorage.setItem('casa24_lang', 'en')")
    page.reload()
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('[data-lang=es]')")
    assert page.get_attribute("a.c24-play[data-lang=es]", "href") == "/es"  # cards: guest
    assert page.get_attribute("[data-dc-area] .c24-dc-btn", "href") == "/auth/discord/login?next=%2Flb%2Fen"
    assert page.is_visible("[data-dc-area] .c24-dc-btn")
    assert page.inner_text("[data-dc-area] .c24-dc-btn").strip() == "Sign in with Discord"  # one language
    assert page.evaluate("getComputedStyle(document.querySelector('.c24-dc-btn')).backgroundColor") == "rgb(88, 101, 242)"
    # privacy dialog: opens from (i), closes with Esc
    page.click("[data-dc-area] [data-dc-privacy]")
    assert page.is_visible("#c24-privacy")
    assert "Discord handles your login" in page.inner_text("#c24-privacy")
    page.keyboard.press("Escape")
    assert not page.is_visible("#c24-privacy")


def test_menu_logged_in_cards_and_guest_toggle(server, page):
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=ME))
    assert page.get_attribute("a.c24-play[data-lang=es]", "href") == "/lb/es"
    page.click(".c24-guest-toggle")
    assert page.get_attribute("a.c24-play[data-lang=es]", "href") == "/es"
    assert page.evaluate("localStorage.getItem('casa24_mode')") == "guest"
    page.reload()
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('[data-lang=es]')")
    assert page.get_attribute("a.c24-play[data-lang=en]", "href") == "/en"
    assert page.is_checked("[data-guest-toggle]")


def card_info(page):
    return page.eval_on_selector_all(".c24-primary > .c24-play", """els => els.map(e => ({
        lang: e.dataset.lang || null, href: e.getAttribute('href'), cls: e.className, dir: e.getAttribute('dir'),
        status: (e.querySelector('.c24-play-status') || {}).textContent || '', h: e.getBoundingClientRect().height,
        trophy: !!e.querySelector('[data-lb-status] .c24-trophy')}))""")


def test_menu_two_big_cards_then_developer_view(server, page):
    page.set_viewport_size({"width": 390, "height": 844})
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=None, demo_enabled=True))
    cards = card_info(page)
    assert [c["lang"] for c in cards[:2]] in (["es", "en"], ["en", "es"])
    assert cards[-1]["lang"] is None and "c24-play-demo" in cards[-1]["cls"]  # Developer view last
    assert len(cards) == 3 and page.locator(".c24-chips, .c24-chip").count() == 0
    # both language cards are links to the guest game when logged out, no dir=rtl anywhere
    assert all(c["href"] == "/" + c["lang"] for c in cards[:2])
    assert all(c["dir"] is None for c in cards)
    # each card speaks its own language
    assert "Jugar" in next(c for c in cards if c["lang"] == "es")["status"]
    assert "Play" in next(c for c in cards if c["lang"] == "en")["status"]
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_menu_logged_in_every_card_goes_to_leaderboard(server, page):
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=ME))
    cards = card_info(page)
    assert len(cards) == 2
    for c in cards:
        assert c["href"] == "/lb/" + c["lang"] and c["trophy"], c
    page.click(".c24-guest-toggle")
    assert page.get_attribute("a.c24-play[data-lang=en]", "href") == "/en"
    assert page.get_attribute("a.c24-play[data-lang=es]", "href") == "/es"


def test_menu_sign_in_goes_to_last_language_played(server, page):
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=None))
    page.evaluate("localStorage.setItem('casa24_lang', 'en')")
    page.reload()
    page.wait_for_function("window.Vue && document.querySelector('[data-lang=en]')")
    assert page.get_attribute("[data-dc-area] .c24-dc-btn", "href") == "/auth/discord/login?next=%2Flb%2Fen"
    assert page.get_attribute("a.c24-play[data-lang=en]", "href") == "/en"  # logged out: guest
    # a removed language saved on the device is ignored
    page.evaluate("localStorage.setItem('casa24_lang', 'ko')")
    page.reload()
    page.wait_for_function("window.Vue && document.querySelector('[data-lang=en]')")
    assert "%2Flb%2Fko" not in page.get_attribute("[data-dc-area] .c24-dc-btn", "href")


def test_menu_avatar_from_fragment_menu_and_logout(server, page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.route("https://cdn.discordapp.com/**", lambda r: r.fulfill(status=200, content_type="image/png", body=b""))
    page.route(server + "/auth/logout", lambda r: r.fulfill(status=200, content_type="text/html", body="bye"))
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=ME), frag="#dc=" + AVATAR_HASH)
    assert page.evaluate("location.hash") == ""
    assert page.evaluate("location.pathname") == "/menu-lb"
    saved = json.loads(page.evaluate("localStorage.getItem('c24_dc_avatar')"))
    assert saved == {"id": ME["id"], "hash": AVATAR_HASH}
    src = page.get_attribute(".c24-dc-me img", "src")
    assert src == f"https://cdn.discordapp.com/avatars/{ME['id']}/{AVATAR_HASH}.png?size=64"
    # header menu: opens, Esc and an outside tap close it
    page.click("[data-dc-toggle]")
    assert page.is_visible("[data-dc-pop]") and page.get_attribute("[data-dc-toggle]", "aria-expanded") == "true"
    assert "@kolo_fan" in page.inner_text("[data-dc-pop]")
    page.keyboard.press("Escape")
    assert not page.is_visible("[data-dc-pop]")
    page.click("[data-dc-toggle]")
    page.mouse.click(5, 400)
    assert not page.is_visible("[data-dc-pop]")
    # an invalid fragment changes nothing (and is removed)
    page.goto("about:blank")
    page.goto(server + "/menu-lb#dc=../../evil")
    page.wait_for_function("window.Vue && document.querySelector('[data-lang=es]')")
    assert page.evaluate("location.hash") == ""
    assert json.loads(page.evaluate("localStorage.getItem('c24_dc_avatar')"))["hash"] == AVATAR_HASH
    # log out forgets the picture
    page.click("[data-dc-toggle]")
    page.click("[data-dc-logout]")
    page.wait_for_url(server + "/auth/logout")
    assert page.evaluate("localStorage.getItem('c24_dc_avatar')") is None
    assert errors == []


def test_avatar_of_someone_else_is_not_used(server, page):
    page.route("https://cdn.discordapp.com/**", lambda r: r.fulfill(status=200, content_type="image/png", body=b""))
    open_menu(server, page, render_menu(lb_enabled=True, lb_user=ME))
    page.evaluate("localStorage.setItem('c24_dc_avatar', JSON.stringify({id: '999', hash: '%s'}))" % AVATAR_HASH)
    page.reload()
    page.wait_for_function("window.Vue && document.querySelector('[data-lang=es]')")
    assert page.get_attribute(".c24-dc-me img", "src") == DEFAULT_AVATAR


def boxes_overlap(a, b):
    return not (a["x"] + a["width"] <= b["x"] + 0.5 or b["x"] + b["width"] <= a["x"] + 0.5
                or a["y"] + a["height"] <= b["y"] + 0.5 or b["y"] + b["height"] <= a["y"] + 0.5)


HEADER_BOXES = """() => [...document.querySelectorAll('header.c24-header > .c24-header-side > *, header.c24-header .c24-header-title a')]
    .filter(e => e.getClientRects().length && getComputedStyle(e).display !== 'none')
    .map(e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height, n: e.className}; })"""


@pytest.mark.parametrize("width,height", [(320, 568), (390, 844), (430, 932), (768, 1024)])
@pytest.mark.parametrize("user", [None, ME])
def test_menu_layout_no_overlap(server, page, width, height, user):
    page.set_viewport_size({"width": width, "height": height})
    open_menu(server, page, render_menu("/?login=cancelled", lb_enabled=True, lb_user=user))
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    boxes = page.evaluate(HEADER_BOXES)
    assert len(boxes) >= 5
    for i, a in enumerate(boxes):
        assert a["x"] >= 0 and a["x"] + a["width"] <= width + 0.5, a
        for b in boxes[i + 1:]:
            assert not boxes_overlap(a, b), (a, b)
    # the title's text fits inside its own box (an overflow would run under the icons)
    assert page.evaluate("(() => { const a = document.querySelector('.c24-header-title a');"
                         " return a.scrollWidth <= a.clientWidth + 1; })()")
    area = page.locator("[data-dc-area]").bounding_box()
    card = page.locator("a.c24-play").first.bounding_box()
    assert area["y"] + area["height"] <= card["y"]
    if user:
        page.click("[data-dc-toggle]")
        pop = page.locator("[data-dc-pop]").bounding_box()
        assert pop["x"] >= 0 and pop["x"] + pop["width"] <= width
        btn = page.locator("[data-dc-toggle]").bounding_box()
        assert pop["y"] >= btn["y"] + btn["height"]  # never covers its own button


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
    assert calls[-1] == {"lang": "es", "guess": "jamon", "attempt": 1}
    tiles = page.locator("main .grid-cols-5").nth(1).inner_text()
    assert "ó" in tiles.lower()  # server spelling shown
    page.wait_for_selector("[data-lb-end] .c24-lb-rank", state="visible", timeout=6000)
    assert "#3" in page.inner_text("[data-lb-end]")
    assert "+5" in page.inner_text("[data-lb-end]")
    # nothing about the leaderboard game is kept in the browser
    saved = page.evaluate("JSON.stringify(Object.assign({}, localStorage))")
    assert "jam" not in saved and '"es":[{' not in saved
    assert errors == []


# ---------- live view: who else plays today (colors only) ----------

from lb_testlib import client, discord, lb_env, login, mem, today  # noqa: E402,F401 (fixtures)

C, S, I = "correct", "semicorrect", "incorrect"
# Words that must never show up: one player's payload is stuffed with letters
# (as if the server misbehaved); the page only ever draws colors.
LEAKY_WORDS = ["perro", "gatos", "jamon", "jamón", "cosas", "pizza"]
LIVE_PLAYERS = [
    {"username": "dj_montuno", "avatar_url": "https://cdn.discordapp.com/avatars/123/" + "ab" * 16 + ".png?size=64",
     "rows": [[I, S, I, I, I], [C, C, C, I, C]], "done": False, "won": False, "live": True},
    {"username": "heisen", "avatar_url": "https://cdn.discordapp.com/embed/avatars/2.png",
     "rows": [[I, I, S, I, I], [C] * 5], "done": True, "won": True, "live": False},
    {"username": "sneaky", "avatar_url": "https://evil.example/track.png",
     "rows": [list("perro"), ["gatos", C, "jamón", S, I], "cosas"], "word": "pizza", "answer": "jamon",
     "guesses": ["perro", "gatos"], "done": True, "won": False, "live": False},
    {"username": "una_persona_con_nombre_larguisimo", "avatar_url": "https://cdn.discordapp.com/embed/avatars/3.png",
     "rows": [], "done": False, "won": False, "live": True},
] + [{"username": f"player{i}", "avatar_url": "https://cdn.discordapp.com/embed/avatars/1.png",
      "rows": [[I, S, I, C, I]], "done": False, "won": False, "live": False} for i in range(6)]

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cff01f0005010201a0e2d2b80000000049454e44ae426082")


def test_lb_game_renders_live_view():
    html = render_game("es", lb=True, lb_state=None, lb_enabled=True, lb_user=ME)
    assert 'id="c24-live"' in html and "data-live-open" in html
    assert "Jugando hoy" in html and "Nadie más está jugando ahora" in html
    assert 'referrerpolicy="no-referrer"' in html and 'loading="lazy"' in html
    assert "Ver quién está jugando hoy" in html  # people button label


@pytest.mark.parametrize("lang", ["es", "en"])
def test_guest_game_has_no_live_view(lb_off, lang):
    html = app.app.test_client().get(f"/{lang}").get_data(as_text=True)
    assert 'id="c24-live"' not in html and "data-live-open" not in html


def test_guest_game_has_no_live_view_when_enabled(lb_env, client, discord):
    login(client, discord)
    html = client.get("/es").get_data(as_text=True)
    assert '"lb":false' in html
    assert 'id="c24-live"' not in html and "data-live-open" not in html


def test_lb_route_renders_live_view(lb_env, client, discord):
    login(client, discord)
    r = client.get("/lb/en")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="c24-live"' in html and "data-live-open" in html
    assert "Playing today" in html


def test_live_text_keys_in_es_and_en():
    for lang in ("es", "en"):
        text = app.Language(lang, app.language_codes_5words[lang]).config["text"]
        for key in ("lb_live_title", "lb_live_empty", "lb_live_now", "lb_live_open", "lb_live_won", "lb_live_lost"):
            assert text.get(key, "").strip(), (lang, key)


def open_lb(server, page, players=LIVE_PLAYERS, status=200, calls=None, errors=None):
    """The leaderboard game page with a faked /api/live; returns the list of /api/live calls."""
    html = render_game("es", lb=True, lb_state=None, lb_enabled=True, lb_user=ME)
    calls = [] if calls is None else calls
    if errors is not None:
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))

    def live(route):
        calls.append(route.request.url)
        current = status() if callable(status) else status
        body = {"players": players, "count": len(players)} if current == 200 else {"error": "rate" if current == 429 else "login"}
        route.fulfill(status=current, content_type="application/json", body=json.dumps(body))

    page.route("https://cdn.discordapp.com/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG_1PX))
    page.route(server + "/lb/es", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.route(server + "/api/live?**", live)
    page.goto(server + "/lb/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    return calls


def live_text_has_no_words(page):
    text = page.evaluate("document.body.innerText").lower()
    live_html = page.inner_html("#c24-live").lower()
    for w in LEAKY_WORDS:
        assert w not in text and w not in live_html, w
    # the mini boards are empty squares: no text inside them at all
    assert page.evaluate("[...document.querySelectorAll('.c24-live-grid')].map(g => g.textContent.trim()).join('')") == ""


def test_live_sidebar_on_desktop(server, page):
    errors = []
    page.set_viewport_size({"width": 1366, "height": 768})
    calls = open_lb(server, page, errors=errors)
    page.wait_for_selector(".c24-live-card")
    assert calls and calls[0].endswith("/api/live?lang=es")
    assert page.is_visible("#c24-live") and not page.is_visible("[data-live-open]")
    assert page.locator(".c24-live-card").count() == len(LIVE_PLAYERS)
    assert page.locator(".c24-live-grid").first.locator("span").count() == 30
    first = page.locator(".c24-live-card").first
    # NYT-style card: only the avatar and the mini board show; name and status are its accessible name
    assert first.get_attribute("title") == "@dj_montuno"
    assert page.get_by_role("listitem", name="@dj_montuno, en vivo").count() == 1
    assert page.get_by_role("listitem", name="@heisen, ganó").count() == 1
    assert page.get_by_role("listitem", name="@sneaky, perdió").count() == 1
    assert first.locator(".c24-live-info").bounding_box()["width"] <= 1  # visually hidden
    assert page.locator(".c24-live-dot").count() == 0
    assert page.locator(".c24-live-head").bounding_box()["width"] <= 1  # heading kept for screen readers only
    assert page.get_by_role("complementary", name=re.compile("^Jugando hoy")).count() == 1
    assert first.locator(".is-correct").count() == 4 and first.locator(".is-semicorrect").count() == 1
    img = first.locator("img")
    assert img.get_attribute("referrerpolicy") == "no-referrer" and img.get_attribute("alt") == ""
    # a URL that isn't Discord's CDN is never loaded
    srcs = page.eval_on_selector_all(".c24-live-avatar", "els => els.map(e => e.getAttribute('src'))")
    assert all(s.startswith("https://cdn.discordapp.com/") for s in srcs)
    # the stuffed player shows only colors (unknown values = empty squares)
    sneaky = page.locator(".c24-live-card").nth(2)
    assert sneaky.locator(".is-empty").count() == 27  # only C, S, I of row 2 are colors
    live_text_has_no_words(page)
    # the sidebar never covers the game
    side = page.locator("#c24-live").bounding_box()
    for sel in (".c24-board", ".c24-keyboard", "header.c24-header"):
        assert not boxes_overlap(side, page.locator(sel).bounding_box()), sel
    assert errors == []


def test_live_sheet_on_phone(server, page):
    errors = []
    page.set_viewport_size({"width": 390, "height": 844})
    open_lb(server, page, errors=errors)
    page.wait_for_selector("[data-live-open] .c24-live-badge")
    assert page.inner_text("[data-live-open] .c24-live-badge") == str(len(LIVE_PLAYERS))
    assert not page.is_visible("#c24-live")
    # opens and closes with ×, Esc and a tap outside
    page.click("[data-live-open]")
    assert page.is_visible("#c24-live") and page.get_attribute("[data-live-open]", "aria-expanded") == "true"
    sheet = page.locator("#c24-live").bounding_box()
    assert sheet["y"] >= 0 and sheet["y"] + sheet["height"] <= 844 + 0.5 and sheet["width"] <= 390
    live_text_has_no_words(page)
    page.click("[data-live-close]")
    assert not page.is_visible("#c24-live")
    page.click("[data-live-open]")
    page.keyboard.press("Escape")
    assert not page.is_visible("#c24-live")
    page.click("[data-live-open]")
    page.mouse.click(195, 30)  # the backdrop, above the sheet
    assert not page.is_visible("#c24-live")
    # typing still goes to the board after closing
    page.keyboard.press("c")
    assert page.locator("main .grid-cols-5 > div").first.inner_text().strip().lower() == "c"
    assert errors == []


def test_live_empty_state(server, page):
    page.set_viewport_size({"width": 390, "height": 844})
    open_lb(server, page, players=[])
    page.click("[data-live-open]")
    page.wait_for_selector(".c24-live-empty", state="visible")
    assert "Nadie más está jugando ahora" in page.inner_text("#c24-live")
    assert page.locator("[data-live-open] .c24-live-badge").count() == 0


def test_live_polling_pauses_when_hidden_and_backs_off(server, page):
    page.clock.install()
    state = {"status": 200}
    calls = open_lb(server, page, status=lambda: state["status"])
    page.wait_for_selector(".c24-live-card", state="attached")
    assert len(calls) == 1

    def advance(ms):
        page.clock.run_for(ms)
        page.wait_for_timeout(150)  # let the faked response arrive

    advance(8100)
    assert len(calls) == 2
    # hidden tab: no requests at all
    page.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
                             document.dispatchEvent(new Event('visibilitychange')); }""")
    advance(60000)
    assert len(calls) == 2
    # visible again: asks right away
    page.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
                             document.dispatchEvent(new Event('visibilitychange')); }""")
    page.wait_for_timeout(150)
    assert len(calls) == 3
    # 429: the wait doubles (16 s), then success brings it back to 8 s
    state["status"] = 429
    advance(8100)
    assert len(calls) == 4
    advance(8100)
    assert len(calls) == 4
    state["status"] = 200
    advance(8000)
    assert len(calls) == 5
    advance(8100)
    assert len(calls) == 6
    # logged out (401): polling stops
    state["status"] = 401
    advance(8100)
    assert len(calls) == 7
    advance(120000)
    assert len(calls) == 7


LIVE_SIZES = [(320, 568), (390, 844), (844, 390), (768, 1024), (860, 600), (1024, 768), (1366, 768), (1920, 1080)]


@pytest.mark.parametrize("width,height", LIVE_SIZES)
def test_live_layout_fits_without_overlap(server, page, width, height):
    errors = []
    page.set_viewport_size({"width": width, "height": height})
    open_lb(server, page, errors=errors)
    page.wait_for_selector(".c24-live-card", state="attached")
    page.wait_for_timeout(100)
    assert page.evaluate("document.documentElement.scrollHeight") <= height
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    boxes = page.evaluate(HEADER_BOXES)
    for i, a in enumerate(boxes):
        assert a["x"] >= 0 and a["x"] + a["width"] <= width + 0.5, a
        for b in boxes[i + 1:]:
            assert not boxes_overlap(a, b), (a, b)
    board = page.locator(".c24-board").bounding_box()
    keys = page.locator(".c24-keyboard").bounding_box()
    assert board["y"] >= 0 and board["y"] + board["height"] <= height + 0.5
    assert keys["y"] + keys["height"] <= height + 0.5
    sidebar = width >= 860 and height > 500
    assert page.is_visible("#c24-live") == sidebar
    assert page.is_visible("[data-live-open]") == (not sidebar)
    if sidebar:
        side = page.locator("#c24-live").bounding_box()
        for other in (board, keys, page.locator("header.c24-header").bounding_box()):
            assert not boxes_overlap(side, other)
    else:
        page.click("[data-live-open]")
        sheet = page.locator("#c24-live").bounding_box()
        assert sheet["y"] >= 0 and sheet["y"] + sheet["height"] <= height + 0.5
        assert sheet["x"] >= 0 and sheet["x"] + sheet["width"] <= width + 0.5
        page.keyboard.press("Escape")
    assert errors == []


def open_lb_mobile(browser, server, players=LIVE_PLAYERS, lang="es", width=390, height=844):
    ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=True, has_touch=True,
                              device_scale_factor=2)
    page = ctx.new_page()
    html = render_game(lang, lb=True, lb_state=None, lb_enabled=True, lb_user=ME)
    page.route("https://cdn.discordapp.com/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG_1PX))
    page.route(server + "/lb/" + lang, lambda r: r.fulfill(body=html, content_type="text/html"))
    page.route(server + "/api/live?**", lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps({"players": players, "count": len(players)})))
    page.goto(server + "/lb/" + lang)
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    return ctx, page


def test_live_facepile_on_phone_opens_sheet_with_loaded_avatars(browser, server):
    ctx, page = open_lb_mobile(browser, server)
    try:
        page.wait_for_selector("[data-live-faces] img")
        faces = page.locator("[data-live-faces] img")
        assert faces.count() == 3  # up to 3 faces + the count
        assert page.inner_text("[data-live-open] .c24-live-badge") == str(len(LIVE_PLAYERS))
        btn = page.locator("[data-live-open]").bounding_box()
        assert btn["height"] >= 44 and btn["width"] >= 44
        page.wait_for_function("[...document.querySelectorAll('[data-live-faces] img')].every(i => i.complete && i.naturalWidth > 0)")
        page.locator("[data-live-faces]").tap()
        assert page.is_visible("#c24-live")
        page.wait_for_function("[...document.querySelectorAll('#c24-live .c24-live-avatar')].length > 0")
        # the sheet's avatars actually load (images in view; lazy ones further down may wait)
        page.wait_for_function("""[...document.querySelectorAll('#c24-live .c24-live-avatar')].slice(0, 4)
            .every(i => i.complete && i.naturalWidth > 0)""")
    finally:
        ctx.close()


def test_live_people_icon_when_nobody_plays(browser, server):
    ctx, page = open_lb_mobile(browser, server, players=[])
    try:
        page.wait_for_function("document.querySelector('[data-live-open] svg')")
        page.wait_for_timeout(200)
        assert page.locator("[data-live-faces]").count() == 0
        assert page.locator("[data-live-open] svg").is_visible()
    finally:
        ctx.close()


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize("width,height", [(320, 568), (360, 740), (390, 844)])
def test_live_facepile_header_fits(browser, server, lang, width, height):
    ctx, page = open_lb_mobile(browser, server, lang=lang, width=width, height=height)
    try:
        page.wait_for_selector("[data-live-faces] img")
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        boxes = page.evaluate(HEADER_BOXES)
        for i, a in enumerate(boxes):
            assert a["x"] >= 0 and a["x"] + a["width"] <= width + 0.5, a
            for b in boxes[i + 1:]:
                assert not boxes_overlap(a, b), (a, b)
        # Kolo and the language badge stay visible inside the brand (left); the trophy is an action (right)
        title = page.locator("header .c24-header-title").bounding_box()
        for sel in ("header .c24-logo", "header .c24-badge"):
            box = page.locator(sel).bounding_box()
            assert box and box["width"] > 0, sel
            assert box["x"] >= title["x"] - 0.5 and box["x"] + box["width"] <= title["x"] + title["width"] + 0.5, sel
        trophy = page.locator("header [data-lb-trophy]").bounding_box()
        assert trophy and trophy["x"] >= title["x"] + title["width"] - 0.5
    finally:
        ctx.close()
