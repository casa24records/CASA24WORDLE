"""Game layout (NYT-style structure, Casa 24 look), web and Discord Activity.

One game.html + style.css for both. Checked at phone, landscape, desktop and
Discord desktop sizes:
  - no vertical page scroll; header, board and keyboard never overlap
  - square tiles; keys at least 26px wide (10-key rows fit at 320px)
  - the header's actions never cover the brand (Kolo + badge always visible)
  - the "Jugando hoy" rail sits in the left gutter: showing it never moves or
    shrinks the board
  - accessibility basics: board grid, spoken names for ⇨/⌫, focus order
Pages are rendered from the templates and served over a real local server
(the pattern of test_leaderboard_ui.py); /api/live is faked.
"""

import json
import re
import threading

import flask
import pytest
from werkzeug.serving import make_server

import app

pytest.importorskip("playwright")

ME = {"id": "100000000000000001", "username": "kolo_fan"}
C, S, I = "correct", "semicorrect", "incorrect"
PLAYERS = [
    {"username": "dj_montuno", "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png",
     "rows": [[I, S, I, I, I], [C, C, C, I, C]], "done": False, "won": False, "live": True},
    {"username": "heisen", "avatar_url": "https://cdn.discordapp.com/embed/avatars/2.png",
     "rows": [[I, I, S, I, I], [C] * 5], "done": True, "won": True, "live": False},
    {"username": "una_persona_con_nombre_larguisimo", "avatar_url": "https://cdn.discordapp.com/embed/avatars/3.png",
     "rows": [[I] * 5], "done": True, "won": False, "live": True},
]
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cff01f0005010201a0e2d2b80000000049454e44ae426082")


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def render_game(variant, lang="es"):
    """guest = /es with the leaderboard on; lb = /lb/es logged in; act = /lb/es?embed=1 in Discord."""
    language = app.Language(lang, app.language_codes_5words[lang])
    ctx = dict(language=language, demo=False)
    if variant == "guest":
        ctx.update(lb_enabled=True, lb_user=None)
    else:
        language.daily_word = ""
        ctx.update(lb=True, lb_state=None, lb_enabled=True, lb_user=ME)
    if variant == "act":
        ctx.update(C24_ACTIVITY=True, activity_client_id="123", activity_params=[],
                   activity_langs=[{"code": c, "name_native": app.language_configs[c]["name_native"]}
                                   for c in ("es", "en")])
    with app.app.test_request_context("/" + lang):
        return flask.render_template("game.html", **ctx)


