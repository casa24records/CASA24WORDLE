"""Discord Activity layer (the game inside Discord).

Server: detection by frame_id / instance_id / platform, "/" and guest pages
redirect to the leaderboard game keeping Discord's query, POST
/api/activity/token (fake Discord: no redirect_uri, nothing stored but ID,
username and avatar hash, token never stored or logged), the Bearer session on
/api/state, /api/guess, /api/live, /api/leaderboard and /api/me/delete, the
discordsays.com origin, and no inline JS anywhere (the Activity's CSP).
The web without those params must stay exactly as it was.

Browser (Playwright): the vendored SDK module is swapped for a shim around the
SDK's own DiscordSDKMock (docs/discord-activity-checklist.md section 4A); the
real Flask app answers everything else with an in-memory store and fake Discord.
One test repeats Discord's real CSP (section 4B) with the proxy's nonce.
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
])
def test_activity_detection(query, expected):
    with app.app.test_request_context("/lb/es?" + query):
        assert app.is_activity() is expected
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

ACTIVITY_MARKERS = ("discord-activity.js", "discord-embedded-app-sdk", 'id="c24-activity"', "data-activity-")


def test_web_pages_have_no_activity_code(lb_env, client, discord):
    pages = ["/", "/es", "/en", "/ko", "/leaderboard", "/es?frame_id=a&instance_id=b&platform=tv"]
    for path in pages:
        html = client.get(path).get_data(as_text=True)
        assert not [m for m in ACTIVITY_MARKERS if m in html], path
    login(client, discord)
    for path in pages + ["/lb/es", "/lb/ar", "/leaderboard?tab=es"]:
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

def test_root_redirects_to_lb_game_keeping_query(lb_env, client):
    r = client.get("/?" + ACT)
    assert r.status_code == 302 and r.headers["Cache-Control"] == "no-store"
    loc = urlparse(r.headers["Location"])
    assert loc.path == "/lb/es"
    q = parse_qs(loc.query)
    assert {k: v[0] for k, v in q.items() if k in ACT_PARAMS} == ACT_PARAMS
    assert q["c24_root"] == ["1"]  # game.js may switch to the device's last language
    r = client.get("/?" + ACT + "&lang=ko")
    loc = urlparse(r.headers["Location"])
    assert loc.path == "/lb/ko" and "c24_root" not in parse_qs(loc.query)
    r = client.get("/?" + ACT + "&lang=xx")
    assert urlparse(r.headers["Location"]).path == "/lb/es"


def test_no_guest_game_inside_activity(lb_env, client):
    r = client.get("/de?" + ACT)
    assert r.status_code == 302
    loc = urlparse(r.headers["Location"])
    assert loc.path == "/lb/de" and parse_qs(loc.query)["frame_id"] == ["f1"]
    r = client.get("/nope?" + ACT)
    assert r.status_code == 302 and "frame_id=f1" in r.headers["Location"]


def test_activity_game_page(lb_env, client, rendered):
    r = client.get("/lb/es?" + ACT)
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    html = r.get_data(as_text=True)
    assert 'type="module" src="/static/discord-activity.js?v=' in html
    data = json.loads(re.search(r'id="c24-activity">(.*?)</script>', html).group(1))
    assert data["client_id"] == CLIENT_ID and data["lang"] == "es" and "ko" in data["langs"]
    assert "fake-client-secret" not in html
    page = json.loads(re.search(r'id="c24-page">(.*?)</script>', html).group(1))
    assert page["activity"] is True and page["lb"] is True and page["todays_word"] == ""
    assert rendered[-1][1]["lb_state"] is None  # no state in the page: game.js asks /api/state after login
    # no login / logout / guest / Developer view inside Discord
    for absent in ("/auth/discord/login", "/auth/logout", "data-dc-toggle", "data-guest-toggle",
                   "c24-demo-bar", "data-demo", "data-dc-login"):
        assert absent not in html, absent
    # every internal link keeps Discord's query
    assert re.search(r'<a href="/\?frame_id=f1&amp;instance_id=i1&amp;platform=desktop', html)
    options = re.findall(r'<option value="(/lb/[a-z]{2}\?[^"]*)"', html)
    assert len(options) == len(app.LB_LANGS) and all("frame_id=f1" in o and "instance_id=i1" in o for o in options)
    hidden = dict(re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)">', html))
    if any(len(app.keyboards[c]["layouts"]) > 1 for c in ["es"]):
        assert hidden.get("frame_id") == "f1"
    # cookies are not touched inside the Activity
    assert not r.headers.getlist("Set-Cookie")


def test_activity_page_with_layout_form_keeps_query(lb_env, client):
    multi = [c for c in app.LB_LANGS if len(app.keyboards[c]["layouts"]) > 1]
    if not multi:
        pytest.skip("no language with two keyboard layouts")
    html = client.get(f"/lb/{multi[0]}?" + ACT).get_data(as_text=True)
    form = re.search(r'<form method="get"[^>]*>(.*?)</form>', html, re.S).group(1)
    assert '<input type="hidden" name="frame_id" value="f1">' in form
    assert '<input type="hidden" name="platform" value="desktop">' in form
    assert "data-autosubmit" in form and "onchange" not in form


def test_leaderboard_page_inside_activity_is_public_and_keeps_query(lb_env, client, discord):
    login(client, discord)  # even with a web cookie, the Activity page shows no account
    html = client.get("/leaderboard?tab=es&" + ACT).get_data(as_text=True)
    assert "/auth/logout" not in html and "/api/me/delete" not in html and "data-dc-login" not in html
    tabs = re.findall(r'<a href="(/leaderboard\?tab=[a-z]+[^"]*)"', html)
    assert tabs and all("frame_id=f1" in t for t in tabs)


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
    assert r.status_code == 302 and mem.get_player(P1) is None


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
    for path in ["/", "/es", "/ar", "/ko", "/leaderboard", "/demo", "/sitemap.xml",
                 "/lb/es?" + ACT, "/lb/ko?" + ACT, "/leaderboard?tab=es&" + ACT]:
        pages[path] = client.get(path).get_data(as_text=True)
    login(client, discord)
    app._record_result(app.lb_store(), P1, "es", app.lb_today()[0], True, 3)
    client.post("/demo", data={"password": "demo-pass-test"})
    for path in ["/", "/lb/es", "/lb/ar", "/leaderboard?tab=es", "/demo/es", "/?login=failed", "/?deleted=1"]:
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
    for name in ("game.js", "index.js", "discord.js", "theme.js", "leaderboard.js", "discord-activity.js"):
        with open(os.path.join(STATIC, name), encoding="utf-8") as f:
            src = f.read()
        assert not re.search(r"\b(confirm|alert)\(", src.replace("confirmDialog(", "")), name
        assert "window.open" not in src, name


def test_activity_script_logs_no_secrets_and_pins_sdk():
    with open(os.path.join(STATIC, "discord-activity.js"), encoding="utf-8") as f:
        src = f.read()
    assert not re.search(r"console\.(log|info|warn|error|debug)\([^)]*(token|session|code)", src)
    assert not re.search(r"(localStorage|sessionStorage)\.setItem", src)
    imports = re.findall(r"""from\s+["']([^"']+)["']""", src)
    assert imports == ["./vendor/discord-embedded-app-sdk-2.5.0/index.mjs"]  # relative, versioned folder
    assert os.path.exists(os.path.join(STATIC, "vendor", "discord-embedded-app-sdk-2.5.0", "index.mjs"))
    assert "prompt: \"none\"" in src and 'scope: ["identify"]' in src


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
document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
const realFetch = window.fetch;
window.fetch = function (url, opts) {
    if (String(url).indexOf('/api/activity/token') >= 0) { window.__calls.push('token'); }
    return realFetch.apply(this, arguments);
};
"""

