"""Web <-> Discord Activity sync: the server is the single source of truth for a
logged-in player's game; web and Activity only paint it.

Backend: GET /api/state and the "attempt" / 409 "stale" contract of /api/guess
(in-memory store, fake Discord). A "second client" with the same session cookie
stands in for the Discord Activity. Browser: game.js repaints from the server's
state (409, focus/visibility, Panama day change) with faked /api/* routes.
"""

import datetime
import json
import threading

import pytest

import app
from lb_testlib import (  # noqa: F401 (fixtures)
    SECRET_BITS, VALID_AVATAR, all_store_text, answer, client, discord, guess, lb_env, login, mem,
    rendered, row_of, today, wrong_words,
)

P1 = "100000000000000001"
COLORS = {"correct", "semicorrect", "incorrect"}


def state(client, lang="es"):
    r = client.get("/api/state", query_string={"lang": lang})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.headers["Cache-Control"] == "no-store"
    return r.get_json()


def activity_client(web_client):
    """A second client with the same session (stands in for the Discord Activity)."""
    other = app.app.test_client()
    other.set_cookie("c24_lb", web_client.get_cookie("c24_lb").value)
    return other


# ---------- GET /api/state contract ----------

def test_state_errors(monkeypatch, mem, client):
    # leaderboard off -> 404
    for name in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    r = client.get("/api/state?lang=es")
    assert r.status_code == 404 and r.get_json() == {"error": "disabled"}


def test_state_login_lang_rate_store(lb_env, client, discord, monkeypatch):
    r = client.get("/api/state?lang=es")
    assert r.status_code == 401 and r.get_json() == {"error": "login"}
    login(client, discord)
    for bad in ("xx", "all", ""):
        r = client.get("/api/state", query_string={"lang": bad})
        assert r.status_code == 400 and r.get_json() == {"error": "bad_lang"}
    assert client.get("/api/state").status_code == 400
    codes = [client.get("/api/state?lang=es").status_code for _ in range(app.STATE_RATE_LIMIT_PER_MINUTE + 1)]
    assert codes[:-1] == [200] * app.STATE_RATE_LIMIT_PER_MINUTE and codes[-1] == 429
    # its own bucket: guesses still work
    assert guess(client, wrong_words("es", 1)[0], attempt=0).status_code == 200
    assert any(k == P1 + ":state" for k, _ in lb_env.rate)

    def boom(*a, **k):
        raise app.store_mod.StoreError("down")
    monkeypatch.setattr(lb_env, "get_game", boom)
    monkeypatch.setattr(lb_env, "rate_hit", lambda *a, **k: 1)
    r = client.get("/api/state?lang=es")
    assert r.status_code == 503 and r.get_json() == {"error": "store"}


def test_state_matches_page_embed(lb_env, client, discord, rendered):
    login(client, discord)
    guess(client, wrong_words("es", 1)[0], attempt=0)
    client.get("/lb/es")
    name, ctx = rendered[-1]
    assert name == "game.html"
    assert ctx["lb_state"] == state(client)
    assert set(ctx["lb_state"]) == {"day", "puzzle", "guesses", "status", "attempts", "done", "won",
                                    "answer", "points", "rank"}


def test_attempt_must_be_a_small_int(lb_env, client, discord):
    login(client, discord)
    w = wrong_words("es", 1)[0]
    for bad in ("0", 1.0, True, -1, 7, [0]):
        r = guess(client, w, attempt=bad)
        assert r.status_code == 400 and r.get_json() == {"error": "bad_request"}, bad
    # no attempt (older clients) still works, None too
    assert guess(client, w, attempt=None).status_code == 200
    assert not lb_env.games or len(next(iter(lb_env.games.values()))["guesses"]) == 1


# ---------- the 9 required cases ----------

def test_1_three_web_guesses_then_fourth(lb_env, client, discord):
    login(client, discord)
    words = wrong_words("es", 4)
    for i, w in enumerate(words[:3]):
        r = guess(client, w, attempt=i)
        assert r.status_code == 200
        body = r.get_json()
        assert body["attempts"] == i + 1 and body["day"] == app.lb_today()[0].isoformat()
    r = client.get("/api/state?lang=es")
    s = r.get_json()
    assert s["status"] == "playing" and s["attempts"] == 3 and s["done"] is False and s["won"] is False
    assert [g["word"] for g in s["guesses"]] == words[:3]
    assert all(len(g["colors"]) == 5 and set(g["colors"]) <= COLORS for g in s["guesses"])
    assert s["answer"] is None and s["points"] is None and s["rank"] is None
    assert answer("es") not in r.get_data(as_text=True)  # never the word while playing
    assert s["day"] == "2026-11-03" and s["puzzle"] == app.lb_today()[1]
    r = guess(client, words[3], attempt=3)
    assert r.status_code == 200 and r.get_json()["attempts"] == 4
    assert state(client)["attempts"] == 4


