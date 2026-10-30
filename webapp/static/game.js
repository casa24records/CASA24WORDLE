// Casa 24 Wordle game page (Vue 3). Word lists, characters, config and page
// settings come from the JSON blocks #c24-data and #c24-page in game.html (data,
// not code: no inline scripts, so the Discord Activity's CSP can run the page).

function readJson(id) {
    try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return null; }
}
const c24_data = readJson("c24-data") || {};
const c24_page = readJson("c24-page") || {};
const word_list = c24_data.word_list || [];
const word_list_supplement = c24_data.word_list_supplement || [];
const characters = c24_data.characters || [];
const config = c24_data.config || {};

function foldAccents(text) {
    // Letters as the game compares them: accents and diaeresis don't count
    // ("canción" -> "cancion", "ü" -> "u"), but ñ is its own letter. NFC first, so a
    // decomposed n + U+0303 is ñ too. Same as fold_accents in leaderboard.py.
    return Array.from(String(text || "").normalize("NFC")).map(function (c) {
        return (c === "ñ" || c === "Ñ") ? c : c.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    }).join("");
}

function inputCharacters() {
    // The letters a player can type: the keyboard's letters (from the page data,
    // else the keys on the page, else the language's characters), folded, no ⇨/⌫.
    var given = c24_data.input_characters;
    if (typeof given === "string") { given = Array.from(given); }
    if (!Array.isArray(given) || !given.length) {
        given = Array.from(document.querySelectorAll(".c24-keyboard [data-char]")).map((b) => b.getAttribute("data-char"));
    }
    if (!given.length) { given = characters; }
    var out = [];
    given.forEach(function (c) {
        var f = foldAccents(String(c).toLowerCase());
        if (Array.from(f).length === 1 && f !== "⇨" && f !== "⌫" && out.indexOf(f) < 0) { out.push(f); }
    });
    return out;
}
const INPUT_CHARS = inputCharacters();
const todays_idx = String(c24_page.todays_idx || "");
const todays_word = c24_page.todays_word || "";  // "" in the leaderboard game: the server colors guesses
const KOLO_BASE = c24_page.kolo_base || "/static/images/kolo/";
const ASSET_V = c24_page.asset_v || "";  // version of the whole kolo/ folder
const DEMO = c24_page.demo === true;  // Developer view: same game + Restart / Fill in word buttons; nothing is saved
const LB = c24_page.lb === true;  // leaderboard game (/lb/<lang>, any language): the server checks every guess; nothing is saved locally
const LB_ENABLED = c24_page.lb_enabled === true;
// Inside the Discord Activity (app.py is_activity()): discord-activity.js logs in
// automatically and exposes window.C24Activity ({session, ready, fetch, reauth});
// every leaderboard request waits for it and carries the session header.
const ACTIVITY = c24_page.activity === true && LB;

function activityReady() {
    // resolves once the Discord login is done (right away on the web)
    if (!ACTIVITY) { return Promise.resolve(); }
    if (window.C24Activity) { return window.C24Activity.ready; }
    return new Promise(function (resolve) {
        window.addEventListener("c24activity", function () { resolve(window.C24Activity.ready); }, { once: true });
    });
}

function lbFetch(url, opts) {
    // the one way game.js talks to /api/*: web = same-origin cookie; Discord = Bearer session
    opts = Object.assign({ credentials: "same-origin" }, opts || {});
    if (!ACTIVITY) { return fetch(url, opts); }
    return activityReady().then(function () { return window.C24Activity.fetch(url, opts); });
}

// Kolo shown on the end screen, one picked at random per game. These must match
// the files in static/images/kolo/win/ and lose/ (scripts/brand_assets.py makes them).
const KOLO_WIN = ["car.webp", "chill.webp", "dj.webp", "face.webp", "hoodie.webp", "montuno.webp", "pizza.webp",
    "prod.webp", "rap-battle.webp", "ross.webp", "young.webp", "young-cropped.webp"];
const KOLO_LOSE = ["baby.webp", "toilet.webp"];

// Leaderboard game (/lb/<lang>, any language): today's guesses so far, sent by the server.
// The answer is not in the page; the server colors each guess (POST /api/guess).
let LB_STATE = null;
try { LB_STATE = JSON.parse(document.getElementById("c24-lb-state").textContent); } catch (e) { }

// tile classes for each color (updateColors and the leaderboard game use the same ones)
const TILE_BASE = "uppercase font-bold select-none text-white";
const COLOR_RANK = { "incorrect": 1, "semicorrect": 2, "correct": 3 };

// Live view (leaderboard game only): who else is playing today, colors only.
// Polls GET /api/live every 3 s while the tab is visible; a 429 doubles the wait (max 60 s).
// Inside Discord, the shell also says who is in the Activity the moment they join
// (C24Activity.onParticipants): their card shows at once, with an empty board until
// /api/live (asked right away) has their colors.
const LIVE_EVERY = 3000;
const LIVE_MAX = 60000;
const LIVE_COLORS = { "correct": "is-correct", "semicorrect": "is-semicorrect", "incorrect": "is-incorrect" };
const LIVE_AVATAR_RE = /^https:\/\/cdn\.discordapp\.com\/(avatars\/\d{1,20}\/(a_)?[0-9a-f]{32}\.png|embed\/avatars\/[0-5]\.png)(\?size=\d{2,4})?$/;
const LIVE = { timer: null, delay: LIVE_EVERY, busy: false, stopped: false };

function liveCells(rows) {
    // 6 rows x 5 cells of color classes; anything unknown stays an empty cell (no text, ever)
    var cells = [];
    for (var r = 0; r < 6; r++) {
        var row = Array.isArray(rows) && Array.isArray(rows[r]) ? rows[r] : [];
        for (var c = 0; c < 5; c++) {
            cells.push(LIVE_COLORS[row[c]] || "is-empty");
        }
    }
    return cells;
}

function livePlayer(p) {
    // a player who just opened the game (presence, no guesses yet) has rows [] -> an empty 6x5 board
    var rows = Array.isArray(p.rows) ? p.rows : [];
    var avatar = typeof p.avatar_url === "string" && LIVE_AVATAR_RE.test(p.avatar_url)
        ? p.avatar_url : "https://cdn.discordapp.com/embed/avatars/0.png";
    return {
        username: String(p.username || "").slice(0, 32),
        avatar_url: avatar,
        cells: liveCells(rows),
        done: p.done === true,
        won: p.won === true,
        live: p.live === true,
    };
}