# Discord's real proxy CSP (observed 2026-10-28, checklist 4B); 'self' = the test server
CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval' 'nonce-TEST' blob:; "
       "style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data: https://cdn.discordapp.com "
       "https://media.discordapp.net; font-src 'self' data:; connect-src 'self' https://discord.com "
       "https://cdn.discordapp.com https://media.discordapp.net data: blob:; media-src 'self' blob: data:; "
       "worker-src 'self' blob:")
PNG_1PX = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


@pytest.fixture(scope="module")
def server():
    srv = make_server("127.0.0.1", 0, app.app, threaded=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def setup_activity(page, server, mocks_js="{}", csp=False, extra_init=""):
    """Route the SDK to the mock shim (and, with csp=True, act like Discord's proxy)."""
    blocked, sdk_loads = [], []
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
            if not csp:
                return route.continue_()
            response = route.fetch(max_redirects=0)  # let the browser follow redirects itself
            if "text/html" in response.headers.get("content-type", ""):
                body = re.sub(r"<script(?![^>]*\bsrc=)", '<script nonce="TEST"', response.text())
                headers = dict(response.headers)
                headers["content-security-policy"] = CSP
                headers.pop("content-length", None)
                return route.fulfill(response=response, body=body, headers=headers)
            return route.fulfill(response=response)
        if parsed.hostname in ("cdn.discordapp.com", "media.discordapp.net"):
            return route.fulfill(body=PNG_1PX, content_type="image/png")
        blocked.append(url)
        return route.abort()

    page.route("**/*", handle)
    page.add_init_script(INIT + "window.__C24_MOCKS__ = " + mocks_js + ";" + extra_init)
    return blocked, sdk_loads


def wait_ready(page):
    page.wait_for_function("document.documentElement.getAttribute('data-activity') === 'ready'", timeout=10000)
    page.wait_for_function("document.querySelector('#app') && window.Vue && document.querySelector('.key')")


BOARD_COLORED = "main .grid-cols-5 > .correct, main .grid-cols-5 > .semicorrect, main .grid-cols-5 > .incorrect"


def type_word(page, word):
    # the on-screen keys (as a player in Discord would tap them)
    for ch in word:
        page.click(f".c24-keyboard .key[data-char='{ch}']")
    page.click(".c24-keyboard .key[data-char='⇨']")
    page.wait_for_function(
        f"document.querySelectorAll('{BOARD_COLORED}').length >= 5 && !document.querySelector('.flip')",
        timeout=8000)


def test_browser_web_never_loads_sdk(lb_env, server, page, discord):
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    for path in ("/", "/es", "/leaderboard", "/es?frame_id=a&instance_id=b&platform=tv"):
        page.goto(server + path)
        page.wait_for_load_state("networkidle")
    assert not [u for u in requests if "discord-activity" in u or "discord-embedded-app-sdk" in u]
    assert page.evaluate("typeof window.C24Activity") == "undefined"


def test_browser_activity_auto_login_and_guess(lb_env, server, page, discord, mem):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    setup_activity(page, server)
    page.goto(server + "/?" + ACT)  # Discord opens "/" -> /lb/es
    wait_ready(page)
    assert urlparse(page.url).path == "/lb/es"
    q = parse_qs(urlparse(page.url).query)
    assert {k: v[0] for k, v in q.items()} == ACT_PARAMS  # c24_root dropped, Discord's params kept
    calls = page.evaluate("window.__calls")
    order = [c for c in calls if c in ("ready", "authorize", "token", "authenticate")]
    assert order == ["ready", "authorize", "token", "authenticate"]
    assert calls[0] == "construct:" + CLIENT_ID
    assert page.evaluate("window.__args.authorize") == {
        "client_id": CLIENT_ID, "response_type": "code", "state": "", "prompt": "none", "scope": ["identify"]}
    assert page.evaluate("window.__args.authenticate.access_token") == SECRET_BITS["token"]
    assert "subscribe:ACTIVITY_LAYOUT_MODE_UPDATE" in calls
    assert not page.is_visible("#c24-activity-overlay")
    # the token is nowhere in the page afterwards (the session stays, in memory only)
    leaked = page.evaluate("""tok => {
        const blobs = [JSON.stringify(localStorage), JSON.stringify(sessionStorage), document.cookie,
                       document.documentElement.outerHTML];
        for (const k of Object.keys(window)) { try { const v = window[k];
            if (typeof v === 'string') blobs.push(v); } catch (e) {} }
        try { blobs.push(JSON.stringify(window.C24Activity)); } catch (e) {}
        return blobs.some(b => b && b.indexOf(tok) >= 0);
    }""", SECRET_BITS["token"])
    assert leaked is False
    assert page.evaluate("typeof window.C24Activity.session") == "string"
    assert page.evaluate("JSON.stringify(localStorage)").find(page.evaluate("window.C24Activity.session")) < 0
    # play one guess: the server colors and keeps it
    word = wrong_words("es", 1)[0]
    type_word(page, word)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word]
    # a new launch (new instance_id) continues the same game from the server
    page.goto(server + "/lb/es?frame_id=f2&instance_id=i2&platform=desktop")
    wait_ready(page)
    page.wait_for_function(f"document.querySelectorAll('{BOARD_COLORED}').length === 5")
    vm = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
    assert page.evaluate(vm + ".active_row") == 1
    # language window: options keep Discord's query; choosing one navigates with it
    page.click("button[aria-label='Settings'], button[aria-label='Ajustes'], .c24-header-end .c24-icon-btn:last-child")
    page.select_option("[data-activity-lang]", index=list(app.LB_LANGS).index("en"))
    page.wait_for_url("**/lb/en?**")
    assert parse_qs(urlparse(page.url).query)["instance_id"] == ["i2"]
    wait_ready(page)
    assert errors == []


