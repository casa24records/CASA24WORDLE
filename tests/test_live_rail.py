"""Live view cards like NYT Wordle's "Playing now" rail: only the profile picture and the grid.

Checked on the web (1366x768) and in Discord desktop (embed, 1000x493):
  - cards are about 147x80 (140-155 x 70-90), a ~64px round avatar and a 6x5 mini board
  - no visible @name, live dot, ✓/✗ or title; each card's accessible name holds the @username
  - the rail sits 16px from the left, 10px under the header, and never covers the board,
    keyboard or header
  - inside Discord the "Invite friends" card has the same size
  - phones (390x844): the people button opens the sheet with the same compact cards
Pages are rendered from the templates and served over a real local server; /api/live
is faked (in the Activity the list is fed to the page directly, as the shell would).
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
     "rows": [[I] * 5] * 6, "done": True, "won": False, "live": True},
    # presence: opened today's game, no guesses yet -> an empty board
    {"username": "recien_llegado", "avatar_url": "https://cdn.discordapp.com/embed/avatars/1.png",
     "rows": [], "done": False, "won": False, "live": True},
]
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cff01f0005010201a0e2d2b80000000049454e44ae426082")
FEED = "p => document.querySelector('#app')._vnode.component.proxy.applyLive({players: p, count: p.length})"
MEASURE = """() => {
  const R = e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; };
  const q = s => document.querySelector(s);
  return {
    header: R(q('header.c24-header')), board: R(q('.c24-board')), keyboard: R(q('.c24-keyboard')),
    rail: R(q('#c24-live')),
    cards: [...document.querySelectorAll('.c24-live-card')].map(c => ({
      box: R(c),
      avatar: R(c.querySelector('.c24-live-avatar')),
      radius: getComputedStyle(c.querySelector('.c24-live-avatar')).borderRadius,
      grid: R(c.querySelector('.c24-live-grid')),
      cells: c.querySelectorAll('.c24-live-grid > span').length,
      colored: c.querySelectorAll('.c24-live-grid > :not(.is-empty)').length,
      info: R(c.querySelector('.c24-live-info')),
      title: c.getAttribute('title'),
    })),
    invite: q('[data-live-invite]') ? R(q('[data-live-invite]')) : null,
    inviteIcon: q('.c24-live-invite-icon') ? R(q('.c24-live-invite-icon')) : null,
  };
}"""


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def render_game(variant, lang="es"):
    """lb = /lb/es logged in; act = the same page inside the Discord Activity (embed)."""
    language = app.Language(lang, app.language_codes_5words[lang])
    language.daily_word = ""
    ctx = dict(language=language, demo=False, lb=True, lb_state=None, lb_enabled=True, lb_user=ME)
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
        page.add_init_script("document.documentElement.classList.add('c24-plat-%s')" % platform)
    page.goto(server + "/game")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    if variant == "act":
        page.evaluate("document.getElementById('c24-activity-overlay').dataset.state = 'ready'")
        page.evaluate(FEED, players)  # in Discord /api/live goes through the shell
    page.wait_for_selector(".c24-live-card", state="attached")
    page.wait_for_timeout(150)


def overlap(a, b):
    return a["x"] < b["x"] + b["width"] - 0.5 and b["x"] < a["x"] + a["width"] - 0.5 \
        and a["y"] < b["y"] + b["height"] - 0.5 and b["y"] < a["y"] + a["height"] - 0.5


def check_cards(page, m, column=True):
    assert len(m["cards"]) == len(PLAYERS)
    for p, c in zip(PLAYERS, m["cards"]):
        name = "@" + p["username"][:32]  # the page caps names at 32 characters
        box = c["box"]
        assert 140 <= box["width"] <= 155 and 70 <= box["height"] <= 90, box
        av = c["avatar"]
        assert 60 <= av["width"] <= 68 and abs(av["width"] - av["height"]) <= 0.5, av
        assert c["radius"] in ("9999px", "50%"), c["radius"]
        # avatar on the left, grid on the right, both inside the card
        assert av["x"] >= box["x"] and av["x"] + av["width"] <= c["grid"]["x"] + 0.5
        assert c["grid"]["x"] + c["grid"]["width"] <= box["x"] + box["width"] + 0.5
        assert 45 <= c["grid"]["width"] <= 60 and 55 <= c["grid"]["height"] <= 70, c["grid"]
        assert c["cells"] == 30
        # nothing written: the name/status are visually hidden, read as the accessible name
        assert c["info"]["width"] <= 1 and c["info"]["height"] <= 1
        assert c["title"] == name
        assert page.get_by_role("listitem", name=re.compile(re.escape(name))).count() == 1
    # the presence player (0 guesses) shows an empty board
    assert m["cards"][3]["colored"] == 0 and m["cards"][0]["colored"] == 10
    # the rail: one column, cards ~9px apart
    if column:
        gaps = [b["box"]["y"] - (a["box"]["y"] + a["box"]["height"]) for a, b in zip(m["cards"], m["cards"][1:])]
        assert all(6 <= g <= 12 for g in gaps), gaps
    assert page.locator(".c24-live-grid").evaluate_all("gs => gs.map(g => g.textContent.trim()).join('')") == ""
    assert page.locator(".c24-live-dot").count() == 0


@pytest.mark.parametrize("variant,width,height", [("lb", 1366, 768), ("act", 1000, 493), ("lb", 860, 600)])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_rail_cards_are_profile_and_grid_only(browser, server, variant, width, height, scheme):
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    page = ctx.new_page()
    try:
        open_game(page, server, variant)
        assert page.is_visible("#c24-live") and not page.is_visible("[data-live-open]")
        m = page.evaluate(MEASURE)
        check_cards(page, m)
        rail = m["rail"]
        # left 16px, 10px under the header (in short Discord panels the header is the column's)
        assert abs(rail["x"] - 16) <= 1 and 140 <= rail["width"] <= 155
        header_bottom = m["header"]["y"] + m["header"]["height"]
        assert abs(rail["y"] - (header_bottom + 10)) <= 2, (rail, m["header"])
        assert rail["y"] + rail["height"] <= height
        for name in ("header", "board", "keyboard"):
            assert not overlap(rail, m[name]), name
            for c in m["cards"]:
                assert not overlap(c["box"], m[name]), name
        if variant == "act":
            inv, icon = m["invite"], m["inviteIcon"]
            card = m["cards"][0]["box"]
            assert abs(inv["width"] - card["width"]) <= 0.5 and abs(inv["height"] - card["height"]) <= 0.5
            assert 60 <= icon["width"] <= 68 and abs(icon["width"] - icon["height"]) <= 0.5
            assert inv["y"] + inv["height"] <= card["y"]  # first in the rail
            assert page.get_by_role("button", name=re.compile("Invitar amigos", re.I)).count() == 1
        else:
            assert m["invite"] is None
    finally:
        ctx.close()


def test_rail_scrolls_inside_when_long(server, page):
    many = [dict(PLAYERS[0], username=f"player{i}") for i in range(20)]
    page.set_viewport_size({"width": 1366, "height": 768})
    open_game(page, server, "lb", players=many)
    lst = page.evaluate("(() => { const l = document.querySelector('.c24-live-list'); const r = l.getBoundingClientRect();"
                        " return {bottom: r.bottom, scroll: l.scrollHeight, client: l.clientHeight}; })()")
    assert lst["bottom"] <= 768 and lst["scroll"] > lst["client"]
    assert page.evaluate("document.documentElement.scrollHeight") <= 768


def test_phone_sheet_shows_compact_cards(browser, server):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        open_game(page, server, "lb")
        assert not page.is_visible("#c24-live")
        page.click("[data-live-open]")
        assert page.is_visible("#c24-live") and page.is_visible("#c24-live-title")  # a dialog keeps its title
        m = page.evaluate(MEASURE)
        check_cards(page, m, column=False)
        sheet = m["rail"]
        assert sheet["x"] >= 0 and sheet["x"] + sheet["width"] <= 390 and sheet["y"] + sheet["height"] <= 844 + 0.5
        # a wrapping grid: two cards side by side
        a, b = m["cards"][0]["box"], m["cards"][1]["box"]
        assert abs(a["y"] - b["y"]) <= 0.5 and b["x"] > a["x"] + a["width"]
        for c in m["cards"]:
            assert c["box"]["x"] >= sheet["x"] and c["box"]["x"] + c["box"]["width"] <= sheet["x"] + sheet["width"]
    finally:
        ctx.close()


def test_activity_phone_sheet_has_invite_card_same_size(browser, server):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        open_game(page, server, "act", platform="mobile")
        page.click("[data-live-open]")
        m = page.evaluate(MEASURE)
        assert m["invite"] and abs(m["invite"]["width"] - m["cards"][0]["box"]["width"]) <= 0.5
        assert abs(m["invite"]["height"] - m["cards"][0]["box"]["height"]) <= 0.5
    finally:
        ctx.close()
