"""Storage for the Discord leaderboard.

Two backends with the same methods (the Store interface below):
- PostgresStore: Neon Postgres on Vercel, via psycopg 3. Env: DATABASE_URL
  (the pooled URL; it carries sslmode=require). Tables are created on first
  use (CREATE TABLE IF NOT EXISTS), all prefixed wordle_.
- MemoryStore: plain Python dicts with the same behavior, for tests and local
  development without a database. Data is lost on restart.

get_store() picks Postgres when DATABASE_URL is set, else MemoryStore when not
on Vercel, else None (the leaderboard is then off in production).

Kept per player: Discord ID, username, Discord avatar hash (only when it has
Discord's format, else NULL; refreshed at every login), a hidden flag, and per
finished game the language, day, won, attempts and points; today's guesses for
2 days; per-minute request counters. Never stored: tokens, email, IP addresses.

Days are datetime.date values (the Panama date from daily.py).
"""

import contextlib
import datetime
import os
import re
import threading

GAME_KEEP_DAYS = 2   # wordle_games rows older than this are deleted
RATE_KEEP_MINUTES = 2
RATE_BUCKETS = ("guess", "live", "state", "token")  # separate per-minute counters per player
# ("token": one global key, "activity:token", for Discord Activity logins; no IPs kept)

# Discord avatar hash: (a_)?<32 lowercase hex>. Anything else is stored as NULL.
AVATAR_HASH_RE = re.compile(r"(a_)?[0-9a-f]{32}")


def clean_avatar(avatar):
    """The avatar hash if it has Discord's format, else None."""
    return avatar if isinstance(avatar, str) and AVATAR_HASH_RE.fullmatch(avatar) else None


def _rate_key(discord_id, bucket):
    """Row key in the rate table: the ID for guesses, "<id>:live" for live polling,
    "<id>:state" for /api/state (focus, day change and sync reloads), and
    "activity:token" for all Discord Activity logins together."""
    if bucket not in RATE_BUCKETS:
        raise ValueError("unknown rate bucket")
    return discord_id if bucket == "guess" else discord_id + ":" + bucket


def _rate_keys(discord_id):
    """One player's counters ("token" is global, not a player's)."""
    return [_rate_key(discord_id, b) for b in RATE_BUCKETS if b != "token"]


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class StoreError(Exception):
    pass


class Store:
    """Interface. `tab` is a language code ("es", "de", "ko", ...) or "all" (every language)."""

    def upsert_player(self, discord_id, username, avatar=None):
        """Create or refresh a player. avatar is kept only if clean_avatar() accepts it."""
        raise NotImplementedError

    def get_player(self, discord_id):
        """{"username", "hidden"} or None."""
        raise NotImplementedError

    def get_avatar(self, discord_id):
        """The saved Discord avatar hash, or None."""
        raise NotImplementedError

    def rate_hit(self, discord_id, minute, bucket="guess"):
        """Count one request in this minute (per bucket); returns the count so far."""
        raise NotImplementedError

    def get_game(self, discord_id, lang, day):
        """(guesses list, result dict {won, attempts, points} or None), read-only."""
        raise NotImplementedError

    def game(self, discord_id, lang, day):
        """Context manager: a locked game handle (.guesses, .result, .save(guesses),
        .record(won, attempts, points) -> bool). Commits when the block ends."""
        raise NotImplementedError

    def record_result(self, discord_id, lang, day, won, attempts, points):
        """Insert a finished game once; False if that day was already recorded."""
        raise NotImplementedError

    def live(self, lang, day, exclude_id, limit=30):
        """Today's games with at least one guess, newest activity first, hidden
        players and exclude_id left out: [{id, username, avatar, guesses,
        updated_at (aware UTC datetime), finished, won}]."""
        raise NotImplementedError

    def leaderboard(self, tab, limit):
        """Ranked rows [{rank, id, username, points, wins, played}], hidden excluded."""
        raise NotImplementedError

    def standing(self, discord_id, tab):
        """The same row for one player, or None (hidden or no games)."""
        raise NotImplementedError

    def histories(self, discord_ids, tab):
        """{id: [(day, won), ...] sorted by day} for streaks."""
        raise NotImplementedError

    def delete_player(self, discord_id):
        raise NotImplementedError

    def set_hidden(self, discord_id, hidden):
        """True if the player exists."""
        raise NotImplementedError

    def close(self):
        pass


