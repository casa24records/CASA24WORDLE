"""Demo mode (/demo): password from DEMO_PASSWORD, random word, nothing saved.

Uses a fake password only. The real one lives in the environment, never in the repo.
"""

import json
import re
import threading

import pytest
from werkzeug.serving import make_server

import app

FAKE_PASSWORD = "test-pass-123"
WORD_RE = re.compile(r'"todays_word":"([^"]*)"')  # in the #c24-page JSON block


def answer_of(html):
    m = WORD_RE.search(html)
    assert m, "todays_word not found"
    return m.group(1)


def pool(lang):
    return set(app.language_codes_5words[lang]) | set(app.casa24_words[lang][0])


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", FAKE_PASSWORD)
    monkeypatch.delenv("SECRET_KEY", raising=False)


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)


@pytest.fixture
def client():
    return app.app.test_client()


def login(client, password=FAKE_PASSWORD):
    return client.post("/demo", data={"password": password})


# ---------- server side (Flask test client) ----------

def test_disabled_hides_everything(disabled, client):
    assert "data-demo" not in client.get("/").get_data(as_text=True)
    assert client.get("/demo").status_code == 404
    assert client.post("/demo", data={"password": ""}).status_code == 404
    assert client.get("/demo/es").status_code == 404


def test_enabled_shows_card(enabled, client):
    assert "data-demo" in client.get("/").get_data(as_text=True)
    r = client.get("/demo")
    assert r.status_code == 200
    assert 'name="password"' in r.get_data(as_text=True)


def test_game_needs_login(enabled, client):
    r = client.get("/demo/es")
    assert r.status_code == 302 and r.headers["Location"].endswith("/demo")


def test_wrong_password(enabled, client):
    r = login(client, "nope")
    assert r.status_code == 401
    assert r.headers["Cache-Control"] == "no-store"
    r = client.get("/demo/es")
    assert r.status_code == 302 and r.headers["Location"].endswith("/demo")


