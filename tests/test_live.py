"""Live view backend: GET /api/live and Store.live(). Other players' boards as
colors only: never the words, the answer or anyone's Discord ID."""

import datetime
import json
import re

import pytest

import app
import leaderboard as lb
import store
from lb_testlib import (  # noqa: F401 (fixtures)
    VALID_AVATAR, all_store_text, answer, client, discord, guess, lb_env, login, mem, today,
    wrong_words,
)

ME = "100000000000000001"   # FakeDiscord's default user
P2 = "100000000000000002"
P3 = "100000000000000003"
P4 = "100000000000000004"
P5 = "100000000000000005"
P6 = "100000000000000006"
HASH = "0123456789abcdef" * 2

# Text that is always in a response; test words must not hide inside it.
STRUCTURE = ("players username avatar_url rows done won live count correct semicorrect "
             "incorrect true false null https cdn discordapp com avatars embed png size "
             "winner loser playing hidden_one english no_guesses")


def _words(lang, n):
    out = [w for w in wrong_words(lang, 200) if w not in STRUCTURE]
    return out[:n]


def _seed(mem, pid, name, words, lang="es", ago=0, avatar=None, finish=None):
    """A player with today's guesses; updated `ago` seconds ago."""
    mem.upsert_player(pid, name, avatar)
    day, _ = app.lb_today()
    with mem.game(pid, lang, day) as g:
        g.save(words)
        if finish is not None:
            g.record(finish, len(words), lb.points(finish, len(words)))
    now = datetime.datetime.now(datetime.timezone.utc)
    mem.games[(pid, lang, day)]["updated_at"] = now - datetime.timedelta(seconds=ago)


def _live(client, lang="es"):
    return client.get("/api/live", query_string={"lang": lang})


def test_live_disabled_without_env(monkeypatch, mem, client):
    for name in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    r = _live(client)
    assert r.status_code == 404 and r.get_json() == {"error": "disabled"}


def test_live_needs_login_and_lang(lb_env, client, discord, mem):
    r = _live(client)
    assert r.status_code == 401 and r.get_json() == {"error": "login"}
    login(client, discord)
    for bad in ("fr", "", "ES", "all"):
        r = _live(client, bad)
        assert r.status_code == 400 and r.get_json() == {"error": "bad_lang"}
    assert client.get("/api/live").get_json() == {"error": "bad_lang"}
    mem.delete_player(ME)  # cookie of a deleted player
    assert _live(client).status_code == 401


def test_live_colors_only_and_filters(lb_env, client, discord, mem):
    words = _words("es", 8)
    ans = answer("es")
    _seed(mem, P2, "playing", words[:2], ago=30, avatar=HASH)
    _seed(mem, P3, "winner", [words[2], ans], ago=10, avatar=VALID_AVATAR, finish=True)
    _seed(mem, P4, "hidden_one", words[3:5], ago=5)
    mem.set_hidden(P4, True)
    _seed(mem, P5, "english", _words("en", 1), lang="en", ago=1)
    _seed(mem, P6, "no_guesses", [], ago=0)
    _seed(mem, "100000000000000007", "loser", words[:6], ago=20, finish=False)
    login(client, discord)
    guess(client, words[7])  # my own game today: never in my list

    r = _live(client)
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    body = r.get_json()
    assert body["count"] == 3 == len(body["players"])
    assert [p["username"] for p in body["players"]] == ["winner", "loser", "playing"]
    winner, loser, playing = body["players"]
    assert set(winner) == {"username", "avatar_url", "rows", "done", "won", "live"}
    assert winner["rows"] == [lb.color_guess(words[2], ans), lb.color_guess(ans, ans)]
    assert winner["rows"][-1] == ["correct"] * 5
    assert (winner["done"], winner["won"], winner["live"]) == (True, True, True)
    assert (loser["done"], loser["won"]) == (True, False) and len(loser["rows"]) == 6
    assert playing["rows"] == [lb.color_guess(w, ans) for w in words[:2]]
    assert (playing["done"], playing["won"], playing["live"]) == (False, False, True)
    assert playing["avatar_url"] == f"https://cdn.discordapp.com/avatars/{P2}/{HASH}.png?size=64"
    assert winner["avatar_url"] == f"https://cdn.discordapp.com/avatars/{P3}/{VALID_AVATAR}.png?size=64"
    default = (int("100000000000000007") >> 22) % 6
    assert loser["avatar_url"] == f"https://cdn.discordapp.com/embed/avatars/{default}.png"

    # no words, no answer, no Discord IDs anywhere in the JSON
    text = r.get_data(as_text=True)
    for w in words + [ans] + _words("en", 1):
        assert w not in text, w
    # Discord IDs: only inside a custom avatar's CDN URL (Discord's URL format needs
    # it); never as a field, and never for hidden/other-language/self players
    without_urls = json.dumps([{k: v for k, v in p.items() if k != "avatar_url"}
                               for p in body["players"]])
    assert not re.search(r"\d{17,}", without_urls)
    assert re.findall(r"\d{17,}", text) == [P3, P2]  # winner's and playing's avatar URLs
    for pid in (ME, P4, P5, P6, "100000000000000007"):
        assert pid not in text
    assert "kolo_fan" not in text and "hidden_one" not in text and "english" not in text

    # the English list only has the English player
    en = _live(client, "en").get_json()
    assert [p["username"] for p in en["players"]] == ["english"] and en["count"] == 1


