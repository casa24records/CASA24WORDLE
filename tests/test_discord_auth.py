"""Discord login with a fake Discord: only the ID goes in the cookie, only the
username goes in the store; tokens, avatar, email etc. are dropped."""

from urllib.parse import parse_qs, urlparse

import app
from lb_testlib import (  # noqa: F401 (fixtures)
    SECRET_BITS, all_store_text, client, decode_lb_cookie, discord, lb_env, login, mem, today,
)

USER_ID = "100000000000000001"


def test_login_redirects_to_discord_with_identify_only(lb_env, client):
    r = client.get("/auth/discord/login?next=/lb/en", base_url="https://wordle.example")
    assert r.status_code == 302
    url = urlparse(r.headers["Location"])
    assert (url.scheme, url.netloc, url.path) == ("https", "discord.com", "/oauth2/authorize")
    q = parse_qs(url.query)
    assert q["scope"] == ["identify"]
    assert q["response_type"] == ["code"]
    assert q["client_id"] == ["123456789"]
    assert q["prompt"] == ["none"]
    assert q["redirect_uri"] == ["https://wordle.example/auth/discord/callback"]
    assert len(q["state"][0]) >= 32
    cookie = r.headers["Set-Cookie"]
    assert cookie.startswith("c24_oauth=")
    for flag in ("HttpOnly", "Secure", "SameSite=Lax", "Max-Age=600"):
        assert flag in cookie


def test_login_flow_keeps_only_id_and_username(lb_env, client, discord, mem):
    r = login(client, discord)
    assert r.status_code == 302
    assert r.headers["Location"] == "/lb/es"
    set_cookies = r.headers.getlist("Set-Cookie")
    lb_cookie = [c for c in set_cookies if c.startswith("c24_lb=")][0]
    for flag in ("HttpOnly", "SameSite=Lax", "Max-Age=2592000"):
        assert flag in lb_cookie
    value = client.get_cookie("c24_lb").value
    assert decode_lb_cookie(value) == USER_ID  # the cookie holds only the ID

    # the store has just the username for this player
    assert mem.players == {USER_ID: {"username": "kolo_fan", "hidden": False}}
    assert not mem.results and not mem.games and not mem.rate
    everything = all_store_text(mem) + "\n" + "\n".join(set_cookies)
    for bit in SECRET_BITS.values():
        assert bit not in everything, bit
    for word in ("avatar", "email", "banner", "global_name", "token", "locale"):
        assert word not in all_store_text(mem)
    assert ("token", "fake-code", "http://localhost/auth/discord/callback") in discord.calls


def test_logged_in_user_in_templates(lb_env, client, discord):
    login(client, discord)
    r = client.get("/lb/es")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"


def test_bad_state_fails(lb_env, client, discord, mem):
    client.get("/auth/discord/login")
    r = client.get("/auth/discord/callback?code=x&state=wrong")
    assert r.status_code == 302 and r.headers["Location"] == "/?login=failed"
    assert client.get_cookie("c24_lb") is None
    assert mem.is_empty()
    assert discord.calls == []


def test_no_oauth_cookie_fails(lb_env, client, discord):
    r = client.get("/auth/discord/callback?code=x&state=abc")
    assert r.headers["Location"] == "/?login=failed"


def test_cancel_on_discord_fails(lb_env, client, discord, mem):
    r = client.get("/auth/discord/login")
    state = parse_qs(urlparse(r.headers["Location"]).query)["state"][0]
    r = client.get(f"/auth/discord/callback?error=access_denied&state={state}")
    assert r.headers["Location"] == "/?login=failed"
    assert mem.is_empty()


def test_discord_error_fails(lb_env, client, discord, monkeypatch):
    def boom(code, redirect_uri):
        raise app.discord_auth.DiscordError("down")
    monkeypatch.setattr(app.discord_auth, "exchange_code", boom)
    r = client.get("/auth/discord/login")
    state = parse_qs(urlparse(r.headers["Location"]).query)["state"][0]
    r = client.get(f"/auth/discord/callback?code=c&state={state}")
    assert r.headers["Location"] == "/?login=failed"


def test_next_must_be_relative(lb_env, client, discord):
    for bad in ("//evil.example/x", "https://evil.example/", "javascript:alert(1)", "/\\evil.example"):
        r = login(client, discord, next_path=bad)
        assert r.headers["Location"] == "/", bad


def test_logout_clears_cookie(lb_env, client, discord):
    login(client, discord)
    r = client.post("/auth/logout")
    assert r.status_code == 302 and r.headers["Location"] == "/"
    assert client.get_cookie("c24_lb") is None


def test_logout_from_other_site_refused(lb_env, client, discord):
    login(client, discord)
    r = client.post("/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.get_cookie("c24_lb") is not None


def test_tampered_cookie_is_ignored(lb_env, client, discord):
    client.set_cookie("c24_lb", "100000000000000001")
    assert guess_status(client) == 401


def guess_status(client):
    return client.post("/api/guess", json={"lang": "es", "guess": "perro"}).status_code