function liveParticipant(p) {
    // someone in this Discord Activity not in /api/live yet: avatar + empty board
    var avatar = "https://cdn.discordapp.com/embed/avatars/0.png";
    try {
        // the same picture the server will send (app.py lb_avatar_url), so nothing flickers
        avatar = p.avatar
            ? "https://cdn.discordapp.com/avatars/" + p.id + "/" + p.avatar + ".png?size=64"
            : "https://cdn.discordapp.com/embed/avatars/" + Number((BigInt(p.id) >> BigInt(22)) % BigInt(6)) + ".png";
    } catch (e) { }
    return {
        username: String(p.username || "").slice(0, 32),
        avatar_url: LIVE_AVATAR_RE.test(avatar) ? avatar : "https://cdn.discordapp.com/embed/avatars/0.png",
        cells: liveCells([]),
        done: false,
        won: false,
        live: true,
        pending: true,
    };
}

// Leaderboard game sync. Rule: the server is the single source of truth for a
// logged-in player's game; the web page (and the Discord Activity) only paint it.
// loadState() = GET /api/state + repaint; submitGuess() = POST /api/guess with
// "attempt" (a 409 "stale" or "finished" answer carries the state to repaint).
// Reloads on focus / visible tab (at most once per 5 s), every 60 s while visible,
// and when the Panama date changes (new word: empty board and keyboard).
const SYNC_MIN_GAP = 5000;
const SYNC_EVERY = 60000;
const SYNC = { busy: false, at: 0, gen: 0, stopped: false, reauthed: false };
// a guess still unanswered after this long is given up (error toast; typing works
// again). Safe: "attempt" makes a late duplicate a 409, never a second guess.
const GUESS_MS = 20000;
const EMPTY_TILE = "border-2 border-neutral-300";

function panamaDate(ms) {
    // "YYYY-MM-DD" in Panama (UTC-5, no daylight saving), like daily.panama_today()
    return new Date((ms === undefined ? Date.now() : ms) - 5 * 3600 * 1000).toISOString().slice(0, 10);
}

