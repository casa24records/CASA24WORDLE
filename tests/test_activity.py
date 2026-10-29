"""Discord Activity layer (the game inside Discord).

Server: detection by frame_id / instance_id / platform (the shell) or embed=1
(the game in the shell's iframe), "/" inside Discord renders the Activity shell
(templates/activity.html: the SDK once, the game in a same-origin iframe), guest
pages redirect to the leaderboard game keeping the Activity's query, POST
/api/activity/token (fake Discord: no redirect_uri, nothing stored but ID,
username and avatar hash, token never stored or logged), the Bearer session on
/api/state, /api/guess, /api/live, /api/leaderboard and /api/me/delete, the
discordsays.com origin, and no inline JS anywhere (the Activity's CSP).
The web without those params must stay exactly as it was.

Browser (Playwright): the vendored SDK module is swapped for a shim around the
SDK's own DiscordSDKMock (docs/discord-activity-checklist.md section 4A); the
real Flask app answers everything else with an in-memory store and fake Discord.
The shell must construct the SDK exactly once per launch: picking a language,
playing, changing language and the leaderboard window never reload the shell.
One test repeats Discord's real CSP (section 4B, with frame-src/child-src) with
the proxy's nonce, on the shell and the iframe.
"""

import json
import logging
import os
import re
import threading
from urllib.parse import parse_qs, urlparse

import pytest
from itsdangerous import URLSafeTimedSerializer
from werkzeug.serving import make_server

import app
import discord_auth
import store
from lb_testlib import (  # noqa: F401 (fixtures)
    FAKE_SECRET_KEY, SECRET_BITS, VALID_AVATAR, all_store_text, answer, client, discord, guess,
    lb_env, login, mem, rendered, today, wrong_words,
)

CLIENT_ID = "123456789"  # lb_env's DISCORD_CLIENT_ID
P1 = "100000000000000001"
ACT = "frame_id=f1&instance_id=i1&platform=desktop&guild_id=g1&channel_id=c1"
ACT_PARAMS = {"frame_id": "f1", "instance_id": "i1", "platform": "desktop", "guild_id": "g1", "channel_id": "c1"}
DISCORDSAYS = f"https://{CLIENT_ID}.discordsays.com"
SDK_DIR = "/static/vendor/discord-embedded-app-sdk-2.5.0/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "webapp", "static")


def session_for(discord_id):
    return URLSafeTimedSerializer(FAKE_SECRET_KEY, salt="c24-lb").dumps(discord_id)


def bearer(value):
    return {"Authorization": "Bearer " + value}


def token_login(client, discord, code="sdk-code", user_id=None, username=None, **headers):
    if user_id:
        discord.user = {"id": user_id, "username": username or "act" + user_id[-3:]}
    return client.post("/api/activity/token", json={"code": code}, headers=headers)


# ---------- detection ----------

@pytest.mark.parametrize("query, expected", [
    ("frame_id=a&instance_id=b&platform=desktop", True),
    ("frame_id=a&instance_id=b&platform=mobile", True),
    ("frame_id=a&instance_id=b&platform=tv", False),
    ("frame_id=a&instance_id=b", False),
    ("frame_id=a&platform=desktop", False),
    ("instance_id=b&platform=desktop", False),
    ("frame_id=&instance_id=b&platform=desktop", False),
    ("", False),
    ("embed=1", True),        # the game in the shell's iframe (no Discord params on purpose)
    ("embed=0", False),
    ("embed=true", False),
])
def test_activity_detection(query, expected):
    with app.app.test_request_context("/lb/es?" + query):
        assert app.is_activity() is expected
        assert app.is_activity_embed() is ("embed=1" in query)
        assert app.is_activity_launch() is (expected and "embed=1" not in query)
        ctx = {}
        app.app.update_template_context(ctx)
        assert ctx["C24_ACTIVITY"] is expected


def test_activity_url_keeps_discord_query_only():
    with app.app.test_request_context("/lb/es?" + ACT + "&layout=azerty&c24_root=1&lang=en"):
        url = app.activity_url("/lb/en")
        assert parse_qs(urlparse(url).query) == {k: [v] for k, v in ACT_PARAMS.items()}
        assert app.activity_url("/leaderboard?tab=es").startswith("/leaderboard?tab=es&frame_id=f1")
    with app.app.test_request_context("/lb/es"):
        assert app.activity_url("/lb/en") == "/lb/en"  # the web: unchanged


# ---------- the web without Discord's params is unchanged ----------

ACTIVITY_MARKERS = ("discord-activity.js", "discord-embedded-app-sdk", 'id="c24-activity"', "data-activity-",
                    "activity-shell.js", "c24-shell", "c24-embed", "modulepreload", "data-lang-choice")


def test_web_pages_have_no_activity_code(lb_env, client, discord):
    pages = ["/", "/es", "/en", "/leaderboard", "/es?frame_id=a&instance_id=b&platform=tv"]
    for path in pages:
        html = client.get(path).get_data(as_text=True)
        assert not [m for m in ACTIVITY_MARKERS if m in html], path
    login(client, discord)
    for path in pages + ["/lb/es", "/lb/en", "/leaderboard?tab=es"]:
        r = client.get(path)
        assert r.status_code == 200, path
        html = r.get_data(as_text=True)
        assert not [m for m in ACTIVITY_MARKERS if m in html], path


def test_web_redirects_and_cookie_unchanged(lb_env, client, discord):
    # logged out: the leaderboard game sends you to Discord's web login, as before
    r = client.get("/lb/es")
    assert r.status_code == 302 and r.headers["Location"].endswith("/auth/discord/login?next=/lb/es")
    r = client.get("/auth/discord/login", query_string={"next": "/lb/es"})
    assert r.headers["Location"].startswith("https://discord.com/oauth2/authorize?")
    assert "redirect_uri=" in r.headers["Location"]
    r = login(client, discord)
    assert discord.calls[0][2].endswith("/auth/discord/callback")  # the web still sends redirect_uri
    cookie = [h for h in r.headers.getlist("Set-Cookie") if h.startswith("c24_lb=")][0]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Max-Age=2592000" in cookie
    assert "Partitioned" not in cookie and "SameSite=None" not in cookie
    assert client.get("/").status_code == 200  # the menu, no redirect
    assert client.get("/es").status_code == 200


# ---------- inside the Activity ----------

def shell_data(html):
    return json.loads(re.search(r'id="c24-shell">(.*?)</script>', html).group(1))


def test_root_inside_activity_renders_the_shell(lb_env, client, rendered):
    """Discord opens "/": the shell itself (no redirect: the SDK answers to the page
    Discord framed), with the SDK preloaded and the game's files preloaded."""
    for path in ("/?" + ACT, "/activity?" + ACT):
        r = client.get(path)
        assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store", path
        assert rendered[-1][0] == "activity.html"
        html = r.get_data(as_text=True)
        assert '<script type="module" src="/static/activity-shell.js?v=' in html
        assert '<script type="module" src="/static/discord-activity.js' not in html  # only preloaded here
        data = shell_data(html)
        assert data["client_id"] == CLIENT_ID and data["lang"] is None
        assert [l["code"] for l in data["langs"]] == list(app.LB_LANGS)
        assert data["langs"][0]["code"] == "es" and data["langs"][1]["code"] == "en"
        assert [l["code"] for l in data["langs"]] == ["es", "en"]  # only Spanish and English
        assert not any("rtl" in l for l in data["langs"])
        assert all(l["loading"] for l in data["langs"])
        assert "fake-client-secret" not in html
        # every SDK module preloaded (plain versioned-folder paths), before the shell's script
        preloads = re.findall(r'<link rel="modulepreload" href="([^"]+)">', html)
        assert [p for p in preloads if p.startswith(SDK_DIR)] == ["/static/" + p for p in app.sdk_modulepreloads()]
        assert SDK_DIR + "index.mjs" in preloads and len(preloads) > 50
        assert html.index("modulepreload") < html.index("activity-shell.js")
        # the game's Vue and Tailwind, with the same ?v URLs as game.html (one download)
        with app.app.test_request_context("/"):
            vue, tw = app.asset("vendor/vue.global.prod.js"), app.asset("tailwind.css")
        assert f'<link rel="preload" href="{vue}" as="script">' in html
        assert f'<link rel="preload" href="{tw}" as="style">' in html
        with app.app.test_request_context("/"):
            gjs, djs = app.asset("game.js"), app.asset("discord-activity.js")
        assert f'<link rel="preload" href="{gjs}" as="script">' in html
        assert f'<link rel="modulepreload" href="{djs}">' in html
        game = client.get("/lb/es?embed=1").get_data(as_text=True)
        assert vue in game and tw in game and gjs in game and djs in game
        # the iframe: same origin, no sandbox; the picker (fallback only): 2 big buttons, bilingual title
        frame = re.search(r'<iframe[^>]*id="c24-game"[^>]*>', html).group(0)
        assert "sandbox" not in frame and "src=" not in frame
        assert re.findall(r'data-pick-lang="([a-z]{2})"', html) == list(app.LB_LANGS)
        assert 'dir="rtl"' not in html
        assert "Elige tu idioma" in html and "Choose your language" in html
        assert "Intentar de nuevo / Try again" in html
        assert inline_problems(html) == []
        assert not r.headers.getlist("Set-Cookie")
    # a language asked for in the URL opens right away
    assert shell_data(client.get("/?" + ACT + "&lang=en").get_data(as_text=True))["lang"] == "en"
    assert shell_data(client.get("/?" + ACT + "&lang=xx").get_data(as_text=True))["lang"] is None
    assert shell_data(client.get("/?" + ACT + "&lang=ko").get_data(as_text=True))["lang"] is None
    # an old /lb/<lang> launch URL: the shell on that language (never the bare game)
    r = client.get("/lb/en?" + ACT)
    assert r.status_code == 200 and shell_data(r.get_data(as_text=True))["lang"] == "en"
    # a removed language's launch URL: 302 to es (Discord's params kept), then the shell
    r = client.get("/lb/de?" + ACT)
    loc = urlparse(r.headers["Location"])
    assert r.status_code == 302 and loc.path == "/lb/es" and parse_qs(loc.query)["frame_id"] == ["f1"]


