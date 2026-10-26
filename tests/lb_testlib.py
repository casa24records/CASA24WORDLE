"""Shared fixtures for the leaderboard tests: an in-memory store, fake env
values and a fake Discord. Nothing here talks to Discord or a real database."""

import datetime
from urllib.parse import parse_qs, urlparse

import pytest
from flask import template_rendered
from itsdangerous import URLSafeTimedSerializer

import app
import daily
import discord_auth
import store

FAKE_SECRET_KEY = "test-secret-key-not-real"
ADMIN_ID = "900000000000000001"
TODAY = datetime.date(2026, 11, 3)

# Everything Discord could send back; only id and username may be kept.
SECRET_BITS = {
    "token": "FAKE-ACCESS-TOKEN-zz9",
    "avatar": "avatarhash-aa11",
    "email": "player-secret@example.com",
    "banner": "bannerhash-bb22",
    "global_name": "Global Display Name XYZ",
}


class FakeDiscord:
    def __init__(self):
        self.user = {"id": "100000000000000001", "username": "kolo_fan"}
        self.calls = []

    def exchange_code(self, code, redirect_uri):
        self.calls.append(("token", code, redirect_uri))
        return SECRET_BITS["token"]

    def fetch_me(self, token):
        assert token == SECRET_BITS["token"]
        self.calls.append(("me",))
        return {
            **self.user,
            "avatar": SECRET_BITS["avatar"],
            "email": SECRET_BITS["email"],
            "banner": SECRET_BITS["banner"],
            "global_name": SECRET_BITS["global_name"],
            "verified": True,
            "locale": "es-ES",
        }


@pytest.fixture
def mem(monkeypatch):
    s = store.MemoryStore()
    monkeypatch.setattr(store, "get_store", lambda: s)
    return s


@pytest.fixture
def today(monkeypatch):
    """Freeze 'today' in Panama; returns a setter for later days."""
    state = {"date": TODAY}
    monkeypatch.setattr(daily, "panama_today", lambda now=None: state["date"])

    def set_day(date):
        state["date"] = date
    set_day.state = state
    return set_day


@pytest.fixture
def discord(monkeypatch):
    fake = FakeDiscord()
    monkeypatch.setattr(discord_auth, "exchange_code", fake.exchange_code)
    monkeypatch.setattr(discord_auth, "fetch_me", fake.fetch_me)
    return fake


@pytest.fixture
def lb_env(monkeypatch, mem, discord, today):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("DISCORD_CLIENT_ID", "123456789")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("SECRET_KEY", FAKE_SECRET_KEY)
    monkeypatch.setenv("ADMIN_DISCORD_IDS", f" 5, {ADMIN_ID} ")
    return mem


@pytest.fixture
def client():
    return app.app.test_client()


@pytest.fixture
def rendered():
    """Templates rendered during the test: list of (name, context)."""
    seen = []

    def record(sender, template, context, **extra):
        seen.append((template.name, context))
    template_rendered.connect(record, app.app)
    yield seen
    template_rendered.disconnect(record, app.app)


def login(client, discord, user_id=None, username=None, next_path="/lb/es"):
    if user_id:
        discord.user = {"id": user_id, "username": username or f"user{user_id[-3:]}"}
    r = client.get("/auth/discord/login", query_string={"next": next_path})
    assert r.status_code == 302
    state = parse_qs(urlparse(r.headers["Location"]).query)["state"][0]
    return client.get("/auth/discord/callback", query_string={"code": "fake-code", "state": state})


def decode_lb_cookie(value):
    return URLSafeTimedSerializer(FAKE_SECRET_KEY, salt="c24-lb").loads(value)


def answer(lang="es"):
    _, idx = app.lb_today()
    return app.lb_answer(lang, idx)


def wrong_words(lang, n, avoid=()):
    ans = answer(lang)
    out = []
    for w in app.language_codes_5words[lang]:
        if w != ans and w not in avoid and w.isascii():
            out.append(w)
        if len(out) == n:
            return out
    raise AssertionError("not enough words")


def guess(client, word, lang="es", **extra):
    return client.post("/api/guess", json={"lang": lang, "guess": word, **extra})


def all_store_text(s):
    """Every table, key and value in the memory store, as one string."""
    return repr(s.dump())


def day_of(idx):
    """The Panama date of puzzle number idx."""
    return daily.EPOCH + datetime.timedelta(days=idx + daily.DAY_OFFSET)


def row_of(s, pid, tab):
    """The leaderboard row (with streaks) for one player, or None."""
    mine = s.standing(pid, tab)
    if not mine:
        return None
    _, today_idx = app.lb_today()
    return app._lb_rows(s, [mine], tab, today_idx, None)[0]
