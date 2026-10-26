from flask import (
    Flask,
    jsonify,
    render_template,
    make_response,
    redirect,
    request,
    session,
    url_for,
    abort,
)
from markupsafe import Markup
import datetime
import hashlib
import hmac
import json
import time
import os
import sys

# Folder of this file. Lets the app run from any working directory
# (locally from webapp/, on Vercel from the repo root).
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)



def load_env_local(path):
    """Read KEY=VALUE lines from .env.local (made by `vercel env pull`) into
    os.environ. Only off Vercel, never overrides a variable that is already
    set. Not called on Vercel or under pytest (tests never see real secrets or KV)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


if not os.environ.get("VERCEL") and "pytest" not in sys.modules:
    load_env_local(os.path.join(os.path.dirname(APP_DIR), ".env.local"))

import daily
import discord_auth
import leaderboard as lbrules
import store as store_mod
from itsdangerous import URLSafeTimedSerializer, BadSignature
from urllib.parse import urlparse
from werkzeug.middleware.proxy_fix import ProxyFix
from flask.sessions import SecureCookieSessionInterface
import glob
import random

# set random seed 42 for reproducibility (important to maintain stable word lists)
random.seed(42)

app = Flask(__name__)
# Behind Vercel (or any proxy) trust X-Forwarded-Proto/Host so request.url_root
# (sitemap, share links) shows the visitor's real https address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Demo mode (/demo) is for the Casa 24 team. Its password lives ONLY in the
# DEMO_PASSWORD environment variable (the repo is public, never commit it).
# No DEMO_PASSWORD -> no Demo button and /demo answers 404.
DEMO_LANGS = ("es", "en")


def demo_password():
    return os.environ.get("DEMO_PASSWORD", "")


def demo_enabled():
    return bool(demo_password())


def _secret_key():
    # SECRET_KEY if set; otherwise derived from the demo password, so every
    # Vercel instance signs the demo session cookie the same way.
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    return hashlib.sha256(("casa24-demo-session:" + demo_password()).encode()).hexdigest()


app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


class _EnvKeySessionInterface(SecureCookieSessionInterface):
    """Signs the session with a key read from the environment on every use.

    Setting app.secret_key in before_request is too late (Flask opens the
    session first), so a cold Vercel instance would fail the first login.
    Reading it here also means a new DEMO_PASSWORD logs everyone out at once.
    """

    def get_signing_serializer(self, app):
        app.secret_key = _secret_key()
        return super().get_signing_serializer(app)


app.session_interface = _EnvKeySessionInterface()
app.jinja_env.policies["json.dumps_kwargs"] = {"sort_keys": False}  # keep menu order (Spanish, English first)

###############################################################################
# VERSIONED STATIC URLS
###############################################################################
# Every static URL in the templates goes through asset(), which adds
# ?v=<short hash of the file>. vercel.json caches /static/ for a year
# ("immutable") only when ?v= is present, so a changed file gets a new URL
# and visitors never keep an old copy.

STATIC_DIR = os.path.join(APP_DIR, "static")
_asset_versions = {}
_fallback_version = None


def _fallback():
    """Version used if a file can't be read (never crash over a cache key).

    The deploy's git commit on Vercel, else a hash of all static files,
    else the start time (always fresh, just less cacheable)."""
    global _fallback_version
    if _fallback_version is None:
        sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
        if sha:
            _fallback_version = sha[:10]
        else:
            try:
                _fallback_version = _hash_path(STATIC_DIR)
            except Exception:
                _fallback_version = ""
            if not _fallback_version:
                _fallback_version = hashlib.sha1(str(time.time()).encode()).hexdigest()[:10]
    return _fallback_version


def _hash_path(path):
    """Short content hash of a file, or of every file in a folder (names + contents)."""
    h = hashlib.sha1()
    if os.path.isdir(path):
        found = False
        for folder, dirs, files in os.walk(path):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(folder, name)
                h.update(os.path.relpath(full, path).encode())
                with open(full, "rb") as f:
                    h.update(f.read())
                found = True
        if not found:
            return ""
    else:
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:10]


def asset_version(path):
    """Content version of a static file or folder (cached after first use)."""
    if path not in _asset_versions:
        try:
            version = _hash_path(os.path.join(STATIC_DIR, path))
        except Exception:
            version = ""
        _asset_versions[path] = version or _fallback()
    return _asset_versions[path]


def asset(path):
    """/static/<path>?v=<hash>: use for every static link in the templates."""
    return url_for("static", filename=path) + "?v=" + asset_version(path)


def json_script(obj):
    """JSON for a <script type="application/json"> block: raw UTF-8 (not
    \\uXXXX, which doubled the Arabic/Korean pages) with < > & ' escaped like
    Flask's tojson, so "</script>" inside a string can't end the block."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    text = (text.replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace("'", "\\u0027"))
    return Markup(text)