def test_shell_never_inside_its_own_iframe(lb_env, client):
    # "/" (or /activity) inside the iframe goes to the game: the SDK can't load twice
    for path, target in (("/?embed=1", "/lb/es"), ("/?embed=1&lang=en", "/lb/en"),
                         ("/?embed=1&lang=ko", "/lb/es"), ("/activity?embed=1", "/lb/es")):
        r = client.get(path)
        assert r.status_code == 302, path
        loc = urlparse(r.headers["Location"])
        assert loc.path == target and parse_qs(loc.query) == {"embed": ["1"]}, path
    # /activity on the web: back to the menu
    r = client.get("/activity")
    assert r.status_code == 302 and r.headers["Location"].endswith("/")


def test_shell_off_when_leaderboard_off(monkeypatch, client):
    for name in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    html = client.get("/?" + ACT).get_data(as_text=True)
    assert "activity-shell.js" not in html  # the normal menu, as before


def test_no_guest_game_inside_activity(lb_env, client):
    r = client.get("/en?" + ACT)
    assert r.status_code == 302
    loc = urlparse(r.headers["Location"])
    assert loc.path == "/lb/en" and parse_qs(loc.query)["frame_id"] == ["f1"]
    r = client.get("/en?embed=1")
    assert r.status_code == 302 and r.headers["Location"] == "/lb/en?embed=1"
    # a removed language: first to /es (params kept), which then goes to /lb/es
    r = client.get("/de?embed=1")
    assert r.status_code == 302 and r.headers["Location"] == "/es?embed=1"
    r = client.get("/nope?" + ACT)
    assert r.status_code == 302 and "frame_id=f1" in r.headers["Location"]


def test_activity_game_page(lb_env, client, rendered):
    """The game in the shell's iframe: /lb/<lang>?embed=1, no SDK, no Discord params."""
    r = client.get("/lb/es?embed=1")
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    html = r.get_data(as_text=True)
    assert 'type="module" src="/static/discord-activity.js?v=' in html
    assert "discord-embedded-app-sdk" not in html and "activity-shell.js" not in html
    assert '<html lang="es" class="c24-embed">' in html
    data = json.loads(re.search(r'id="c24-activity">(.*?)</script>', html).group(1))
    assert data["lang"] == "es" and "en" in data["langs"]
    assert "fake-client-secret" not in html
    page = json.loads(re.search(r'id="c24-page">(.*?)</script>', html).group(1))
    assert page["activity"] is True and page["lb"] is True and page["todays_word"] == ""
    assert rendered[-1][1]["lb_state"] is None  # no state in the page: game.js asks /api/state after login
    # no login / logout / guest / Developer view inside Discord
    for absent in ("/auth/discord/login", "/auth/logout", "data-dc-toggle", "data-guest-toggle",
                   "c24-demo-bar", "data-demo", "data-dc-login"):
        assert absent not in html, absent
    # nothing navigates to "/" or another page: the title is the language button ("ES ▾")
    assert not re.search(r'<a href="/(\?|")', html)
    assert 'href="/leaderboard' not in html
    btn = re.search(r'<button[^>]*data-activity-lang-open[^>]*>', html, re.S).group(0)
    assert 'aria-label="Cambiar idioma (Español)"' in btn
    assert re.search(r'<span class="c24-badge">es ▾</span>', html)
    # the language window: Español and English, the current one marked
    assert re.findall(r'data-lang-choice="([a-z]{2})"', html) == ["es", "en"]
    assert 'dir="rtl"' not in html
    assert re.search(r'data-lang-choice="es"[^>]*aria-current="true"', html, re.S)
    # the old Settings language select is gone
    assert "activity-lang-select" not in html and "data-activity-lang>" not in html
    # cookies are not touched inside the Activity
    assert not r.headers.getlist("Set-Cookie")


def test_activity_page_with_layout_form_keeps_query(lb_env, client):
    multi = [c for c in app.LB_LANGS if len(app.keyboards[c]["layouts"]) > 1]
    if not multi:
        pytest.skip("no language with two keyboard layouts")
    html = client.get(f"/lb/{multi[0]}?embed=1").get_data(as_text=True)
    form = re.search(r'<form method="get"[^>]*>(.*?)</form>', html, re.S).group(1)
    assert '<input type="hidden" name="embed" value="1">' in form  # stays in the iframe's game
    assert "frame_id" not in form
    assert "data-autosubmit" in form and "onchange" not in form


def test_activity_texts_in_all_languages():
    for code in app.LB_LANGS:
        text = app.language_configs[code]["text"]
        for key in ("activity_pick_title", "activity_loading_game", "activity_lang_button"):
            assert text.get(key, "").strip(), (code, key)
    assert app.language_configs["es"]["text"]["activity_pick_title"] == "Elige tu idioma"
    assert app.language_configs["en"]["text"]["activity_pick_title"] == "Choose your language"


def test_leaderboard_page_inside_activity_is_public_and_keeps_query(lb_env, client, discord):
    login(client, discord)  # even with a web cookie, the Activity page shows no account
    html = client.get("/leaderboard?tab=es&" + ACT).get_data(as_text=True)
    assert "/auth/logout" not in html and "/api/me/delete" not in html and "data-dc-login" not in html
    tabs = re.findall(r'<a href="(/leaderboard\?tab=[a-z]+[^"]*)"', html)
    assert tabs and all("frame_id=f1" in t for t in tabs)
    html = client.get("/leaderboard?tab=es&embed=1").get_data(as_text=True)
    assert "/auth/logout" not in html
    tabs = re.findall(r'<a href="(/leaderboard\?tab=[a-z]+[^"]*)"', html)
    assert tabs and all("embed=1" in t for t in tabs)


# ---------- POST /api/activity/token ----------

