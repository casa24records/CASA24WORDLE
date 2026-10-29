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
    set. Not called on Vercel or under pytest (tests never see real secrets or the database)."""
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
from preload import sdk_modulepreloads
import store as store_mod
from itsdangerous import URLSafeTimedSerializer, BadSignature
from urllib.parse import urlencode, urlparse
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


def public_url():
    """Canonical public origin for share links ("https://casa-24-wordle.vercel.app").
    PUBLIC_URL (env, optional) wins; else the address the visitor used (ProxyFix
    makes it the real https host). Never the page's own origin in the browser:
    inside the Discord Activity that is a discordsays.com proxy nobody can open."""
    env = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    parsed = urlparse(env)
    if parsed.scheme in ("http", "https") and parsed.netloc and not parsed.path \
            and not parsed.query and not parsed.fragment:
        return env
    return request.url_root.rstrip("/")


@app.context_processor
def inject_asset_helpers():
    return {"asset": asset, "asset_version": asset_version, "json_script": json_script,
            "public_url": public_url()}


###############################################################################
# DISCORD ACTIVITY (the game inside Discord, same app and same server)
###############################################################################
# Discord opens the Activity as an iframe on https://<client id>.discordsays.com
# (a proxy to this server) with ?frame_id=...&instance_id=...&platform=... in the
# URL. Only then is a page "inside the Activity". "/" (and "/activity") is then the
# Activity shell (templates/activity.html + static/activity-shell.js): the one page
# that loads the Discord SDK (once per launch: ready, authorize, token,
# authenticate) and hosts the game in a same-origin <iframe> at /lb/<lang>?embed=1
# (no Discord params in the iframe: is_activity_embed()). The game page
# (static/discord-activity.js) borrows the shell's session; language changes swap
# the iframe, never the shell (a second SDK handshake after any navigation can't
# work: the SDK answers to document.referrer). Inside: no guest mode, no
# login/logout buttons, no Developer view, and every internal link keeps the
# Activity's query (embed=1), so the server still knows.
# Without those params nothing here changes the web.

ACTIVITY_PLATFORMS = ("desktop", "mobile")
# our own page params: never carried to the next page by activity_url()
ACTIVITY_OWN_PARAMS = ("layout", "tab", "lang", "c24_root", "login", "deleted", "skip", "next")


def is_activity_launch():
    """True when Discord's launch params are in the URL (frame_id, instance_id and a
    valid platform; the SDK refuses any other platform): the Activity shell."""
    args = request.args
    return bool(args.get("frame_id") and args.get("instance_id")) \
        and args.get("platform") in ACTIVITY_PLATFORMS


def is_activity_embed():
    """The game page inside the Activity shell's <iframe> (?embed=1). Its URL has no
    frame_id / instance_id / platform on purpose (like Discord's nested-messages
    sample): nothing in the iframe can mistake itself for the Activity's top page or
    start the SDK; it borrows the shell's session (window.parent.C24Activity)."""
    return request.args.get("embed") == "1"


def is_activity():
    """Inside the Discord Activity: the shell (launch params) or its game iframe (embed=1)."""
    return is_activity_launch() or is_activity_embed()


def activity_params():
    """[(key, value)] of Discord's launch query, to keep on every in-Activity link
    (everything in the URL except our own page params). [] outside the Activity."""
    if not is_activity():
        return []
    return [(k, v) for k, v in request.args.items(multi=True) if k not in ACTIVITY_OWN_PARAMS]


def activity_url(path):
    """`path` plus Discord's launch query inside the Activity; `path` unchanged on the web."""
    params = activity_params()
    if not params:
        return path
    base, _, fragment = path.partition("#")
    url = base + ("&" if "?" in base else "?") + urlencode(params)
    return url + ("#" + fragment if fragment else "")


app.jinja_env.globals.update(asset=asset, json_script=json_script, aq=activity_url)