def test_live_flag_and_unfinished_win(lb_env, client, discord, mem):
    ans = answer("es")
    _seed(mem, P2, "old", _words("es", 1), ago=6 * 60)
    _seed(mem, P3, "recent", _words("es", 1), ago=4 * 60)
    # answer guessed but no result row yet (still counts as done + won)
    _seed(mem, P4, "won_now", [ans], ago=0)
    login(client, discord)
    players = {p["username"]: p for p in _live(client).get_json()["players"]}
    assert players["old"]["live"] is False and players["recent"]["live"] is True
    assert (players["won_now"]["done"], players["won_now"]["won"]) == (True, True)


def test_live_order_and_limit(lb_env, client, discord, mem):
    for n in range(35):
        _seed(mem, str(200000000000000000 + n), f"p{n:02d}", _words("es", 1), ago=n)
    login(client, discord)
    body = _live(client).get_json()
    assert body["count"] == app.LIVE_LIMIT == 30
    assert [p["username"] for p in body["players"]] == [f"p{n:02d}" for n in range(30)]


def test_live_rate_limit_is_separate_from_guesses(lb_env, client, discord, mem):
    login(client, discord)
    codes = [_live(client).status_code for _ in range(app.LIVE_RATE_LIMIT_PER_MINUTE + 1)]
    assert codes[:-1] == [200] * app.LIVE_RATE_LIMIT_PER_MINUTE
    assert codes[-1] == 429 and _live(client).get_json() == {"error": "rate"}
    # polling never used the guess budget
    assert guess(client, _words("es", 1)[0]).status_code == 200
    assert [v for (k, _), v in mem.rate.items() if k == ME] == [1]


def test_live_store_error_is_503(lb_env, client, discord, mem, monkeypatch):
    login(client, discord)

    def boom(*a, **k):
        raise store.StoreError("database error: X")
    monkeypatch.setattr(mem, "live", boom)
    r = _live(client)
    assert r.status_code == 503 and r.get_json() == {"error": "store"}


def test_delete_removes_avatar_and_live_counter(lb_env, client, discord, mem):
    discord.avatar = VALID_AVATAR
    login(client, discord)
    assert mem.players[ME]["avatar"] == VALID_AVATAR
    _live(client)
    assert any(k == ME + ":live" for k, _ in mem.rate)
    assert client.post("/api/me/delete").status_code == 302
    assert ME not in all_store_text(mem) and VALID_AVATAR not in all_store_text(mem)
    assert mem.is_empty()


def test_cookie_still_only_the_id(lb_env, client, discord):
    from lb_testlib import decode_lb_cookie
    discord.avatar = VALID_AVATAR
    r = login(client, discord)
    assert decode_lb_cookie(client.get_cookie("c24_lb").value) == ME
    assert all(VALID_AVATAR not in c for c in r.headers.getlist("Set-Cookie"))