def test_token_endpoint(lb_env, client, discord, mem, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    discord.avatar = VALID_AVATAR
    r = token_login(client, discord, code="sdk-code-1")
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    body = r.get_json()
    assert set(body) == {"access_token", "session", "user"}
    assert body["access_token"] == SECRET_BITS["token"]
    assert body["user"] == {"username": "kolo_fan"}
    assert URLSafeTimedSerializer(FAKE_SECRET_KEY, salt="c24-lb").loads(body["session"]) == P1
    # exchanged WITHOUT a redirect_uri (the SDK's codes)
    assert discord.calls[0] == ("token", "sdk-code-1", None)
    # stored: ID, username, avatar hash. Never the token, email, banner, name, code
    assert mem.get_player(P1) == {"username": "kolo_fan", "hidden": False}
    assert mem.get_avatar(P1) == VALID_AVATAR
    dump = all_store_text(mem)
    for secret in (SECRET_BITS["token"], SECRET_BITS["email"], SECRET_BITS["banner"],
                   SECRET_BITS["global_name"], "sdk-code-1"):
        assert secret not in dump
    logs = caplog.text + capsys.readouterr().out
    assert SECRET_BITS["token"] not in logs and "sdk-code-1" not in logs
    assert not r.headers.getlist("Set-Cookie")  # no cookie: the session travels in a header


def test_token_endpoint_errors(lb_env, client, discord, monkeypatch, mem):
    assert client.get("/api/activity/token").status_code == 405
    for bad in (None, {}, {"code": ""}, {"code": 5}, {"code": "x" * 201}, {"code": "a\nb"}):
        r = client.post("/api/activity/token", json=bad) if bad is not None else \
            client.post("/api/activity/token", data="nope")
        assert r.status_code == 400 and r.get_json()["error"] == "bad_request", bad
    r = token_login(client, discord, Origin="https://evil.example")
    assert r.status_code == 403
    assert token_login(client, discord, Origin=DISCORDSAYS).status_code == 200

    def boom(*a, **k):
        raise discord_auth.DiscordError("discord request failed: HTTPError")
    monkeypatch.setattr(discord_auth, "exchange_code", boom)
    r = token_login(client, discord)
    assert r.status_code == 400 and r.get_json() == {"error": "discord"}

    monkeypatch.setattr(app, "ACTIVITY_TOKEN_PER_MINUTE", 1)
    assert token_login(client, discord).status_code == 429  # global budget (no IPs)
    assert "activity:token" in repr(mem.dump()["rate"])


def test_token_endpoint_404_when_leaderboard_off(monkeypatch, client):
    for name in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert client.post("/api/activity/token", json={"code": "x"}).status_code == 404


def test_exchange_code_omits_redirect_uri(monkeypatch):
    monkeypatch.setenv("DISCORD_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "s3cret")
    sent = []

    def fake_request(req):
        sent.append(parse_qs(req.data.decode()))
        return {"access_token": "tok"}
    monkeypatch.setattr(discord_auth, "_request_json", fake_request)
    assert discord_auth.exchange_code("abc") == "tok"
    assert discord_auth.exchange_code("abc", None) == "tok"
    assert discord_auth.exchange_code("abc", "https://x/auth/discord/callback") == "tok"
    assert all("redirect_uri" not in s for s in sent[:2])
    assert sent[0] == {"client_id": [CLIENT_ID], "client_secret": ["s3cret"],
                       "grant_type": ["authorization_code"], "code": ["abc"]}
    assert sent[2]["redirect_uri"] == ["https://x/auth/discord/callback"]


# ---------- the Bearer session ----------

def test_bearer_session_state_guess_live(lb_env, client, discord, mem):
    session = token_login(client, discord).get_json()["session"]
    h = bearer(session)
    r = client.get("/api/state", query_string={"lang": "es"}, headers=h)
    assert r.status_code == 200 and r.get_json()["attempts"] == 0
    word = wrong_words("es", 1)[0]
    r = client.post("/api/guess", json={"lang": "es", "guess": word, "attempt": 0},
                    headers={**h, "Origin": DISCORDSAYS})
    assert r.status_code == 200 and len(r.get_json()["colors"]) == 5
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word]
    # the web (cookie) sees the same game: one server-side truth
    login(client, discord)
    assert client.get("/api/state", query_string={"lang": "es"}).get_json()["attempts"] == 1
    other = app.app.test_client()
    r = other.get("/api/live", query_string={"lang": "es"}, headers=h)
    assert r.status_code == 200 and "players" in r.get_json()
    r = other.get("/api/leaderboard", query_string={"tab": "es"}, headers=h)
    assert r.status_code == 200


def test_bad_or_expired_session_is_401(lb_env, client, discord, monkeypatch):
    session = token_login(client, discord).get_json()["session"]
    other = app.app.test_client()
    forged = URLSafeTimedSerializer("not-the-key", salt="c24-lb").dumps(P1)
    for headers in (bearer(forged), bearer(session + "x"), bearer(""), {"Authorization": "Basic " + session},
                    bearer(URLSafeTimedSerializer(FAKE_SECRET_KEY, salt="c24-oauth").dumps(P1))):
        assert other.get("/api/state", query_string={"lang": "es"}, headers=headers).status_code == 401
        assert other.post("/api/guess", json={"lang": "es", "guess": "perro"}, headers=headers).status_code == 401
        assert other.get("/api/live", query_string={"lang": "es"}, headers=headers).status_code == 401
    # a bad header never falls back to a valid web cookie
    login(client, discord)
    assert client.get("/api/state", query_string={"lang": "es"}, headers=bearer(forged)).status_code == 401
    assert client.get("/api/state", query_string={"lang": "es"}).status_code == 200
    # expired (older than the 30 days the cookie lives)
    monkeypatch.setattr(app, "LB_COOKIE_AGE", -1)
    assert other.get("/api/state", query_string={"lang": "es"}, headers=bearer(session)).status_code == 401


def test_query_ids_never_choose_the_player(lb_env, client, discord):
    session = token_login(client, discord).get_json()["session"]
    r = client.get("/api/state", query_string={"lang": "es", "user_id": "5", "instance_id": "i9"},
                   headers=bearer(session))
    assert r.status_code == 200
    assert app.app.test_client().get("/api/state?lang=es&user_id=" + P1).status_code == 401


def test_delete_my_data_with_bearer(lb_env, client, discord, mem):
    session = token_login(client, discord).get_json()["session"]
    r = app.app.test_client().post("/api/me/delete", headers={**bearer(session), "Origin": DISCORDSAYS})
    # the Activity's Settings posts with fetch: a JSON answer, no page to go to
    assert r.status_code == 200 and r.get_json() == {"deleted": True} and mem.get_player(P1) is None
    assert r.headers["Cache-Control"] == "no-store"


# ---------- same origin: our host or exactly <client id>.discordsays.com ----------

@pytest.mark.parametrize("origin, ok", [
    (DISCORDSAYS, True),
    (DISCORDSAYS + "/lb/es?frame_id=f1", True),        # as a Referer
    ("https://evil.discordsays.com", False),
    (f"http://{CLIENT_ID}.discordsays.com", False),
    (f"https://{CLIENT_ID}.discordsays.com.evil.com", False),
    ("https://987654321.discordsays.com", False),
    ("https://evil.example", False),
    ("null", False),
])
def test_discordsays_origin(lb_env, client, discord, origin, ok):
    login(client, discord)
    header = "Referer" if "/lb/" in origin else "Origin"
    r = client.post("/api/guess", json={"lang": "es", "guess": wrong_words("es", 1)[0]}, headers={header: origin})
    assert (r.status_code == 200) is ok, (origin, r.status_code)


# ---------- GET /api/leaderboard (the Activity's leaderboard window) ----------

def test_api_leaderboard(lb_env, client, discord, mem):
    for i in range(3):
        pid = f"20000000000000000{i}"
        mem.upsert_player(pid, f"p{i}")
        app._record_result(mem, pid, "es", app.lb_today()[0], True, 2 + i)
    r = client.get("/api/leaderboard", query_string={"tab": "es"})
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    data = r.get_json()
    assert [row["username"] for row in data["rows"]] == ["p0", "p1", "p2"] and data["me"] is None
    assert "200000000000000000" not in r.get_data(as_text=True)  # no Discord IDs
    assert set(data["rows"][0]) == set(app.BOARD_FIELDS)
    session = token_login(client, discord).get_json()["session"]
    app._record_result(mem, P1, "es", app.lb_today()[0], False, 6)
    data = app.app.test_client().get("/api/leaderboard?tab=es", headers=bearer(session)).get_json()
    assert [r["is_me"] for r in data["rows"]] == [False, False, False, True]
    assert client.get("/api/leaderboard?tab=xx").status_code == 400
    assert client.get("/api/leaderboard").get_json()["tab"] == "all"


# ---------- CSP readiness: no inline JS in any page ----------

INLINE_HANDLER = re.compile(r"<[a-zA-Z][^>]*\son[a-z]+\s*=", re.S)
SCRIPT_TAG = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)


def inline_problems(html):
    problems = []
    if INLINE_HANDLER.search(html):
        problems.append("on*= attribute: " + INLINE_HANDLER.search(html).group(0)[:80])
    if re.search(r"javascript:", html, re.I):
        problems.append("javascript: URL")
    for attrs, body in SCRIPT_TAG.findall(html):
        if "src=" in attrs:
            continue
        if 'type="application/json"' not in attrs:
            problems.append("inline <script>: " + body.strip()[:60])
    return problems


def test_no_inline_js_in_rendered_pages(lb_env, client, discord, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "demo-pass-test")
    monkeypatch.setenv("ADMIN_DISCORD_IDS", P1)
    pages = {}
    for path in ["/", "/es", "/en", "/leaderboard", "/demo", "/sitemap.xml",
                 "/?" + ACT, "/activity?" + ACT, "/lb/es?" + ACT, "/lb/es?embed=1", "/lb/en?embed=1",
                 "/leaderboard?tab=es&" + ACT, "/leaderboard?tab=es&embed=1"]:
        pages[path] = client.get(path).get_data(as_text=True)
    login(client, discord)
    app._record_result(app.lb_store(), P1, "es", app.lb_today()[0], True, 3)
    client.post("/demo", data={"password": "demo-pass-test"})
    for path in ["/", "/lb/es", "/lb/en", "/leaderboard?tab=es", "/demo/es", "/?login=failed", "/?deleted=1"]:
        r = client.get(path)
        assert r.status_code == 200, path
        pages["in:" + path] = r.get_data(as_text=True)
    bad = {p: inline_problems(h) for p, h in pages.items() if inline_problems(h)}
    assert not bad, bad
    assert "data-confirm=" in pages["in:/leaderboard?tab=es"]  # delete my data: in-page dialog


def test_no_inline_js_in_template_sources():
    folder = os.path.join(ROOT, "webapp", "templates")
    for name in os.listdir(folder):
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            src = f.read()
        assert not INLINE_HANDLER.search(src), name
        assert "javascript:" not in src.lower(), name
        assert "window.confirm" not in src and "alert(" not in src, name


def test_static_js_has_no_confirm_alert_or_open():
    for name in ("game.js", "index.js", "discord.js", "theme.js", "leaderboard.js", "discord-activity.js",
                 "activity-shell.js"):
        with open(os.path.join(STATIC, name), encoding="utf-8") as f:
            src = f.read()
        assert not re.search(r"\b(confirm|alert)\(", src.replace("confirmDialog(", "")), name
        assert "window.open" not in src, name


