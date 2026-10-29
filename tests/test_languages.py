"""Spanish and English only (owner decision 2026-10-29): folders, constants, old
links, the API, the leaderboard tabs, the Activity shell, the daily words and
scripts/purge_languages.py (against a fake database connection, never a real one)."""

import csv
import datetime
import json
import os
import re
from urllib.parse import parse_qs, urlparse

import pytest

import app
import daily
import purge_languages as purge
import store
from lb_testlib import (  # noqa: F401 (fixtures)
    client, discord, guess, lb_env, login, mem, rendered, today,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RETIRED = ("ar", "de", "fr", "ko", "pt", "ru", "tr", "vi")
ACT = "frame_id=f1&instance_id=i1&platform=desktop"


# ---------- data and constants ----------

def test_only_es_and_en_folders():
    folders = sorted(os.listdir(os.path.join(ROOT, "webapp", "data", "languages")))
    assert folders == ["en", "es"]
    assert app.SUPPORTED_LANGS == ("es", "en")
    assert app.language_codes == ["es", "en"]
    assert app.LB_LANGS == ("es", "en") and app.LB_TABS == ("all", "es", "en")
    assert store.SUPPORTED_LANGS == app.SUPPORTED_LANGS
    assert set(app.RETIRED_LANGS) == set(RETIRED)
    assert list(app.languages) == ["es", "en"]


@pytest.mark.parametrize("lang", ("es", "en"))
def test_every_language_ships_its_keyboard(lang):
    # no generated keyboard any more: a missing file must fail here
    path = os.path.join(ROOT, "webapp", "data", "languages", lang, f"{lang}_keyboard.json")
    assert os.path.exists(path)
    assert app.keyboards[lang]["layouts"]
    assert not hasattr(app.Language, "_generate_alphabetical_keyboard")


def test_input_characters():
    letters = set("abcdefghijklmnopqrstuvwxyz")
    for lang in ("es", "en"):
        chars = app.Language(lang, app.language_codes_5words[lang]).input_characters
        assert "⇨" not in chars and "⌫" not in chars
        assert letters <= set(chars), lang
        # the union over every layout (QWERTY, Dvorak, alphabetical...)
        for layout in app.keyboards[lang]["layouts"].values():
            keys = {k for row in layout["rows"] for k in row} - {"⇨", "⌫"}
            assert keys <= set(chars), (lang, layout["label"])
    assert set(app.input_characters("en")) == letters
    assert "ñ" in app.input_characters("es")


def test_no_rtl_left():
    assert not hasattr(app, "_is_rtl")
    assert all("right_to_left" not in info for info in app.languages.values())


# The daily words must not change when the other languages go (the word lists
# still load es then en after random.seed(42)). Computed with the code before
# the change (10 languages), 2026-10-29.
EXPECTED_DAILY = {
    "es": ["zanca", "talle", "hacer", "joyel", "focha", "milán", "losas", "juego", "cabra", "égida", "radio"],
    "en": ["rebut", "sissy", "humph", "awake", "blush", "focal", "video", "naval", "serve", "heath", "dwarf"],
}


@pytest.mark.parametrize("lang", ("es", "en"))
def test_daily_words_unchanged(lang):
    start = datetime.date(2026, 10, 26)
    got = [app.lb_answer(lang, daily.day_index(start + datetime.timedelta(days=i))) for i in range(11)]
    assert got == EXPECTED_DAILY[lang]


# ---------- old links ----------

def _loc(r):
    loc = urlparse(r.headers["Location"])
    return loc.path, parse_qs(loc.query)


@pytest.mark.parametrize("code", RETIRED)
def test_old_language_link_redirects(client, code):
    r = client.get(f"/{code}")
    assert r.status_code == 302 and _loc(r) == ("/es", {})


def test_old_language_link_follows_browser_language(client):
    r = client.get("/fr", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert r.status_code == 302 and _loc(r)[0] == "/en"
    r = client.get("/fr", headers={"Accept-Language": "es-PA,es;q=0.9,en;q=0.5"})
    assert _loc(r)[0] == "/es"
    r = client.get("/fr", headers={"Accept-Language": "fr-FR,de;q=0.8"})
    assert _loc(r)[0] == "/es"  # neither: Spanish


def test_old_leaderboard_link_keeps_query(lb_env, client):
    r = client.get("/lb/ko?embed=1")
    assert r.status_code == 302 and _loc(r) == ("/lb/es", {"embed": ["1"]})
    r = client.get("/lb/ko?embed=1", headers={"Accept-Language": "en"})
    assert _loc(r) == ("/lb/en", {"embed": ["1"]})
    r = client.get("/lb/vi?" + ACT)
    path, query = _loc(r)
    assert path == "/lb/es" and query["frame_id"] == ["f1"] and query["platform"] == ["desktop"]


def test_unknown_codes_unchanged(lb_env, client):
    assert client.get("/xx").headers["Location"] == "/"
    assert _loc(client.get("/lb/xx"))[0] == "/lb/es"


def test_api_refuses_old_language(lb_env, client, discord):
    login(client, discord)
    for code in ("de", "ko", "ar"):
        r = guess(client, "perro", lang=code)
        assert r.status_code == 400 and r.get_json() == {"error": "bad_lang"}
        assert client.get(f"/api/state?lang={code}").get_json() == {"error": "bad_lang"}
        assert client.get(f"/api/live?lang={code}").get_json() == {"error": "bad_lang"}
    assert client.get("/api/leaderboard?tab=fr").get_json() == {"error": "bad_tab"}


def test_leaderboard_has_three_tabs(lb_env, client, rendered):
    html = client.get("/leaderboard").get_data(as_text=True)
    assert re.findall(r'data-tab="([a-z]+)"', html) == ["all", "es", "en"]
    client.get("/leaderboard?tab=de")
    assert rendered[-1][1]["tab"] == "all"


def test_sitemap_only_es_and_en(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    locs = re.findall(r"<loc>([^<]+)</loc>", xml)
    assert locs == ["http://localhost", "http://localhost/es", "http://localhost/en",
                    "http://localhost/terms", "http://localhost/privacy"]


def test_hreflang_links_passed_to_game(client, rendered):
    client.get("/en")
    links = rendered[-1][1]["hreflang_links"]
    assert links == [{"lang": "es", "href": "http://localhost/es"},
                     {"lang": "en", "href": "http://localhost/en"},
                     {"lang": "x-default", "href": "http://localhost/"}]


# ---------- Discord Activity ----------

def test_activity_shell_lists_es_and_en(lb_env, client):
    html = client.get("/?" + ACT).get_data(as_text=True)
    data = json.loads(re.search(r'id="c24-shell">(.*?)</script>', html, re.S).group(1))
    assert [l["code"] for l in data["langs"]] == ["es", "en"]
    assert re.findall(r'data-pick-lang="([a-z]{2})"', html) == ["es", "en"]


def test_activity_shell_language_rule_and_invite_bridge():
    with open(os.path.join(ROOT, "webapp", "static", "activity-shell.js"), encoding="utf-8") as f:
        shell = f.read()
    with open(os.path.join(ROOT, "webapp", "static", "discord-activity.js"), encoding="utf-8") as f:
        game = f.read()
    # saved choice first, then Discord's locale ("es…" -> es, else en), picker only as a fallback
    assert 'indexOf("es") === 0 ? "es" : "en"' in shell
    assert "userSettingsGetLocale" in shell and "showPicker()" in shell
    assert "openInviteDialog()" in shell and '"c24-invite"' in shell
    assert 'type: "c24-invite"' in game and "window.location.origin" in game
    assert 'scope: ["identify"]' in shell  # no new OAuth scope for the invite


# ---------- scripts/purge_languages.py ----------

class FakeDB:
    """A fake psycopg connection over two in-memory tables."""

    def __init__(self, results, games):
        self.tables = {"wordle_results": list(results), "wordle_games": list(games)}
        self.sent = []
        self.transactions = 0
        self.closed = False

    def transaction(self):
        db = self

        class Tx:
            def __enter__(self):
                db.transactions += 1
                db.snapshot = {k: list(v) for k, v in db.tables.items()}
                return self

            def __exit__(self, exc_type, *a):
                if exc_type:  # rollback
                    db.tables = db.snapshot
                return False
        return Tx()

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rows = []
        self.rowcount = -1
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.db.sent.append((sql, params))
        table = "wordle_results" if "wordle_results" in sql else "wordle_games"
        rows = self.db.tables[table]
        keep = (params or {}).get("keep")
        if sql.startswith("SELECT lang, COUNT(*)"):
            counts = {}
            for r in rows:
                counts[r["lang"]] = counts.get(r["lang"], 0) + 1
            self.rows = sorted(counts.items())
        elif sql.startswith("SELECT"):
            cols = [c.strip() for c in sql.split("FROM")[0][len("SELECT"):].split(",")]
            self.description = [(c,) for c in cols]
            self.rows = [tuple(r[c] for c in cols) for r in rows if r["lang"] not in keep]
        elif sql.startswith("DELETE"):
            assert isinstance(keep, list)
            self.db.tables[table] = [r for r in rows if r["lang"] in keep]
            self.rowcount = len(rows) - len(self.db.tables[table])
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self.rows


def _db():
    day = datetime.date(2026, 10, 28)
    res = lambda pid, lang: {"discord_id": pid, "lang": lang, "day": day, "won": True,  # noqa: E731
                             "attempts": 3, "points": 4, "finished_at": "2026-10-28T12:00:00Z"}
    game = lambda pid, lang: {"discord_id": pid, "lang": lang, "day": day,  # noqa: E731
                              "guesses": '["perro"]', "updated_at": "2026-10-28T12:00:00Z"}
    return FakeDB([res("1", "es"), res("1", "fr"), res("2", "ko"), res("2", "en")],
                  [game("1", "es"), game("1", "de")])


def _run(monkeypatch, capsys, args, db=None):
    db = db or _db()
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    code = purge.main(args, connect=lambda url: db)
    out = capsys.readouterr()
    return code, db, out.out, out.err


def test_purge_dry_run_changes_nothing(monkeypatch, capsys):
    code, db, out, _ = _run(monkeypatch, capsys, [])
    assert code == 0 and db.closed
    assert "Dry run" in out
    assert "wordle_results: en=1, es=1, fr=1, ko=1  -> to delete: 2" in out
    assert "wordle_games: de=1, es=1  -> to delete: 1" in out
    assert len(db.tables["wordle_results"]) == 4 and len(db.tables["wordle_games"]) == 2
    assert not [s for s, _ in db.sent if s.startswith("DELETE")]


def test_purge_export(monkeypatch, capsys, tmp_path):
    code, db, out, _ = _run(monkeypatch, capsys, ["--export", str(tmp_path / "out")])
    assert code == 0
    with open(tmp_path / "out" / "wordle_results.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][:2] == ["discord_id", "lang"] and sorted(r[1] for r in rows[1:]) == ["fr", "ko"]
    with open(tmp_path / "out" / "wordle_games.csv", newline="", encoding="utf-8") as f:
        assert [r[1] for r in list(csv.reader(f))[1:]] == ["de"]
    assert len(db.tables["wordle_results"]) == 4  # exporting deletes nothing


def test_purge_execute_needs_owner_approval(monkeypatch, capsys):
    code, db, _, err = _run(monkeypatch, capsys, ["--execute"])
    assert code == 2 and "--yes-i-have-owner-approval" in err
    assert db.sent == [] and len(db.tables["wordle_results"]) == 4


def test_purge_execute_deletes_in_one_transaction(monkeypatch, capsys):
    db = _db()
    before = db.transactions
    code, db, out, _ = _run(monkeypatch, capsys, ["--execute", "--yes-i-have-owner-approval"], db)
    assert code == 0
    assert {r["lang"] for r in db.tables["wordle_results"]} == {"es", "en"}
    assert {r["lang"] for r in db.tables["wordle_games"]} == {"es"}
    deletes = [(i, s, p) for i, (s, p) in enumerate(db.sent) if s.startswith("DELETE")]
    assert [s for _, s, _ in deletes] == [sql for _, sql in purge.SQL_DELETE]
    assert all(p == {"keep": ["es", "en"]} for _, _, p in deletes)  # parameterized
    assert deletes[1][0] == deletes[0][0] + 1  # back to back, same transaction
    assert db.transactions - before == 3  # counts, delete (both tables), counts again
    assert "deleted 2 rows from wordle_results" in out and "deleted 1 rows from wordle_games" in out
    assert "After:" in out and "wordle_results: en=1, es=1  -> to delete: 0" in out


def test_purge_sql_is_constant_and_parameterized():
    for sql in list(purge.SQL_COUNTS.values()) + list(purge.SQL_EXPORT.values()) + [s for _, s in purge.SQL_DELETE]:
        assert "{" not in sql and "'" not in sql
    for _, sql in purge.SQL_DELETE:
        assert sql.endswith("WHERE lang <> ALL(%(keep)s)")
    assert purge.KEEP_LANGS == app.SUPPORTED_LANGS


def test_purge_needs_database_url(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert purge.main([], connect=lambda url: pytest.fail("must not connect")) == 2
    # --env-file is read only when given, and only DATABASE_URL from it
    env = tmp_path / "env"
    env.write_text('OTHER=1\nDATABASE_URL="postgresql://from-file"\n', encoding="utf-8")
    seen = []
    assert purge.main(["--env-file", str(env)], connect=lambda url: seen.append(url) or _db()) == 0
    assert seen == ["postgresql://from-file"]
    assert "OTHER" not in os.environ