def open_game(page, server, variant, players=PLAYERS, platform="desktop"):
    html = render_game(variant)
    page.route("https://cdn.discordapp.com/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG_1PX))
    page.route(server + "/game", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.route(server + "/api/live?**", lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps({"players": players, "count": len(players)})))
    if variant == "act":
        # what the Activity shell passes to the game (discord-activity.js copies it onto <html>)
        page.add_init_script("document.documentElement.classList.add('c24-plat-%s')" % platform)
    page.goto(server + "/game")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    if variant == "act":
        # outside the real shell the bridge can't log in: hide its overlay to measure the game
        page.evaluate("document.getElementById('c24-activity-overlay').dataset.state = 'ready'")
    page.wait_for_timeout(150)


MEASURE = """() => {
  const vis = e => e && e.getClientRects().length && getComputedStyle(e).display !== 'none';
  const R = e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; };
  const keys = [...document.querySelectorAll('.c24-keyboard .key')].map(R);
  return {
    scrollH: document.documentElement.scrollHeight, scrollW: document.documentElement.scrollWidth,
    header: R(document.querySelector('header.c24-header')),
    brand: R(document.querySelector('header .c24-header-title > a, header .c24-lang-btn')),
    brandOverflow: (() => { const b = document.querySelector('header .c24-header-title > a, header .c24-lang-btn');
                            return b.scrollWidth - b.clientWidth; })(),
    logo: R(document.querySelector('header .c24-logo')),
    badge: R(document.querySelector('header .c24-badge')),
    actions: [...document.querySelectorAll('header .c24-header-end > *')].filter(vis).map(R),
    board: R(document.querySelector('.c24-board')),
    keyboard: R(document.querySelector('.c24-keyboard')),
    tiles: [...document.querySelectorAll('main .grid-cols-5 > div')].map(R),
    keys,
    rail: vis(document.querySelector('#c24-live')) ? R(document.querySelector('#c24-live')) : null,
  };
}"""


def overlap(a, b):
    return a["x"] < b["x"] + b["width"] - 0.5 and b["x"] < a["x"] + a["width"] - 0.5 \
        and a["y"] < b["y"] + b["height"] - 0.5 and b["y"] < a["y"] + a["height"] - 0.5


def check_layout(m, width, height):
    size = f"{width}x{height}"
    assert m["scrollH"] <= height + 1, size
    assert m["scrollW"] <= width, size
    # header, board, keyboard: all on screen, none on top of another
    for name in ("header", "board", "keyboard"):
        box = m[name]
        assert box["y"] >= -0.5 and box["y"] + box["height"] <= height + 1, (size, name)
    assert not overlap(m["header"], m["board"]), size
    assert not overlap(m["header"], m["keyboard"]), size
    assert not overlap(m["board"], m["keyboard"]), size
    # square tiles, keys wide enough
    for t in m["tiles"]:
        assert abs(t["width"] - t["height"]) <= 1, (size, t)
    assert min(k["width"] for k in m["keys"]) >= 26, size
    assert len(m["keys"]) == 29  # QWERTY + ñ, ⇨ and ⌫ (3 rows)
    # header: Kolo and the badge stay; the actions never cover the brand or leave the screen
    for name in ("logo", "badge"):
        assert m[name]["width"] > 0, (size, name)
    assert m["brandOverflow"] <= 0, size
    brand_right = m["brand"]["x"] + m["brand"]["width"]
    for a in m["actions"]:
        assert a["x"] >= brand_right - 0.5, (size, a)
        assert a["x"] + a["width"] <= width + 0.5, (size, a)
        assert a["height"] >= 40, (size, a)
    for i, a in enumerate(m["actions"]):
        for b in m["actions"][i + 1:]:
            assert not overlap(a, b), size
    if m["rail"]:
        for name in ("header", "board", "keyboard"):
            assert not overlap(m["rail"], m[name]), (size, name)


WEB_SIZES = [(320, 568), (390, 844), (844, 390), (1366, 768)]


@pytest.mark.parametrize("width,height", WEB_SIZES)
@pytest.mark.parametrize("variant", ["guest", "lb"])
def test_web_game_fits_without_overlap(server, page, variant, width, height):
    page.set_viewport_size({"width": width, "height": height})
    open_game(page, server, variant)
    m = page.evaluate(MEASURE)
    check_layout(m, width, height)
    if variant == "lb":
        assert (m["rail"] is not None) == (width >= 1024 and height > 500)
        assert page.is_visible("[data-live-open]") == (m["rail"] is None)


@pytest.mark.parametrize("width,height", [(320, 568), (360, 740), (390, 844)])
def test_phone_header_with_facepile_fits(browser, server, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        open_game(page, server, "lb")
        page.wait_for_selector("[data-live-faces] img")
        check_layout(page.evaluate(MEASURE), width, height)
        btn = page.locator("[data-live-open]").bounding_box()
        assert btn["height"] >= 44 and btn["width"] >= 40
    finally:
        ctx.close()


@pytest.mark.parametrize("width,height", [(640, 360), (400, 700), (875, 400), (1280, 600)])
def test_activity_desktop_fits_without_overlap(server, page, width, height):
    page.set_viewport_size({"width": width, "height": height})
    open_game(page, server, "act")
    m = page.evaluate(MEASURE)
    check_layout(m, width, height)
    # Discord desktop: always stacked (board above keyboard)
    assert m["keyboard"]["y"] >= m["board"]["y"] + m["board"]["height"] - 0.5
    assert min(t["width"] for t in m["tiles"]) >= 28
    assert (m["rail"] is not None) == (width >= 860)
    if m["rail"]:
        # the column stays centered in the panel; the rail lives in the left gutter
        col = page.locator(".c24-game").bounding_box()
        assert abs((col["x"] + col["width"] / 2) - width / 2) <= 2
        assert m["rail"]["x"] + m["rail"]["width"] <= col["x"] + 0.5
        assert page.is_visible("[data-live-invite]")


def test_activity_phone_keeps_bottom_sheet(browser, server):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        open_game(page, server, "act", platform="mobile")
        m = page.evaluate(MEASURE)
        check_layout(m, 390, 844)
        assert m["rail"] is None and page.is_visible("[data-live-open]")
        page.click("[data-live-open]")
        assert page.is_visible("#c24-live") and page.is_visible("[data-live-invite]")
    finally:
        ctx.close()


@pytest.mark.parametrize("variant,width,height", [("lb", 1366, 768), ("lb", 1920, 1080), ("act", 1000, 450)])
def test_rail_never_moves_or_shrinks_the_board(server, page, variant, width, height):
    page.set_viewport_size({"width": width, "height": height})
    open_game(page, server, variant)
    if variant == "lb":
        page.wait_for_selector(".c24-live-card")  # (in the Activity /api/live goes through the shell)
    assert page.is_visible("#c24-live")
    with_rail = page.locator(".c24-board").bounding_box()
    keys_with = page.locator(".c24-keyboard").bounding_box()
    page.evaluate("document.getElementById('c24-live').style.setProperty('display', 'none', 'important')")
    without = page.locator(".c24-board").bounding_box()
    keys_without = page.locator(".c24-keyboard").bounding_box()
    assert with_rail == without and keys_with == keys_without
    # and it matches the guest game, which has no rail at all
    if variant == "lb":
        guest = page.context.new_page()
        guest.set_viewport_size({"width": width, "height": height})
        open_game(guest, server, "guest")
        g = guest.locator(".c24-board").bounding_box()
        assert abs(g["x"] - with_rail["x"]) <= 0.5 and abs(g["width"] - with_rail["width"]) <= 0.5
        guest.close()


def test_rail_shows_cards_even_with_nobody_playing(server, page):
    page.set_viewport_size({"width": 1366, "height": 768})
    open_game(page, server, "lb", players=[])
    page.wait_for_selector(".c24-live-empty", state="visible")
    assert page.is_visible("#c24-live") and page.locator(".c24-live-card").count() == 0
    assert page.locator("[data-live-invite]").count() == 0  # the invite card is Discord only


def test_board_size_is_reserved_before_vue(server, page):
    """No layout shift: the board and keyboard have their final size from CSS alone."""
    html = render_game("guest")
    page.set_viewport_size({"width": 390, "height": 844})
    page.route("**/static/vendor/vue.global.prod.js*", lambda r: r.fulfill(body="", content_type="text/javascript"))
    page.route("**/static/game.js*", lambda r: r.fulfill(body="", content_type="text/javascript"))
    page.route(server + "/game", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.goto(server + "/game")
    before = page.evaluate(MEASURE)
    page.unroute("**/static/vendor/vue.global.prod.js*")
    page.unroute("**/static/game.js*")
    page.goto(server + "/game")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    page.wait_for_timeout(150)
    after = page.evaluate(MEASURE)
    assert before["board"] == after["board"] and before["keyboard"] == after["keyboard"]


def test_accessibility_basics():
    html = render_game("lb")
    assert re.search(r'<div class="c24-board" role="grid" aria-label="[^"]+">', html)
    assert html.count('role="row"') == 6 and html.count('role="gridcell"') == 30
    enter = re.search(r'<button[^>]*data-char="⇨"[^>]*>', html, re.S).group(0)
    back = re.search(r'<button[^>]*data-char="⌫"[^>]*>', html, re.S).group(0)
    assert 'aria-label="⇨"' not in enter and re.search(r'aria-label="[^"⇨]+"', enter)
    assert 'aria-label="⌫"' not in back and re.search(r'aria-label="[^"⌫]+"', back)
    # every icon-only header button or link has a name
    header = re.search(r"<header.*?</header>", html, re.S).group(0)
    for tag in re.findall(r"""<(?:button|a)\b(?:[^>"']|"[^"]*"|'[^']*')*>""", header):
        if "c24-icon-btn" in tag:  # icon-only buttons need a name (the brand and menu items have text)
            assert "aria-label=" in tag, tag
    # no right-to-left leftovers
    assert "right_to_left" not in html and 'dir="rtl"' not in html
    # the page data carries the keyboard's letters for game.js
    data = json.loads(re.search(r'<script type="application/json" id="c24-data">(.*?)</script>', html, re.S).group(1))
    assert data["input_characters"]


def test_focus_order_brand_actions_board_keyboard(server, page):
    page.set_viewport_size({"width": 1366, "height": 768})
    open_game(page, server, "lb")
    order = page.evaluate("""() => {
        const all = [...document.querySelectorAll('a[href], button, [tabindex]')]
            .filter(e => e.getClientRects().length && !e.closest('[v-cloak], .c24-modal-wrap, #c24-live'));
        const where = e => e.closest('.c24-header-title') ? 'brand' : e.closest('header') ? 'actions'
            : e.closest('.c24-keyboard') ? 'keyboard' : 'other';
        return all.map(where);
    }""")
    seen = [x for i, x in enumerate(order) if i == 0 or order[i - 1] != x]
    assert seen[:3] == ["brand", "actions", "keyboard"], seen
    assert page.evaluate("getComputedStyle(document.querySelector('.key')).touchAction") == "manipulation"
    page.keyboard.press("Tab")
    assert page.evaluate("!!document.activeElement.closest('.c24-header-title')")
    page.keyboard.press("Tab")
    ring = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    assert ring == "solid"


def test_settings_keeps_keyboard_layout_choice_and_fits(server, page):
    page.set_viewport_size({"width": 320, "height": 568})
    open_game(page, server, "guest")
    page.click("header [aria-label='Ajustes'], header .c24-header-end .c24-icon-btn:last-child")
    page.wait_for_selector("#keyboard-layout-select", state="visible")
    assert page.locator("#keyboard-layout-select option").count() >= 2
    assert page.locator("#right_to_left").count() == 0
    sel = page.locator("#keyboard-layout-select").bounding_box()
    modal = page.locator("[aria-labelledby='settings-title']").bounding_box()
    assert sel["x"] + sel["width"] <= modal["x"] + modal["width"] + 0.5


@pytest.mark.parametrize("width", [320, 390, 768])
def test_leaderboard_page_tabs_one_row(server, page, width):
    tabs = [{"code": "all", "name_native": None}] + [
        {"code": c, "name_native": app.language_configs[c]["name_native"]} for c in ("es", "en")]
    with app.app.test_request_context("/leaderboard?tab=es"):
        html = flask.render_template("leaderboard.html", tab="es", lb_tabs=tabs, rows=[], me_row=None,
                                     is_admin=False, lb_user=None, lb_enabled=True)
    page.set_viewport_size({"width": width, "height": 800})
    page.route(server + "/board", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.goto(server + "/board")
    boxes = page.eval_on_selector_all(".c24-lb-tab", "els => els.map(e => { const r = e.getBoundingClientRect();"
                                      " return {x: r.x, y: r.y, width: r.width, height: r.height}; })")
    assert len(boxes) == 3
    assert len({round(b["y"]) for b in boxes}) == 1  # one row
    assert all(b["height"] >= 44 and b["x"] >= 0 and b["x"] + b["width"] <= width for b in boxes)
    assert page.evaluate("document.documentElement.scrollWidth") <= width