def test_activity_script_logs_no_secrets_and_pins_sdk():
    sources = {}
    for name in ("activity-shell.js", "discord-activity.js"):
        with open(os.path.join(STATIC, name), encoding="utf-8") as f:
            sources[name] = f.read()
        src = sources[name]
        assert not re.search(r"console\.(log|info|warn|error|debug)\([^)]*(token|session|code)", src), name
        assert "sessionStorage" not in src, name
    shell, game = sources["activity-shell.js"], sources["discord-activity.js"]
    # only the shell imports the SDK (relative, versioned folder); the game page never does
    imports = re.findall(r"""from\s+["']([^"']+)["']""", shell)
    assert imports == ["./vendor/discord-embedded-app-sdk-2.5.0/index.mjs"]
    assert os.path.exists(os.path.join(STATIC, "vendor", "discord-embedded-app-sdk-2.5.0", "index.mjs"))
    assert "prompt: \"none\"" in shell and 'scope: ["identify"]' in shell
    assert not re.search(r"\bimport\b", game) and "DiscordSDK" not in game and "authorize(" not in game
    # storage: only the shell's language choice, never the session or a token
    assert re.findall(r"localStorage\.setItem\(([^,]+),", shell) == ["LANG_KEY"]
    assert 'const LANG_KEY = "c24_activity_lang";' in shell
    assert "localStorage" not in game
    # the shell never navigates itself (only a reload, after ready() failed)
    for bad in ("location.href =", "location.assign", "location.replace(\"", "window.open", "history.back"):
        assert bad not in shell, bad
    assert shell.count("window.location.reload()") == 1
    # messages between the pages: plain objects (the SDK reads arrays as opcodes)
    assert not re.search(r"postMessage\(\s*\[", shell + game)


# ---------- browser: the Activity with the SDK's own mock ----------

pytest.importorskip("playwright")

SHIM = """
import { DiscordSDKMock } from './mock.mjs';
export * from './index.real.mjs';
export class DiscordSDK extends DiscordSDKMock {
    constructor(clientId) {
        super(clientId, 'g1', 'c1', null);
        window.__calls = window.__calls || [];
        window.__calls.push('construct:' + clientId);
        this.platform = new URLSearchParams(location.search).get('platform') || 'desktop';
        window.__sdk = this;
        const mocks = window.__C24_MOCKS__ || {};
        const wrap = (name, fallback) => async (...args) => {
            window.__calls.push(name);
            window.__args = window.__args || {};
            window.__args[name] = args[0];
            return mocks[name] ? mocks[name](...args) : fallback(...args);
        };
        this._updateCommandMocks({
            authorize: wrap('authorize', () => ({ code: 'mock_code' })),
            authenticate: wrap('authenticate', (a) => ({ access_token: a.access_token,
                user: { id: '1', username: 'x', discriminator: '0', avatar: null, public_flags: 0 },
                scopes: ['identify'], expires: '2099-01-01', application: { id: clientId, description: '', name: 'c24' } })),
            setOrientationLockState: wrap('setOrientationLockState', () => null),
            openExternalLink: wrap('openExternalLink', () => ({ opened: true })),
            openInviteDialog: wrap('openInviteDialog', () => null),
            // default: Discord can't tell its language (an old client): the picker shows
            userSettingsGetLocale: wrap('userSettingsGetLocale', () => { throw new Error('unsupported'); }),
        });
    }
    ready() {
        window.__calls.push('ready');
        return window.__C24_READY_NEVER ? new Promise(() => {}) : Promise.resolve();
    }
    async subscribe(event, listener) {
        window.__calls.push('subscribe:' + event);
        return super.subscribe(event, listener);
    }
}
"""

INIT = """
window.__calls = [];
window.__csp = [];
document.addEventListener('securitypolicyviolation', e => {
    const m = e.violatedDirective + ' ' + e.blockedURI;
    window.__csp.push(m);
    try { if (window.top !== window && window.top.__csp) { window.top.__csp.push('iframe: ' + m); } } catch (err) {}
});
const realFetch = window.fetch;
window.fetch = function (url, opts) {
    if (String(url).indexOf('/api/activity/token') >= 0) { window.__calls.push('token'); }
    return realFetch.apply(this, arguments);
};
"""


def discord_csp(origin):
    """Discord's real proxy CSP (observed 2026-10-28, checklist 4B), with the
    frame-src / child-src lines the proxy also sends (our own discordsays origin,
    here the test server): the shell may frame our own pages."""
    return ("default-src 'self'; script-src 'self' 'unsafe-eval' 'nonce-TEST' blob:; "
            "style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data: https://cdn.discordapp.com "
            "https://media.discordapp.net; font-src 'self' data:; connect-src 'self' https://discord.com "
            "https://cdn.discordapp.com https://media.discordapp.net data: blob:; media-src 'self' blob: data:; "
            f"worker-src 'self' blob:; frame-src {origin}/ https://discord.com/embeds/video-frame; "
            f"child-src {origin}/ blob:")


PNG_1PX = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app, threaded=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def setup_activity(page, server, mocks_js="{}", csp=False, extra_init="", fail_once=()):
    """Route the SDK to the mock shim (and, with csp=True, act like Discord's proxy).
    fail_once: API paths answered 401 the first time (an expired session)."""
    blocked, sdk_loads, api = [], [], []
    failing = set(fail_once)
    real_index = os.path.join(STATIC, "vendor", "discord-embedded-app-sdk-2.5.0", "index.mjs")

    def handle(route):
        url = route.request.url
        parsed = urlparse(url)
        if url.startswith(server):
            if parsed.path == SDK_DIR + "index.mjs":
                sdk_loads.append(url)
                return route.fulfill(body=SHIM, content_type="text/javascript")
            if parsed.path == SDK_DIR + "index.real.mjs":
                return route.fulfill(path=real_index, content_type="text/javascript")
            if parsed.path.startswith("/api/"):
                api.append((parsed.path, parsed.query, route.request.headers.get("authorization", "")))
                if parsed.path in failing:
                    failing.discard(parsed.path)
                    return route.fulfill(status=401, body='{"error": "login"}', content_type="application/json")
            if not csp:
                return route.continue_()
            response = route.fetch(max_redirects=0)  # let the browser follow redirects itself
            if "text/html" in response.headers.get("content-type", ""):
                body = re.sub(r"<script(?![^>]*\bsrc=)", '<script nonce="TEST"', response.text())
                headers = dict(response.headers)
                headers["content-security-policy"] = discord_csp(server)
                headers.pop("content-length", None)
                return route.fulfill(response=response, body=body, headers=headers)
            return route.fulfill(response=response)
        if parsed.hostname in ("cdn.discordapp.com", "media.discordapp.net"):
            return route.fulfill(body=PNG_1PX, content_type="image/png")
        blocked.append(url)
        return route.abort()

    page.route("**/*", handle)
    page.add_init_script(INIT + "window.__C24_MOCKS__ = " + mocks_js + ";" + extra_init)
    return blocked, sdk_loads, api


def game(page):
    """The game page in the shell's iframe (a Playwright Frame; it survives the
    iframe's own navigations, e.g. a language change)."""
    page.wait_for_selector("iframe#c24-game:not([hidden])")
    return page.frame(name="c24-game")


def wait_ready(page, lang="es"):
    """Shell logged in and showing the game in `lang`; the game ready to type."""
    page.wait_for_function("document.documentElement.getAttribute('data-activity') === 'ready'", timeout=10000)
    frame = game(page)
    frame.wait_for_url(f"**/lb/{lang}?embed=1", timeout=10000)
    page.wait_for_function("document.getElementById('c24-activity-overlay').getAttribute('data-state') === 'ready'",
                           timeout=10000)
    frame.wait_for_function("document.documentElement.getAttribute('data-activity') === 'ready'"
                            " && window.Vue && document.querySelector('#app') && document.querySelector('.key')")
    frame.wait_for_function(VM + ".lb_ready === true", timeout=10000)
    return frame


VM = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
BOARD_COLORED = "main .grid-cols-5 > .correct, main .grid-cols-5 > .semicorrect, main .grid-cols-5 > .incorrect"
SDK_COUNT = "window.__calls.filter(c => c.indexOf('construct:') === 0).length"


def calls(page, name):
    return page.evaluate(f"window.__calls.filter(c => c === {json.dumps(name)}).length")


def type_word(frame, word, rows=1):
    # the on-screen keys (as a player in Discord would tap them)
    for ch in word:
        frame.click(f".c24-keyboard .key[data-char='{ch}']")
    frame.click(".c24-keyboard .key[data-char='⇨']")
    frame.wait_for_function(
        f"document.querySelectorAll('{BOARD_COLORED}').length >= {5 * rows} && !document.querySelector('.flip')",
        timeout=8000)


def test_browser_web_never_loads_sdk(lb_env, server, page, discord):
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    for path in ("/", "/es", "/leaderboard", "/es?frame_id=a&instance_id=b&platform=tv"):
        page.goto(server + path)
        page.wait_for_load_state("networkidle")
    assert not [u for u in requests if "discord-activity" in u or "discord-embedded-app-sdk" in u
                or "activity-shell" in u]
    assert page.evaluate("typeof window.C24Activity") == "undefined"