def _is_rtl(lang):
    return str(language_configs[lang].get("right_to_left", "false")).lower() == "true"


def activity_shell(lang=None):
    """The Activity shell: loads the Discord SDK ONCE per launch (ready, authorize,
    token, authenticate), keeps the session in memory and hosts the game in a
    same-origin <iframe>. Language changes swap the iframe, never this page, so
    the SDK handshake never runs twice. `lang`: a language to open right away
    (else the one this device chose last, else the language picker)."""
    langs = [{"code": c, "name": language_configs[c]["name_native"],
              "rtl": _is_rtl(c),
              "loading": language_configs[c]["text"].get("activity_loading_game", "Loading game…")}
             for c in LB_LANGS]
    pick = {c: language_configs[c]["text"].get("activity_pick_title", fallback)
            for c, fallback in (("es", "Elige tu idioma"), ("en", "Choose your language"))}
    response = make_response(render_template(
        "activity.html",
        shell={"client_id": discord_auth.client_id(), "langs": langs,
               "lang": lang if lang in LB_LANGS else None},
        pick=pick,
        sdk_preloads=sdk_modulepreloads(),
    ))
    return _no_store(response)


@app.context_processor
def inject_activity():
    activity = is_activity()
    ctx = {"C24_ACTIVITY": activity, "activity_params": activity_params() if activity else [],
           "activity_langs": []}
    if activity:
        # the public app ID for the SDK (never the secret) and the language window's list
        ctx["activity_client_id"] = discord_auth.client_id()
        ctx["activity_langs"] = [{"code": c, "name_native": language_configs[c]["name_native"],
                                  "rtl": _is_rtl(c)} for c in LB_LANGS]
    return ctx


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
    if is_activity() and lb_enabled():
        # inside Discord (URL Mapping "/"): the Activity shell, no redirect (no menu,
        # no guest mode). Inside the shell's iframe "/" goes to the game instead,
        # so the shell (and the SDK) can never load twice.
        lang = request.args.get("lang")
        if is_activity_embed():
            return _no_store(redirect(activity_url(f"/lb/{lang if lang in LB_LANGS else 'es'}")))
        return activity_shell(lang)
    return render_template(
        "index.html",
        languages=languages,
        language_codes=language_codes,
        todays_idx=get_todays_idx(),
        demo_enabled=demo_enabled(),
        texts={lang: language_configs[lang]["text"] for lang in DEMO_LANGS},
    )


@app.route("/activity")
def activity_page():
    # the Activity shell by its own name (same as "/" inside Discord)
    if not (is_activity() and lb_enabled()):
        return redirect("/")
    if is_activity_embed():
        return _no_store(redirect(activity_url("/lb/es")))
    return activity_shell(request.args.get("lang"))


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
        return redirect(activity_url("/"))
    if is_activity() and lb_enabled() and lang_code in LB_LANGS:
        # no guest games inside Discord: the same language's leaderboard game
        return _no_store(redirect(activity_url(f"/lb/{lang_code}")))
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
# DISCORD LEADERBOARD (every language; owner decision 2026-10-28)
###############################################################################
# Storage: webapp/store.py (Postgres tables wordle_players, wordle_results,
# wordle_games, wordle_rate; an in-memory copy for tests and local dev).
# Kept: Discord ID, username, Discord avatar hash (Discord's format only, else
# NULL), hidden flag, per finished game lang/day/won/attempts/points, today's
# guesses (2 days), per-minute request counters (guesses, live polling).
# Never stored: Discord tokens, email, IP addresses. The c24_lb cookie holds only
# the ID; the avatar hash also reaches the player's own browser in the login
# redirect's #dc= fragment. /api/live shows other players' colors only.
#
# Ranking and streaks are computed from wordle_results when read: SQL sums
# points/wins/played per tab; streaks come from the player's ordered results
# in Python (leaderboard.streaks), only for the rows on screen.
#
# POSTs check that Origin (or Referer) matches this host when the browser sends
# one; the c24_lb cookie is also SameSite=Lax, so other sites can't post with it.

