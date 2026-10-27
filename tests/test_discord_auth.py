"""Discord login with a fake Discord: only the ID goes in the cookie; the store
keeps the ID, the username and the avatar hash (only in Discord's format, else
NULL); tokens, email etc. are never stored. The avatar hash also reaches the
player's browser in the redirect's #dc= fragment, never a cookie or the body."""

from urllib.parse import parse_qs, urlparse

import app
import pytest

import discord_auth
from lb_testlib import (  # noqa: F401 (fixtures)
    SECRET_BITS, VALID_AVATAR, all_store_text, client, decode_lb_cookie, discord, lb_env, login,
    mem, today,
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


def test_login_flow_keeps_only_id_username_and_valid_avatar(lb_env, client, discord, mem):
    r = login(client, discord)
    assert r.status_code == 302
    assert r.headers["Location"] == "/lb/es"  # fake avatar isn't a valid hash: no fragment
    set_cookies = r.headers.getlist("Set-Cookie")
    lb_cookie = [c for c in set_cookies if c.startswith("c24_lb=")][0]
    for flag in ("HttpOnly", "SameSite=Lax", "Max-Age=2592000"):
        assert flag in lb_cookie
    value = client.get_cookie("c24_lb").value
    assert decode_lb_cookie(value) == USER_ID  # the cookie holds only the ID

    # the store has the username, and no avatar (the fake one isn't a valid hash)
    assert mem.players == {USER_ID: {"username": "kolo_fan", "hidden": False, "avatar": None}}
    assert not mem.results and not mem.games and not mem.rate
    everything = all_store_text(mem) + "\n" + "\n".join(set_cookies)
    for bit in SECRET_BITS.values():
        assert bit not in everything, bit
    for word in ("email", "banner", "global_name", "token", "locale", "verified"):
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


def test_cancel_on_discord_is_cancelled(lb_env, client, discord, mem):
    r = client.get("/auth/discord/login")
    state = parse_qs(urlparse(r.headers["Location"]).query)["state"][0]
    r = client.get(f"/auth/discord/callback?error=access_denied&state={state}")
    assert r.status_code == 302 and r.headers["Location"] == "/?login=cancelled"
    assert client.get_cookie("c24_lb") is None
    assert client.get_cookie("c24_oauth", path="/auth/discord") is None
    assert mem.is_empty()
    assert discord.calls == []


def test_other_discord_error_fails(lb_env, client, discord, mem):
    r = client.get("/auth/discord/login")
    state = parse_qs(urlparse(r.headers["Location"]).query)["state"][0]
    r = client.get(f"/auth/discord/callback?error=server_error&state={state}")
    assert r.headers["Location"] == "/?login=failed"
    assert mem.is_empty()


def _all_memory_store_contents(mem):
    """Every attribute of the MemoryStore (not just dump()), as text."""
    return all_store_text(mem) + "\n" + repr(vars(mem))


@pytest.mark.parametrize("avatar", [VALID_AVATAR, "0123456789abcdef" * 2])
def test_avatar_hash_in_store_and_fragment_only(lb_env, client, discord, mem, avatar):
    discord.avatar = avatar
    r = login(client, discord, next_path="/lb/en")
    assert r.status_code == 302
    assert r.headers["Location"] == "/lb/en#dc=" + avatar
    url = urlparse(r.headers["Location"])
    assert avatar not in url.path and avatar not in url.query
    # nowhere else in the response
    for name, value in r.headers.items():
        if name != "Location":
            assert avatar not in value, name
    for cookie in r.headers.getlist("Set-Cookie"):
        assert avatar not in cookie
    assert avatar.encode() not in r.get_data()
    assert decode_lb_cookie(client.get_cookie("c24_lb").value) == "100000000000000001"
    # stored with the player (for the live view), and nowhere else
    assert mem.players == {"100000000000000001": {"username": "kolo_fan", "hidden": False,
                                                  "avatar": avatar}}
    assert _all_memory_store_contents(mem).count(avatar) == 2  # dump() + vars(): same dict
    # refreshed at every login: removing the Discord picture clears it
    discord.avatar = None
    login(client, discord)
    assert mem.players["100000000000000001"]["avatar"] is None


@pytest.mark.parametrize("none", [None, "", 12345, ["0" * 32], {"x": 1}])
def test_no_avatar_gives_empty_fragment(lb_env, client, discord, mem, none):
    # Discord sends null for "no avatar"; identify() treats any non-string the same
    discord.avatar = none
    r = login(client, discord)
    assert r.headers["Location"] == "/lb/es#dc="


@pytest.mark.parametrize("bad", [
    "avatarhash-aa11", "A_" + "0" * 32, "0" * 31, "0" * 33, "g" * 32, "ABCDEF" + "0" * 26,
    "b_" + "0" * 32, "0" * 32 + "\n", "0" * 32 + "#x", "0" * 32 + "&next=//evil", " " + "0" * 32,
])
def test_invalid_avatar_hash_gives_no_fragment(lb_env, client, discord, mem, bad):
    discord.avatar = bad
    r = login(client, discord)
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert loc == "/lb/es", loc
    assert bad not in _all_memory_store_contents(mem)
    assert mem.players["100000000000000001"]["avatar"] is None  # stored as NULL
    assert all(bad not in c for c in r.headers.getlist("Set-Cookie"))


def test_next_fragment_is_replaced(lb_env, client, discord):
    discord.avatar = VALID_AVATAR
    r = login(client, discord, next_path="/lb/es#dc=" + "f" * 32)
    assert r.headers["Location"] == "/lb/es#dc=" + VALID_AVATAR
    discord.avatar = "not-a-hash"
    r = login(client, discord, next_path="/leaderboard?tab=en#top")
    assert r.headers["Location"] == "/leaderboard?tab=en"


def test_identify_returns_avatar(discord):
    discord.avatar = VALID_AVATAR
    assert discord_auth.identify("c", "http://x/cb") == ("100000000000000001", "kolo_fan", VALID_AVATAR)
    discord.avatar = None
    assert discord_auth.identify("c", "http://x/cb")[2] is None
    discord.avatar = 7
    assert discord_auth.identify("c", "http://x/cb")[2] is None


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