def test_browser_shell_one_sdk_for_the_whole_launch(lb_env, server, page, discord, mem):
    """First launch (Discord's language unknown): picker -> English -> guess -> header "EN ▾" -> Español -> guess
    -> leaderboard window. One SDK, one handshake, one login, the shell never reloads."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    top_navigations = []
    page.on("framenavigated", lambda f: f == page.main_frame and top_navigations.append(f.url))
    _, sdk_loads, api = setup_activity(page, server)
    page.goto(server + "/?" + ACT)  # Discord opens "/": the shell, no redirect
    assert urlparse(page.url).path == "/"
    # first launch, Discord's locale unknown: the picker (fallback)
    page.wait_for_selector("#c24-picker:not([hidden])")
    assert "Elige tu idioma" in page.inner_text("#c24-picker-title")
    assert "Choose your language" in page.inner_text("#c24-picker-title")
    codes = page.eval_on_selector_all("[data-pick-lang]", "els => els.map(e => e.getAttribute('data-pick-lang'))")
    assert codes == list(app.LB_LANGS) == ["es", "en"]
    assert page.is_hidden("#c24-game")
    page.wait_for_function("document.documentElement.getAttribute('data-activity') === 'ready'")
    page.evaluate("window.__top_marker = 42")
    page.click("[data-pick-lang=en]")
    frame = wait_ready(page, "en")
    # the iframe has no Discord params (nothing in it can start the SDK)
    assert parse_qs(urlparse(frame.url).query) == {"embed": ["1"]}
    assert frame.evaluate("typeof window.DiscordSDK") == "undefined"
    assert page.evaluate("localStorage.getItem('c24_activity_lang')") == "en"
    calls_now = page.evaluate("window.__calls")
    order = [c for c in calls_now if c in ("ready", "authorize", "token", "authenticate")]
    assert order == ["ready", "authorize", "token", "authenticate"]
    assert calls_now[0] == "construct:" + CLIENT_ID
    assert page.evaluate("window.__args.authorize") == {
        "client_id": CLIENT_ID, "response_type": "code", "state": "", "prompt": "none", "scope": ["identify"]}
    assert page.evaluate("window.__args.authenticate.access_token") == SECRET_BITS["token"]
    assert "subscribe:ACTIVITY_LAYOUT_MODE_UPDATE" in calls_now
    # the token is nowhere afterwards (the session stays, in memory only)
    leak_check = """tok => {
        const blobs = [JSON.stringify(localStorage), JSON.stringify(sessionStorage), document.cookie,
                       document.documentElement.outerHTML];
        for (const k of Object.keys(window)) { try { const v = window[k];
            if (typeof v === 'string') blobs.push(v); } catch (e) {} }
        try { blobs.push(JSON.stringify(window.C24Activity)); } catch (e) {}
        return blobs.some(b => b && b.indexOf(tok) >= 0);
    }"""
    assert page.evaluate(leak_check, SECRET_BITS["token"]) is False
    assert frame.evaluate(leak_check, SECRET_BITS["token"]) is False
    session = page.evaluate("window.C24Activity.session")
    assert isinstance(session, str) and frame.evaluate("window.C24Activity.session") == session
    assert session not in page.evaluate("JSON.stringify(localStorage)")
    # play in English
    word_en = wrong_words("en", 1)[0]
    type_word(frame, word_en)
    assert mem.get_game(P1, "en", app.lb_today()[0])[0] == [word_en]
    # change language from the header: the window lists the 2, choosing swaps the iframe
    assert frame.inner_text("[data-activity-lang-open] .c24-badge").strip() == "EN ▾"
    frame.click("[data-activity-lang-open]")
    frame.wait_for_selector("[data-activity-langs]", state="visible")
    assert frame.eval_on_selector_all("[data-lang-choice]", "els => els.length") == len(app.LB_LANGS)
    page.keyboard.press("Escape")
    frame.wait_for_selector("[data-activity-langs]", state="hidden")
    frame.click("[data-activity-lang-open]")
    frame.click("[data-lang-choice=es]")
    frame = wait_ready(page, "es")
    assert page.evaluate("localStorage.getItem('c24_activity_lang')") == "es"
    word_es = wrong_words("es", 1)[0]
    type_word(frame, word_es)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word_es]
    # the leaderboard window, inside the game (no page change)
    frame.click("[data-activity-board-open]")
    frame.wait_for_selector("[data-board-table], [data-board-empty]")
    page.keyboard.press("Escape")
    # one SDK, one handshake, one login for everything; the shell was never reloaded
    assert page.evaluate(SDK_COUNT) == 1
    assert calls(page, "ready") == 1 and calls(page, "authorize") == 1
    assert calls(page, "token") == 1 and calls(page, "authenticate") == 1
    assert len(sdk_loads) == 1
    assert page.evaluate("window.__top_marker") == 42
    assert len(top_navigations) == 1 and urlparse(page.url).path == "/"
    # every API call carried the shell's session; none had Discord's params
    assert api and all(h == "Bearer " + session for p, q, h in api if p != "/api/activity/token")
    assert not [q for p, q, h in api if "frame_id" in q]
    assert errors == []


def test_browser_remembered_language_on_relaunch(lb_env, server, page, discord, mem):
    setup_activity(page, server)
    page.goto(server + "/?" + ACT)
    page.click("[data-pick-lang=en]")
    frame = wait_ready(page, "en")
    word = wrong_words("en", 1)[0]
    type_word(frame, word)
    ctx = page.context
    page.close()
    # a new launch (new instance_id), same device: straight to English, the same game,
    # even though Discord now says Spanish (the device's choice wins)
    page2 = ctx.new_page()
    setup_activity(page2, server, mocks_js="{userSettingsGetLocale: () => ({locale: 'es-ES'})}")
    page2.goto(server + "/?frame_id=f2&instance_id=i2&platform=desktop")
    frame = wait_ready(page2, "en")
    assert page2.is_hidden("#c24-picker")
    frame.wait_for_function(f"document.querySelectorAll('{BOARD_COLORED}').length === 5")
    assert frame.evaluate(VM + ".active_row") == 1
    assert page2.evaluate(SDK_COUNT) == 1


@pytest.mark.parametrize("locale, lang", [("es-ES", "es"), ("es-419", "es"), ("en-US", "en"),
                                          ("pt-BR", "en"), ("ko", "en")])
def test_browser_first_launch_follows_discord_locale(lb_env, server, page, discord, mem, locale, lang):
    """Nothing saved on the device: Discord's language picks es (es-*) or en (anything
    else), with no picker; the choice is then saved."""
    setup_activity(page, server, mocks_js="{userSettingsGetLocale: () => ({locale: %s})}" % json.dumps(locale))
    page.goto(server + "/?" + ACT)
    frame = wait_ready(page, lang)
    assert page.is_hidden("#c24-picker")
    assert page.evaluate("localStorage.getItem('c24_activity_lang')") == lang
    calls_now = page.evaluate("window.__calls")
    assert calls_now.index("authenticate") < calls_now.index("userSettingsGetLocale")
    # Invite: the game asks the shell, which opens Discord's invite window (no new scope)
    frame.evaluate("window.C24Activity.invite()")
    page.wait_for_function("window.__calls.indexOf('openInviteDialog') >= 0")
    assert page.evaluate("window.__args.authorize.scope") == ["identify"]


def test_browser_locale_timeout_shows_picker(lb_env, server, page, discord):
    setup_activity(page, server, mocks_js="{userSettingsGetLocale: () => new Promise(() => {})}")
    page.goto(server + "/?" + ACT)
    page.wait_for_selector("#c24-picker:not([hidden])", timeout=10000)
    assert page.eval_on_selector_all("[data-pick-lang]", "els => els.map(e => e.getAttribute('data-pick-lang'))") \
        == ["es", "en"]


def test_browser_bearer_through_the_shell(lb_env, server, page, discord, mem):
    """The game's /api calls carry the shell's session; a 401 -> the shell logs in
    again (silently, same SDK) and the call is retried once."""
    _, _, api = setup_activity(page, server, fail_once=("/api/live",))
    page.goto(server + "/?" + ACT + "&lang=es")
    frame = wait_ready(page)
    session = page.evaluate("window.C24Activity.session")
    statuses = frame.evaluate("""async () => {
        const out = {};
        for (const u of ['/api/state?lang=es', '/api/leaderboard?tab=es', '/api/live?lang=es']) {
            const r = await window.C24Activity.fetch(u, { headers: { 'Accept': 'application/json' } });
            out[u.split('?')[0]] = r.status;
        }
        return out;
    }""")
    assert statuses == {"/api/state": 200, "/api/leaderboard": 200, "/api/live": 200}
    word = wrong_words("es", 1)[0]
    type_word(frame, word)  # POST /api/guess through the shell's session
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word]
    paths = {p for p, q, h in api}
    assert {"/api/state", "/api/guess", "/api/live", "/api/leaderboard"} <= paths
    for p, q, h in api:
        if p != "/api/activity/token":
            assert h.startswith("Bearer "), p
    # the 401 made the shell authorize again (same SDK, no new handshake)
    assert calls(page, "authorize") == 2 and calls(page, "ready") == 1 and page.evaluate(SDK_COUNT) == 1
    assert page.evaluate("window.C24Activity.session") != "" and session


def test_browser_leaderboard_window_and_share(lb_env, server, page, discord, mem):
    for i in range(2):
        pid = f"30000000000000000{i}"
        mem.upsert_player(pid, f"rival{i}")
        app._record_result(mem, pid, "es", app.lb_today()[0], True, 3 + i)
    setup_activity(page, server)
    page.goto(server + "/?" + ACT + "&lang=es")
    frame = wait_ready(page)
    frame.click("[data-activity-board-open]")
    frame.wait_for_selector("[data-board-table] tbody tr")
    assert frame.inner_text("[data-board-table]").count("@rival") == 2
    frame.click("[data-board-tab=all]")
    frame.wait_for_function("document.querySelector('[data-board-tab=all]').classList.contains('is-active')")
    page.keyboard.press("Escape")
    assert not frame.is_visible("[data-activity-board]")
    # share: copy to the clipboard; when that fails, the text in a window (never a new window)
    frame.evaluate("() => { navigator.clipboard.writeText = () => Promise.reject(new Error('blocked')); }")
    opened = []
    page.on("popup", lambda p: opened.append(p))
    frame.evaluate(VM + ".shareResults()")
    frame.wait_for_selector("[data-share-dialog]", state="visible")
    assert frame.input_value("[data-share-text]").startswith("Casa 24 Wordle ES #")
    assert opened == []


def test_browser_refused_then_try_again(lb_env, server, page, discord):
    mocks = """{ authorize: (() => { let n = 0; return () => { n += 1;
        if (n === 1) { return Promise.reject({ code: 5000, message: 'User cancelled' }); }
        return { code: 'mock_code' }; }; })() }"""
    setup_activity(page, server, mocks_js=mocks)
    page.goto(server + "/?" + ACT + "&lang=es")
    page.wait_for_selector("#c24-activity-overlay[data-state=denied]")
    assert page.is_visible("[data-when=denied]") and page.is_visible("[data-activity-retry]")
    assert "Intentar de nuevo / Try again" in page.inner_text("[data-activity-retry]")
    assert page.locator("a[href*='/auth/discord/login']").count() == 0  # no web login inside Discord
    page.evaluate("window.__top_marker = 1")
    page.click("[data-activity-retry]")
    wait_ready(page)
    assert calls(page, "authorize") == 2 and calls(page, "ready") == 1
    assert page.evaluate("window.__top_marker") == 1  # retried in the page, no reload


def test_browser_ready_timeout_shows_error(lb_env, server, page, discord):
    setup_activity(page, server, extra_init="window.__C24_READY_NEVER = true;")
    page.clock.install()
    page.goto(server + "/?" + ACT + "&lang=es")
    page.wait_for_selector("#c24-activity-overlay[data-state=loading]")
    assert page.is_visible("#c24-activity-overlay .c24-step-connect")
    page.clock.run_for(11000)
    page.wait_for_selector("#c24-activity-overlay[data-state=error]")
    assert page.is_visible("[data-activity-retry]")
    assert page.evaluate("window.__calls.indexOf('authorize')") == -1


def test_browser_discord_csp(lb_env, server, page, discord, mem):
    """Discord's proxy CSP (with frame-src) + nonce on inline scripts, on the shell
    and the game iframe: zero violations, nothing loaded from other hosts, and the
    game works (guess, help, stats, theme, leaderboard, language, keyboard layout)."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    blocked, sdk_loads, _ = setup_activity(page, server, csp=True)
    page.goto(server + "/?" + ACT)
    page.click("[data-pick-lang=es]")
    frame = wait_ready(page)
    assert sdk_loads
    csp_header = page.evaluate("""async () => (await fetch('/lb/es?embed=1')).headers.get('content-security-policy')""")
    assert csp_header and "frame-src" in csp_header  # the iframe's page got the proxy's CSP too
    word = wrong_words("es", 1)[0]
    type_word(frame, word)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word]
    frame.click("button[data-help-open]")
    page.keyboard.press("Escape")
    frame.click("button[data-stats-open]")
    page.keyboard.press("Escape")
    frame.click(".c24-header-end .c24-icon-btn:last-child")  # settings
    frame.select_option("[data-theme-select]", "dark")
    assert frame.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.keyboard.press("Escape")
    frame.click("[data-activity-board-open]")
    frame.wait_for_selector("[data-board-table], [data-board-empty]")
    page.keyboard.press("Escape")
    frame.click("[data-activity-lang-open]")
    frame.click("[data-lang-choice=en]")
    frame = wait_ready(page, "en")
    # a keyboard layout change: a GET form inside the iframe (keeps embed=1)
    multi = [c for c in app.LB_LANGS if len(app.keyboards[c]["layouts"]) > 1]
    if multi:
        frame.click("[data-activity-lang-open]")
        frame.click(f"[data-lang-choice={multi[0]}]")
        frame = wait_ready(page, multi[0])
        frame.click(".c24-header-end .c24-icon-btn:last-child")
        other = [k for k in app.keyboards[multi[0]]["layouts"] if k != app.keyboards[multi[0]]["default"]][0]
        frame.select_option("#keyboard-layout-select", other)
        frame.wait_for_url(f"**layout={other}**")
        assert "embed=1" in frame.url and "frame_id" not in frame.url
        frame.wait_for_function("document.documentElement.getAttribute('data-activity') === 'ready'"
                                " && document.querySelector('.key')")
    page.wait_for_timeout(500)  # (the game polls /api/live, so no "networkidle")
    assert page.evaluate("window.__csp") == []
    assert blocked == []
    assert errors == [], errors
    assert page.evaluate(SDK_COUNT) == 1 and calls(page, "authorize") == 1