def test_browser_last_language_on_relaunch(lb_env, server, page, discord):
    setup_activity(page, server, extra_init="try { localStorage.setItem('casa24_lang', 'ko'); } catch (e) {}")
    page.goto(server + "/?" + ACT)
    page.wait_for_url("**/lb/ko?**")
    wait_ready(page)
    assert "c24_root" not in page.url and "frame_id=f1" in page.url


def test_browser_leaderboard_window_and_share(lb_env, server, page, discord, mem):
    for i in range(2):
        pid = f"30000000000000000{i}"
        mem.upsert_player(pid, f"rival{i}")
        app._record_result(mem, pid, "es", app.lb_today()[0], True, 3 + i)
    setup_activity(page, server)
    page.goto(server + "/lb/es?" + ACT)
    wait_ready(page)
    page.click("[data-activity-board-open]")
    page.wait_for_selector("[data-board-table] tbody tr")
    assert page.inner_text("[data-board-table]").count("@rival") == 2
    page.click("[data-board-tab=all]")
    page.wait_for_function("document.querySelector('[data-board-tab=all]').classList.contains('is-active')")
    page.keyboard.press("Escape")
    assert not page.is_visible("[data-activity-board]")
    # share: copy to the clipboard; when that fails, the text in a window (never a new window)
    page.evaluate("() => { navigator.clipboard.writeText = () => Promise.reject(new Error('blocked')); }")
    opened = []
    page.on("popup", lambda p: opened.append(p))
    vm = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
    page.evaluate(vm + ".shareResults()")
    page.wait_for_selector("[data-share-dialog]", state="visible")
    assert page.input_value("[data-share-text]").startswith("Casa 24 Wordle ES #")
    assert opened == []