@app.context_processor
def inject_asset_helpers():
    return {"asset": asset, "asset_version": asset_version, "json_script": json_script}


###############################################################################
# DATA
###############################################################################

data_dir = os.path.join(APP_DIR, "data") + "/"


def load_characters(lang):
    with open(f"{data_dir}languages/{lang}/{lang}_characters.txt", "r") as f:
        characters = [line.strip() for line in f]
    return characters


language_codes = [f.split("/")[-1] for f in glob.glob(f"{data_dir}/languages/*")]
# Spanish and English first on the menu, then the rest alphabetically
language_codes = sorted(language_codes, key=lambda c: (c not in ("es", "en"), c != "es", c))
language_characters = {lang: load_characters(lang) for lang in language_codes}


def load_words(lang):
    """loads the words and does some basic QA"""
    _5words = []
    with open(f"{data_dir}/languages/{lang}/{lang}_5words.txt", "r") as f:
        for line in f:
            _5words.append(line.strip())
    # QA
    _5words = [word.lower() for word in _5words if len(word) == 5 and word.isalpha()]
    # remove words without correct characters
    _5words = [
        word
        for word in _5words
        if all([char in language_characters[lang] for char in word])
    ]

    # we don't want words in order, so if .txt is not pre-shuffled, shuffle
    last_letter = ""
    n_in_order = 0
    for word in _5words:
        letter = word[0]
        # check if sorted
        if letter <= last_letter:
            n_in_order += 1
        last_letter = letter
    # if 80% of words are in order, then we consider the list sorted and we shuffle it deterministically
    if n_in_order / len(_5words) > 0.8:
        random.shuffle(_5words)
        print(f"{lang} words are sorted, shuffling")
    return _5words


def load_supplemental_words(lang):
    """loads the supplemental words file if it exists"""
    try:
        with open(f"{data_dir}languages/{lang}/{lang}_5words_supplement.txt", "r") as f:
            supplemental_words = [line.strip() for line in f]
        supplemental_words = [
            word
            for word in supplemental_words
            if all([char in language_characters[lang] for char in word])
        ]
    except FileNotFoundError:
        supplemental_words = []
    return supplemental_words


def load_language_config(lang):
    with open(f"{data_dir}languages/{lang}/language_config.json", "r") as f:
        return json.load(f)


def load_keyboard(lang):
    """
    Return normalized keyboard layouts for a language.

    Reads the language-specific keyboard JSON, handles legacy formats,
    and always returns a dict with default layout metadata.
    """
    keyboard_path = f"{data_dir}languages/{lang}/{lang}_keyboard.json"
    try:
        with open(keyboard_path, "r") as f:
            keyboard_data = json.load(f)
    except FileNotFoundError:
        return {"default": None, "layouts": {}}
    except Exception:
        return {"default": None, "layouts": {}}

    if isinstance(keyboard_data, list):
        if not keyboard_data:
            return {"default": None, "layouts": {}}
        return {
            "default": "default",
            "layouts": {"default": {"label": "Default", "rows": keyboard_data}},
        }

    if not isinstance(keyboard_data, dict):
        return {"default": None, "layouts": {}}

    layouts_block = keyboard_data.get("layouts")
    if isinstance(layouts_block, dict):
        source_layouts = layouts_block
    else:
        source_layouts = {
            key: value for key, value in keyboard_data.items() if key != "default"
        }

    normalized_layouts = {}
    for layout_name, layout_value in source_layouts.items():
        if isinstance(layout_value, dict):
            rows = layout_value.get("rows", [])
            label = layout_value.get("label") or layout_name.replace("_", " ").title()
        else:
            rows = layout_value
            label = layout_name.replace("_", " ").title()
        normalized_layouts[layout_name] = {"label": label, "rows": rows}

    default_layout = keyboard_data.get("default")
    if default_layout not in normalized_layouts:
        default_layout = next(iter(normalized_layouts), None)

    return {"default": default_layout, "layouts": normalized_layouts}