@pytest.mark.parametrize("avatar,kept", [
    (HASH, True), (VALID_AVATAR, True), (None, False), ("", False), ("A_" + "0" * 32, False),
    ("0" * 31, False), ("0" * 32 + "\n", False), (12345, False), ("../" + "0" * 29, False),
])
def test_memory_store_avatar_rule(avatar, kept):
    s = store.MemoryStore()
    s.upsert_player("1", "a", avatar)
    assert s.players["1"]["avatar"] == (avatar if kept else None)
    assert s.get_player("1") == {"username": "a", "hidden": False}
    s.upsert_player("1", "a")  # every login refreshes it
    assert s.players["1"]["avatar"] is None


def test_memory_store_live_directly():
    s = store.MemoryStore()
    day = datetime.date(2026, 11, 3)
    s.upsert_player("1", "me")
    s.upsert_player("2", "two", HASH)
    for pid in ("1", "2"):
        with s.game(pid, "es", day) as g:
            g.save(["perro"])
    with s.game("2", "es", day - datetime.timedelta(days=1)) as g:  # yesterday: not shown
        g.save(["gatos"])
    rows = s.live("es", day, "1")
    assert len(rows) == 1
    row = rows[0]
    assert {k: row[k] for k in ("id", "username", "avatar", "guesses", "finished", "won")} == \
        {"id": "2", "username": "two", "avatar": HASH, "guesses": ["perro"],
         "finished": False, "won": False}
    assert row["updated_at"].tzinfo is not None
    assert s.live("es", day, "1", limit=0) == []


def test_postgres_live_against_fake_connection(monkeypatch):
    sent = []
    when = datetime.datetime(2026, 11, 3, 12, tzinfo=datetime.timezone.utc)

    class Cur:
        rows = []

        def execute(self, sql, params=None):
            sent.append((sql, params))
            Cur.rows = [("2", "two", HASH, ["perro"], when, True, False),
                        ("3", "three", "bad-hash", "not-a-list", when, False, False)] \
                if sql == store.SQL_LIVE else [(1,)]

        def fetchone(self):
            return Cur.rows[0] if Cur.rows else None

        def fetchall(self):
            return Cur.rows

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Conn:
        closed = broken = False

        def transaction(self):
            return Cur()

        def cursor(self):
            return Cur()

        def close(self):
            self.closed = True

    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: Conn())
    monkeypatch.setattr(store.PostgresStore, "_schema_ready", False)
    st = store.PostgresStore("postgresql://fake")
    day = datetime.date(2026, 11, 3)
    rows = st.live("es", day, "1'; DROP TABLE x;--", 30)
    assert (store.SQL_LIVE, ("es", day, "1'; DROP TABLE x;--", 30)) in sent
    assert rows[0] == {"id": "2", "username": "two", "avatar": HASH, "guesses": ["perro"],
                       "updated_at": when, "finished": True, "won": False}
    assert rows[1]["avatar"] is None and rows[1]["guesses"] == []
    queries = [q for q, _ in sent]
    assert "ALTER TABLE wordle_players ADD COLUMN IF NOT EXISTS avatar text" in queries
    assert queries.index(store.SQL_SCHEMA[0]) < queries.index(
        "ALTER TABLE wordle_players ADD COLUMN IF NOT EXISTS avatar text")
    st.close()


def test_live_sql_shape():
    sql = " ".join(store.SQL_LIVE.split())
    for part in ("JOIN wordle_players p", "LEFT JOIN wordle_results r", "g.lang = %s",
                 "g.day = %s", "NOT p.hidden", "g.discord_id <> %s",
                 "jsonb_array_length(g.guesses) > 0", "ORDER BY g.updated_at DESC", "LIMIT %s"):
        assert part in sql, part
    assert "updated_at = now()" in store.SQL_GAME_SAVE  # every saved guess bumps it


def test_avatar_url_helper():
    assert app.lb_avatar_url(P2, HASH) == f"https://cdn.discordapp.com/avatars/{P2}/{HASH}.png?size=64"
    for bad in (None, "", "x" * 32, HASH + "?a=b"):
        assert app.lb_avatar_url(P2, bad) == \
            f"https://cdn.discordapp.com/embed/avatars/{(int(P2) >> 22) % 6}.png"
    assert json.dumps(app.lb_avatar_url("0", None)).endswith('/0.png"')