def test_browser_refused_then_try_again(lb_env, server, page, discord):
    mocks = """{ authorize: (() => { let n = 0; return () => { n += 1;
        if (n === 1) { return Promise.reject({ code: 5000, message: 'User cancelled' }); }
        return { code: 'mock_code' }; }; })() }"""
    setup_activity(page, server, mocks_js=mocks)
    page.goto(server + "/lb/es?" + ACT)
    page.wait_for_selector("#c24-activity-overlay[data-state=denied]")
    assert page.is_visible("[data-when=denied]") and page.is_visible("[data-activity-retry]")
    assert "Intentar de nuevo / Try again" in page.inner_text("[data-activity-retry]")
    assert page.locator("a[href*='/auth/discord/login']").count() == 0  # no web login inside Discord
    page.click("[data-activity-retry]")
    wait_ready(page)
    assert page.evaluate("window.__calls.filter(c => c === 'authorize').length") == 2
    assert page.evaluate("window.__calls.filter(c => c === 'ready').length") == 1


def test_browser_ready_timeout_shows_error(lb_env, server, page, discord):
    setup_activity(page, server, extra_init="window.__C24_READY_NEVER = true;")
    page.clock.install()
    page.goto(server + "/lb/es?" + ACT)
    page.wait_for_selector("#c24-activity-overlay[data-state=loading]")
    page.clock.run_for(11000)
    page.wait_for_selector("#c24-activity-overlay[data-state=error]")
    assert page.is_visible("[data-activity-retry]")
    assert page.evaluate("window.__calls.indexOf('authorize')") == -1