def test_right_password_and_game(enabled, client):
    r = login(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/demo/es")
    # already logged in: the login page sends you to the game
    r = client.get("/demo")
    assert r.status_code == 302 and r.headers["Location"].endswith("/demo/es")
    for lang in ("es", "en"):
        r = client.get(f"/demo/{lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert '"demo":true' in html
        assert "c24-demo-bar" in html
        assert "no-store" in r.headers["Cache-Control"]
        assert answer_of(html) in pool(lang)


def todays(lang):
    return app.Language(lang, app.language_codes_5words[lang]).daily_word


def test_first_open_is_word_of_the_day(enabled, client):
    login(client)
    for lang in ("es", "en"):
        for _ in range(5):
            assert answer_of(client.get(f"/demo/{lang}").get_data(as_text=True)) == todays(lang)
        real = answer_of(client.get(f"/{lang}").get_data(as_text=True))
        assert real == todays(lang)


def test_restart_is_random_and_never_repeats(enabled, client):
    login(client)
    first = answer_of(client.get("/demo/es").get_data(as_text=True))
    seen = set()
    for _ in range(50):
        word = answer_of(client.get(f"/demo/es?skip={first}").get_data(as_text=True))
        assert word != first and word in pool("es")
        seen.add(word)
    assert len(seen) > 1  # random, not one fixed word


def test_other_languages_redirect(enabled, client):
    login(client)
    for code in ("fr", "xx"):
        r = client.get(f"/demo/{code}")
        assert r.status_code == 302 and r.headers["Location"].endswith("/demo/es")


COLD_START = """
import app
c = app.app.test_client()
r = c.post("/demo", data={"password": "%s"})
assert r.status_code == 302, r.status_code
print("ok")
""" % FAKE_PASSWORD

# The session key must be ready before Flask opens the session, or the first
# request on a cold Vercel instance fails (regression tests for that bug).


def test_login_on_cold_start():
    import os
    import subprocess
    import sys

    env = dict(os.environ, DEMO_PASSWORD=FAKE_PASSWORD)
    env.pop("SECRET_KEY", None)
    r = subprocess.run(
        [sys.executable, "-c", COLD_START], cwd=os.getcwd(), env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-500:]


def test_new_password_logs_everyone_out(enabled, client, monkeypatch):
    login(client)
    assert client.get("/demo/es").status_code == 200
    # a new password (no SECRET_KEY) must invalidate old demo cookies at once
    monkeypatch.setenv("DEMO_PASSWORD", "another-fake-456")
    assert client.get("/demo/es").status_code == 302


def test_real_game_is_not_demo(enabled, client):
    html = client.get("/es").get_data(as_text=True)
    assert '"demo":false' in html
    assert "c24-demo-bar" not in html


def test_password_not_in_pages(enabled, client):
    login(client)
    for path in ("/", "/demo/es", "/demo/en", "/es"):
        assert FAKE_PASSWORD not in client.get(path).get_data(as_text=True)


# ---------- browser (Playwright) ----------

@pytest.fixture(scope="module")
def server():
    pytest.importorskip("playwright")
    srv = make_server("127.0.0.1", 0, app.app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


FAKE_SAVE = {
    "tiles": [["c", "o", "s", "a", "s"]] + [[""] * 5 for _ in range(5)],
    "tile_classes": [["incorrect"] * 5] + [[""] * 5 for _ in range(5)],
    "active_row": 1,
    "active_cell": 0,
    "todays_word": "zzzzz",
}
FAKE_RESULTS = {"es": [{"won": True, "attempts": 3, "date": "2026-10-25T12:00:00.000Z"}]}


def storage(page):
    return page.evaluate(
        "Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)]))"
    )


def wait_game(page):
    page.wait_for_function("document.querySelector('#app') && window.Vue")
    page.wait_for_function("document.querySelector('[data-demo-fill]')")


def test_demo_in_browser_saves_nothing(enabled, server, page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.set_viewport_size({"width": 390, "height": 844})

    # a real player's saved game and results
    page.goto(server + "/")
    page.evaluate(
        "([save, results]) => { localStorage.setItem('es', save);"
        " localStorage.setItem('game_results', results); localStorage.setItem('casa24_lang', 'en'); }",
        [json.dumps(FAKE_SAVE), json.dumps(FAKE_RESULTS)],
    )
    before = storage(page)

    # the Developer view card leads to the login form (not logged in yet)
    page.click("[data-demo] a[href='/demo/es']")
    page.wait_for_url("**/demo")
    page.fill("#demo-password", FAKE_PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url("**/demo/es")
    wait_game(page)

    first = page.evaluate("todays_word")
    assert first == todays("es")  # first open: the real word of the day
    page.click(".c24-demo-bar [data-demo-fill]")
    page.wait_for_function(
        "document.querySelector('.c24-result') && document.querySelector('.c24-result').innerText.includes('¡Ganaste!')",
        timeout=8000,
    )
    page.wait_for_timeout(300)
    assert storage(page) == before  # nothing new, nothing changed

    # the end window is the real one (countdown, share, stats)
    page.wait_for_selector("#copy_button", state="visible", timeout=8000)
    assert page.locator(".c24-result:visible").inner_text().strip() == "¡Ganaste!"
    # restart: a different word (the bar button stays usable with the end window open)
    if page.locator(".c24-close:visible").count():
        page.locator(".c24-close:visible").first.click()
    page.click(".c24-demo-bar [data-demo-restart]")
    page.wait_for_url(re.compile(r".*/demo/es\?skip=.*"))
    wait_game(page)
    assert page.evaluate("todays_word") != first
    assert page.locator(".c24-result").count() == 0
    assert storage(page) == before

    # English from the start screen card
    page.goto(server + "/")
    page.click("[data-demo] a[href='/demo/en']")
    page.wait_for_url("**/demo/en")
    wait_game(page)
    assert page.evaluate("todays_word") in pool("en")
    assert storage(page) == before

    assert errors == []


def test_wrong_password_in_browser(enabled, server, page):
    page.goto(server + "/demo")
    page.fill("#demo-password", "wrong-fake")
    page.click("button[type=submit]")
    page.wait_for_selector(".c24-demo-login-error")
    page.goto(server + "/demo/es")
    assert page.url.endswith("/demo")
