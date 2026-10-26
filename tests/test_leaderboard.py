"""Leaderboard: pure rules (points, ranking key, streaks, accent and color
port of game.js) and the server routes, with a fake Discord and an in-memory
store. Nothing here talks to Discord or a real Redis."""

import datetime
import json
import os
import shutil
import subprocess

import pytest

import app
import leaderboard as lb
import store
from lb_testlib import (  # noqa: F401 (fixtures)
    ADMIN_ID, all_store_text, answer, client, discord, guess, lb_env, login, mem, rendered,
    today, wrong_words,
)

C, S, I = "correct", "semicorrect", "incorrect"
P1 = "100000000000000001"
P2 = "100000000000000002"
P3 = "100000000000000003"


# ---------- pure rules ----------

def test_points():
    assert [lb.points(True, n) for n in range(1, 7)] == [6, 5, 4, 3, 2, 1]
    assert lb.points(False, 6) == 0
    assert lb.points(True, 0) == 0 and lb.points(True, 7) == 0


def test_score_order_points_then_wins_then_earliest():
    a = lb.score(10, 2, 30)   # 10 points, 2 wins, reached day 30
    b = lb.score(10, 3, 40)   # more wins beats earlier day
    c = lb.score(10, 2, 20)   # same points/wins, reached earlier
    d = lb.score(11, 1, 99)   # more points beats everything
    assert sorted([a, b, c, d], reverse=True) == [d, b, c, a]
    assert lb.score(10**6, 9999, 0) < 2**53  # exact in a float


def test_streaks():
    cur, best, last = lb.update_streak(0, 0, None, 10, True)
    assert (cur, best, last) == (1, 1, 10)
    cur, best, last = lb.update_streak(cur, best, last, 11, True)
    assert (cur, best) == (2, 2)
    cur, best, last = lb.update_streak(cur, best, last, 12, False)  # loss ends a language streak
    assert (cur, best, last) == (0, 2, 11)
    cur, best, last = lb.update_streak(cur, best, last, 14, True)
    assert (cur, best) == (1, 2)
    # combined: a loss changes nothing, a 2nd win the same day doesn't count twice
    assert lb.update_streak(3, 5, 14, 15, False, combined=True) == (3, 5, 14)
    assert lb.update_streak(3, 5, 15, 15, True, combined=True) == (3, 5, 15)
    assert lb.update_streak(3, 5, 14, 15, True, combined=True) == (4, 5, 15)
    assert lb.effective_streak(4, 15, 16) == 4   # won yesterday: still alive
    assert lb.effective_streak(4, 15, 17) == 0   # a day without a win
    assert lb.effective_streak(0, None, 17) == 0


def test_fold_accents_keeps_enye():
    assert lb.fold_accents("canción") == "cancion"
    assert lb.fold_accents("pingüino") == "pinguino"
    assert lb.fold_accents("año") == "año"


def test_resolve_accents():
    words = ["canto", "papás", "jamón", "cañon"]
    sup = ["sofás"]
    assert lb.resolve_accents("cancion", "canción", words, sup, True) == "canción"  # today's answer wins
    assert lb.resolve_accents("canto", "cantó", words, sup, True) == "cantó"       # even over a real word
    assert lb.resolve_accents("canto", "perro", words, sup, True) == "canto"       # a real word stays
    assert lb.resolve_accents("jamon", "perro", words, sup, True) == "jamón"
    assert lb.resolve_accents("sofas", "perro", words, sup, True) == "sofás"
    assert lb.resolve_accents("canon", "perro", words, sup, True) == "canon"       # ñ is its own letter
    assert lb.resolve_accents("jamon", "perro", words, sup, False) == "jamon"      # off for this language


COLOR_CASES = [
    ("speed", "abide", [I, I, S, I, S]),
    ("geese", "those", [I, I, I, C, C]),
    ("eerie", "lever", [S, C, S, I, I]),
    ("lever", "eerie", [I, C, I, S, S]),
    ("perro", "perro", [C, C, C, C, C]),
    ("canto", "cantó", [C, C, C, C, I]),   # plain o never counts for ó
    ("pasas", "papás", [C, C, I, I, C]),   # a used up; á is a different letter
    ("cantó", "tocan", [S, S, S, S, I]),
    ("állos", "salas", [I, I, C, I, C]),
    ("aaaaa", "abaca", [C, I, C, I, C]),
]


