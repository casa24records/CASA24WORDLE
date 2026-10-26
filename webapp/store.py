"""Tiny key-value store for the Discord leaderboard.

Two backends with the same methods:
- UpstashStore: Upstash Redis over its REST API (stdlib urllib, no package).
  Env: KV_REST_API_URL + KV_REST_API_TOKEN (Vercel Marketplace names) or
  UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN.
- MemoryStore: an in-process imitation of the same Redis commands, for tests
  and local development without KV. Data is lost on restart.

get_store() picks Upstash when its env vars are set, else MemoryStore when not
on Vercel, else None (the leaderboard is then off in production).

Both backends speak Redis commands through execute(*args); the helper methods
just build commands, so pipelines work the same on both.
"""

import fnmatch
import json
import os
import threading
import time
import urllib.error
import urllib.request

TIMEOUT = 5  # seconds per Upstash request


class StoreError(Exception):
    pass


class _Commands:
    """Helper methods shared by both backends (all go through execute)."""

    def execute(self, *args):  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def pipeline(self, commands):
        """Run several commands; returns their results in order."""
        return [self.execute(*cmd) for cmd in commands]

    # strings
    def get(self, key):
        return self.execute("GET", key)

    def set(self, key, value, nx=False, ex=None):
        """True when written, False when NX found the key already there."""
        cmd = ["SET", key, value]
        if nx:
            cmd.append("NX")
        if ex:
            cmd += ["EX", int(ex)]
        return self.execute(*cmd) is not None

    def incr(self, key):
        return int(self.execute("INCR", key))

    def expire(self, key, seconds):
        return self.execute("EXPIRE", key, int(seconds))

    def delete(self, *keys):
        if not keys:
            return 0
        return int(self.execute("DEL", *keys))

    # hashes
    def hget(self, key, field):
        return self.execute("HGET", key, field)

    def hset(self, key, mapping):
        if not mapping:
            return 0
        args = []
        for k, v in mapping.items():
            args += [k, v]
        return self.execute("HSET", key, *args)

    def hgetall(self, key):
        result = self.execute("HGETALL", key)
        if isinstance(result, dict):
            return dict(result)
        result = result or []
        return {result[i]: result[i + 1] for i in range(0, len(result), 2)}

    def hdel(self, key, *fields):
        if not fields:
            return 0
        return self.execute("HDEL", key, *fields)

    # sorted sets
    def zadd(self, key, score, member):
        return self.execute("ZADD", key, score, member)

    def zrem(self, key, member):
        return self.execute("ZREM", key, member)

    def zcard(self, key):
        return int(self.execute("ZCARD", key) or 0)

    def zrevrank(self, key, member):
        r = self.execute("ZREVRANK", key, member)
        return None if r is None else int(r)

    def zrevrange(self, key, start, stop):
        """[(member, score)] from the highest score down."""
        flat = self.execute("ZREVRANGE", key, start, stop, "WITHSCORES") or []
        return [(flat[i], float(flat[i + 1])) for i in range(0, len(flat), 2)]