def test_browser_discord_csp(lb_env, server, page, discord, mem):
    """Discord's proxy CSP + nonce on inline scripts: zero violations, nothing
    loaded from other hosts, and the game works (guess, help, stats, theme, layout)."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    blocked, sdk_loads = setup_activity(page, server, csp=True)
    page.goto(server + "/?" + ACT)
    wait_ready(page)
    assert sdk_loads
    word = wrong_words("es", 1)[0]
    type_word(page, word)
    assert mem.get_game(P1, "es", app.lb_today()[0])[0] == [word]
    page.click("button[aria-label='instructions']")
    page.keyboard.press("Escape")
    page.click("button[aria-label='stats']")
    page.keyboard.press("Escape")
    page.click(".c24-header-end .c24-icon-btn:last-child")  # settings
    page.select_option("[data-theme-select]", "dark")
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.keyboard.press("Escape")
    page.click("[data-activity-board-open]")
    page.wait_for_selector("[data-board-table], [data-board-empty]")
    page.keyboard.press("Escape")
    # a page with a keyboard layout form, through the form (keeps Discord's query)
    multi = [c for c in app.LB_LANGS if len(app.keyboards[c]["layouts"]) > 1]
    if multi:
        page.goto(server + f"/lb/{multi[0]}?" + ACT)
        wait_ready(page)
        page.click(".c24-header-end .c24-icon-btn:last-child")
        other = [k for k in app.keyboards[multi[0]]["layouts"] if k != app.keyboards[multi[0]]["default"]][0]
        page.select_option("#keyboard-layout-select", other)
        page.wait_for_url(f"**layout={other}**")
        assert "frame_id=f1" in page.url
        wait_ready(page)
    page.goto(server + "/leaderboard?tab=es&" + ACT)
    page.click("[data-theme-toggle]")
    page.wait_for_load_state("networkidle")
    assert page.evaluate("window.__csp") == []
    assert blocked == []
    assert errors == [], errors


def test_browser_mobile_layout_pip_and_safe_area(lb_env, browser, server, discord):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        setup_activity(page, server)
        page.goto(server + "/lb/es?" + ACT.replace("desktop", "mobile"))
        wait_ready(page)
        assert page.evaluate("window.__args.setOrientationLockState") == {"lock_state": 2}
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        kb = page.locator(".c24-keyboard").bounding_box()
        board = page.locator(".c24-board").bounding_box()
        assert kb["y"] + kb["height"] <= 844 + 1 and board["y"] >= 0 and board["y"] + board["height"] <= kb["y"] + 1
        # Discord's safe-area variable moves the keyboard up
        pad = "parseFloat(getComputedStyle(document.querySelector('.c24-keyboard')).paddingBottom)"
        before = page.evaluate(pad)
        page.evaluate("document.documentElement.style.setProperty('--discord-safe-area-inset-bottom', '40px')")
        assert page.evaluate(pad) >= 40 and page.evaluate(pad) != before
        # picture-in-picture: the board only
        page.evaluate("window.__sdk.emitEvent('ACTIVITY_LAYOUT_MODE_UPDATE', { layout_mode: 1 })")
        page.wait_for_function("document.documentElement.classList.contains('c24-pip')")
        assert not page.is_visible(".c24-keyboard") and not page.is_visible(".c24-header")
        page.set_viewport_size({"width": 240, "height": 180})
        board = page.locator(".c24-board").bounding_box()
        assert board["width"] > 40 and board["y"] >= 0 and board["y"] + board["height"] <= 180 + 1
        assert board["x"] >= 0 and board["x"] + board["width"] <= 240 + 1
        page.evaluate("window.__sdk.emitEvent('ACTIVITY_LAYOUT_MODE_UPDATE', { layout_mode: 0 })")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_function("!document.documentElement.classList.contains('c24-pip')")
        assert page.is_visible(".c24-keyboard")
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