@pytest.mark.parametrize("guess_word,answer_word,expected", COLOR_CASES)
def test_color_guess(guess_word, answer_word, expected):
    assert lb.color_guess(guess_word, answer_word) == expected


def _js_method(source, name):
    """Body of a method in game.js, found by brace matching."""
    start = source.index(name + "(")
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[source.index("(", start):i + 1]
    raise AssertionError(name)


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_color_and_fold_match_game_js():
    """Run the real updateColors/foldAccents from game.js in node on the same cases."""
    with open(os.path.join(app.STATIC_DIR, "game.js"), encoding="utf-8") as f:
        src = f.read()
    update = _js_method(src, "updateColors")
    fold = _js_method(src, "foldAccents")
    cases = [[g, a] for g, a, _ in COLOR_CASES]
    words = ["canción", "pingüino", "año", "árbol", "ÉxitO".lower()]
    script = f"""
const TILE_BASE = "uppercase font-bold select-none text-white";
const obj = {{ updateColors{update}, foldAccents{fold} }};
const out = {{colors: [], folds: []}};
for (const [g, a] of {json.dumps(cases)}) {{
  obj.todays_word = a; obj.active_row = 0; obj.key_classes = {{}};
  obj.tiles = [g.split("")]; obj.tile_classes = [["", "", "", "", ""]];
  obj.updateColors();
  out.colors.push(obj.tile_classes[0].map(c => c.split(" ")[0]));
}}
for (const w of {json.dumps(words)}) out.folds.push(obj.foldAccents(w));
console.log(JSON.stringify(out));
"""
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["colors"] == [lb.color_guess(g, a) for g, a in cases]
    assert out["folds"] == [lb.fold_accents(w) for w in words]


# ---------- store ----------

def test_memory_store_basics():
    s = store.MemoryStore()
    assert s.set("a", "1", nx=True, ex=60) is True
    assert s.set("a", "2", nx=True) is False and s.get("a") == "1"
    assert s.incr("n") == 1 and s.incr("n") == 2
    s.hset("h", {"x": "1", "y": "2"})
    s.hdel("h", "x")
    assert s.hgetall("h") == {"y": "2"}
    s.zadd("z", 5, "p"), s.zadd("z", 7, "q"), s.zadd("z", 1, "r")
    assert s.zrevrange("z", 0, 1) == [("q", 7.0), ("p", 5.0)]
    assert s.zrevrank("z", "r") == 2 and s.zcard("z") == 3
    s.zrem("z", "q")
    assert s.zrevrank("z", "q") is None
    assert s.delete("a", "h", "missing") == 2
    assert s.pipeline([["INCR", "n"], ["GET", "n"]]) == [3, "3"]