def get_todays_idx():
    """Puzzle number for today in Panama time (see daily.py)."""
    return daily.day_index(daily.panama_today())


def load_casa24_words(lang, tier):
    """Casa 24 word files: 'answers', 'guesses', or private 'aliases'."""
    path = f"{data_dir}languages/{lang}/{lang}_5words_casa24_{tier}.txt"
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        words = [line.strip().lower() for line in f]
    return [w for w in words if w and not w.startswith("#")]


def load_casa24(lang):
    answers = load_casa24_words(lang, "answers")
    guesses = load_casa24_words(lang, "guesses")
    # member aliases stay off unless explicitly turned on
    if os.environ.get("CASA24_ENABLE_ALIASES") == "1":
        guesses += load_casa24_words(lang, "aliases")
    return answers, guesses


language_codes_5words = {l_code: load_words(l_code) for l_code in language_codes}
casa24_words = {l_code: load_casa24(l_code) for l_code in language_codes}
# Valid guesses that are not in the main list: the supplement plus all Casa 24 words.
language_codes_5words_supplements = {
    l_code: sorted(
        set(load_supplemental_words(l_code))
        | set(casa24_words[l_code][0])
        | set(casa24_words[l_code][1])
    )
    for l_code in language_codes
}
language_configs = {l_code: load_language_config(l_code) for l_code in language_codes}

keyboards = {k: load_keyboard(k) for k in language_codes}


def load_languages():
    """returns a dict of language codes mapped to their english name and native name"""

    languages = {}
    # for each language folder, get the language config.name and config.name_natove
    for lang in language_codes:
        language_config = language_configs[lang]
        languages[lang] = {
            "language_name": language_config["name"],
            "language_name_native": language_config["name_native"],
            "language_code": lang,
            "right_to_left": str(language_config.get("right_to_left", "false")).lower(),
        }
    return languages


languages = load_languages()



###############################################################################
# CLASSES
###############################################################################