// Canonical public address for share links (server-side public_url(); never the
// page's own origin, which inside the Discord Activity is a proxy nobody can open).
const PUBLIC_ORIGIN = (function () {
    var el = document.getElementById("app");
    var value = el ? (el.getAttribute("data-public-origin") || "") : "";
    return /^https?:\/\/[^\s\/?#]+$/.test(value.replace(/\/+$/, "")) ? value.replace(/\/+$/, "") : window.location.origin;
})();

function pageKey() {
    // localStorage key of a saved guest game: the last path segment ("/es" -> "es"),
    // never the query string (?frame_id=... broke it). Same key as older saves.
    var path = window.location.pathname.replace(/\/+$/, "");
    return path.substring(path.lastIndexOf("/") + 1);
}

function readFlag(key) {
    try { return localStorage.getItem(key) === "1"; } catch (e) { return false; }
}

const app = Vue.createApp({
    delimiters: ['[[', ']]'],  // don't want to clash with Jinja (backend templating coming from flask)
    data() {
        return {
            active_row: 0,
            active_cell: 0,
            full_word_inputted: false,
            game_over: false,
            game_lost: false,
            game_won: false,

            // these variables come from Jinja
            todays_word: todays_word,
            todays_idx: todays_idx,
            config: config,
            allow_any_word: false,


            showHelpModal: false,
            show_stats_modal: false,
            show_options_modal: false,

            notification: {
                show: false,
                message: "",
                top: 0,
                timeout: 0,
            },

            tiles: [
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
            ],
            tile_classes: [
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
            ],

            // what is drawn: a copy of tiles/tile_classes (the flipping row keeps its own classes)
            tiles_visual: [
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
                ["", "", "", "", ""],
            ],
            tile_classes_visual: [
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
                ["border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300", "border-2 border-neutral-300"],
            ],

            // countdown to the next word, updated every second
            time_until_next_day: "",

            // true while the last guess is flipping, typing is ignored meanwhile
            revealing: false,
            revealing_row: -1,
            pending_key_classes: null,  // keyboard colors waiting for the flip to end

            kolo_image: "",  // e.g. "win/pizza.webp", chosen when the game ends
            kolo_base: KOLO_BASE,

            emoji_board: "⬜⬜⬜⬜⬜\n",
            attempts: "0",

            stats: {},

            // leaderboard game only
            lb_busy: false,     // a guess is on its way to the server: typing waits
            lb_points: null,    // points for today's game, once it's over
            lb_rank: null,      // place in this language's ranking, once it's over
            lb_hint_off: readFlag("casa24_lb_hint_off"),
            lb_day: (LB_STATE && LB_STATE.day) || null,  // the server's Panama date for this game
            lb_local_day: panamaDate(),                 // this device's Panama date (midnight check)
            live_players: [],   // live view: other players today (colors only)
            live_participants: [],  // Discord Activity: others in this Activity now (no board yet)
            live_count: 0,
            live_loaded: false, // first answer arrived (shows the empty state)
            live_settled: false, // first cards are on screen: from now on joins pop in (style.css .is-live)
            live_open: false,   // narrow screens: the bottom sheet is open
            lb_ready: !ACTIVITY, // Discord Activity: the first state from the server has been painted
            board_open: false,  // Discord Activity: leaderboard window
            lang_open: false,   // Discord Activity: language window (header "ES ▾")
            board_tab: "",
            board_rows: [],
            board_me: null,
            board_loading: false,
            board_error: false,
            share_open: false,  // share text to copy by hand
            share_text: "",
        }
    },
    computed: {
        // computed properties
        key_classes: {
            // one entry per keyboard letter (folded: "o" also colors for "ó"), plus ⇨ and ⌫
            get() {
                let keys = {};
                for (let i = 0; i < INPUT_CHARS.length; i++) {
                    keys[INPUT_CHARS[i]] = "";
                }
                keys["⇨"] = "";
                keys["⌫"] = "";
                return keys;
            },
            set(saved) {
                // a saved game's key colors (this.key_classes = ... would recurse).
                // Old saves may have accented keys ("á"): they color the plain key.
                for (let i = 0; i < INPUT_CHARS.length; i++) {
                    this.key_classes[INPUT_CHARS[i]] = "";
                }
                if (!saved || typeof saved !== "object") {
                    return;
                }
                for (var k in saved) {
                    var f = foldAccents(String(k).toLowerCase());
                    if (INPUT_CHARS.indexOf(f) >= 0) {
                        this.colorKey(this.key_classes, f, saved[k]);
                    }
                }
            }
        },

        acceptable_characters() {
            return INPUT_CHARS.join("");
        },
        live_cards() {
            // live view cards: the server's players (with boards), then anyone in this
            // Discord Activity the server doesn't list yet (empty board, shown at once)
            var known = new Set(this.live_players.map((p) => p.username));
            var extra = this.live_participants.filter((p) => !known.has(p.username));
            return this.live_players.concat(extra);
        },
        live_total() {
            return this.live_count + this.live_cards.length - this.live_players.length;
        },
    },
    created() {
        // remember the last language played, for the start screen
        if (!DEMO) {
            try { localStorage.setItem("casa24_lang", this.config.language_code); } catch (e) { }
        }
        // listen for any keypresses
        window.addEventListener('keydown', this.keyDown);

        // load results (storage can be blocked, e.g. inside some iframes: then start empty)
        try {
            if (localStorage.getItem("game_results") === null) {
                this.game_results = {};
                this.game_results[this.config.language_code] = [];
                localStorage.setItem("game_results", JSON.stringify(this.game_results));
            } else {
                this.game_results = JSON.parse(localStorage.getItem("game_results"));
                if (!this.game_results[this.config.language_code]) {
                    this.game_results[this.config.language_code] = [];
                }
            }
        } catch (e) {
            this.game_results = {};
            this.game_results[this.config.language_code] = [];
        }

        //calculate stats
        this.stats = this.calculateStats(this.config.language_code);

        this.time_until_next_day = this.get_time_until_next_day();
    },
    mounted() {
        // print time until next day every 5 seconds
        setInterval(() => {
            this.time_until_next_day = this.get_time_until_next_day();
            if (LB) {
                // Panama midnight on this device: ask the server for the new day's game
                var local_day = panamaDate();
                if (local_day !== this.lb_local_day) {
                    this.lb_local_day = local_day;
                    this.loadState(true);
                }
            }
        }, 1000);
        if (ACTIVITY) {
            // inside Discord the page has no state: ask the server once logged in
            activityReady().then(this.activityFirstLoad);
            this.activityWatchdog();
        } else if (LB) {
            this.restoreLb(LB_STATE);
        } else {
            this.loadFromLocalStorage();
        }
        this.showTiles();

        if (this.game_over) {
            this.show_stats_modal = true;
        }
        if (LB) {
            // live view: first ask after the board has rendered, then every 3 s while visible
            document.addEventListener("visibilitychange", this.liveVisibility);
            if (ACTIVITY) { activityReady().then(() => { window.C24Activity.onParticipants(this.applyParticipants); }); }
            this.$nextTick(() => { setTimeout(this.liveFetch, 0); });
            // sync: the page already has fresh state; reload when the player comes back
            SYNC.at = Date.now();
            document.addEventListener("visibilitychange", this.syncOnReturn);
            window.addEventListener("focus", this.syncOnReturn);
            setInterval(() => { if (!document.hidden) { this.loadState(); } }, SYNC_EVERY);
        }
    },
    beforeUpdate() {
        if (this.show_stats_modal) {
            this.emoji_board = this.getEmojiBoard();
        }
    },
    methods: {
        async shareResults() {
            // share text, e.g. "Casa 24 Wordle ES #123 3/6" + link + emoji grid.
            // Web: the system share sheet, else copy. Inside Discord: copy only (no new
            // windows from the iframe). Can't copy: a window with the text to copy by hand.
            this.emoji_board = this.getEmojiBoard();
            var text_to_share = "Casa 24 Wordle " + this.config.language_code.toUpperCase() + " #" + this.todays_idx + " " + this.attempts + "/6" + "\n" + PUBLIC_ORIGIN + "/" + this.config.language_code + "\n" + "\n" + this.emoji_board;
            if (navigator.share && !ACTIVITY) {
                try {
                    await navigator.share({
                        text: text_to_share,
                    });
                } catch (error) {
                    console.log('Error sharing: ', error);
                }
            } else if (navigator.clipboard && navigator.clipboard.writeText) {
                try {
                    await navigator.clipboard.writeText(text_to_share);
                    this.showNotification(this.text("notification-copied", "Copied to clipboard"));
                } catch (error) {
                    this.openShareText(text_to_share);
                }
            } else {
                this.openShareText(text_to_share);
            }
        },
        openShareText(text) {
            // the share text in a window, selected, to copy by hand
            this.share_text = text;
            this.share_open = true;
            this.$nextTick(() => {
                var area = document.querySelector("[data-share-text]");
                if (area) { area.focus(); area.select(); }
            });
        },
        openBoard() {
            // Discord Activity: the leaderboard in a window of this page
            this.show_stats_modal = false;
            this.board_open = true;
            this.loadBoard(this.board_tab || this.config.language_code);
        },
        openLang() {
            // Discord Activity: the language window (header "ES ▾")
            this.show_options_modal = false;
            this.show_stats_modal = false;
            this.lang_open = true;
            this.$nextTick(() => {
                var current = document.querySelector("[data-lang-choice][aria-current='true']");
                if (current && current.focus) { current.focus(); }
            });
        },
        chooseLang(code) {
            // the Activity shell swaps this page for the other language; its Discord
            // connection stays (no new login, no reload of the Activity)
            this.lang_open = false;
            if (code === this.config.language_code) { return; }
            if (window.C24Activity && window.C24Activity.setLang) { window.C24Activity.setLang(code); }
        },
        loadBoard(tab) {
            this.board_tab = tab;
            this.board_loading = true;
            this.board_error = false;
            lbFetch("/api/leaderboard?tab=" + encodeURIComponent(tab), {
                cache: "no-store",
                headers: { "Accept": "application/json" },
            }).then((response) => response.ok ? response.json() : null).then((data) => {
                if (this.board_tab !== tab) { return; }  // another tab was picked meanwhile
                this.board_loading = false;
                if (!data || !Array.isArray(data.rows)) {
                    this.board_error = true;
                    return;
                }
                this.board_rows = data.rows.slice(0, 100);
                this.board_me = data.me || null;
            }).catch(() => {
                if (this.board_tab === tab) {
                    this.board_loading = false;
                    this.board_error = true;
                }
            });
        },
        activityFirstLoad() {
            // first state after the Discord login; retried until the server answers
            this.loadState(true).then(() => {
                if (!this.lb_ready && !SYNC.stopped) { setTimeout(this.activityFirstLoad, 3000); }
            });
        },
        activityWatchdog() {
            // discord-activity.js never ran (blocked or failed to load): say so, offer a reload
            setTimeout(() => {
                if (window.C24Activity) { return; }
                var overlay = document.getElementById("c24-activity-overlay");
                if (!overlay) { return; }
                overlay.setAttribute("data-state", "error");
                var retry = overlay.querySelector("[data-activity-retry]");
                if (retry) { retry.addEventListener("click", function () { window.location.reload(); }); }
            }, 20000);
        },
        activityReauth() {
            // Discord Activity: session refused (401). Log in again silently, once per page.
            if (!ACTIVITY || SYNC.reauthed || !window.C24Activity || !window.C24Activity.reauth) {
                return false;
            }
            SYNC.reauthed = true;
            window.C24Activity.reauth().then((ok) => {
                if (ok) {
                    SYNC.stopped = false;
                    LIVE.stopped = false;
                    this.loadState(true);
                    this.liveFetch();
                }
            });
            return true;
        },
        get_time_until_next_day() {
            // returns time until the next day in Panama (UTC-5) formatted as "h m s"

            var d = new Date();
            var h = (d.getUTCHours() + 24 - 5) % 24; // Panama time, UTC-5
            var m = d.getUTCMinutes();
            var s = d.getUTCSeconds();
            
            var time_until_next_day = ""
            if (h < 23) {
                time_until_next_day += (23 - h) + "h ";
            } else {
                time_until_next_day += "0h ";
            }
            if (m < 59) {
                time_until_next_day += (59 - m) + "m ";
            } else {
                time_until_next_day += "0m ";
            }
            if (s < 59) {
                time_until_next_day += (59 - s) + "s";
            } else {
                time_until_next_day += "0s";
            }
            return time_until_next_day;
        },
        addChar(char) {
            this.tiles[this.active_row][this.active_cell] = char;
            this.tile_classes[this.active_row][this.active_cell] = "uppercase font-bold select-none border-2 border-neutral-500 pop";
            this.active_cell = Math.min(this.active_cell + 1, 5);
            if (this.active_cell == 5) {
                this.full_word_inputted = true;
            }
        },

        accentInsensitive() {
            return this.config.accent_insensitive === true || this.config.accent_insensitive === "true";
        },
        resolveAccents(word) {
            // In accent-insensitive languages, find the real (accented) word the
            // player meant: "cancion" -> "canción". Today's word wins ties.
            if (!this.accentInsensitive()) {
                return word;
            }
            var folded = foldAccents(word);
            if (folded === foldAccents(this.todays_word)) {
                return this.todays_word;
            }
            if (this.checkWord(word) && !this.allow_any_word) {
                return word;
            }
            if (!this.fold_map) {
                this.fold_map = {};
                var lists = [word_list, word_list_supplement];
                for (var l = 0; l < lists.length; l++) {
                    for (var i = 0; i < lists[l].length; i++) {
                        var key = foldAccents(lists[l][i]);
                        if (!(key in this.fold_map)) {
                            this.fold_map[key] = lists[l][i];
                        }
                    }
                }
            }
            return this.fold_map[folded] || word;
        },
        checkWord(word) {
            if (this.allow_any_word) {
                return true;
            }
            return word_list.indexOf(word) != -1 || word_list_supplement.indexOf(word) != -1;
        },

        updateColors() {
            // Colors for the current row. Letters are compared folded (foldAccents): a plain
            // "o" counts for "ó" in today's word and the other way round, ü = u; ñ is its own
            // letter. Greens first; then yellows from the letters left over, left to right
            // (a letter that appears once in the answer colors only once); the rest gray.
            // The key of the folded letter gets the best color (colorKey).
            var answer = Array.from(foldAccents(this.todays_word));
            var guess = this.tiles[this.active_row].map((c) => foldAccents(c));
            var counts = {};
            for (let i = 0; i < answer.length; i++) {
                counts[answer[i]] = (counts[answer[i]] || 0) + 1;
            }
            var colors = [];
            for (let i = 0; i < guess.length; i++) {
                if (guess[i] === answer[i]) {
                    colors[i] = "correct";
                    counts[guess[i]] -= 1;
                }
            }
            for (let i = 0; i < guess.length; i++) {
                if (colors[i]) {
                    continue;
                }
                if (counts[guess[i]] > 0) {
                    colors[i] = "semicorrect";
                    counts[guess[i]] -= 1;
                } else {
                    colors[i] = "incorrect";
                }
            }
            for (let i = 0; i < guess.length; i++) {
                this.tile_classes[this.active_row][i] = colors[i] + " " + TILE_BASE;
                this.colorKey(this.key_classes, guess[i], colors[i]);
            }
        },
        keyClick(key) {
            // an on-screen key was tapped: handle it like a typed key
            this.keyDown({ key: key });
            // drop focus from the tapped key, so a physical Enter afterwards
            // submits the word instead of pressing that key again
            var focused = document.activeElement;
            if (focused && focused.classList && focused.classList.contains("key")) {
                focused.blur();
            }
        },
        normalizeKey(key) {
            // A typed letter becomes a keyboard letter: Shift/Caps Lock "A" -> "a", accented
            // keys "á"/"Ü" -> "a"/"u" (accents are optional), "Ñ" -> "ñ" (its own letter).
            // Named keys ("Enter", "Backspace", "Dead") and ⇨/⌫ stay as they are.
            if (typeof key !== "string") {
                return key;
            }
            var nfc = key.normalize("NFC");
            if (Array.from(nfc).length !== 1) {
                return key;
            }
            return foldAccents(nfc.toLowerCase());
        },
        keyDown(event) {
            var key = event.key;
            if (key === "Escape") { // QoL
                this.closeLive();
                this.showHelpModal = false;
                this.show_stats_modal = false;
                this.show_options_modal = false;
                this.board_open = false;
                this.lang_open = false;
                this.share_open = false;
                return;
            }
            // shortcuts (Ctrl+R, Cmd+C...) and IME composition are not typing;
            // AltGr (Ctrl+Alt on Windows) still types letters on some layouts
            var alt_graph = event.getModifierState && event.getModifierState("AltGraph");
            if (event.metaKey || ((event.ctrlKey || event.altKey) && !alt_graph) || event.isComposing) {
                return;
            }
            // typing in the settings (a select or input) is not a guess
            var target = event.target;
            if (target && target.tagName && (/^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName) || target.isContentEditable)) {
                return;
            }
            key = this.normalizeKey(key);

            // (typing never waits for the first state: a guess sent before it carries
            // "attempt", and a server that has moved on answers 409 with its game)
            if (this.game_over || this.revealing || this.lb_busy) {
                return;
            }
            // console.log('keyDown', this.active_cell, this.active_row, event.key);
            if (key === "Enter" || key === "⇨") {
                if (!this.full_word_inputted) {
                    this.showNotification(this.text("notification-partial-word", "Please enter a full word"));
                    return;
                }
                if (LB) {
                    // the server checks the word and colors it (submitGuess)
                    this.submitGuess();
                    return;
                }
                // if checkWord returns true, then go to next row
                var word = this.tiles[this.active_row].join("").toLowerCase();
                // "cancion" becomes "canción": the board then shows the accented word
                var resolved = this.resolveAccents(word);
                if (resolved !== word) {
                    word = resolved;
                    for (let i = 0; i < 5; i++) {
                        this.tiles[this.active_row][i] = word[i];
                    }
                }
                var word_is_valid = this.checkWord(word);
                // the same word can't be guessed twice in one game
                var already_tried = this.tiles.slice(0, this.active_row).some(r => r.join("") === word);
                if (word_is_valid && already_tried) {
                    this.showNotification(this.text("notification-repeated", "You already tried that word"));
                } else if (word_is_valid) {
                    // color the keyboard only after the tiles finish flipping
                    var keys_before = Object.assign({}, this.key_classes);
                    this.updateColors();
                    var keys_after = Object.assign({}, this.key_classes);
                    Object.assign(this.key_classes, keys_before);
                    var won = word === this.todays_word;
                    this.commitRow(keys_after, won, won || this.active_row == 5);
                } else {
                    this.showNotification(this.text("notification-not-valid", "Word is not valid"));
                }

            } else if ((key === "Backspace" || key === "Delete" || key === "⌫") && this.active_cell > 0) {
                // set current active cell to empty and move backwards one
                this.tiles[this.active_row][this.active_cell - 1] = "";
                this.active_cell = Math.max(this.active_cell - 1, 0);
                this.tile_classes[this.active_row][this.active_cell] = "border-2 border-neutral-300";
                this.full_word_inputted = false;
                // if key is esc, close any modal

            } else {
                if (!this.full_word_inputted) {
                    if (Array.from(key).length === 1 && this.acceptable_characters.indexOf(key) >= 0) {
                        this.addChar(key);
                    }
                }
            }
            this.showTiles();
            this.saveToLocalStorage();
        },
        commitRow(keys_after, won, done) {
            // The current row's tile_classes are final: move to the next row, flip
            // the tiles, then color the keyboard (and bounce on a win).
            var row = this.active_row;
            // saved right away, so a reload mid-flip keeps the keyboard colors
            this.pending_key_classes = keys_after;
            this.active_row++;
            this.active_cell = 0;
            this.full_word_inputted = false;
            var reveal_ms = this.revealRow(row, () => {
                Object.assign(this.key_classes, keys_after);
                this.pending_key_classes = null;
                this.showTiles();
                if (won) {
                    this.bounceRow(row);
                }
                this.saveToLocalStorage();
            });
            if (won) {
                this.gameWon(reveal_ms);
            } else if (done) {
                this.gameLost(reveal_ms);
            }
        },
        colorKey(keys, character, color) {
            // a key keeps its best color: correct > semicorrect > incorrect
            if ((COLOR_RANK[color] || 0) > (COLOR_RANK[keys[character]] || 0)) {
                keys[character] = color;
            }
        },
        setRowFromServer(row, word, colors) {
            // the server's spelling (accents resolved) and colors for one guess
            var letters = Array.from(word);
            for (let i = 0; i < 5; i++) {
                this.tiles[row][i] = letters[i] || "";
                this.tile_classes[row][i] = colors[i] + " " + TILE_BASE;
            }
        },
        restoreLb(state) {
            // leaderboard game: rebuild today's board from the server (no localStorage)
            if (!state || !Array.isArray(state.guesses)) {
                return;
            }
            if (typeof state.day === "string") { this.lb_day = state.day; }
            if (Number.isInteger(state.puzzle)) { this.todays_idx = String(state.puzzle); }
            var keys = Object.assign({}, this.key_classes);
            var guesses = state.guesses.slice(0, 6);
            for (let r = 0; r < guesses.length; r++) {
                this.setRowFromServer(r, guesses[r].word, guesses[r].colors);
                var letters = Array.from(guesses[r].word);
                for (let i = 0; i < 5; i++) {
                    this.colorKey(keys, foldAccents(letters[i] || ""), guesses[r].colors[i]);
                }
            }
            Object.assign(this.key_classes, keys);
            this.active_row = guesses.length;
            this.active_cell = 0;
            this.full_word_inputted = false;
            if (state.done) {
                this.game_over = true;
                this.game_won = !!state.won;
                this.todays_word = state.answer || "";
                this.lb_points = state.points === undefined ? null : state.points;
                this.lb_rank = state.rank === undefined ? null : state.rank;
                this.pickKolo();
                this.emoji_board = this.getEmojiBoard();
            }
        },
        resetBoard() {
            // empty board and keyboard, no end window: before painting the server's state
            for (let r = 0; r < 6; r++) {
                for (let i = 0; i < 5; i++) {
                    this.tiles[r][i] = "";
                    this.tile_classes[r][i] = EMPTY_TILE;
                }
            }
            var keys = {};
            for (var k in this.key_classes) { keys[k] = ""; }
            Object.assign(this.key_classes, keys);
            this.pending_key_classes = null;
            this.active_row = 0;
            this.active_cell = 0;
            this.full_word_inputted = false;
            this.game_over = false;
            this.game_won = false;
            this.game_lost = false;
            this.todays_word = "";
            this.lb_points = null;
            this.lb_rank = null;
            this.kolo_image = "";
            this.emoji_board = "";
            this.attempts = "0";
        },
        paintState(state) {
            // repaint from the server's state (GET /api/state, or a 409/finished answer).
            // Same day and same progress: keep what the player is typing, only refresh numbers.
            if (!state || !Array.isArray(state.guesses)) {
                return;
            }
            this.lb_ready = true;
            var same_day = state.day === this.lb_day;
            var n = Math.min(state.guesses.length, 6);
            if (same_day && n === this.active_row && !!state.done === this.game_over) {
                if (state.done) {
                    this.lb_points = state.points === undefined ? null : state.points;
                    this.lb_rank = state.rank === undefined ? null : state.rank;
                }
                if (Number.isInteger(state.puzzle)) { this.todays_idx = String(state.puzzle); }
                return;
            }
            var was_over = this.game_over;
            this.resetBoard();
            this.restoreLb(state);
            this.revealing_row = -1;
            this.showTiles();
            if (!same_day) {
                // a new word: close the old end window and the old answer toast
                this.hideNotification();
                this.show_stats_modal = false;
            }
            if (this.game_over && (!was_over || !same_day)) {
                this.show_stats_modal = true;  // finished elsewhere (another tab, Discord)
            }
        },
        loadState(force) {
            // GET /api/state and repaint. Skipped while a guess is on its way or flipping;
            // at most once per 5 s unless forced (day change, 409, finished).
            if (!LB || SYNC.stopped || SYNC.busy || this.lb_busy || this.revealing) {
                return Promise.resolve(false);
            }
            var now = Date.now();
            if (!force && now - SYNC.at < SYNC_MIN_GAP) {
                return Promise.resolve(false);
            }
            SYNC.at = now;
            SYNC.busy = true;
            var gen = SYNC.gen;
            return lbFetch("/api/state?lang=" + encodeURIComponent(this.config.language_code), {
                credentials: "same-origin",
                cache: "no-store",
                headers: { "Accept": "application/json" },
            }).then((response) => {
                return response.json().catch(() => null).then((data) => ({ ok: response.ok, status: response.status, data: data }));
            }).then((result) => {
                SYNC.busy = false;
                if (result.status === 401 || result.status === 404 || result.status === 400) {
                    SYNC.stopped = true;  // logged out / feature off: the next guess handles it
                    if (result.status === 401) { this.activityReauth(); }
                    return false;
                }
                // a guess started meanwhile: its answer is newer than this state
                if (!result.ok || gen !== SYNC.gen || this.lb_busy || this.revealing) {
                    return false;
                }
                this.paintState(result.data);
                return true;
            }).catch(() => {
                SYNC.busy = false;
                return false;
            });
        },
        syncOnReturn() {
            // back to the tab / window: the game may have moved on elsewhere (Discord, another device)
            if (!document.hidden) {
                this.loadState();
            }
        },
        submitGuess() {
            // leaderboard game: the server checks the guess, colors it and keeps score.
            // "attempt" = the row being filled; if the server has a different count
            // (played elsewhere meanwhile) it answers 409 with its state and nothing is saved.
            if (this.lb_busy) {
                return;
            }
            var row = this.active_row;
            var typed = this.tiles[row].join("").toLowerCase();
            // the same word can't be guessed twice (also typed without accents)
            var resolved = this.resolveAccents(typed);
            var fold = (w) => this.accentInsensitive() ? foldAccents(w) : w;
            var already_tried = this.tiles.slice(0, row).some(r => {
                var w = r.join("");
                return w === resolved || fold(w) === fold(typed);
            });
            if (already_tried) {
                this.showNotification(this.text("notification-repeated", "You already tried that word"));
                return;
            }
            this.lb_busy = true;
            SYNC.gen++;
            var lang = this.config.language_code;
            // never stuck "on its way": give up after GUESS_MS (also while still waiting
            // for the Discord login), so typing and syncing never stop for good
            var ctrl = typeof AbortController === "function" ? new AbortController() : null;
            var timer = setTimeout(() => { if (ctrl) { ctrl.abort(); } }, GUESS_MS);
            lbFetch("/api/guess", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lang: lang, guess: typed, attempt: row }),
                signal: ctrl ? ctrl.signal : undefined,
            }).then((response) => {
                return response.json().catch(() => ({})).then((data) => ({ ok: response.ok, status: response.status, data: data }));
            }).then((result) => {
                clearTimeout(timer);
                this.lb_busy = false;
                var data = result.data || {};
                if (result.ok && Array.isArray(data.colors)) {
                    if (typeof data.day === "string" && this.lb_day && data.day !== this.lb_day) {
                        // the day changed under us: paint the new day's game from the server
                        this.loadState(true);
                        return;
                    }
                    this.applyLbGuess(data);
                } else if (data.state && (result.status === 409 || data.error === "finished" || data.error === "too_many")) {
                    // played elsewhere meanwhile: just show the server's game, no error
                    this.paintState(data.state);
                } else {
                    this.lbError(data.error || (result.status === 401 ? "login" : ""), "http " + result.status);
                }
            }).catch((error) => {
                clearTimeout(timer);
                this.lb_busy = false;
                this.lbError("", error && error.name === "AbortError" ? "timeout" : "network");
            });
        },
        applyLbGuess(res) {
            // one guess colored by the server: same flip / bounce / end flow as a guest game
            var row = this.active_row;
            this.setRowFromServer(row, res.word, res.colors);
            var keys_after = Object.assign({}, this.key_classes);
            var letters = Array.from(res.word);
            for (let i = 0; i < 5; i++) {
                this.colorKey(keys_after, foldAccents(letters[i] || ""), res.colors[i]);
            }
            if (res.done) {
                // the answer only arrives once the game is over
                this.todays_word = res.answer || "";
                this.lb_points = res.points === undefined ? null : res.points;
                this.lb_rank = res.rank === undefined ? null : res.rank;
            }
            this.commitRow(keys_after, !!res.won, !!res.done);
            this.showTiles();
        },
        lbError(code, detail) {
            // inside Discord: also into Discord's debug console (via the shell; codes only)
            if (ACTIVITY && code !== "invalid_word" && code !== "repeat" && window.C24Activity && window.C24Activity.log) {
                window.C24Activity.log("guess not saved: " + (code || "") + " " + (detail || ""));
            }
            if (code === "login" && ACTIVITY) {
                // inside Discord: log in again silently (no login page in the iframe)
                if (!this.activityReauth()) {
                    this.showNotification(this.text("lb_error", "Something went wrong. Please try again."));
                }
            } else if (code === "login") {
                // session expired: log in again, then come back to this game
                var next = "/lb/" + this.config.language_code;
                window.location.href = "/auth/discord/login?next=" + encodeURIComponent(next);
            } else if (code === "invalid_word") {
                this.showNotification(this.text("notification-not-valid", "Word is not valid"));
            } else if (code === "repeat") {
                this.showNotification(this.text("notification-repeated", "You already tried that word"));
            } else if (code === "finished" || code === "too_many" || code === "stale") {
                // finished or moved on elsewhere: show the server's game
                this.loadState(true);
            } else {
                this.showNotification(this.text("lb_error", "Something went wrong. Please try again."));
            }
        },
        liveFetch() {
            // one GET /api/live; schedules the next one (unless hidden or stopped)
            clearTimeout(LIVE.timer);
            LIVE.timer = null;
            if (LIVE.stopped || LIVE.busy || document.hidden) {
                return;
            }
            LIVE.busy = true;
            lbFetch("/api/live?lang=" + encodeURIComponent(this.config.language_code), {
                credentials: "same-origin",
                cache: "no-store",
                headers: { "Accept": "application/json" },
            }).then((response) => {
                return response.json().catch(() => null).then((data) => ({ ok: response.ok, status: response.status, data: data }));
            }).then((result) => {
                LIVE.busy = false;
                if (result.ok && result.data && Array.isArray(result.data.players)) {
                    this.applyLive(result.data);
                    LIVE.delay = LIVE_EVERY;
                } else if (result.status === 401 || result.status === 404 || result.status === 400) {
                    LIVE.stopped = true;  // logged out / feature off: stop asking
                    if (result.status === 401) { this.activityReauth(); }
                    return;
                } else {
                    LIVE.delay = Math.min(LIVE.delay * 2, LIVE_MAX);  // 429 rate or server trouble: back off
                }
                this.liveSchedule();
            }).catch(() => {
                LIVE.busy = false;
                LIVE.delay = Math.min(LIVE.delay * 2, LIVE_MAX);
                this.liveSchedule();
            });
        },
        liveSchedule() {
            clearTimeout(LIVE.timer);
            LIVE.timer = null;
            if (!LIVE.stopped && !document.hidden) {
                LIVE.timer = setTimeout(this.liveFetch, LIVE.delay);
            }
        },
        liveVisibility() {
            // hidden tab: no polling; visible again: ask right away
            if (document.hidden) {
                clearTimeout(LIVE.timer);
                LIVE.timer = null;
            } else {
                this.liveFetch();
            }
        },
        applyLive(data) {
            var players = data.players.filter((p) => p && typeof p === "object").slice(0, 50).map((p) => livePlayer(p));
            this.live_players = players;
            this.live_count = Number.isInteger(data.count) && data.count >= 0 ? data.count : players.length;
            this.live_loaded = true;
            if (!this.live_settled) { setTimeout(() => { this.live_settled = true; }, 0); }
        },
        applyParticipants(list) {
            // Discord: someone joined or left this Activity. Show them now, then ask
            // /api/live right away for their board.
            var before = this.live_participants.map((p) => p.username).join(",");
            this.live_participants = list.map(liveParticipant);
            if (this.live_participants.map((p) => p.username).join(",") !== before) {
                LIVE.delay = LIVE_EVERY;
                this.liveFetch();
            }
        },
        toggleLive() {
            if (this.live_open) {
                this.closeLive();
                return;
            }
            this.live_open = true;
            this.$nextTick(() => {
                var close = document.querySelector("[data-live-close]");
                if (close && close.offsetParent !== null) { close.focus(); }
            });
        },
        closeLive() {
            if (!this.live_open) {
                return;
            }
            this.live_open = false;
            // drop focus (like the keys), so a physical Enter next submits a word, not this button
            var focused = document.activeElement;
            if (focused && focused.closest && focused.closest("#c24-live, [data-live-open]")) {
                focused.blur();
            }
        },
        dismissLbHint() {
            this.lb_hint_off = true;
            try { localStorage.setItem("casa24_lb_hint_off", "1"); } catch (e) { }
        },
        showTiles() {
            // copy the board to what is drawn; the row that is flipping keeps its own
            // classes (revealRow handles it)
            for (let i = 0; i < this.tiles.length; i++) {
                this.tiles_visual[i] = this.tiles[i].map(x => x);
                if (i !== this.revealing_row) {
                    this.tile_classes_visual[i] = this.tile_classes[i].map(x => x);
                }
            }
        },
        reduceMotion() {
            return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        },
        revealRow(row, onDone) {
            // Flip the tiles of a just-guessed row one by one; each shows its color
            // halfway through the flip. Only the visual classes change: tile_classes
            // (what gets saved) already has the final colors.
            // Returns how long the whole reveal takes, in ms.
            const STAGGER = 300;  // time between one tile and the next
            const FLIP = 500;     // one tile's flip, must match .flip in style.css
            if (this.reduceMotion()) {
                onDone();
                return 0;
            }
            const final = this.tile_classes[row].map(x => x);
            const typed = "uppercase font-bold select-none border-2 border-neutral-500";
            const classes = this.tile_classes_visual[row];
            this.revealing = true;
            this.revealing_row = row;
            for (let i = 0; i < final.length; i++) {
                classes[i] = typed;
                setTimeout(() => { classes[i] = typed + " flip"; }, i * STAGGER);
                setTimeout(() => { classes[i] = final[i] + " flip"; }, i * STAGGER + FLIP / 2);
                setTimeout(() => { classes[i] = final[i]; }, i * STAGGER + FLIP);
            }
            const total = (final.length - 1) * STAGGER + FLIP;
            setTimeout(() => {
                this.revealing = false;
                this.revealing_row = -1;
                onDone();
            }, total);
            return total;
        },
        bounceRow(row) {
            // the winning row jumps letter by letter (delays are in style.css)
            if (this.reduceMotion()) {
                return;
            }
            const classes = this.tile_classes_visual[row];
            for (let i = 0; i < classes.length; i++) {
                classes[i] = classes[i] + " bounce bounce-d" + i;
            }
            setTimeout(() => { this.showTiles(); }, 1500);
        },
        kolo_url() {
            // "win/pizza.webp" -> /static/images/kolo/win/pizza.webp?v=...
            // (games saved before the PNGs were removed stored "win/pizza.png")
            var name = this.kolo_image.replace(/\.png$/, ".webp");
            return this.kolo_base + name + "?v=" + ASSET_V;
        },
        pickKolo() {
            var pool = this.game_won ? KOLO_WIN : KOLO_LOSE;
            var folder = this.game_won ? "win/" : "lose/";
            this.kolo_image = folder + pool[Math.floor(Math.random() * pool.length)];
        },
        gameWon(delay = 0) {
            // the game ends now (and is saved); the word and stats show after the tiles flip
            this.game_over = true;
            this.game_won = true;
            this.pickKolo();
            this.emoji_board = this.getEmojiBoard();
            setTimeout(() => {
                this.showNotification(this.todays_word.toUpperCase(), 12);
            }, delay);
            setTimeout(() => {
                this.hideNotification();  // the answer toast would cover the window title
                this.show_stats_modal = true;
            }, delay + (delay > 0 ? 1600 : 400));

            if (DEMO || LB) { return; }  // demo results don't count; leaderboard results live on the server
            // save a win to localStorage
            const result = { "won": true, "attempts": this.attempts, "date": new Date() };
            this.game_results[this.config.language_code].push(result);
            localStorage.setItem("game_results", JSON.stringify(this.game_results));
            
            // refresh stats
            this.stats = this.calculateStats(this.config.language_code);

        },
        gameLost(delay = 0) {
            setTimeout(() => {
                this.showNotification(this.todays_word.toUpperCase(), 12);
            }, delay);

            this.game_over = true;
            this.game_won = false;
            this.pickKolo();
            this.attempts = "X";
            setTimeout(() => {
                this.hideNotification();  // the answer toast would cover the window title
                this.show_stats_modal = true;
            }, delay + 400);
            if (DEMO || LB) { return; }  // demo results don't count; leaderboard results live on the server
            // save a loss to local storage game results
            this.game_results[this.config.language_code].push({ "won": false, "attempts": this.attempts, "date": new Date() });
            localStorage.setItem("game_results", JSON.stringify(this.game_results));

            // refresh stats
            this.stats = this.calculateStats(this.config.language_code);

        },
        demoRestart() {
            // new random word (the server skips the current one)
            window.location.href = "/demo/" + this.config.language_code + "?skip=" + encodeURIComponent(this.todays_word);
        },
        demoFillAnswer() {
            // type today's (demo) answer into the current row and press Enter, like a player would
            if (this.game_over || this.revealing) { return; }
            while (this.active_cell > 0) { this.keyDown({ key: "Backspace" }); }
            // folded like a physical keyboard ("ó" -> "o"); Enter turns it back into the answer
            for (const c of Array.from(foldAccents(this.todays_word))) { this.keyDown({ key: c }); }
            this.keyDown({ key: "Enter" });
        },
        inviteFriends() {
            // Discord Activity: open Discord's invite dialog (the bridge in discord-activity.js)
            if (window.C24Activity && window.C24Activity.invite) {
                window.C24Activity.invite();
            }
        },
        hideNotification() {
            clearTimeout(this.notification.timeout);
            this.notification.show = false;
        },
        showNotification(message, duration = 3) {
            // if there's already a notification, wait for it to finish then show new one
            if (this.notification.show) {
                this.notification.show = false;
                // clear existing timeout
                clearTimeout(this.notification.timeout);
                this.showNotification(message);
                return;
            }

            // show notification for 3 seconds
            this.notification.show = true;
            this.notification.message = message;
            this.notification.timeout = setTimeout(() => {
                this.notification.show = false;
            }, duration * 1000);
            
            // make notification appear at top of screen and move down continuously
            // this actually stopped working for some reason but whtv, was bad anyways
            this.notification.top = 0;
            var notification_interval = setInterval(() => {
                this.notification.top += 1;
                if (this.notification.top > 50) {
                    // stop moving down
                    clearInterval(notification_interval);
                }
            }, 2);
        },

        getEmojiBoard() {
            // turns tiles board into emojis
            // correct: 🟩
            // semi-correct: 🟧 (Kolo orange)
            // incorrect: ⬜
            var emoji_board = "";
            for (let i = 0; i < this.tile_classes.length; i++) {
                var row = this.tile_classes[i];
                for (let j = 0; j < row.length; j++) {
                    var tile_class = row[j];
                    if (tile_class.indexOf("correct") >= 0 && tile_class.indexOf("semicorrect") == -1 && tile_class.indexOf("incorrect") == -1) {
                        emoji_board += "🟩";
                    } else if (tile_class.indexOf("semicorrect") >= 0) {
                        emoji_board += "🟧";
                    } else if (tile_class.indexOf("incorrect") >= 0) {
                        emoji_board += "⬜";
                    } else {
                        return emoji_board;
                    }
                }

                // add newline if not last row
                if (i < this.tile_classes.length - 1) {
                    emoji_board += "\n";
                }
                
                this.attempts = String(i+1);
                // if game lost, show X
                if (this.game_over && !this.game_won) {
                    this.attempts = "X";
                }
            }
            return emoji_board;
        },

        text(key, fallback) {
            // UI text from language_config.json "text", English fallback if missing
            var value = this.config.text && this.config.text[key];
            return value ? value.trim() : fallback;
        },
        saveToLocalStorage() {
            if (DEMO || LB) { return; }  // demo games are never saved; leaderboard games live on the server
            // saves tiles, tile_classes, active_row and active_cell to local storage with key: page_name
            var page_name = pageKey();
            var data = {
                tiles: this.tiles,
                tile_classes: this.tile_classes,
                key_classes: this.pending_key_classes || this.key_classes,
                active_row: this.active_row,
                active_cell: this.active_cell,
                todays_word: this.todays_word,
                game_over: this.game_over,
                game_won: this.game_won,
                emoji_board: this.emoji_board,
                attempts: this.attempts,
                full_word_inputted: this.full_word_inputted,
                kolo_image: this.kolo_image,
            };
            localStorage.setItem(page_name, JSON.stringify(data));
        },
        loadFromLocalStorage() {
            if (DEMO || LB) { return; }
            // if local storage has data and the daily word is the same as the todays word, then load data
            var page_name = pageKey();
            var data = JSON.parse(localStorage.getItem(page_name));
            if (data && data.todays_word === this.todays_word) {
                this.tiles = data.tiles;
                this.tile_classes = data.tile_classes;
                this.key_classes = data.key_classes;
                this.active_row = data.active_row;
                this.active_cell = data.active_cell;
                this.todays_word = data.todays_word;
                this.game_over = data.game_over;
                this.game_won = data.game_won;
                this.emoji_board = data.emoji_board;
                this.attempts = data.attempts;
                this.full_word_inputted = data.full_word_inputted;
                this.kolo_image = data.kolo_image || "";
                if (this.game_over && !this.kolo_image) {
                    // games saved before random Kolos existed
                    this.pickKolo();
                }
            }
        },
        calculateStats(language_code) {
            // returns stats for the current language
            
            if (!this.game_results[language_code]) {
                return {
                    "n_wins": 0,
                    "n_losses": 0,
                    "n_games": 0,
                    "win_percentage": 0,
                    "longest_streak": 0,
                    "current_streak": 0,
                };
            }

            var results = this.game_results[language_code];
            var n_wins = 0;
            var n_losses = 0;
            var n_games = results.length;
            var current_streak = 0;
            var longest_streak = 0;
            for (let i = 0; i < results.length; i++) {
                var result = results[i];
                if (result.won) {
                    n_wins++;
                    current_streak++;
                    if (current_streak > longest_streak) {
                        longest_streak = current_streak;
                    }
                } else {
                    n_losses++;
                    current_streak = 0;
                }
            }
            var win_percentage = Math.round(n_wins / (n_wins + n_losses) * 100) || 0;

            return {
                "n_wins": n_wins,
                "n_losses": n_losses,
                "n_games": n_games,
                "win_percentage": win_percentage,
                "longest_streak": longest_streak,
                "current_streak": current_streak,
            };
        },
    },
});

app.mount('#app'); // mount vue on #app div