import re
import secrets
import unicodedata

LB_LANGS = tuple(language_codes)  # all loaded languages, menu order (es, en first)
LB_TABS = LB_LANGS + ("all",)      # "all" = combined, sums every language
LB_TEXT_FALLBACK = ("es", "en")    # texts always passed to leaderboard.html
LB_COOKIE = "c24_lb"
LB_COOKIE_AGE = 30 * 24 * 3600
OAUTH_COOKIE = "c24_oauth"
OAUTH_COOKIE_AGE = 10 * 60
OAUTH_COOKIE_PATH = "/auth/discord"
RATE_LIMIT_PER_MINUTE = 30
LIVE_RATE_LIMIT_PER_MINUTE = 20  # own counter: polling every ~8 s never eats the guess budget
STATE_RATE_LIMIT_PER_MINUTE = 30  # own counter for GET /api/state (focus/visibility/day-change reloads)
LIVE_LIMIT = 30
LIVE_RECENT_SECONDS = 5 * 60    # "en vivo" when the last guess is this recent
TOP_N = 50


def lb_secret():
    return os.environ.get("SECRET_KEY", "")


def lb_store():
    try:
        return store_mod.get_store()
    except Exception:
        return None


@app.teardown_appcontext
def _close_store(exc):
    # one short-lived database connection per request (serverless friendly)
    store_mod.close_connections()


def lb_enabled():
    """Discord app + SECRET_KEY + a store: otherwise every leaderboard route is 404."""
    return bool(discord_auth.client_id() and discord_auth.client_secret() and lb_secret()) \
        and lb_store() is not None


def lb_admin_ids():
    return {x.strip() for x in os.environ.get("ADMIN_DISCORD_IDS", "").split(",") if x.strip()}


def _serializer(salt):
    return URLSafeTimedSerializer(lb_secret(), salt=salt)


def _lb_session_value():
    """The signed session: `Authorization: Bearer <signed id>` (the Discord Activity,
    where our cookies don't travel) or else the c24_lb cookie (the web). When the
    header is there it is the only thing read, never mixed with a cookie."""
    header = request.headers.get("Authorization")
    if header is not None:
        scheme, _, value = header.strip().partition(" ")
        return value.strip() if scheme.lower() == "bearer" else ""
    return request.cookies.get(LB_COOKIE)


def lb_player_id():
    """Discord ID from the signed session (cookie or Bearer header; same signature,
    salt and 30-day max age; it holds nothing else). The one place that decides who is playing."""
    raw = _lb_session_value()
    if not raw or not lb_secret():
        return None
    try:
        value = _serializer("c24-lb").loads(raw, max_age=LB_COOKIE_AGE)
    except BadSignature:
        return None
    return value if isinstance(value, str) and value.isdigit() else None


def lb_current_user(st=None):
    """{"id", "username", "avatar_url", "has_avatar"} for the logged-in player, None if logged out or deleted."""
    pid = lb_player_id()
    st = st or lb_store()
    if not pid or st is None:
        return None
    try:
        player = st.get_player(pid)
    except store_mod.StoreError:
        return None
    if not player:
        return None
    try:
        avatar = st.get_avatar(pid)
    except store_mod.StoreError:
        avatar = None
    return {"id": pid, "username": player["username"],
            "avatar_url": lb_avatar_url(pid, avatar), "has_avatar": bool(avatar)}


AVATAR_REFRESH_COOKIE = "c24_avr"


def lb_avatar_refresh(user, next_path):
    """Players who signed in before we stored pictures have no avatar saved.
    Pass them once through Discord (prompt=none, no extra click) to fetch it;
    a 1-day cookie stops this from repeating if they have no Discord picture."""
    if not user or user.get("has_avatar") or request.cookies.get(AVATAR_REFRESH_COOKIE):
        return None
    response = redirect(f"/auth/discord/login?next={next_path}")
    response.set_cookie(AVATAR_REFRESH_COOKIE, "1", max_age=60 * 60 * 24, httponly=True,
                        secure=request.is_secure, samesite="Lax")
    return response