class UpstashStore(_Commands):
    def __init__(self, url, token):
        self.url = url.rstrip("/")
        self._token = token

    def _post(self, path, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.url + path,
            data=data,
            method="POST",
            headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as e:
            # never include the token or URL in the message
            raise StoreError("store request failed: " + type(e).__name__) from None

    @staticmethod
    def _unwrap(item):
        if isinstance(item, dict) and item.get("error"):
            raise StoreError("store command failed")
        return item.get("result") if isinstance(item, dict) else None

    def execute(self, *args):
        return self._unwrap(self._post("", [str(a) for a in args]))

    def pipeline(self, commands):
        if not commands:
            return []
        body = [[str(a) for a in cmd] for cmd in commands]
        return [self._unwrap(item) for item in self._post("/pipeline", body)]


class MemoryStore(_Commands):
    """Enough of Redis for this app: strings, hashes, sorted sets, expiry."""

    def __init__(self):
        self.data = {}
        self.expires = {}
        self._lock = threading.RLock()

    def _alive(self, key):
        exp = self.expires.get(key)
        if exp is not None and exp <= time.time():
            self.data.pop(key, None)
            self.expires.pop(key, None)
        return key in self.data

    def keys(self, pattern="*"):
        with self._lock:
            return sorted(k for k in list(self.data) if self._alive(k) and fnmatch.fnmatchcase(k, pattern))

    def execute(self, *args):
        with self._lock:
            cmd = str(args[0]).upper()
            a = [str(x) for x in args[1:]]
            return getattr(self, "_c_" + cmd.lower())(*a)

    # strings
    def _c_get(self, key):
        return self.data[key] if self._alive(key) else None

    def _c_set(self, key, value, *opts):
        opts = [o.upper() for o in opts]
        if "NX" in opts and self._alive(key):
            return None
        self.data[key] = value
        self.expires.pop(key, None)
        if "EX" in opts:
            self.expires[key] = time.time() + int(opts[opts.index("EX") + 1])
        return "OK"

    def _c_incr(self, key):
        value = int(self.data[key]) + 1 if self._alive(key) else 1
        self.data[key] = str(value)
        return value

    def _c_expire(self, key, seconds):
        if not self._alive(key):
            return 0
        self.expires[key] = time.time() + int(seconds)
        return 1

    def _c_del(self, *keys):
        n = 0
        for k in keys:
            if self._alive(k):
                n += 1
            self.data.pop(k, None)
            self.expires.pop(k, None)
        return n

    # hashes
    def _hash(self, key, create=False):
        if self._alive(key):
            return self.data[key]
        if create:
            self.data[key] = {}
            return self.data[key]
        return {}

    def _c_hget(self, key, field):
        return self._hash(key).get(field)

    def _c_hset(self, key, *pairs):
        h = self._hash(key, create=True)
        added = 0
        for i in range(0, len(pairs), 2):
            added += pairs[i] not in h
            h[pairs[i]] = pairs[i + 1]
        return added

    def _c_hgetall(self, key):
        flat = []
        for k, v in self._hash(key).items():
            flat += [k, v]
        return flat

    def _c_hdel(self, key, *fields):
        h = self._hash(key)
        n = sum(1 for f in fields if h.pop(f, None) is not None)
        if self._alive(key) and not h:
            self._c_del(key)
        return n

    # sorted sets
    def _c_zadd(self, key, score, member):
        z = self._hash(key, create=True)
        added = member not in z
        z[member] = float(score)
        return int(added)

    def _c_zrem(self, key, member):
        z = self._hash(key)
        n = 1 if z.pop(member, None) is not None else 0
        if self._alive(key) and not z:
            self._c_del(key)
        return n

    def _c_zcard(self, key):
        return len(self._hash(key))

    def _ordered(self, key):
        # Redis order for ZREVRANGE: score desc, then member desc
        return sorted(self._hash(key).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)

    def _c_zrevrank(self, key, member):
        for i, (m, _) in enumerate(self._ordered(key)):
            if m == member:
                return i
        return None

    def _c_zrevrange(self, key, start, stop, *opts):
        items = self._ordered(key)
        start, stop = int(start), int(stop)
        stop = len(items) - 1 if stop < 0 else stop
        flat = []
        for m, s in items[start:stop + 1]:
            flat += [m, repr(s)]
        return flat


_memory = None
_memory_lock = threading.Lock()


def _upstash_env():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return url, token


def get_store():
    """Upstash when configured; an in-memory store locally; None on Vercel without KV."""
    global _memory
    url, token = _upstash_env()
    if url and token:
        return UpstashStore(url, token)
    if os.environ.get("VERCEL"):
        return None
    with _memory_lock:
        if _memory is None:
            _memory = MemoryStore()
        return _memory