def test_browser_mobile_layout_pip_and_safe_area(lb_env, browser, server, discord):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        setup_activity(page, server)
        page.goto(server + "/?" + ACT.replace("desktop", "mobile") + "&lang=es")
        frame = wait_ready(page)
        assert page.evaluate("window.__args.setOrientationLockState") == {"lock_state": 2}
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        assert frame.evaluate("document.documentElement.scrollWidth") <= 390
        kb = frame.locator(".c24-keyboard").bounding_box()
        board = frame.locator(".c24-board").bounding_box()
        assert kb["y"] + kb["height"] <= 844 + 1 and board["y"] >= 0 and board["y"] + board["height"] <= kb["y"] + 1
        # Discord's safe-area variables (on the shell) keep the whole game inside them
        page.evaluate("document.documentElement.style.setProperty('--discord-safe-area-inset-bottom', '40px')")
        page.evaluate("document.documentElement.style.setProperty('--discord-safe-area-inset-top', '30px')")
        frame.wait_for_function("window.innerHeight === 844 - 70")
        kb = frame.locator(".c24-keyboard").bounding_box()
        head = frame.locator(".c24-header").bounding_box()
        assert kb["y"] + kb["height"] <= 844 - 40 + 1 and head["y"] >= 30 - 1
        page.evaluate("document.documentElement.style.removeProperty('--discord-safe-area-inset-bottom')")
        page.evaluate("document.documentElement.style.removeProperty('--discord-safe-area-inset-top')")
        # picture-in-picture: the board only
        page.evaluate("window.__sdk.emitEvent('ACTIVITY_LAYOUT_MODE_UPDATE', { layout_mode: 1 })")
        frame.wait_for_function("document.documentElement.classList.contains('c24-pip')")
        assert not frame.is_visible(".c24-keyboard") and not frame.is_visible(".c24-header")
        page.set_viewport_size({"width": 240, "height": 180})
        frame.wait_for_function("window.innerWidth === 240")
        board = frame.locator(".c24-board").bounding_box()
        assert board["width"] > 40 and board["y"] >= 0 and board["y"] + board["height"] <= 180 + 1
        assert board["x"] >= 0 and board["x"] + board["width"] <= 240 + 1
        page.evaluate("window.__sdk.emitEvent('ACTIVITY_LAYOUT_MODE_UPDATE', { layout_mode: 0 })")
        page.set_viewport_size({"width": 390, "height": 844})
        frame.wait_for_function("!document.documentElement.classList.contains('c24-pip')")
        assert frame.is_visible(".c24-keyboard")
        assert page.evaluate(SDK_COUNT) == 1
    finally:
        ctx.close()


ACT_LIVE = [{"username": f"player{i}", "avatar_url": "https://cdn.discordapp.com/embed/avatars/1.png",
             "rows": [["correct", "incorrect", "semicorrect", "incorrect", "incorrect"]],
             "done": False, "won": False, "live": i == 0} for i in range(4)]
SHOTS = os.environ.get("C24_ACT_SHOTS")  # optional folder for screenshots of the desktop layout


def boxes_overlap(a, b):
    return a["x"] < b["x"] + b["width"] - 0.5 and b["x"] < a["x"] + a["width"] - 0.5 \
        and a["y"] < b["y"] + b["height"] - 0.5 and b["y"] < a["y"] + a["height"] - 0.5