@app.context_processor
def inject_leaderboard():
    enabled = lb_enabled()
    user = lb_current_user() if enabled and request.cookies.get(LB_COOKIE) else None
    return {"lb_enabled": enabled, "lb_user": user}


def _discordsays_host():
    """<client id>.discordsays.com: Discord's proxy for our Activity (None without a client ID)."""
    cid = discord_auth.client_id()
    return f"{cid}.discordsays.com" if cid.isdigit() else None


def _same_origin():
    """False when the browser says the POST came from another site. Our own host,
    or exactly https://<DISCORD_CLIENT_ID>.discordsays.com (the Activity's proxy)."""
    for header in ("Origin", "Referer"):
        value = request.headers.get(header)
        if value:
            if value == "null":
                return False
            parsed = urlparse(value)
            if parsed.netloc == request.host:
                return True
            proxy = _discordsays_host()
            return bool(proxy) and parsed.scheme == "https" and parsed.netloc == proxy
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
    """(Panama date, puzzle number). The client's date is never used."""
    date = daily.panama_today()
    return date, daily.day_index(date)


def lb_answer(lang, idx):
    """The real word of the day (same as Language(lang, ...).daily_word)."""
    return daily.pick_daily_word(lang, idx, language_codes_5words[lang], casa24_words[lang][0])


_lb_word_cache = {}
_lb_form_cache = {}


def _lb_words(lang):
    if lang not in _lb_word_cache:
        main = language_codes_5words[lang]
        sup = language_codes_5words_supplements[lang]
        _lb_word_cache[lang] = (set(main), set(sup), lbrules.build_fold_map(main, sup))
    return _lb_word_cache[lang]


def _lb_norm_form(lang):
    """Unicode form of this language's word lists. Korean lists are decomposed
    jamo (NFD: the board has one tile per jamo); every other list is NFC. NFC on
    a Korean guess would merge the jamo into syllables and break it."""
    if lang not in _lb_form_cache:
        main, sup, _ = _lb_words(lang)
        words = list(main) + list(sup)
        nfd_only = bool(words) and not all(unicodedata.is_normalized("NFC", w) for w in words) \
            and all(unicodedata.is_normalized("NFD", w) for w in words)
        _lb_form_cache[lang] = "NFD" if nfd_only else "NFC"
    return _lb_form_cache[lang]


def lb_normalize(lang, typed):
    """The guess as the word lists store it: same Unicode form, lowercase.
    Turkish/Azeri lowercase like game.js normalizeKey (toLocaleLowerCase):
    "I" -> "ı", "İ" -> "i" (Python's lower() would give "i" and "i̇")."""
    word = unicodedata.normalize("NFC", typed).strip()
    if lang in ("tr", "az"):
        word = word.replace("I", "ı").replace("İ", "i")
    return unicodedata.normalize(_lb_norm_form(lang), word.lower())


def _accent_insensitive(lang):
    value = language_configs[lang].get("accent_insensitive")
    return value is True or value == "true"


def _rank(st, pid, tab):
    row = st.standing(pid, tab)
    return row["rank"] if row else None


def _record_result(st, pid, lang, day, won, attempts):
    """Count a finished game once (insert ... on conflict do nothing). Tests use it to seed data."""
    return st.record_result(pid, lang, day, won, attempts, lbrules.points(won, attempts))


