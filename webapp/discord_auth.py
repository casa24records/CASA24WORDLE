"""Discord login (OAuth2, scope "identify" only), stdlib urllib.

identify(code, redirect_uri) trades the one-time code for an access token,
asks Discord who the player is, and returns ONLY (id, username, avatar_hash).
The token never leaves this module, is never stored and never logged.
The server stores id, username and the avatar hash (only when it has Discord's
format, for the live view's pictures; see store.clean_avatar). avatar_hash is
also handed to the player's own browser (URL fragment after login, see
app.discord_callback); it is never logged or put in a cookie.

exchange_code() and fetch_me() are the only two network calls; tests replace
them with fakes (monkeypatch), so the test suite never talks to Discord.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
ME_URL = "https://discord.com/api/users/@me"
TIMEOUT = 5
USER_AGENT = "Casa24Wordle (https://casa24records.com, 1.0)"


class DiscordError(Exception):
    pass


def client_id():
    return os.environ.get("DISCORD_CLIENT_ID", "")


def client_secret():
    return os.environ.get("DISCORD_CLIENT_SECRET", "")


def authorize_url(redirect_uri, state):
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id(),
        "scope": "identify",
        "redirect_uri": redirect_uri,
        "state": state,
        "prompt": "none",
    })
    return AUTHORIZE_URL + "?" + query


def _request_json(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as e:
        # no response body or headers in the message (they could hold secrets)
        raise DiscordError("discord request failed: " + type(e).__name__) from None


def exchange_code(code, redirect_uri):
    """POST the code to Discord; returns the access token string."""
    body = urllib.parse.urlencode({
        "client_id": client_id(),
        "client_secret": client_secret(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    data = _request_json(req)
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise DiscordError("no access token")
    return token


def fetch_me(access_token):
    """GET /users/@me with the token; returns Discord's JSON object."""
    req = urllib.request.Request(ME_URL, method="GET", headers={
        "Authorization": "Bearer " + access_token,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    data = _request_json(req)
    if not isinstance(data, dict):
        raise DiscordError("bad user object")
    return data


def identify(code, redirect_uri):
    """(discord_id, username, avatar_hash) for this login. Everything else is dropped here.

    avatar_hash is a string or None. The callback stores it only if it has
    Discord's format (else NULL) and passes it to the player's browser in the
    redirect fragment; it is never logged or put in a cookie."""
    me = fetch_me(exchange_code(code, redirect_uri))
    discord_id = str(me.get("id") or "")
    username = str(me.get("username") or "").strip()[:32]
    avatar = me.get("avatar")
    avatar_hash = avatar if isinstance(avatar, str) and avatar else None
    del me  # email, banner, etc. are never kept
    if not (discord_id.isdigit() and len(discord_id) <= 20 and username):
        raise DiscordError("bad user object")
    return discord_id, username, avatar_hash