def test_browser_desktop_panel_stays_stacked_with_sidebar(lb_env, browser, server, discord):
    """Discord desktop: a wide but short panel (875x400) keeps header / board / keyboard
    stacked (never the landscape side-by-side layout); the live rail shows from
    860px wide at any height, in the left gutter: the game column stays centered in
    the panel (the rail never moves or shrinks it)."""
    ctx = browser.new_context(viewport={"width": 875, "height": 400})
    page = ctx.new_page()
    try:
        setup_activity(page, server)
        page.route("**/api/live?**", lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"players": ACT_LIVE, "count": len(ACT_LIVE)})))
        page.goto(server + "/?" + ACT + "&lang=es")
        frame = wait_ready(page)
        frame.wait_for_function("document.documentElement.classList.contains('c24-plat-desktop')")
        frame.wait_for_selector(".c24-live-card", state="attached")
        for width, height in ((875, 400), (1000, 450), (1280, 600), (1600, 800), (700, 400), (875, 360)):
            page.set_viewport_size({"width": width, "height": height})
            frame.wait_for_function(f"window.innerWidth === {width} && window.innerHeight === {height}")
            frame.wait_for_timeout(50)
            size = f"{width}x{height}"
            assert frame.evaluate("document.documentElement.scrollHeight") <= height, size
            assert frame.evaluate("document.documentElement.scrollWidth") <= width, size
            head = frame.locator("header.c24-header").bounding_box()
            board = frame.locator(".c24-board").bounding_box()
            kb = frame.locator(".c24-keyboard").bounding_box()
            # stacked: header above the board, the board above the keyboard, all on screen
            assert head["y"] + head["height"] <= board["y"] + 0.5, size
            assert kb["y"] >= board["y"] + board["height"] - 0.5, size
            assert kb["y"] + kb["height"] <= height + 0.5, size
            tile = frame.locator("main .grid-cols-5 > div").first.bounding_box()
            assert abs(tile["width"] - tile["height"]) <= 1 and tile["width"] >= 20, size
            keys = frame.evaluate("[...document.querySelectorAll('.c24-keyboard .key')].map(k => "
                                  "{ const r = k.getBoundingClientRect(); return [r.width, r.height]; })")
            assert min(w for w, _ in keys) >= 24 and min(h for _, h in keys) >= 26, size
            sidebar = width >= 860
            assert frame.is_visible("#c24-live") == sidebar, size
            assert frame.is_visible("[data-live-open]") == (not sidebar), size
            if sidebar:
                side = frame.locator("#c24-live").bounding_box()
                assert 150 <= side["width"] <= 280 and side["height"] >= height - 80, size
                for other in (head, board, kb):
                    assert not boxes_overlap(side, other), size
                # the game column stays centered in the panel; the rail sits left of it
                col = frame.locator(".c24-game").bounding_box()
                assert abs(col["x"] + col["width"] / 2 - width / 2) <= 2, size
                assert side["x"] + side["width"] <= col["x"] + 0.5, size
            if SHOTS and size in ("875x400", "1280x600"):
                page.screenshot(path=os.path.join(SHOTS, f"activity-{size}.png"))
        assert page.evaluate(SDK_COUNT) == 1
    finally:
        ctx.close()


def test_browser_website_landscape_unchanged(server, page):
    """The website (no Activity) on a landscape phone still puts the board and the
    keyboard side by side; the Activity's desktop rules never reach it."""
    page.set_viewport_size({"width": 844, "height": 390})
    page.goto(server + "/es")
    page.wait_for_function("window.Vue && document.querySelector('#app') && document.querySelector('.key')")
    assert not page.evaluate("document.documentElement.classList.contains('c24-embed')")
    board = page.locator(".c24-board").bounding_box()
    kb = page.locator(".c24-keyboard").bounding_box()
    assert kb["x"] >= board["x"] + board["width"] - 0.5
    assert kb["y"] < board["y"] + board["height"]
    assert page.evaluate("document.documentElement.scrollHeight") <= 390


def test_browser_picker_small_screens(lb_env, browser, server, discord):
    """The first-launch picker at phone size and in a 240x180 picture-in-picture tile."""
    for size in ({"width": 390, "height": 844}, {"width": 240, "height": 180}):
        ctx = browser.new_context(viewport=size, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        try:
            setup_activity(page, server)
            page.goto(server + "/?" + ACT.replace("desktop", "mobile"))
            page.wait_for_selector("#c24-picker:not([hidden])")
            assert page.evaluate("document.documentElement.scrollWidth") <= size["width"]
            btn = page.locator("[data-pick-lang=es]").bounding_box()
            assert btn["height"] >= 40 and btn["x"] >= 0 and btn["x"] + btn["width"] <= size["width"] + 1
            if size["width"] >= 390:  # the 2 big buttons fit on a phone without scrolling
                last = page.locator("[data-pick-lang]").last.bounding_box()
                assert last["y"] + last["height"] <= size["height"]
            page.locator("[data-pick-lang=en]").scroll_into_view_if_needed()
            page.click("[data-pick-lang=en]")
            wait_ready(page, "en")
        finally:
            ctx.close()


def test_browser_delete_confirm_is_an_in_page_dialog(lb_env, server, page, discord, mem):
    """Web leaderboard page: "Delete my data" asks in a <dialog> (no window.confirm)."""
    ctx = page.context
    c = app.app.test_client()
    login(c, discord)
    ctx.add_cookies([{"name": "c24_lb", "value": c.get_cookie("c24_lb").value, "url": server},
                     {"name": "c24_avr", "value": "1", "url": server}])
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.type), d.dismiss()))
    page.goto(server + "/leaderboard")
    page.click("[data-dc-toggle]")
    page.click("[data-lb-delete]")
    page.wait_for_selector("dialog[data-c24-confirm]")
    page.click("[data-confirm-no]")
    assert mem.get_player(P1) is not None
    page.click("[data-dc-toggle]")
    page.click("[data-lb-delete]")
    page.click("[data-confirm-yes]")
    page.wait_for_url("**/?deleted=1")
    assert mem.get_player(P1) is None
    assert dialogs == []  # never a browser confirm()/alert()


# ---------- browser: typing a guess (physical keyboard / on-screen keys) and sync ----------

ERRS_INIT = """
window.__errs = [];
window.addEventListener('error', e => window.__errs.push(String(e.message)));
window.addEventListener('unhandledrejection', e => window.__errs.push('rejection ' + String(e.reason && e.reason.message)));
"""
COLORED_ROWS = "document.querySelectorAll('" + BOARD_COLORED + "').length"


def wait_rows(frame, rows):
    frame.wait_for_function(f"{COLORED_ROWS} >= {5 * rows} && !document.querySelector('.flip')", timeout=8000)


def guess_posts(api):
    return [h for p, q, h in api if p == "/api/guess"]


def web_page(ctx, server, lang="es"):
    """The website's leaderboard game for P1 (the c24_lb cookie = the same signed ID
    the Activity's Bearer session carries)."""
    ctx.add_cookies([{"name": "c24_lb", "value": session_for(P1), "url": server},
                     {"name": "c24_avr", "value": "1", "url": server}])
    web = ctx.new_page()
    web.goto(server + "/lb/" + lang)
    web.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")
    return web


def force_sync(target):
    # what a focus / visible-tab event does after the 5 s gap: GET /api/state and repaint
    target.evaluate("SYNC.at = 0; window.dispatchEvent(new Event('focus'))")