def test_2_win_on_web(lb_env, client, discord, mem):
    login(client, discord)
    w, extra = wrong_words("es", 2)
    guess(client, w, attempt=0)
    body = guess(client, answer("es"), attempt=1).get_json()
    assert body["won"] and body["done"] and body["points"] == 5
    s = state(client)
    assert s["status"] == "won" and s["done"] is True and s["won"] is True  # done: keyboard disabled
    assert s["attempts"] == 2 and s["points"] == 5 and s["rank"] == 1 and s["answer"] == answer("es")
    # an extra guess is refused (with the state to repaint) and adds no points
    for attempt in (2, 1, None):
        r = guess(client, extra, attempt=attempt)
        assert r.status_code == 400
        assert r.get_json()["error"] == "finished" and r.get_json()["state"] == s
    assert len(mem.results) == 1
    assert row_of(mem, P1, "es")["points"] == 5
    assert len(mem.games[(P1, "es", app.lb_today()[0])]["guesses"]) == 2


def test_3_lose_on_web(lb_env, client, discord, mem):
    login(client, discord)
    words = wrong_words("es", 7)
    for i, w in enumerate(words[:6]):
        assert guess(client, w, attempt=i).status_code == 200
    s = state(client)
    assert s["status"] == "lost" and s["done"] is True and s["won"] is False
    assert s["attempts"] == 6 and s["answer"] == answer("es") and s["points"] == 0
    r = guess(client, words[6], attempt=6)
    assert r.status_code == 400 and r.get_json()["error"] == "finished" and r.get_json()["state"] == s
    assert len(mem.results) == 1


def test_4_win_on_second_client_shows_on_first(lb_env, client, discord, mem, rendered):
    login(client, discord)
    activity = activity_client(client)
    w1, w2, w3 = wrong_words("es", 3)
    guess(client, w1, attempt=0)
    # the Activity sees the web's guess, then plays on and wins
    assert [g["word"] for g in state(activity)["guesses"]] == [w1]
    assert guess(activity, w2, attempt=1).status_code == 200
    assert guess(activity, answer("es"), attempt=2).get_json()["won"] is True
    s = state(client)
    assert s["status"] == "won" and s["done"] and s["attempts"] == 3 and s["points"] == 4
    # the web tab still thinks it's on row 1: refused with the state, nothing saved
    r = guess(client, w3, attempt=1)
    assert r.status_code == 400 and r.get_json()["error"] == "finished" and r.get_json()["state"] == s
    assert len(mem.results) == 1
    client.get("/leaderboard?tab=es")
    rows = rendered[-1][1]["rows"]
    assert [(r["id"], r["points"], r["wins"], r["played"]) for r in rows] == [(P1, 4, 1, 1)]