def rank_key(row):
    """Order: points, then wins, then who reached the total on an earlier day."""
    return (-row["points"], -row["wins"], row["reached"], row["id"])


###############################################################################
# In-memory backend
###############################################################################


class _MemoryGame:
    def __init__(self, st, key):
        self._st, self._key = st, key
        game = st.games.get(key)
        self.guesses = list(game["guesses"]) if game else []
        result = st.results.get(key)
        self.result = dict(result) if result else None

    def save(self, guesses):
        self._st.games[self._key] = {"guesses": list(guesses), "updated_at": _utcnow()}
        oldest = self._key[2] - datetime.timedelta(days=GAME_KEEP_DAYS)
        for k in [k for k in self._st.games if k[2] < oldest]:
            del self._st.games[k]

    def record(self, won, attempts, points):
        return self._st.record_result(*self._key, won, attempts, points)


class MemoryStore(Store):
    def __init__(self):
        self.players = {}   # id -> {"username", "hidden", "avatar"}
        self.results = {}   # (id, lang, day) -> {"won", "attempts", "points"}
        self.games = {}     # (id, lang, day) -> {"guesses": [...], "updated_at"}
        self.rate = {}      # (id or "id:live", minute) -> count
        self._lock = threading.RLock()

    def dump(self):
        """Every table, for tests that check what is stored."""
        return {"players": self.players, "results": self.results,
                "games": self.games, "rate": self.rate}

    def is_empty(self):
        return not any(self.dump().values())

    def upsert_player(self, discord_id, username, avatar=None):
        with self._lock:
            p = self.players.setdefault(discord_id, {"username": username, "hidden": False})
            p["username"] = username
            p["avatar"] = clean_avatar(avatar)

    def get_player(self, discord_id):
        with self._lock:
            p = self.players.get(discord_id)
            return {"username": p["username"], "hidden": p["hidden"]} if p else None

    def get_avatar(self, discord_id):
        with self._lock:
            p = self.players.get(discord_id)
            return p.get("avatar") if p else None

    def rate_hit(self, discord_id, minute, bucket="guess"):
        with self._lock:
            key = (_rate_key(discord_id, bucket), minute)
            self.rate[key] = self.rate.get(key, 0) + 1
            for k in [k for k in self.rate if k[1] < minute - RATE_KEEP_MINUTES]:
                del self.rate[k]
            return self.rate[key]

    def get_game(self, discord_id, lang, day):
        with self._lock:
            g = _MemoryGame(self, (discord_id, lang, day))
            return g.guesses, g.result

    @contextlib.contextmanager
    def game(self, discord_id, lang, day):
        with self._lock:
            if discord_id not in self.players:
                raise StoreError("unknown player")
            yield _MemoryGame(self, (discord_id, lang, day))

    def record_result(self, discord_id, lang, day, won, attempts, points):
        with self._lock:
            if discord_id not in self.players:
                raise StoreError("unknown player")
            key = (discord_id, lang, day)
            if key in self.results:
                return False
            self.results[key] = {"won": bool(won), "attempts": int(attempts), "points": int(points)}
            return True

    def _ranked(self, tab):
        agg = {}
        for (pid, lang, day), r in self.results.items():
            player = self.players.get(pid)
            if not player or player["hidden"] or (tab != "all" and lang != tab):
                continue
            a = agg.setdefault(pid, {"id": pid, "username": player["username"], "points": 0,
                                     "wins": 0, "played": 0, "_point_days": [], "_days": []})
            a["points"] += r["points"]
            a["wins"] += 1 if r["won"] else 0
            a["played"] += 1
            a["_days"].append(day)
            if r["points"] > 0:
                a["_point_days"].append(day)
        rows = []
        for a in agg.values():
            a["reached"] = max(a.pop("_point_days")) if a["_point_days"] else min(a["_days"])
            a.pop("_days")
            rows.append(a)
        rows.sort(key=rank_key)
        return [{"rank": i + 1, **{k: v for k, v in r.items() if k != "reached"}}
                for i, r in enumerate(rows)]

    def live(self, lang, day, exclude_id, limit=30):
        with self._lock:
            out = []
            for (pid, g_lang, g_day), g in self.games.items():
                player = self.players.get(pid)
                if (g_lang != lang or g_day != day or pid == exclude_id or not player
                        or player["hidden"] or not g["guesses"]):
                    continue
                result = self.results.get((pid, g_lang, g_day))
                out.append({"id": pid, "username": player["username"],
                            "avatar": player.get("avatar"), "guesses": list(g["guesses"]),
                            "updated_at": g["updated_at"], "finished": result is not None,
                            "won": bool(result and result["won"])})
            out.sort(key=lambda r: r["updated_at"], reverse=True)
            return out[:max(0, int(limit))]

    def leaderboard(self, tab, limit):
        with self._lock:
            return self._ranked(tab)[:limit]

    def standing(self, discord_id, tab):
        with self._lock:
            return next((r for r in self._ranked(tab) if r["id"] == discord_id), None)

    def histories(self, discord_ids, tab):
        with self._lock:
            out = {pid: [] for pid in discord_ids}
            for (pid, lang, day), r in sorted(self.results.items(), key=lambda kv: kv[0][2]):
                if pid in out and (tab == "all" or lang == tab):
                    out[pid].append((day, r["won"]))
            return out

    def delete_player(self, discord_id):
        with self._lock:
            self.players.pop(discord_id, None)
            for table in (self.results, self.games):
                for k in [k for k in table if k[0] == discord_id]:
                    del table[k]
            rate_keys = set(_rate_keys(discord_id))
            for k in [k for k in self.rate if k[0] in rate_keys]:
                del self.rate[k]

    def set_hidden(self, discord_id, hidden):
        with self._lock:
            if discord_id not in self.players:
                return False
            self.players[discord_id]["hidden"] = bool(hidden)
            return True