def test_browser_physical_keyboard_with_focus_on_the_shell_or_the_game(lb_env, server, page, discord, mem):
    """Regression (2026-10-29): a word typed on the computer's keyboard was never sent
    (no POST /api/guess) when focus was on the shell document (a click on the overlay,
    picker or safe-area margin) instead of the game iframe: game.js listens on the
    iframe's window. The shell now passes keys on and moves focus into the game."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _, _, api = setup_activity(page, server, extra_init=ERRS_INIT)
    page.goto(server + "/?" + ACT)
    page.click("[data-pick-lang=es]")  # a click in the shell: focus is on the shell document
    frame = wait_ready(page)
    session = page.evaluate("window.C24Activity.session")
    w1, w2, w3 = wrong_words("es", 3)
    # 1) focus on the shell (not in the iframe): typing still reaches the board
    page.evaluate("document.activeElement && document.activeElement.blur(); window.focus()")
    assert frame.evaluate("document.hasFocus()") is False
    page.keyboard.type(w1)
    assert frame.evaluate(VM + ".tiles[0].join('')") == w1
    page.keyboard.press("Enter")
    wait_rows(frame, 1)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [w1]
    assert frame.evaluate("document.hasFocus()") is True  # the next keys go straight to the game
    # 2) focus inside the iframe (a click on the board), typed in CAPITALS
    frame.click(".c24-board")
    page.keyboard.type(w2.upper())
    page.keyboard.press("Enter")
    wait_rows(frame, 2)
    # 3) typed before the first state from the server (lb_ready false): not dropped
    frame.evaluate(VM + ".lb_ready = false")
    page.keyboard.type(w3)
    page.keyboard.press("Enter")
    wait_rows(frame, 3)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [w1, w2, w3]
    posts = guess_posts(api)
    assert posts == ["Bearer " + session] * 3
    assert errors == [] and page.evaluate("window.__errs") == [] and frame.evaluate("window.__errs") == []


def test_browser_on_screen_keys_and_both_sync_directions(lb_env, server, page, discord, mem):
    """On-screen keys (incl. ⇨) send the guess; Activity -> web (cookie login, same
    rows), web -> Activity (a relaunch shows the web's rows), and with both open a
    guess on one side shows on the other after a focus; a stale row is a 409 that
    repaints the server's game (nothing saved twice, nothing lost)."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _, _, api = setup_activity(page, server, extra_init=ERRS_INIT)
    page.goto(server + "/?" + ACT + "&lang=es")
    frame = wait_ready(page)
    w1, w2, w3, w4, w5 = wrong_words("es", 5)
    type_word(frame, w1)  # on-screen letters + ⇨
    assert guess_posts(api) == ["Bearer " + page.evaluate("window.C24Activity.session")]
    day = app.lb_today()[0]
    assert mem.get_game(P1, "es", day)[0] == [w1]
    # Activity -> web: the website shows the same row
    ctx = page.context
    web = web_page(ctx, server)
    web.wait_for_function(f"{COLORED_ROWS} === 5")
    assert web.evaluate(VM + ".tiles[0].join('')") == w1 and web.evaluate(VM + ".active_row") == 1
    # web -> Activity, both open: a guess on the web shows in the Activity after a focus
    for ch in w2:
        web.click(f".c24-keyboard .key[data-char='{ch}']")
    web.click(".c24-keyboard .key[data-char='⇨']")
    web.wait_for_function(f"{COLORED_ROWS} >= 10 && !document.querySelector('.flip')")
    assert mem.get_game(P1, "es", day)[0] == [w1, w2]
    force_sync(frame)
    wait_rows(frame, 2)
    assert frame.evaluate(VM + ".tiles[1].join('')") == w2 and frame.evaluate(VM + ".active_row") == 2
    # Activity -> web, both open
    type_word(frame, w3, rows=3)
    force_sync(web)
    web.wait_for_function(f"{COLORED_ROWS} >= 15 && !document.querySelector('.flip')")
    assert web.evaluate(VM + ".tiles[2].join('')") == w3
    # a stale side (the web missed a guess made in the Activity): 409 -> repaint, no double save
    frame.click(".c24-board")
    page.keyboard.type(w4)
    page.keyboard.press("Enter")
    wait_rows(frame, 4)
    for ch in w5:
        web.click(f".c24-keyboard .key[data-char='{ch}']")  # web still shows 3 rows: attempt 3
    web.click(".c24-keyboard .key[data-char='⇨']")
    web.wait_for_function(f"{COLORED_ROWS} >= 20 && !document.querySelector('.flip')")
    assert web.evaluate(VM + ".tiles[3].join('')") == w4 and web.evaluate(VM + ".active_row") == 4
    assert mem.get_game(P1, "es", day)[0] == [w1, w2, w3, w4]
    # relaunch the Activity: the server's rows on load
    web.close()
    page.close()
    page2 = ctx.new_page()
    setup_activity(page2, server)
    page2.goto(server + "/?frame_id=f2&instance_id=i2&platform=desktop")
    frame2 = wait_ready(page2)
    wait_rows(frame2, 4)
    assert [frame2.evaluate(VM + f".tiles[{r}].join('')") for r in range(4)] == [w1, w2, w3, w4]
    assert frame2.evaluate(VM + ".active_row") == 4
    assert errors == []


def test_browser_web_guess_then_activity_launch(lb_env, server, browser, discord, mem):
    """web -> Activity: a guess made on the website first; the Activity's first state shows it."""
    ctx = browser.new_context()
    try:
        mem.upsert_player(P1, "x")
        web = web_page(ctx, server)
        word = wrong_words("es", 1)[0]
        for ch in word:
            web.click(f".c24-keyboard .key[data-char='{ch}']")
        web.click(".c24-keyboard .key[data-char='⇨']")
        web.wait_for_function(f"{COLORED_ROWS} >= 5 && !document.querySelector('.flip')")
        assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word]
        page = ctx.new_page()
        setup_activity(page, server)
        page.goto(server + "/?" + ACT + "&lang=es")
        frame = wait_ready(page)
        wait_rows(frame, 1)
        assert frame.evaluate(VM + ".tiles[0].join('')") == word and frame.evaluate(VM + ".active_row") == 1
    finally:
        ctx.close()


def test_browser_guess_error_is_shown_and_logged(lb_env, server, page, discord, mem):
    """A guess the server can't take: a toast for the player, a line in Discord's console
    (through the shell), and the game keeps working."""
    logs = []
    page.on("console", lambda m: logs.append(m.text))
    setup_activity(page, server)
    page.goto(server + "/?" + ACT + "&lang=es")
    frame = wait_ready(page)
    page.route("**/api/guess", lambda r: r.fulfill(status=500, body="{}", content_type="application/json"))
    w1 = wrong_words("es", 1)[0]
    frame.click(".c24-board")
    page.keyboard.type(w1)
    page.keyboard.press("Enter")
    frame.wait_for_function(VM + ".notification.show === true")
    assert frame.evaluate(VM + ".lb_busy") is False
    page.wait_for_function("true")
    assert any("Casa 24 game: guess not saved" in t for t in logs), logs
    page.unroute("**/api/guess")
    page.keyboard.press("Enter")  # the same word again, now saved
    wait_rows(frame, 1)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [w1]


def test_vendored_sdk_fully_tracked():
    """Every module the vendored Discord SDK imports must be committed to git.

    Regression: the Python `lib/` rule in .gitignore once hid the SDK's bundled
    dependencies (lib/tslib, lib/uuid, ...); they existed locally but 404'd on
    Vercel, so the Activity never connected.
    """
    import pathlib
    import re
    import subprocess

    root = pathlib.Path(__file__).resolve().parents[1]
    sdk = root / "webapp" / "static" / "vendor"
    tracked = set(subprocess.run(
        ["git", "ls-files", "webapp/static/vendor"], cwd=root,
        capture_output=True, text=True, check=True).stdout.split())
    spec = re.compile(r"""(?:import|export)[^'"]*?from\s*['"](\.[^'"]+)['"]|import\s*\(\s*['"](\.[^'"]+)['"]""")
    missing = []
    for mod in sdk.rglob("*.mjs"):
        for m in spec.finditer(mod.read_text(encoding="utf-8")):
            target = (mod.parent / (m.group(1) or m.group(2))).resolve()
            rel = target.relative_to(root).as_posix()
            if rel not in tracked:
                missing.append(f"{mod.relative_to(root).as_posix()} -> {rel}")
    assert not missing, "vendored SDK imports files that are not in git:\n" + "\n".join(missing[:20])
    ignored = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "webapp/static/vendor"],
        cwd=root, capture_output=True, text=True, check=True).stdout.split()
    assert not ignored, f"git ignores vendored files: {ignored[:10]}"


def test_browser_settings_legal_links_and_delete_my_data(lb_env, server, page, discord, mem, monkeypatch):
    """Discord's Developer Policy: privacy policy reachable and data deletion easy from
    inside the app. Terms / Privacy open through the SDK's openExternalLink (via the
    shell); "Delete my data" posts with the Bearer session; the shell never navigates."""
    monkeypatch.setenv("PUBLIC_URL", "https://casa-24-wordle.vercel.app")
    setup_activity(page, server)
    page.goto(server + "/?" + ACT + "&lang=es")
    frame = wait_ready(page)
    shell_url = page.url
    assert mem.get_player(P1) is not None
    frame.evaluate(VM + ".show_options_modal = true")
    frame.wait_for_selector("[data-legal-links] a[href*='/privacy']", state="visible")
    frame.click("[data-legal-links] a[href*='/privacy']")
    page.wait_for_function("window.__calls.indexOf('openExternalLink') >= 0")
    assert page.evaluate("window.__args.openExternalLink") == {"url": "https://casa-24-wordle.vercel.app/privacy?lang=es"}
    frame.click("[data-legal-links] a[href*='/terms']")
    page.wait_for_function("window.__args.openExternalLink.url.indexOf('/terms') > 0")
    assert page.evaluate("window.__args.openExternalLink.url") == "https://casa-24-wordle.vercel.app/terms?lang=es"
    assert frame.url.endswith("/lb/es?embed=1") and page.url == shell_url  # nothing navigated
    # delete my data: in-page confirm, then POST with the Bearer session
    frame.click("[data-activity-delete] button")
    frame.wait_for_selector("[data-c24-confirm] [data-confirm-yes]", state="visible")
    frame.click("[data-c24-confirm] [data-confirm-yes]")
    page.wait_for_function("document.getElementById('c24-activity-overlay').getAttribute('data-state') === 'deleted'")
    assert mem.get_player(P1) is None and P1 not in all_store_text(mem)
    assert page.is_visible("[data-activity-again]") and not page.is_visible("[data-activity-retry]")
    assert page.url == shell_url and page.evaluate(SDK_COUNT) == 1
    # play again: signs in again on the same SDK (a new, empty account)
    page.click("[data-activity-again]")
    page.wait_for_function("document.getElementById('c24-activity-overlay').getAttribute('data-state') === 'ready'")
    assert mem.get_player(P1) is not None and page.evaluate(SDK_COUNT) == 1 and page.url == shell_url