def lb_game_state(st, pid, lang):
    """The player's game today, as the server sees it (the single source of truth).

    Same shape for the /lb/<lang> page embed (#c24-lb-state), GET /api/state and
    the "state" field of /api/guess's stale/finished errors:
    {"day": "YYYY-MM-DD" (Panama), "puzzle": day number, "guesses": [{"word", "colors"}],
     "status": "playing"|"won"|"lost", "attempts": n, "done", "won",
     "answer": only once done (else None), "points", "rank" (None while playing)}.
    The guesses are the player's own words; the answer never leaves while playing."""
    day, idx = lb_today()
    answer = lb_answer(lang, idx)
    guesses, result = st.get_game(pid, lang, day)
    guesses = [g for g in guesses if isinstance(g, str)][:lbrules.MAX_GUESSES]
    won = answer in guesses
    done = won or len(guesses) >= lbrules.MAX_GUESSES or result is not None
    if result is not None:
        won = bool(result["won"])
    won = bool(done and won)
    state = {
        "day": day.isoformat(), "puzzle": idx,
        "guesses": [{"word": w, "colors": lbrules.color_guess(w, answer)} for w in guesses],
        "status": ("won" if won else "lost") if done else "playing",
        "attempts": len(guesses),
        "done": done, "won": won, "answer": None, "points": None, "rank": None,
    }
    if done:
        state["answer"] = answer
        state["points"] = int(result["points"]) if result else lbrules.points(won, len(guesses))
        state["rank"] = _rank(st, pid, lang)
    return state


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _err_state(code, status, st, pid, lang):
    """An /api/guess refusal that also carries the current state, so the client
    can repaint from the server instead of showing an error."""
    response = jsonify({"error": code, "state": lb_game_state(st, pid, lang)})
    response.status_code = status
    return _no_store(response)


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


AVATAR_HASH_RE = store_mod.AVATAR_HASH_RE  # (a_)?<32 lowercase hex>


def _avatar_fragment(avatar_hash):
    """"#dc=<hash>" for the player's browser ("#dc=" when they have no avatar).
    A hash that doesn't look like Discord's format is dropped (no fragment)."""
    if avatar_hash is None:
        return "#dc="
    if isinstance(avatar_hash, str) and AVATAR_HASH_RE.fullmatch(avatar_hash):
        return "#dc=" + avatar_hash
    return ""