###############################################################################
# Postgres backend (Neon). Every query is a constant with %s / %(name)s
# placeholders; values are always passed as parameters.
###############################################################################

SCHEMA_LOCK_ID = 2424_2026  # pg_advisory_xact_lock id, so two cold starts don't race

SQL_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS wordle_players (
        discord_id text PRIMARY KEY,
        username text NOT NULL,
        hidden boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS wordle_results (
        discord_id text NOT NULL REFERENCES wordle_players ON DELETE CASCADE,
        lang text NOT NULL,
        day date NOT NULL,
        won boolean NOT NULL,
        attempts integer NOT NULL,
        points integer NOT NULL,
        finished_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (discord_id, lang, day))""",
    """CREATE TABLE IF NOT EXISTS wordle_games (
        discord_id text NOT NULL REFERENCES wordle_players ON DELETE CASCADE,
        lang text NOT NULL,
        day date NOT NULL,
        guesses jsonb NOT NULL DEFAULT '[]'::jsonb,
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (discord_id, lang, day))""",
    """CREATE TABLE IF NOT EXISTS wordle_rate (
        discord_id text NOT NULL,
        minute bigint NOT NULL,
        count integer NOT NULL,
        PRIMARY KEY (discord_id, minute))""",
    # added 2026-10-27 for the live view (existing databases get it on first use)
    "ALTER TABLE wordle_players ADD COLUMN IF NOT EXISTS avatar text",
    "CREATE INDEX IF NOT EXISTS wordle_games_lang_day ON wordle_games (lang, day, updated_at DESC)",
)

SQL_SCHEMA_LOCK = "SELECT pg_advisory_xact_lock(%s)"

SQL_UPSERT_PLAYER = """
    INSERT INTO wordle_players (discord_id, username, avatar) VALUES (%s, %s, %s)
    ON CONFLICT (discord_id) DO UPDATE SET username = EXCLUDED.username, avatar = EXCLUDED.avatar"""

SQL_GET_PLAYER = "SELECT username, hidden FROM wordle_players WHERE discord_id = %s"
SQL_GET_AVATAR = "SELECT avatar FROM wordle_players WHERE discord_id = %s"

SQL_RATE_HIT = """
    INSERT INTO wordle_rate (discord_id, minute, count) VALUES (%s, %s, 1)
    ON CONFLICT (discord_id, minute) DO UPDATE SET count = wordle_rate.count + 1
    RETURNING count"""

SQL_RATE_CLEANUP = "DELETE FROM wordle_rate WHERE minute < %s"

SQL_GAME_ENSURE = """
    INSERT INTO wordle_games (discord_id, lang, day) VALUES (%s, %s, %s)
    ON CONFLICT (discord_id, lang, day) DO NOTHING"""

SQL_GAME_LOCK = """
    SELECT guesses FROM wordle_games
    WHERE discord_id = %s AND lang = %s AND day = %s FOR UPDATE"""

SQL_GAME_GET = "SELECT guesses FROM wordle_games WHERE discord_id = %s AND lang = %s AND day = %s"

SQL_GAME_SAVE = """
    UPDATE wordle_games SET guesses = %s, updated_at = now()
    WHERE discord_id = %s AND lang = %s AND day = %s"""

SQL_GAME_CLEANUP = "DELETE FROM wordle_games WHERE day < %s"

# Live view: everyone else's game today in one language (params: lang, day,
# exclude_id, limit). Words are read here but app.py only sends colors.
SQL_LIVE = """
    SELECT g.discord_id, p.username, p.avatar, g.guesses, g.updated_at,
           (r.discord_id IS NOT NULL) AS finished, COALESCE(r.won, false) AS won
    FROM wordle_games g
    JOIN wordle_players p ON p.discord_id = g.discord_id
    LEFT JOIN wordle_results r
           ON r.discord_id = g.discord_id AND r.lang = g.lang AND r.day = g.day
    WHERE g.lang = %s AND g.day = %s AND NOT p.hidden AND g.discord_id <> %s
      AND jsonb_array_length(g.guesses) > 0
    ORDER BY g.updated_at DESC
    LIMIT %s"""

SQL_RESULT_GET = """
    SELECT won, attempts, points FROM wordle_results
    WHERE discord_id = %s AND lang = %s AND day = %s"""

SQL_RESULT_INSERT = """
    INSERT INTO wordle_results (discord_id, lang, day, won, attempts, points)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (discord_id, lang, day) DO NOTHING
    RETURNING 1"""

# "reached": the last day the player scored points (when the current total was
# reached); for players with no points yet, their first day.
SQL_RANKED = """
    WITH agg AS (
        SELECT r.discord_id, p.username,
               SUM(r.points)::int AS points,
               (COUNT(*) FILTER (WHERE r.won))::int AS wins,
               COUNT(*)::int AS played,
               COALESCE(MAX(r.day) FILTER (WHERE r.points > 0), MIN(r.day)) AS reached
        FROM wordle_results r JOIN wordle_players p ON p.discord_id = r.discord_id
        WHERE NOT p.hidden AND (%(tab)s::text = 'all' OR r.lang = %(tab)s::text)
        GROUP BY r.discord_id, p.username
    ), ranked AS (
        SELECT agg.*, ROW_NUMBER() OVER (
            ORDER BY points DESC, wins DESC, reached ASC, discord_id ASC) AS rank
        FROM agg
    )"""

SQL_LEADERBOARD = SQL_RANKED + """
    SELECT rank, discord_id, username, points, wins, played FROM ranked
    ORDER BY rank LIMIT %(limit)s"""

SQL_STANDING = SQL_RANKED + """
    SELECT rank, discord_id, username, points, wins, played FROM ranked
    WHERE discord_id = %(id)s"""

SQL_HISTORIES = """
    SELECT discord_id, day, won FROM wordle_results
    WHERE discord_id = ANY(%(ids)s) AND (%(tab)s::text = 'all' OR lang = %(tab)s::text)
    ORDER BY day"""

SQL_DELETE_PLAYER = "DELETE FROM wordle_players WHERE discord_id = %s"  # cascades
SQL_DELETE_RATE = "DELETE FROM wordle_rate WHERE discord_id = ANY(%s)"  # every bucket
SQL_SET_HIDDEN = "UPDATE wordle_players SET hidden = %s WHERE discord_id = %s RETURNING 1"


def _row(r):
    return {"rank": int(r[0]), "id": r[1], "username": r[2],
            "points": int(r[3]), "wins": int(r[4]), "played": int(r[5])}


class _PostgresGame:
    def __init__(self, cur, key):
        self._cur, self._key = cur, key
        cur.execute(SQL_GAME_ENSURE, key)
        cur.execute(SQL_GAME_LOCK, key)  # row lock: concurrent guesses wait here
        row = cur.fetchone()
        self.guesses = list(row[0]) if row and isinstance(row[0], list) else []
        cur.execute(SQL_RESULT_GET, key)
        r = cur.fetchone()
        self.result = {"won": r[0], "attempts": r[1], "points": r[2]} if r else None

    def save(self, guesses):
        from psycopg.types.json import Jsonb
        self._cur.execute(SQL_GAME_SAVE, (Jsonb(list(guesses)), *self._key))
        self._cur.execute(SQL_GAME_CLEANUP, (self._key[2] - datetime.timedelta(days=GAME_KEEP_DAYS),))

    def record(self, won, attempts, points):
        self._cur.execute(SQL_RESULT_INSERT, (*self._key, bool(won), int(attempts), int(points)))
        return self._cur.fetchone() is not None


class PostgresStore(Store):
    """One connection per thread, opened lazily and closed after each request
    (app.py calls close_connections() at teardown), so serverless instances
    don't hold idle connections. Autocommit is off; every method runs in an
    explicit transaction."""

    _schema_ready = False
    _schema_lock = threading.Lock()

    def __init__(self, url):
        self._url = url
        self._local = threading.local()

    def _connect(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None and not conn.closed and not conn.broken:
            return conn
        import psycopg
        # prepare_threshold=None: no server-side prepared statements (pooled URL)
        conn = psycopg.connect(self._url, connect_timeout=5, autocommit=False, prepare_threshold=None)
        self._local.conn = conn
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn):
        cls = type(self)
        with cls._schema_lock:
            if cls._schema_ready:
                return
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(SQL_SCHEMA_LOCK, (SCHEMA_LOCK_ID,))
                for statement in SQL_SCHEMA:
                    cur.execute(statement)
            cls._schema_ready = True

    @contextlib.contextmanager
    def _tx(self):
        import psycopg
        try:
            conn = self._connect()
            with conn.transaction(), conn.cursor() as cur:
                yield cur
        except psycopg.Error as e:
            self.close()
            # no query text or values in the message
            raise StoreError("database error: " + type(e).__name__) from None

    def close(self):
        conn = getattr(self._local, "conn", None)
        self._local.conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def upsert_player(self, discord_id, username, avatar=None):
        with self._tx() as cur:
            cur.execute(SQL_UPSERT_PLAYER, (discord_id, username, clean_avatar(avatar)))

    def get_player(self, discord_id):
        with self._tx() as cur:
            cur.execute(SQL_GET_PLAYER, (discord_id,))
            r = cur.fetchone()
        return {"username": r[0], "hidden": bool(r[1])} if r else None

    def get_avatar(self, discord_id):
        with self._tx() as cur:
            cur.execute(SQL_GET_AVATAR, (discord_id,))
            r = cur.fetchone()
        return r[0] if r else None

    def rate_hit(self, discord_id, minute, bucket="guess"):
        with self._tx() as cur:
            cur.execute(SQL_RATE_HIT, (_rate_key(discord_id, bucket), minute))
            count = int(cur.fetchone()[0])
            if count == 1:
                cur.execute(SQL_RATE_CLEANUP, (minute - RATE_KEEP_MINUTES,))
        return count

    def get_game(self, discord_id, lang, day):
        key = (discord_id, lang, day)
        with self._tx() as cur:
            cur.execute(SQL_GAME_GET, key)
            row = cur.fetchone()
            cur.execute(SQL_RESULT_GET, key)
            r = cur.fetchone()
        guesses = list(row[0]) if row and isinstance(row[0], list) else []
        return guesses, ({"won": r[0], "attempts": r[1], "points": r[2]} if r else None)

    @contextlib.contextmanager
    def game(self, discord_id, lang, day):
        with self._tx() as cur:
            yield _PostgresGame(cur, (discord_id, lang, day))

    def record_result(self, discord_id, lang, day, won, attempts, points):
        with self._tx() as cur:
            cur.execute(SQL_RESULT_INSERT, (discord_id, lang, day, bool(won), int(attempts), int(points)))
            return cur.fetchone() is not None

    def live(self, lang, day, exclude_id, limit=30):
        with self._tx() as cur:
            cur.execute(SQL_LIVE, (lang, day, exclude_id, int(limit)))
            rows = cur.fetchall()
        return [{"id": r[0], "username": r[1], "avatar": clean_avatar(r[2]),
                 "guesses": list(r[3]) if isinstance(r[3], list) else [],
                 "updated_at": r[4], "finished": bool(r[5]), "won": bool(r[6])} for r in rows]

    def leaderboard(self, tab, limit):
        with self._tx() as cur:
            cur.execute(SQL_LEADERBOARD, {"tab": tab, "limit": int(limit)})
            return [_row(r) for r in cur.fetchall()]

    def standing(self, discord_id, tab):
        with self._tx() as cur:
            cur.execute(SQL_STANDING, {"tab": tab, "id": discord_id})
            r = cur.fetchone()
        return _row(r) if r else None

    def histories(self, discord_ids, tab):
        out = {pid: [] for pid in discord_ids}
        if not out:
            return out
        with self._tx() as cur:
            cur.execute(SQL_HISTORIES, {"ids": list(out), "tab": tab})
            for pid, day, won in cur.fetchall():
                out[pid].append((day, bool(won)))
        return out

    def delete_player(self, discord_id):
        with self._tx() as cur:
            cur.execute(SQL_DELETE_PLAYER, (discord_id,))
            cur.execute(SQL_DELETE_RATE, (_rate_keys(discord_id),))

    def set_hidden(self, discord_id, hidden):
        with self._tx() as cur:
            cur.execute(SQL_SET_HIDDEN, (bool(hidden), discord_id))
            return cur.fetchone() is not None


###############################################################################

_memory = None
_postgres = {}
_choose_lock = threading.Lock()


def get_store():
    """Postgres when DATABASE_URL is set; in-memory locally; None on Vercel without it."""
    global _memory
    url = os.environ.get("DATABASE_URL")
    with _choose_lock:
        if url:
            if url not in _postgres:
                _postgres[url] = PostgresStore(url)  # connects lazily, on first query
            return _postgres[url]
        if os.environ.get("VERCEL"):
            return None
        if _memory is None:
            _memory = MemoryStore()
        return _memory


def close_connections():
    """Close this thread's database connections (called after every request)."""
    for st in list(_postgres.values()):
        st.close()
