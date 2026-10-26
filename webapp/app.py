from flask import (
    Flask,
    render_template,
    make_response,
    redirect,
    request,
    url_for,
)
from markupsafe import Markup
import hashlib
import json
import time
import os
import sys

# Folder of this file. Lets the app run from any working directory
# (locally from webapp/, on Vercel from the repo root).
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

import daily
from werkzeug.middleware.proxy_fix import ProxyFix
import glob
import random

# set random seed 42 for reproducibility (important to maintain stable word lists)
random.seed(42)

app = Flask(__name__)
# Behind Vercel (or any proxy) trust X-Forwarded-Proto/Host so request.url_root
# (sitemap, share links) shows the visitor's real https address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
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
    response = make_response(render_template("game.html", language=language))
    selected_layout = language.keyboard_layout_name
    if request.cookies.get(cookie_key) != selected_layout:
        response.set_cookie(
            cookie_key,
            selected_layout,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
        )
    return response


if __name__ == "__main__":
    app.run()