def test_5_simultaneous_same_attempt(lb_env, client, discord, mem):
    login(client, discord)
    activity = activity_client(client)
    w0, a, b, c, d = wrong_words("es", 5)
    guess(client, w0, attempt=0)
    # threads: both send attempt=1 at once
    barrier = threading.Barrier(2)
    out = {}

    def send(name, cl, word):
        barrier.wait()
        out[name] = guess(cl, word, attempt=1)
    threads = [threading.Thread(target=send, args=("web", client, a)),
               threading.Thread(target=send, args=("act", activity, b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    codes = sorted(r.status_code for r in out.values())
    assert codes == [200, 409]
    stale = [r for r in out.values() if r.status_code == 409][0].get_json()
    assert stale["error"] == "stale" and stale["state"]["attempts"] == 2
    saved = mem.games[(P1, "es", app.lb_today()[0])]["guesses"]
    assert len(saved) == 2 and saved[0] == w0 and saved[1] in (a, b)
    assert stale["state"] == state(client)
    # sequential with the same attempt value: exactly one saved
    assert guess(client, c, attempt=2).status_code == 200
    r = guess(activity, d, attempt=2)
    assert r.status_code == 409 and r.get_json()["state"]["attempts"] == 3
    assert len(mem.games[(P1, "es", app.lb_today()[0])]["guesses"]) == 3
    assert r.headers["Cache-Control"] == "no-store"


def test_6_es_and_en_are_separate_games(lb_env, client, discord):
    login(client, discord)
    guess(client, wrong_words("es", 1)[0], attempt=0)
    guess(client, answer("es"), attempt=1)
    en = state(client, "en")
    assert en["attempts"] == 0 and en["status"] == "playing" and en["guesses"] == []
    assert guess(client, wrong_words("en", 1)[0], lang="en", attempt=0).status_code == 200
    assert state(client, "es")["status"] == "won" and state(client, "en")["attempts"] == 1
    assert state(client, "en")["day"] == state(client, "es")["day"]


def test_7_panama_day_change_new_empty_game(lb_env, client, discord, mem, today, rendered):
    login(client, discord)
    words = wrong_words("es", 2)
    for i, w in enumerate(words):
        guess(client, w, attempt=i)
    before = state(client)
    assert before["attempts"] == 2 and before["day"] == "2026-11-03"
    today(datetime.date(2026, 11, 4))
    after = state(client)
    assert after["day"] == "2026-11-04" and after["puzzle"] == before["puzzle"] + 1
    assert after["guesses"] == [] and after["attempts"] == 0 and after["status"] == "playing"
    assert after["answer"] is None
    # a client still on yesterday's row 2 is told to repaint (nothing saved)
    r = guess(client, wrong_words("es", 3)[2], attempt=2)
    assert r.status_code == 409 and r.get_json()["state"] == after
    assert (P1, "es", datetime.date(2026, 11, 4)) not in mem.games
    assert guess(client, wrong_words("es", 1)[0], attempt=0).status_code == 200
    client.get("/lb/es")
    assert rendered[-1][1]["lb_state"]["day"] == "2026-11-04"
    assert rendered[-1][1]["lb_state"]["attempts"] == 1


def test_8_guest_web_pages_write_nothing(lb_env, client, discord, mem):
    paths = ["/", "/es", "/en", "/ko", "/es?frame_id=abc&instance_id=i&platform=desktop", "/leaderboard"]
    for path in paths:
        assert client.get(path).status_code == 200, path
    assert client.get("/api/state?lang=es").status_code == 401
    assert mem.is_empty()
    # logged in: guest pages still write nothing
    login(client, discord)
    before = repr(mem.dump())
    for path in paths:
        assert client.get(path).status_code == 200, path
    assert repr(mem.dump()) == before


def test_9_nothing_secret_stored(lb_env, client, discord, mem):
    discord.avatar = VALID_AVATAR
    login(client, discord)
    activity = activity_client(client)
    guess(client, wrong_words("es", 1)[0], attempt=0)
    state(client)
    state(activity)
    guess(activity, wrong_words("es", 2)[1], attempt=0)  # stale
    guess(activity, answer("es"), attempt=1)
    text = all_store_text(mem)
    for bit in SECRET_BITS.values():
        assert bit not in text, bit
    for word in ("email", "banner", "global_name", "token", "locale", "verified"):
        assert word not in text
    assert mem.players == {P1: {"username": "kolo_fan", "hidden": False, "avatar": VALID_AVATAR}}
    # the state answer carries no Discord ID, avatar or token
    body = client.get("/api/state?lang=es").get_data(as_text=True)
    for bit in (P1, VALID_AVATAR, *SECRET_BITS.values()):
        assert bit not in body


# ---------- public URL for share links ----------

def test_public_origin_in_game_page(client, monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    html = client.get("/es?frame_id=1").get_data(as_text=True)
    assert 'data-public-origin="http://localhost"' in html
    monkeypatch.setenv("PUBLIC_URL", "https://casa-24-wordle.vercel.app/")
    html = client.get("/es").get_data(as_text=True)
    assert 'data-public-origin="https://casa-24-wordle.vercel.app"' in html
    for bad in ("javascript:alert(1)", "https://x.example/path", "nope"):
        monkeypatch.setenv("PUBLIC_URL", bad)
        assert 'data-public-origin="http://localhost"' in client.get("/es").get_data(as_text=True)
    js = open(app.os.path.join(app.STATIC_DIR, "game.js"), encoding="utf-8").read()
    assert "PUBLIC_ORIGIN + \"/\" + this.config.language_code" in js
    assert "window.location.origin + \"/\"" not in js


def test_guest_sync_text_in_every_language():
    for lang in app.language_codes:
        assert app.language_configs[lang]["text"].get("lb_guest_sync", "").strip(), lang
    assert app.language_configs["es"]["text"]["lb_guest_sync"] == \
        "Inicia sesión con Discord para continuar esta partida en Discord y que cuente para el ranking."
    assert app.language_configs["en"]["text"]["lb_guest_sync"] == \
        "Sign in with Discord to continue this game on Discord and count it toward the ranking."


# ---------- browser: game.js paints the server's state ----------

from test_leaderboard_ui import BOARD_COLORED, ME, render_game, server, wait_reveal  # noqa: E402,F401

C, S, I = "correct", "semicorrect", "incorrect"
DAY = "2026-11-03"
TOAST = "#app .fixed.top-0 p.font-bold"


def lb_state(words, day=DAY, puzzle=9, done=False, won=False, answer=None, points=None, rank=None):
    guesses = [{"word": w, "colors": cols} for w, cols in words]
    status = ("won" if won else "lost") if done else "playing"
    return {"day": day, "puzzle": puzzle, "guesses": guesses, "status": status, "attempts": len(guesses),
            "done": done, "won": won, "answer": answer, "points": points, "rank": rank}


def open_game(server, page, embed, errors, states=None, guess_handler=None, clock=None):
    """/lb/es rendered with `embed`; /api/state answers states.pop(0) (or the last one)."""
    html = render_game("es", lb=True, lb_state=embed, lb_enabled=True, lb_user=ME)
    calls = {"state": 0, "guess": []}
    page.on("pageerror", lambda e: errors.append(str(e)))

    def api_state(route):
        calls["state"] += 1
        body = states.pop(0) if len(states) > 1 else states[0]
        route.fulfill(content_type="application/json", body=json.dumps(body))

    def api_guess(route):
        calls["guess"].append(json.loads(route.request.post_data))
        status, body = guess_handler(calls["guess"][-1])
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    if clock is not None:
        page.clock.install(time=clock)  # a datetime (a plain number would be seconds)
    page.route(server + "/lb/es", lambda r: r.fulfill(body=html, content_type="text/html"))
    page.route(server + "/api/live?**", lambda r: r.fulfill(content_type="application/json",
                                                             body='{"players": [], "count": 0}'))
    page.route(server + "/api/state?**", api_state)
    if guess_handler:
        page.route(server + "/api/guess", api_guess)
    page.goto(server + "/lb/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    return calls


def type_word(page, word):
    for ch in word:
        page.keyboard.press(ch)
    page.keyboard.press("Enter")


def test_browser_409_repaints_from_state(server, page):
    first = ("cosas", [I, S, I, I, I])
    other = ("perro", [C, I, I, S, I])   # played on Discord meanwhile
    embed = lb_state([first])
    fresh = lb_state([first, other])
    errors = []
    calls = open_game(server, page, embed, errors, states=[fresh],
                      guess_handler=lambda b: (409, {"error": "stale", "state": fresh}))
    assert page.locator(BOARD_COLORED).count() == 5
    type_word(page, "gatos")
    page.wait_for_function(f"document.querySelectorAll('{BOARD_COLORED}').length === 10")
    assert calls["guess"] == [{"lang": "es", "guess": "gatos", "attempt": 1}]
    row2 = page.locator("main .grid-cols-5").nth(1).inner_text().lower()
    assert "perro" in row2.replace("\n", "") and "gatos" not in page.inner_text("main").lower().replace("\n", "")
    assert "correct" in page.get_attribute(".key[data-char=p]", "class")
    page.wait_for_timeout(300)
    assert page.locator(TOAST).count() == 0  # no error toast
    # the next guess goes on row 2
    type_word(page, "jamon")
    page.wait_for_timeout(300)
    assert calls["guess"][-1]["attempt"] == 2
    assert errors == []


def test_browser_finished_elsewhere_shows_end_window(server, page):
    first = ("cosas", [I, S, I, I, I])
    won = lb_state([first, ("jamón", [C] * 5)], done=True, won=True, answer="jamón", points=5, rank=2)
    errors = []
    calls = open_game(server, page, lb_state([first]), errors, states=[won],
                      guess_handler=lambda b: (400, {"error": "finished", "state": won}))
    type_word(page, "gatos")
    page.wait_for_selector("[data-lb-end] .c24-lb-rank", state="visible", timeout=6000)
    assert "#2" in page.inner_text("[data-lb-end]") and "+5" in page.inner_text("[data-lb-end]")
    assert page.locator(BOARD_COLORED).count() == 10
    assert page.locator(TOAST).count() == 0
    # finished: the keyboard does nothing
    page.keyboard.press("Escape")
    type_word(page, "perro")
    page.wait_for_timeout(300)
    assert len(calls["guess"]) == 1
    assert errors == []


def test_browser_focus_and_visibility_reload(server, page):
    first = ("cosas", [I, S, I, I, I])
    later = lb_state([first, ("perro", [C, I, I, S, I]), ("gatos", [I, I, I, I, C])])
    errors = []
    start = datetime.datetime(2026, 11, 3, 15, 0, tzinfo=datetime.timezone.utc)
    calls = open_game(server, page, lb_state([first]), errors, states=[later], clock=start)
    # right after load: throttled (the page has fresh state)
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.wait_for_timeout(100)
    assert calls["state"] == 0
    page.clock.fast_forward(6000)
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.wait_for_function(f"document.querySelectorAll('{BOARD_COLORED}').length === 15")
    assert calls["state"] == 1
    # visibilitychange -> visible also asks (after the 5 s gap)
    page.clock.fast_forward(6000)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(200)
    assert calls["state"] == 2
    assert page.locator(TOAST).count() == 0
    assert errors == []


def test_browser_day_rollover_clears_board(server, page):
    old = lb_state([("cosas", [I, S, I, I, I]), ("jamón", [C] * 5)], done=True, won=True,
                   answer="jamón", points=5, rank=1)
    new_day = lb_state([], day="2026-11-04", puzzle=10)
    errors = []
    # 23:59:57 in Panama (04:59:57 UTC next day)
    start = datetime.datetime(2026, 11, 4, 4, 59, 57, tzinfo=datetime.timezone.utc)
    calls = open_game(server, page, old, errors, states=[new_day], clock=start,
                      guess_handler=lambda b: (200, {"word": "perro", "colors": [I] * 5, "done": False,
                                                     "won": False, "answer": None, "points": None,
                                                     "rank": None, "day": "2026-11-04", "attempts": 1}))
    page.wait_for_selector("[data-lb-end] .c24-lb-rank", state="visible", timeout=6000)
    assert page.locator(BOARD_COLORED).count() == 10
    page.clock.fast_forward(5000)  # midnight passes: the 1 s tick sees the new Panama date
    page.wait_for_function(f"document.querySelectorAll('{BOARD_COLORED}').length === 0")
    assert calls["state"] >= 1
    assert not page.is_visible("[data-lb-end]")
    for ch in "cjoasm":
        cls = page.get_attribute(f".key[data-char={ch}]", "class") or ""
        assert "correct" not in cls, ch
    vm = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
    assert page.evaluate(vm + ".todays_idx") == "10"
    assert page.evaluate(vm + ".game_over") is False
    assert page.evaluate(vm + ".todays_word") == ""
    # a new game can start on row 0
    type_word(page, "perro")
    page.clock.fast_forward(3000)
    page.wait_for_function(f"document.querySelectorAll('{BOARD_COLORED}').length === 5")
    assert calls["guess"][-1] == {"lang": "es", "guess": "perro", "attempt": 0}
    assert errors == []


def test_browser_guest_save_key_ignores_query(server, page, monkeypatch):
    """The guest game's localStorage key is the path's last segment ("es"), so
    ?frame_id=... doesn't lose the saved game and older saves still load."""
    for name in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    page.goto(server + "/es?frame_id=abc&platform=desktop")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    page.keyboard.press("c")
    page.wait_for_timeout(50)
    keys = page.evaluate("Object.keys(localStorage)")
    assert "es" in keys and not any("?" in k for k in keys)
    saved = json.loads(page.evaluate("localStorage.getItem('es')"))
    assert saved["tiles"][0][0] == "c"
    page.goto(server + "/es")
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    assert page.locator("main .grid-cols-5").first.inner_text().lower().startswith("c")


def test_menu_notice_cleanup_keeps_other_params(server, page):
    page.goto(server + "/?login=cancelled&frame_id=abc&platform=desktop")
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    page.wait_for_function("!/login=/.test(location.search)")
    assert page.evaluate("location.search") == "?frame_id=abc&platform=desktop"