@app.route("/auth/discord/callback")
def discord_callback():
    if not lb_enabled():
        abort(404)
    failed = redirect("/?login=failed")
    failed.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
    if request.args.get("error") == "access_denied":
        # the player pressed Cancel on Discord: a gentle notice, not an error
        cancelled = redirect("/?login=cancelled")
        cancelled.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
        return cancelled
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
        # avatar_hash is stored only if it has Discord's format (else NULL), for
        # the live view; it is never logged or put in a cookie. The player's own
        # browser also gets it in the URL fragment (browsers never send fragments)
        discord_id, username, avatar_hash = discord_auth.identify(
            code, request.url_root + "auth/discord/callback")
        lb_store().upsert_player(discord_id, username, avatar_hash)
    except Exception:
        return failed  # nothing logged: messages could carry request details
    response = redirect(_safe_next(saved.get("next")).split("#", 1)[0] + _avatar_fragment(avatar_hash))
    response.set_data(b"")  # the hash only in the Location header, not echoed in an HTML body
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
        return redirect(activity_url("/lb/es"))
    cookie_key = f"keyboard_layout_{lang_code}"
    if is_activity() and not is_activity_embed():
        # inside Discord but not in the shell's iframe: open the shell on this language
        return activity_shell(lang_code)
    if is_activity():
        # the game in the Activity shell's iframe: no cookie travels, so the page is an
        # empty board; game.js asks GET /api/state with the shell's session (Bearer)
        language = Language(lang_code, language_codes_5words[lang_code], request.args.get("layout"))
        language.daily_word = ""
        response = make_response(render_template(
            "game.html", language=language, demo=False, lb=True, lb_state=None, lb_user=None))
        return _no_store(response)
    st = lb_store()
    user = lb_current_user(st)
    if not user:
        return redirect(f"/auth/discord/login?next=/lb/{lang_code}")
    refresh = lb_avatar_refresh(user, f"/lb/{lang_code}")
    if refresh is not None:
        return refresh
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
        if st.rate_hit(pid, int(time.time() // 60)) > RATE_LIMIT_PER_MINUTE:
            return _err("rate", 429)

        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("guess"), str):
            return _err("bad_request", 400)
        lang = body.get("lang")
        if lang not in LB_LANGS:
            return _err("bad_lang", 400)
        attempt = _read_attempt(body)
        if attempt is False:
            return _err("bad_request", 400)
        return _apply_guess(st, pid, lang, body["guess"], attempt)
    except store_mod.StoreError:
        return _err("store", 503)


def _read_attempt(body):
    """Optional "attempt": the 0-based row the client is filling (= how many
    guesses it believes exist). None when absent; False when malformed."""
    if "attempt" not in body or body["attempt"] is None:
        return None
    value = body["attempt"]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= lbrules.MAX_GUESSES:
        return False
    return value


def _apply_guess(st, pid, lang, typed, attempt=None):
    day, idx = lb_today()
    answer = lb_answer(lang, idx)
    word = lb_normalize(lang, typed)
    main, sup, fold_map = _lb_words(lang)
    word = lbrules.resolve_accents(word, answer, main, sup, _accent_insensitive(lang), fold_map)
    valid = len(word) == 5 and (word in main or word in sup or word == answer)

    # the game row stays locked until this block ends, so two guesses can't race
    # (web + Discord Activity at once: the second one sees a new count -> 409 stale)
    refusal = None
    with st.game(pid, lang, day) as game:
        guesses = [g for g in game.guesses if isinstance(g, str)]
        if answer in guesses or game.result is not None:
            refusal = ("finished", 400)
        elif len(guesses) >= lbrules.MAX_GUESSES:
            refusal = ("too_many", 400)
        elif attempt is not None and attempt != len(guesses):
            refusal = ("stale", 409)
        elif not valid:
            return _err("invalid_word", 400)
        elif word in guesses:
            return _err("repeat", 400)
        else:
            guesses.append(word)
            game.save(guesses)
            won = word == answer
            done = won or len(guesses) >= lbrules.MAX_GUESSES
            if done:
                game.record(won, len(guesses), lbrules.points(won, len(guesses)))
    if refusal:
        # state read after the lock is released
        return _err_state(refusal[0], refusal[1], st, pid, lang)

    result = {"word": word, "colors": lbrules.color_guess(word, answer), "done": done,
              "won": won, "answer": None, "points": None, "rank": None,
              "day": day.isoformat(), "attempts": len(guesses)}
    if done:
        _, stored = st.get_game(pid, lang, day)
        result["answer"] = answer
        result["points"] = int(stored["points"]) if stored else lbrules.points(won, len(guesses))
        result["rank"] = _rank(st, pid, lang)
    return _no_store(jsonify(result))


@app.route("/api/state")
def api_state():
    """Read-only: the logged-in player's game today in one language (the same
    shape as the /lb/<lang> page embed). Web and the Discord Activity repaint from it."""
    if not lb_enabled():
        return _err("disabled", 404)
    st = lb_store()
    try:
        user = lb_current_user(st)
        if not user:
            return _err("login", 401)
        lang = request.args.get("lang")
        if lang not in LB_LANGS:
            return _err("bad_lang", 400)
        if st.rate_hit(user["id"], int(time.time() // 60), "state") > STATE_RATE_LIMIT_PER_MINUTE:
            return _err("rate", 429)
        state = lb_game_state(st, user["id"], lang)
    except store_mod.StoreError:
        return _err("store", 503)
    return _no_store(jsonify(state))


ACTIVITY_TOKEN_PER_MINUTE = 120  # all Activity logins together (no IPs kept): a small global budget


@app.route("/api/activity/token", methods=["POST"])
def api_activity_token():
    """Discord Activity login: the SDK's authorize() code -> Discord token -> who is it.

    Body {"code"}. Answers {"access_token", "session", "user": {"username"}}:
    the access token goes back only so the browser can call the SDK's
    authenticate(); it is never stored or logged here. "session" is the same
    signed ID as the c24_lb cookie, sent back as `Authorization: Bearer`.
    Stored: ID, username, avatar hash (Discord's format only), like the web login."""
    if not lb_enabled():
        return _err("disabled", 404)
    if not _same_origin():
        return _err("forbidden", 403)
    body = request.get_json(silent=True)
    code = body.get("code") if isinstance(body, dict) else None
    if not isinstance(code, str) or not 0 < len(code) <= 200 or not code.isprintable():
        return _err("bad_request", 400)
    st = lb_store()
    try:
        if st.rate_hit("activity", int(time.time() // 60), "token") > ACTIVITY_TOKEN_PER_MINUTE:
            return _err("rate", 429)
    except store_mod.StoreError:
        return _err("store", 503)
    try:
        # no redirect_uri: the Embedded App SDK's codes are exchanged without one
        token = discord_auth.exchange_code(code, None)
        discord_id, username, avatar_hash = discord_auth.parse_me(discord_auth.fetch_me(token))
    except Exception:
        return _err("discord", 400)  # nothing logged: messages could carry request details
    try:
        st.upsert_player(discord_id, username, avatar_hash)
    except store_mod.StoreError:
        return _err("store", 503)
    response = jsonify({"access_token": token,
                        "session": _serializer("c24-lb").dumps(discord_id),
                        "user": {"username": username}})
    del token
    return _no_store(response)


def lb_avatar_url(discord_id, avatar_hash):
    """Discord CDN picture (64 px), or Discord's default avatar when there is no hash."""
    if isinstance(avatar_hash, str) and AVATAR_HASH_RE.fullmatch(avatar_hash):
        return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png?size=64"
    return f"https://cdn.discordapp.com/embed/avatars/{(int(discord_id) >> 22) % 6}.png"


def _live_player(row, answer, now):
    """One live card: colors only. No words, no answer, no Discord ID."""
    guesses = [g for g in row["guesses"] if isinstance(g, str)][:lbrules.MAX_GUESSES]
    won = bool(row["won"]) if row["finished"] else answer in guesses
    done = bool(row["finished"]) or answer in guesses or len(guesses) >= lbrules.MAX_GUESSES
    updated = row["updated_at"]
    if isinstance(updated, datetime.datetime) and updated.tzinfo is None:
        updated = updated.replace(tzinfo=datetime.timezone.utc)
    live = isinstance(updated, datetime.datetime) and \
        (now - updated).total_seconds() <= LIVE_RECENT_SECONDS
    return {
        "username": row["username"],
        "avatar_url": lb_avatar_url(row["id"], row["avatar"]),
        "rows": [lbrules.color_guess(w, answer) for w in guesses],
        "done": done, "won": bool(done and won), "live": bool(live),
    }


@app.route("/api/live")
def api_live():
    """Everyone else playing today's word in this language (leaderboard mode only)."""
    if not lb_enabled():
        return _err("disabled", 404)
    st = lb_store()
    try:
        user = lb_current_user(st)
        if not user:
            return _err("login", 401)
        lang = request.args.get("lang")
        if lang not in LB_LANGS:
            return _err("bad_lang", 400)
        if st.rate_hit(user["id"], int(time.time() // 60), "live") > LIVE_RATE_LIMIT_PER_MINUTE:
            return _err("rate", 429)
        day, idx = lb_today()
        answer = lb_answer(lang, idx)
        now = datetime.datetime.now(datetime.timezone.utc)
        players = [_live_player(r, answer, now) for r in st.live(lang, day, user["id"], LIVE_LIMIT)]
    except store_mod.StoreError:
        return _err("store", 503)
    response = jsonify({"players": players, "count": len(players)})
    response.headers["Cache-Control"] = "no-store"
    return response


def _lb_rows(st, ranked, tab, today_idx, me_id):
    """Add streaks (from each player's ordered results) to ranked rows."""
    histories = st.histories([r["id"] for r in ranked], tab)
    rows = []
    for r in ranked:
        history = [(daily.day_index(day), won) for day, won in histories.get(r["id"], [])]
        current, best = lbrules.streaks(history, today_idx, combined=(tab == "all"))
        rows.append({
            "rank": r["rank"], "id": r["id"], "username": r["username"],
            "points": r["points"], "wins": r["wins"], "played": r["played"],
            "current_streak": current, "best_streak": best, "is_me": r["id"] == me_id,
        })
    return rows


def lb_tabs():
    """Tabs for leaderboard.html: every language (menu order), then "all"
    (name_native None: the template labels it with lb_tab_all)."""
    return [{"code": code, "name_native": language_configs[code]["name_native"]}
            for code in LB_LANGS] + [{"code": "all", "name_native": None}]


def lb_board(st, tab, me_id):
    """(top rows, my row when I'm not in them) for one tab: the /leaderboard page
    and GET /api/leaderboard use the same numbers."""
    _, today_idx = lb_today()
    rows = _lb_rows(st, st.leaderboard(tab, TOP_N), tab, today_idx, me_id)
    me_row = None
    if me_id and not any(r["is_me"] for r in rows):
        mine = st.standing(me_id, tab)
        if mine:
            me_row = _lb_rows(st, [mine], tab, today_idx, me_id)[0]
    return rows, me_row


BOARD_FIELDS = ("rank", "username", "points", "wins", "played", "current_streak", "best_streak", "is_me")


@app.route("/api/leaderboard")
def api_leaderboard():
    """The /leaderboard table as JSON (the Discord Activity shows it in a window
    instead of opening another page). Public like the page; with a session
    (cookie or Bearer) the player's own row is marked. No Discord IDs."""
    if not lb_enabled():
        return _err("disabled", 404)
    tab = request.args.get("tab", "all")
    if tab not in LB_TABS:
        return _err("bad_tab", 400)
    st = lb_store()
    try:
        rows, me_row = lb_board(st, tab, lb_player_id())
    except store_mod.StoreError:
        return _err("store", 503)
    pick = lambda r: {k: r[k] for k in BOARD_FIELDS}  # noqa: E731
    return _no_store(jsonify({"tab": tab, "rows": [pick(r) for r in rows],
                              "me": pick(me_row) if me_row else None}))


@app.route("/leaderboard")
def leaderboard_page():
    if not lb_enabled():
        abort(404)
    tab = request.args.get("tab", "all")
    if tab not in LB_TABS:
        tab = "all"
    st = lb_store()
    # inside the Activity no cookie travels: the public table (the game shows yours)
    user = None if is_activity() else lb_current_user(st)
    me_id = user["id"] if user else None
    rows, me_row = lb_board(st, tab, me_id)
    text_langs = LB_TEXT_FALLBACK + ((tab,) if tab in LB_LANGS and tab not in LB_TEXT_FALLBACK else ())
    response = make_response(render_template(
        "leaderboard.html", tab=tab, rows=rows, me_row=me_row,
        is_admin=bool(me_id and me_id in lb_admin_ids()), lb_user=user,
        lb_tabs=lb_tabs(), lb_langs=LB_LANGS,
        texts={lang: language_configs[lang]["text"] for lang in text_langs}))
    response.headers["Cache-Control"] = "no-store"
    return response


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
    st.delete_player(pid)  # results and games go with it (on delete cascade)
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
    lb_store().set_hidden(target, request.form.get("hidden", "1") == "1")
    tab = request.form.get("tab")
    return redirect("/leaderboard" + (f"?tab={tab}" if tab in LB_TABS else ""))


if __name__ == "__main__":
    app.run()