def test_get_store_choice(monkeypatch):
    for k in ("KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    assert isinstance(store.get_store(), store.MemoryStore)
    monkeypatch.setenv("VERCEL", "1")
    assert store.get_store() is None
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://example.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "fake")
    assert isinstance(store.get_store(), store.UpstashStore)  # built, never called


def test_upstash_request_shape(monkeypatch):
    """The REST client posts a JSON command array with a Bearer token (fake urlopen)."""
    sent = []

    class Resp:
        def __init__(self, body):
            self.body = body

        def read(self):
            return json.dumps(self.body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        sent.append((req.full_url, req.get_header("Authorization"), json.loads(req.data), timeout))
        if req.full_url.endswith("/pipeline"):
            return Resp([{"result": 1}, {"result": "OK"}])
        return Resp({"result": "OK"})
    monkeypatch.setattr(store.urllib.request, "urlopen", fake_urlopen)
    s = store.UpstashStore("https://kv.example.invalid/", "tok")
    assert s.set("k", "v", nx=True, ex=10) is True
    assert s.pipeline([["INCR", "n"], ["SET", "a", "b"]]) == [1, "OK"]
    assert sent[0] == ("https://kv.example.invalid", "Bearer tok", ["SET", "k", "v", "NX", "EX", "10"], 5)
    assert sent[1][0] == "https://kv.example.invalid/pipeline"


def test_env_local_loader(tmp_path, monkeypatch):
    path = tmp_path / ".env.local"
    path.write_text('# comment\nC24_T_A="quoted value"\nexport C24_T_B=plain\nC24_T_C=\'single\'\n'
                    "C24_T_KEEP=new\n\nnot a line\n")
    monkeypatch.setenv("C24_T_KEEP", "old")
    for k in ("C24_T_A", "C24_T_B", "C24_T_C"):
        monkeypatch.delenv(k, raising=False)
    app.load_env_local(str(path))
    try:
        assert os.environ["C24_T_A"] == "quoted value"
        assert os.environ["C24_T_B"] == "plain"
        assert os.environ["C24_T_C"] == "single"
        assert os.environ["C24_T_KEEP"] == "old"  # never overrides
    finally:
        for k in ("C24_T_A", "C24_T_B", "C24_T_C"):
            os.environ.pop(k, None)


# ---------- disabled ----------

def test_disabled_without_env(monkeypatch, mem, client):
    for k in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert client.get("/lb/es").status_code == 404
    assert client.get("/leaderboard").status_code == 404
    assert client.get("/auth/discord/login").status_code == 404
    r = guess(client, "perro")
    assert r.status_code == 404 and r.get_json() == {"error": "disabled"}
    assert mem.keys() == []


def test_disabled_on_vercel_without_kv(monkeypatch, client):
    monkeypatch.setenv("VERCEL", "1")
    for k in ("KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DISCORD_CLIENT_ID", "1")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "2")
    monkeypatch.setenv("SECRET_KEY", "3")
    assert not app.lb_enabled()
    assert client.get("/leaderboard").status_code == 404


# ---------- game routes ----------

def test_lb_page_needs_login_and_hides_answer(lb_env, client, discord, rendered):
    r = client.get("/lb/es")
    assert r.status_code == 302 and r.headers["Location"] == "/auth/discord/login?next=/lb/es"
    assert client.get("/lb/fr").headers["Location"] == "/lb/es"
    login(client, discord)
    r = client.get("/lb/es")
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    html = r.get_data(as_text=True)
    assert 'const todays_word = "";' in html
    name, ctx = rendered[-1]
    assert name == "game.html"
    assert ctx["lb"] is True and ctx["demo"] is False
    assert ctx["language"].daily_word == ""
    assert ctx["lb_state"] == {"guesses": [], "done": False, "won": False,
                               "answer": None, "points": None, "rank": None}
    assert ctx["lb_user"] == {"id": P1, "username": "kolo_fan"}


def test_guess_needs_login(lb_env, client):
    r = guess(client, "perro")
    assert r.status_code == 401 and r.get_json() == {"error": "login"}


def test_guess_validation(lb_env, client, discord):
    login(client, discord)
    assert guess(client, "zzzzz").get_json() == {"error": "invalid_word"}
    assert guess(client, "zzzzz").status_code == 400
    assert guess(client, "perr").get_json() == {"error": "invalid_word"}
    assert guess(client, "perro", lang="fr").get_json() == {"error": "bad_lang"}
    assert client.post("/api/guess", data="nope").get_json() == {"error": "bad_request"}
    assert client.post("/api/guess", json={"lang": "es", "guess": 5}).status_code == 400
    w = wrong_words("es", 1)[0]
    r = guess(client, w.upper())
    assert r.status_code == 200
    body = r.get_json()
    assert body["word"] == w and len(body["colors"]) == 5
    assert body["done"] is False and body["answer"] is None and body["points"] is None
    r = guess(client, w)
    assert r.status_code == 400 and r.get_json() == {"error": "repeat"}


def test_guess_from_other_site_refused(lb_env, client, discord):
    login(client, discord)
    r = client.post("/api/guess", json={"lang": "es", "guess": "perro"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/guess", json={"lang": "es", "guess": "perro"},
                    headers={"Origin": "http://localhost"})
    assert r.status_code != 403


def test_accentless_typing_resolves(lb_env, client, discord):
    login(client, discord)
    ans = answer("es")
    folded = lb.fold_accents(ans)
    r = guess(client, folded)
    body = r.get_json()
    assert body["word"] == ans and body["won"] is True and body["colors"] == [C] * 5


def test_win_records_once(lb_env, client, discord, mem):
    login(client, discord)
    w = wrong_words("es", 1)[0]
    guess(client, w)
    r = guess(client, answer("es"))
    body = r.get_json()
    assert body["done"] and body["won"] and body["answer"] == answer("es")
    assert body["points"] == 5 and body["rank"] == 1
    assert guess(client, wrong_words("es", 2)[1]).get_json() == {"error": "finished"}
    date, idx = app.lb_today()
    # a second finish can't count twice
    app._record_result(mem, P1, "es", date, idx, True, 1)
    p = mem.hgetall(f"player:{P1}")
    assert (p["es_points"], p["es_wins"], p["es_played"]) == ("5", "1", "1")
    assert (p["all_points"], p["all_cur_streak"], p["all_best_streak"]) == ("5", "1", "1")
    assert mem.zrevrange("lb:es", 0, -1) == [(P1, float(lb.score(5, 1, idx)))]
    assert mem.zrevrange("lb:all", 0, -1) == [(P1, float(lb.score(5, 1, idx)))]
    assert mem.zcard("lb:en") == 0
    # resume state after reload
    state = app.lb_game_state(mem, P1, "es")
    assert state["done"] and state["won"] and state["points"] == 5 and state["rank"] == 1
    assert [g["word"] for g in state["guesses"]] == [w, answer("es")]


def test_six_misses_then_finished(lb_env, client, discord, mem):
    login(client, discord)
    words = wrong_words("es", 7)
    for i, w in enumerate(words[:6]):
        body = guess(client, w).get_json()
        assert body["done"] is (i == 5)
    assert body["won"] is False and body["answer"] == answer("es") and body["points"] == 0
    assert body["rank"] == 1  # a loss still puts you on the board
    r = guess(client, words[6])
    assert r.status_code == 400 and r.get_json()["error"] in ("finished", "too_many")
    p = mem.hgetall(f"player:{P1}")
    assert (p["es_points"], p["es_played"], p["es_wins"]) == ("0", "1", "0")


def test_client_date_is_ignored(lb_env, client, discord, mem):
    login(client, discord)
    w = wrong_words("es", 1)[0]
    r = guess(client, w, date="2001-01-01", day=1, answer="perro", points=6)
    assert r.status_code == 200
    date, _ = app.lb_today()
    assert date == "2026-11-03"
    assert json.loads(mem.get(f"game:{P1}:es:{date}")) == [w]
    assert not any("2001" in k for k in mem.keys())


def test_new_day_new_game_and_streak(lb_env, client, discord, mem, today):
    login(client, discord)
    guess(client, answer("es"))
    today(datetime.date(2026, 11, 4))
    assert guess(client, answer("es")).get_json()["points"] == 6
    body = guess(client, answer("en"), lang="en").get_json()
    assert body["won"] and body["rank"] == 1
    p = mem.hgetall(f"player:{P1}")
    assert (p["es_cur_streak"], p["es_best_streak"], p["es_points"]) == ("2", "2", "12")
    assert (p["all_cur_streak"], p["all_points"], p["all_played"]) == ("2", "18", "3")
    assert p["en_cur_streak"] == "1"


def test_rate_limit(lb_env, client, discord):
    login(client, discord)
    codes = [guess(client, "zzzzz").status_code for _ in range(31)]
    assert codes[:30] == [400] * 30
    assert codes[30] == 429


def test_guest_routes_never_write(lb_env, client, discord, mem):
    for path in ["/", "/es", "/en", "/fr", "/sitemap.xml", "/leaderboard"]:
        assert client.get(path).status_code == 200, path
    assert mem.keys() == []


# ---------- leaderboard page, delete, admin ----------

def _seed(mem, pid, name, games):
    """games: (day_idx, won, attempts) in es."""
    mem.hset(f"player:{pid}", {"username": name})
    for idx, won, attempts in games:
        app._record_result(mem, pid, "es", f"d{idx}", idx, won, attempts)


def test_leaderboard_order_and_rows(lb_env, client, discord, mem, rendered):
    _, today_idx = app.lb_today()
    _seed(mem, P1, "late", [(today_idx, True, 1)])                        # 6 pts, 1 win, today
    _seed(mem, P2, "two_wins", [(today_idx - 5, True, 4), (today_idx, True, 4)])  # 6 pts, 2 wins
    _seed(mem, P3, "early", [(today_idx - 3, True, 1)])                   # 6 pts, 1 win, earlier
    r = client.get("/leaderboard?tab=es")
    assert r.status_code == 200
    name, ctx = rendered[-1]
    assert name == "leaderboard.html" and ctx["tab"] == "es"
    assert [row["username"] for row in ctx["rows"]] == ["two_wins", "early", "late"]
    assert [row["rank"] for row in ctx["rows"]] == [1, 2, 3]
    top = ctx["rows"][0]
    assert top == {"rank": 1, "id": P2, "username": "two_wins", "points": 6, "wins": 2,
                   "played": 2, "current_streak": 1, "best_streak": 1, "is_me": False}
    assert ctx["rows"][1]["current_streak"] == 0  # no win since 3 days ago
    assert ctx["me_row"] is None and ctx["is_admin"] is False and ctx["lb_user"] is None
    client.get("/leaderboard?tab=bogus")
    assert rendered[-1][1]["tab"] == "all"
    client.get("/leaderboard?tab=en")
    assert rendered[-1][1]["rows"] == []


def test_leaderboard_me_row_outside_top(lb_env, client, discord, mem, rendered):
    _, idx = app.lb_today()
    for n in range(55):
        _seed(mem, str(200000000000000000 + n), f"p{n}", [(idx - 1, True, 1)])
    login(client, discord)
    _seed(mem, P1, "kolo_fan", [(idx, False, 6)])
    client.get("/leaderboard?tab=all")
    ctx = rendered[-1][1]
    assert len(ctx["rows"]) == 50
    assert ctx["me_row"]["rank"] == 56 and ctx["me_row"]["is_me"] is True
    assert ctx["lb_user"] == {"id": P1, "username": "kolo_fan"}


def test_delete_my_data(lb_env, client, discord, mem):
    _seed(mem, P2, "other", [(1, True, 2)])
    login(client, discord)
    guess(client, wrong_words("es", 1)[0])
    guess(client, answer("es"))
    guess(client, answer("en"), lang="en")
    assert any(P1 in k for k in mem.keys())
    assert client.post("/api/me/delete", headers={"Origin": "https://evil.example"}).status_code == 403
    r = client.post("/api/me/delete")
    assert r.status_code == 302 and r.headers["Location"] == "/?deleted=1"
    assert client.get_cookie("c24_lb") is None
    assert P1 not in all_store_text(mem)
    assert "other" in all_store_text(mem)  # other players untouched
    assert client.post("/api/me/delete").status_code == 401


def test_deleted_player_is_logged_out(lb_env, client, discord, mem):
    login(client, discord)
    mem.delete(f"player:{P1}")
    assert guess(client, "perro").status_code == 401
    assert client.get("/lb/es").status_code == 302


def test_admin_hide_and_unhide(lb_env, client, discord, mem, rendered):
    _seed(mem, P2, "rude_name", [(3, True, 1)])
    _seed(mem, P3, "nice", [(3, True, 2)])
    login(client, discord)  # P1, not an admin
    r = client.post("/admin/hide", data={"discord_id": P2, "hidden": "1"})
    assert r.status_code == 403
    assert mem.zrevrank("lb:all", P2) is not None

    login(client, discord, user_id=ADMIN_ID, username="owner")
    client.get("/leaderboard")
    assert rendered[-1][1]["is_admin"] is True
    r = client.post("/admin/hide", data={"discord_id": P2, "hidden": "1", "tab": "es"})
    assert r.status_code == 302 and r.headers["Location"] == "/leaderboard?tab=es"
    assert mem.hget(f"player:{P2}", "hidden") == "1"
    for scope in ("es", "all"):
        assert mem.zrevrank(f"lb:{scope}", P2) is None
    client.get("/leaderboard")
    assert [row["username"] for row in rendered[-1][1]["rows"]] == ["nice"]
    # a hidden player's new games don't put them back
    app._record_result(mem, P2, "es", "d4", 4, True, 1)
    assert mem.zrevrank("lb:es", P2) is None

    client.post("/admin/hide", data={"discord_id": P2, "hidden": "0"})
    assert mem.hget(f"player:{P2}", "hidden") is None
    assert mem.zrevrank("lb:es", P2) == 0  # 12 points now
    assert client.post("/admin/hide", data={"discord_id": P2, "hidden": "1"},
                       headers={"Origin": "https://evil.example"}).status_code == 403