class Language:
    """Holds the attributes of a language"""

    def __init__(self, language_code, word_list, keyboard_layout=None):
        """
        Populate language metadata and select the desired keyboard layout.

        Parameters:
            language_code: Two-letter language identifier (e.g. 'en').
            word_list: Base five-letter word list for the language.
            keyboard_layout: Optional layout name chosen via query/cookie.
        """
        self.language_code = language_code
        self.word_list = word_list
        self.word_list_supplement = language_codes_5words_supplements[language_code]
        todays_idx = get_todays_idx()
        self.daily_word = daily.pick_daily_word(
            language_code, todays_idx, word_list, casa24_words[language_code][0]
        )
        self.todays_idx = todays_idx
        self.config = language_configs[language_code]

        self.characters = language_characters[language_code]
        # remove chars that aren't used to reduce bloat a bit
        characters_used = []
        for word in self.word_list:
            characters_used += list(word)
        characters_used = list(set(characters_used))
        self.characters = [char for char in self.characters if char in characters_used]

        keyboard_config = keyboards.get(language_code, {"default": None, "layouts": {}})
        self.keyboard_layouts = self._build_keyboard_layouts(keyboard_config)
        self.keyboard_layout_name = self._select_keyboard_layout(
            keyboard_layout, keyboard_config.get("default")
        )
        layout_meta = self.keyboard_layouts[self.keyboard_layout_name]
        self.keyboard = layout_meta["rows"]

    def _build_keyboard_layouts(self, keyboard_config):
        """
        Build canonical layout metadata from the raw keyboard config.

        Ensures every layout has a label/rows and falls back to an
        auto-generated alphabetical layout when no layouts are provided.
        """
        layouts = {}
        for layout_name, layout_meta in keyboard_config.get("layouts", {}).items():
            label = layout_meta.get("label") or layout_name.replace("_", " ").title()
            rows = layout_meta.get("rows", [])
            layouts[layout_name] = {"label": label, "rows": rows}

        if not layouts:
            layouts["alphabetical"] = {
                "label": "Alphabetical",
                "rows": self._generate_alphabetical_keyboard(),
            }
        return layouts

    def _select_keyboard_layout(self, requested_layout, default_layout):
        """
        Choose the active keyboard layout in priority order.

        Prefers the user-requested layout, then the config default,
        and finally falls back to the first available layout.
        """
        if requested_layout and requested_layout in self.keyboard_layouts:
            return requested_layout
        if default_layout and default_layout in self.keyboard_layouts:
            return default_layout
        return next(iter(self.keyboard_layouts))

    def _generate_alphabetical_keyboard(self):
        """
        Lay the letters out in alphabetical order, about 10 keys per row.

        ⇨ (Enter) starts the last row and ⌫ ends it. Keys are spread evenly
        over the rows (earlier rows get the extra key), so no row has more
        than 11 keys and the last row isn't crammed or nearly empty.
        """
        letters = list(self.characters)
        if not letters:
            return []
        total = len(letters) + 2  # plus ⇨ and ⌫
        n_rows = max(1, -(-len(letters) // 10))
        while -(-total // n_rows) > 11:
            n_rows += 1
        base, extra = divmod(total, n_rows)
        sizes = [base + 1 if i < extra else base for i in range(n_rows)]
        keyboard = []
        pos = 0
        for i, size in enumerate(sizes):
            if i == n_rows - 1:
                keyboard.append(["⇨"] + letters[pos:] + ["⌫"])
            else:
                keyboard.append(letters[pos:pos + size])
                pos += size
        return keyboard


###############################################################################
# ROUTES
###############################################################################


@app.route("/")
def index():
    return render_template(
        "index.html",
        languages=languages,
        language_codes=language_codes,
        todays_idx=get_todays_idx(),
        demo_enabled=demo_enabled(),
        texts={lang: language_configs[lang]["text"] for lang in DEMO_LANGS},
    )


# sitemap
@app.route("/sitemap.xml")
def site_map():
    response = make_response(
        render_template(
            "sitemap.xml", languages=languages, base_url=request.url_root.rstrip("/")
        )
    )
    response.headers["Content-Type"] = "application/xml"
    return response


# demo mode for the team: random word, restart, fill in the answer
def _demo_logged_in():
    return demo_enabled() and session.get("demo") is True


@app.route("/demo", methods=["GET", "POST"])
def demo_login():
    if not demo_enabled():
        abort(404)
    error = False
    if request.method == "POST":
        given = request.form.get("password", "")
        if hmac.compare_digest(given.encode(), demo_password().encode()):
            session.permanent = True
            session["demo"] = True
            return redirect("/demo/es")
        error = True
    elif _demo_logged_in():
        return redirect("/demo/es")
    texts = {lang: language_configs[lang]["text"] for lang in DEMO_LANGS}
    response = make_response(
        render_template("demo_login.html", error=error, texts=texts), 401 if error else 200
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/demo/<lang_code>")
def demo_game(lang_code):
    if not demo_enabled():
        abort(404)
    if not _demo_logged_in():
        return redirect("/demo")
    if lang_code not in DEMO_LANGS:
        return redirect("/demo/es")
    word_list = language_codes_5words[lang_code]
    language = Language(lang_code, word_list, request.cookies.get(f"keyboard_layout_{lang_code}"))
    # first open: the real word of the day, like the normal game.
    # Restart (?skip=<current word>): a random answer from the same pool, never the same word.
    if "skip" in request.args:
        pool = sorted(set(word_list) | set(casa24_words[lang_code][0]))
        skip = request.args.get("skip", "")
        choices = [w for w in pool if w != skip] or pool
        language.daily_word = random.SystemRandom().choice(choices)
    response = make_response(render_template("game.html", language=language, demo=True))
    response.headers["Cache-Control"] = "no-store"
    return response


# arbitrary app route
@app.route("/<lang_code>")
def language(lang_code):
    if lang_code not in language_codes:
        # removed or unknown languages go back to the menu instead of an error
        return redirect("/")
    word_list = language_codes_5words[lang_code]
    cookie_key = f"keyboard_layout_{lang_code}"
    requested_layout = request.args.get("layout") or request.cookies.get(cookie_key)
    language = Language(lang_code, word_list, requested_layout)
    response = make_response(render_template("game.html", language=language, demo=False))
    selected_layout = language.keyboard_layout_name
    if request.cookies.get(cookie_key) != selected_layout:
        response.set_cookie(
            cookie_key,
            selected_layout,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
        )
    return response

###############################################################################
# DISCORD LEADERBOARD (es/en only)
###############################################################################
# Data kept (see webapp/store.py for the backends):
#   player:{id}              hash: username, hidden ("1"), and per scope
#                            (es / en / all): {scope}_points, _wins, _played,
#                            _cur_streak, _best_streak, _last_win_day, _reached_day
#   game:{id}:{lang}:{date}  JSON list of today's guesses (expires after 2 days)
#   result:{id}:{lang}:{date} JSON {won, attempts, points}, written once (SET NX)
#   keys:{id}                hash whose fields are this player's result/game
#                            keys, so "delete my data" needs no SCAN
#   lb:es / lb:en / lb:all   sorted sets, member = Discord ID, score = leaderboard.score()
#   rl:{id}:{minute}         guess counter for the rate limit (expires in 120 s)
#   lock:{id}                5-second lock so two guesses can't race
# Never stored: Discord tokens, avatar, email, IP addresses.
#
# POSTs check that Origin (or Referer) matches this host when the browser sends
# one; the c24_lb cookie is also SameSite=Lax, so other sites can't post with it.

import secrets
import unicodedata

LB_LANGS = ("es", "en")
LB_TABS = ("es", "en", "all")
LB_COOKIE = "c24_lb"
LB_COOKIE_AGE = 30 * 24 * 3600
OAUTH_COOKIE = "c24_oauth"
OAUTH_COOKIE_AGE = 10 * 60
OAUTH_COOKIE_PATH = "/auth/discord"
GAME_TTL = 2 * 24 * 3600
RATE_LIMIT_PER_MINUTE = 30
TOP_N = 50
STAT_FIELDS = ("points", "wins", "played", "cur_streak", "best_streak", "last_win_day", "reached_day")


def lb_secret():
    return os.environ.get("SECRET_KEY", "")


def lb_store():
    try:
        return store_mod.get_store()
    except Exception:
        return None


def lb_enabled():
    """Discord app + SECRET_KEY + a store: otherwise every leaderboard route is 404."""
    return bool(discord_auth.client_id() and discord_auth.client_secret() and lb_secret()) \
        and lb_store() is not None


def lb_admin_ids():
    return {x.strip() for x in os.environ.get("ADMIN_DISCORD_IDS", "").split(",") if x.strip()}


def _serializer(salt):
    return URLSafeTimedSerializer(lb_secret(), salt=salt)


def lb_player_id():
    """Discord ID from the signed c24_lb cookie (the cookie holds nothing else)."""
    raw = request.cookies.get(LB_COOKIE)
    if not raw or not lb_secret():
        return None
    try:
        value = _serializer("c24-lb").loads(raw, max_age=LB_COOKIE_AGE)
    except BadSignature:
        return None
    return value if isinstance(value, str) and value.isdigit() else None


def lb_current_user(st=None):
    """{"id", "username"} for the logged-in player, None if logged out or deleted."""
    pid = lb_player_id()
    st = st or lb_store()
    if not pid or st is None:
        return None
    try:
        username = st.hget(f"player:{pid}", "username")
    except store_mod.StoreError:
        return None
    return {"id": pid, "username": username} if username else None


@app.context_processor
def inject_leaderboard():
    enabled = lb_enabled()
    user = lb_current_user() if enabled and request.cookies.get(LB_COOKIE) else None
    return {"lb_enabled": enabled, "lb_user": user}


def _same_origin():
    """False when the browser says the POST came from another site."""
    for header in ("Origin", "Referer"):
        value = request.headers.get(header)
        if value:
            return value != "null" and urlparse(value).netloc == request.host
    return True


def _safe_next(value):
    """Only relative paths on this site ("/lb/es"), never "//evil" or a full URL."""
    if (isinstance(value, str) and value.startswith("/") and not value.startswith("//")
            and "\\" not in value and value.isprintable() and len(value) <= 200):
        return value
    return "/"


def _set_lb_cookie(response, discord_id):
    response.set_cookie(
        LB_COOKIE, _serializer("c24-lb").dumps(discord_id), max_age=LB_COOKIE_AGE,
        httponly=True, secure=request.is_secure, samesite="Lax",
    )


def _clear_lb_cookie(response):
    response.delete_cookie(LB_COOKIE, httponly=True, secure=request.is_secure, samesite="Lax")


def _err(code, status):
    response = jsonify({"error": code})
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def lb_today():
    """(Panama date "YYYY-MM-DD", puzzle number). The client's date is never used."""
    date = daily.panama_today()
    return date.isoformat(), daily.day_index(date)


def lb_answer(lang, idx):
    """The real word of the day (same as Language(lang, ...).daily_word)."""
    return daily.pick_daily_word(lang, idx, language_codes_5words[lang], casa24_words[lang][0])


_lb_word_cache = {}


def _lb_words(lang):
    if lang not in _lb_word_cache:
        main = language_codes_5words[lang]
        sup = language_codes_5words_supplements[lang]
        _lb_word_cache[lang] = (set(main), set(sup), lbrules.build_fold_map(main, sup))
    return _lb_word_cache[lang]


def _accent_insensitive(lang):
    value = language_configs[lang].get("accent_insensitive")
    return value is True or value == "true"


def _game_key(pid, lang, date):
    return f"game:{pid}:{lang}:{date}"


def _result_key(pid, lang, date):
    return f"result:{pid}:{lang}:{date}"


def _load_json(raw, kind):
    try:
        value = json.loads(raw) if raw else None
    except ValueError:
        return None
    return value if isinstance(value, kind) else None


def _load_guesses(st, pid, lang, date):
    guesses = _load_json(st.get(_game_key(pid, lang, date)), list) or []
    return [g for g in guesses if isinstance(g, str)]


def _rank(st, pid, scope):
    r = st.zrevrank(f"lb:{scope}", pid)
    return None if r is None else r + 1


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _scope_score(player, scope):
    return lbrules.score(_int(player.get(f"{scope}_points")), _int(player.get(f"{scope}_wins")),
                         _int(player.get(f"{scope}_reached_day")))


def _record_result(st, pid, lang, date, idx, won, attempts):
    """Count a finished game once (SET NX); update stats, streaks and rankings."""
    pts = lbrules.points(won, attempts)
    rkey = _result_key(pid, lang, date)
    if not st.set(rkey, json.dumps({"won": won, "attempts": attempts, "points": pts}), nx=True):
        return  # already counted
    st.hset(f"keys:{pid}", {rkey: "1"})
    pkey = f"player:{pid}"
    player = st.hgetall(pkey)
    updates = {}
    for scope in (lang, "all"):
        old = {f: player.get(f"{scope}_{f}") for f in STAT_FIELDS}
        cur, best, last = lbrules.update_streak(
            old["cur_streak"], old["best_streak"], old["last_win_day"], idx, won, combined=(scope == "all"))
        reached = old["reached_day"]
        if reached in (None, "") or pts > 0:
            reached = idx
        new = {
            "points": _int(old["points"]) + pts,
            "wins": _int(old["wins"]) + (1 if won else 0),
            "played": _int(old["played"]) + 1,
            "cur_streak": cur,
            "best_streak": best,
            "last_win_day": "" if last is None else last,
            "reached_day": reached,
        }
        updates.update({f"{scope}_{k}": str(v) for k, v in new.items()})
    st.hset(pkey, updates)
    player.update(updates)
    if player.get("hidden") != "1":
        for scope in (lang, "all"):
            st.zadd(f"lb:{scope}", _scope_score(player, scope), pid)


def lb_game_state(st, pid, lang):
    """Resume state for /lb/<lang>: today's guesses with colors; the answer only once done."""
    date, idx = lb_today()
    answer = lb_answer(lang, idx)
    guesses = _load_guesses(st, pid, lang, date)
    result = _load_json(st.get(_result_key(pid, lang, date)), dict)
    won = answer in guesses
    done = won or len(guesses) >= lbrules.MAX_GUESSES or result is not None
    if result is not None:
        won = bool(result.get("won"))
    state = {
        "guesses": [{"word": w, "colors": lbrules.color_guess(w, answer)} for w in guesses],
        "done": done, "won": bool(done and won), "answer": None, "points": None, "rank": None,
    }
    if done:
        state["answer"] = answer
        state["points"] = _int(result.get("points")) if result else lbrules.points(won, len(guesses))
        state["rank"] = _rank(st, pid, lang)
    return state


@app.route("/auth/discord/login")
def discord_login():
    if not lb_enabled():
        abort(404)
    state = secrets.token_urlsafe(32)
    redirect_uri = request.url_root + "auth/discord/callback"
    response = redirect(discord_auth.authorize_url(redirect_uri, state))
    response.set_cookie(
        OAUTH_COOKIE, _serializer("c24-oauth").dumps({"state": state, "next": _safe_next(request.args.get("next"))}),
        max_age=OAUTH_COOKIE_AGE, path=OAUTH_COOKIE_PATH,
        httponly=True, secure=request.is_secure, samesite="Lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/auth/discord/callback")
def discord_callback():
    if not lb_enabled():
        abort(404)
    failed = redirect("/?login=failed")
    failed.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
    raw = request.cookies.get(OAUTH_COOKIE)
    try:
        saved = _serializer("c24-oauth").loads(raw, max_age=OAUTH_COOKIE_AGE) if raw else None
    except BadSignature:
        saved = None
    code = request.args.get("code", "")
    given = request.args.get("state", "")
    if request.args.get("error") or not code or not isinstance(saved, dict):
        return failed
    if not hmac.compare_digest(given.encode(), str(saved.get("state", "")).encode()):
        return failed
    try:
        # the access token lives only inside discord_auth.identify()
        discord_id, username = discord_auth.identify(code, request.url_root + "auth/discord/callback")
        lb_store().hset(f"player:{discord_id}", {"username": username})
    except Exception:
        return failed  # nothing logged: messages could carry request details
    response = redirect(_safe_next(saved.get("next")))
    response.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
    _set_lb_cookie(response, discord_id)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/auth/logout", methods=["POST"])
def discord_logout():
    if not _same_origin():
        abort(403)
    response = redirect("/")
    _clear_lb_cookie(response)
    return response


@app.route("/lb/<lang_code>")
def lb_game(lang_code):
    if not lb_enabled():
        abort(404)
    if lang_code not in LB_LANGS:
        return redirect("/lb/es")
    st = lb_store()
    user = lb_current_user(st)
    if not user:
        return redirect(f"/auth/discord/login?next=/lb/{lang_code}")
    cookie_key = f"keyboard_layout_{lang_code}"
    language = Language(lang_code, language_codes_5words[lang_code],
                        request.args.get("layout") or request.cookies.get(cookie_key))
    language.daily_word = ""  # the browser never gets the answer; the server colors guesses
    state = lb_game_state(st, user["id"], lang_code)
    response = make_response(render_template(
        "game.html", language=language, demo=False, lb=True, lb_state=state, lb_user=user))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/guess", methods=["POST"])
def api_guess():
    if not lb_enabled():
        return _err("disabled", 404)
    if not _same_origin():
        return _err("forbidden", 403)
    st = lb_store()
    try:
        user = lb_current_user(st)
        if not user:
            return _err("login", 401)
        pid = user["id"]
        rkey = f"rl:{pid}:{int(time.time() // 60)}"
        count = st.pipeline([["INCR", rkey], ["EXPIRE", rkey, 120]])[0]
        if _int(count) > RATE_LIMIT_PER_MINUTE:
            return _err("rate", 429)

        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("guess"), str):
            return _err("bad_request", 400)
        lang = body.get("lang")
        if lang not in LB_LANGS:
            return _err("bad_lang", 400)

        lock = f"lock:{pid}"
        if not st.set(lock, "1", nx=True, ex=5):
            return _err("rate", 429)
        try:
            return _apply_guess(st, pid, lang, body["guess"])
        finally:
            st.delete(lock)
    except store_mod.StoreError:
        return _err("store", 503)


def _apply_guess(st, pid, lang, typed):
    date, idx = lb_today()
    answer = lb_answer(lang, idx)
    word = unicodedata.normalize("NFC", typed).strip().lower()
    main, sup, fold_map = _lb_words(lang)
    word = lbrules.resolve_accents(word, answer, main, sup, _accent_insensitive(lang), fold_map)
    if len(word) != 5 or not (word in main or word in sup or word == answer):
        return _err("invalid_word", 400)

    guesses = _load_guesses(st, pid, lang, date)
    if answer in guesses or st.get(_result_key(pid, lang, date)) is not None:
        return _err("finished", 400)
    if len(guesses) >= lbrules.MAX_GUESSES:
        return _err("too_many", 400)
    if word in guesses:
        return _err("repeat", 400)

    guesses.append(word)
    gkey = _game_key(pid, lang, date)
    st.set(gkey, json.dumps(guesses, ensure_ascii=False), ex=GAME_TTL)
    st.hset(f"keys:{pid}", {gkey: "1"})

    won = word == answer
    done = won or len(guesses) >= lbrules.MAX_GUESSES
    result = {"word": word, "colors": lbrules.color_guess(word, answer), "done": done,
              "won": won, "answer": None, "points": None, "rank": None}
    if done:
        _record_result(st, pid, lang, date, idx, won, len(guesses))
        stored = _load_json(st.get(_result_key(pid, lang, date)), dict) or {}
        result["answer"] = answer
        result["points"] = _int(stored.get("points", lbrules.points(won, len(guesses))))
        result["rank"] = _rank(st, pid, lang)
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def _lb_row(rank, pid, player, tab, today, me_id):
    def stat(name):
        return player.get(f"{tab}_{name}")
    return {
        "rank": rank,
        "id": pid,
        "username": player.get("username", ""),
        "points": _int(stat("points")),
        "wins": _int(stat("wins")),
        "played": _int(stat("played")),
        "current_streak": lbrules.effective_streak(stat("cur_streak"), stat("last_win_day"), today),
        "best_streak": _int(stat("best_streak")),
        "is_me": pid == me_id,
    }


def _flat_hash(value):
    if isinstance(value, dict):
        return value
    value = value or []
    return {value[i]: value[i + 1] for i in range(0, len(value), 2)}


@app.route("/leaderboard")
def leaderboard_page():
    if not lb_enabled():
        abort(404)
    tab = request.args.get("tab", "all")
    if tab not in LB_TABS:
        tab = "all"
    st = lb_store()
    user = lb_current_user(st)
    me_id = user["id"] if user else None
    _, today = lb_today()
    top = st.zrevrange(f"lb:{tab}", 0, TOP_N - 1)
    players = st.pipeline([["HGETALL", f"player:{pid}"] for pid, _ in top])
    rows = []
    for i, ((pid, _), raw) in enumerate(zip(top, players)):
        player = _flat_hash(raw)
        if player and player.get("hidden") != "1":
            rows.append(_lb_row(i + 1, pid, player, tab, today, me_id))
    me_row = None
    if me_id and not any(r["is_me"] for r in rows):
        rank = _rank(st, me_id, tab)
        player = st.hgetall(f"player:{me_id}")
        if rank is not None and player.get("hidden") != "1" and _int(player.get(f"{tab}_played")):
            me_row = _lb_row(rank, me_id, player, tab, today, me_id)
    response = make_response(render_template(
        "leaderboard.html", tab=tab, rows=rows, me_row=me_row,
        is_admin=bool(me_id and me_id in lb_admin_ids()), lb_user=user,
        texts={lang: language_configs[lang]["text"] for lang in DEMO_LANGS}))
    response.headers["Cache-Control"] = "no-store"
    return response


def _delete_player(st, pid):
    """Remove every key this app keeps for one player."""
    keys = set(st.hgetall(f"keys:{pid}").keys())
    # also today's and recent game keys, in case the index missed one
    for days_back in range(3):
        date = (daily.panama_today() - datetime.timedelta(days=days_back)).isoformat()
        for lang in LB_LANGS:
            keys.add(_game_key(pid, lang, date))
            keys.add(_result_key(pid, lang, date))
    minute = int(time.time() // 60)
    keys.update(f"rl:{pid}:{m}" for m in range(minute - 2, minute + 1))
    keys.update({f"player:{pid}", f"keys:{pid}", f"lock:{pid}"})
    st.delete(*sorted(keys))
    for scope in LB_TABS:
        st.zrem(f"lb:{scope}", pid)


@app.route("/api/me/delete", methods=["POST"])
def lb_delete_me():
    if not _same_origin():
        abort(403)
    pid = lb_player_id()
    st = lb_store()
    if st is None:
        abort(404)
    if not pid:
        return _err("login", 401)
    _delete_player(st, pid)
    response = redirect("/?deleted=1")
    _clear_lb_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/admin/hide", methods=["POST"])
def lb_admin_hide():
    if not lb_enabled():
        abort(404)
    if not _same_origin():
        abort(403)
    pid = lb_player_id()
    if not pid or pid not in lb_admin_ids():
        abort(403)
    target = request.form.get("discord_id", "").strip()
    if not target.isdigit():
        abort(400)
    st = lb_store()
    pkey = f"player:{target}"
    player = st.hgetall(pkey)
    if player:
        if request.form.get("hidden", "1") == "1":
            st.hset(pkey, {"hidden": "1"})
            for scope in LB_TABS:
                st.zrem(f"lb:{scope}", target)
        else:
            st.hdel(pkey, "hidden")
            for scope in LB_TABS:
                if _int(player.get(f"{scope}_played")):
                    st.zadd(f"lb:{scope}", _scope_score(player, scope), target)
    tab = request.form.get("tab")
    return redirect("/leaderboard" + (f"?tab={tab}" if tab in LB_TABS else ""))


if __name__ == "__main__":
    app.run()
