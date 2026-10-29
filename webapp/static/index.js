// Casa 24 Wordle start screen.
// Two big cards, Español and English (last of the two played first, else the
// browser language); both follow the guest / leaderboard mode. Also
// today's puzzle number with a countdown to midnight Panama time, and stats.

function panamaDay(date) {
    // calendar day in Panama (UTC-5, no daylight saving), e.g. "2026-10-25"
    return new Date(date.getTime() - 5 * 3600 * 1000).toISOString().slice(0, 10);
}

function readStorage(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
}

function writeStorage(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { }
}

function readJson(id) {
    try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return null; }
}

// data from the server (JSON blocks in index.html; no inline scripts)
var languages = readJson("c24-languages") || {};
var todays_idx = String((readJson("c24-menu") || {}).todays_idx || "");

// leaderboard settings from the server: {"enabled": bool, "user": {"id", "username"} | null}
var lb_info = readJson("c24-lb") || { enabled: false, user: null };

const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        var results = {};
        try { results = JSON.parse(readStorage("game_results")) || {}; } catch (e) { results = {}; }
        return {
            showAboutModal: false,
            showStatsModal: false,
            languages: languages,
            todays_idx: todays_idx,
            game_results: results,
            total_stats: {},
            countdown: "",
            lb: lb_info,
            // where the Español/English cards go: signed in with Discord → "lb" (the
            // leaderboard game) unless the player switched on "play as guest"; else "guest"
            mode: lb_info.enabled && lb_info.user && readStorage("casa24_mode") !== "guest" ? "lb" : "guest",
        }
    },
    computed: {
        preferredLanguage() {
            var saved = readStorage("casa24_lang");
            if (saved === "es" || saved === "en") return saved;
            var browser = (navigator.language || "es").toLowerCase();
            return browser.indexOf("es") === 0 ? "es" : "en";
        },
        primaryLanguages() {
            var first = this.preferredLanguage;
            var second = first === "es" ? "en" : "es";
            return [this.languages[first], this.languages[second]];
        },
        menuLanguages() {
            return this.primaryLanguages;
        },
        loginLanguage() {
            // where the Discord sign-in lands: the last language played, else the browser's
            return this.preferredLanguage;
        },
        status() {
            // per language: played today? current streak?
            var today = panamaDay(new Date());
            var out = {};
            for (var code in this.languages) {
                var list = this.game_results[code] || [];
                var last = list[list.length - 1];
                out[code] = {
                    played_today: !!(last && last.date && panamaDay(new Date(last.date)) === today),
                    streak: this.calculateStats(code).current_streak,
                };
            }
            return out;
        },
    },
    created() {
        this.total_stats = this.calculateTotalStats();
        document.documentElement.lang = this.preferredLanguage;
        this.tick();
        setInterval(this.tick, 1000);
        // ?login=failed / ?deleted=1 notices show once; a reload shouldn't bring them back
        // (only those two params go: anything else in the query, like the Discord Activity's
        // frame_id / instance_id / platform, must stay)
        if (/[?&](login|deleted)=/.test(window.location.search) && window.history.replaceState) {
            var params = new URLSearchParams(window.location.search);
            params.delete("login");
            params.delete("deleted");
            var query = params.toString();
            window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : "") + window.location.hash);
        }
    },
    mounted() {
        window.addEventListener('keydown', this.keyDown);
        // the Discord sign-in links (server-rendered, v-pre) go to the player's language
        if (this.lb.enabled && !this.lb.user) {
            var href = "/auth/discord/login?next=" + encodeURIComponent("/lb/" + this.loginLanguage);
            var links = document.querySelectorAll("[data-dc-login]");
            for (var i = 0; i < links.length; i++) links[i].setAttribute("href", href);
        }
    },
    methods: {
        setMode(mode) {
            this.mode = mode === "lb" && this.lb.user ? "lb" : "guest";
            writeStorage("casa24_mode", this.mode);
        },
        label(code, key) {
            // each card speaks its own language
            var es = code === "es";
            if (key === "played") return es ? "Jugada hoy" : "Played today";
            return es ? "Jugar" : "Play";
        },
        playHref(code) {
            // guest: /en; leaderboard (signed in): /lb/en
            if (this.mode !== "lb" || !this.lb.enabled || !this.lb.user) return "/" + code;
            return "/lb/" + code;
        },
        tick() {
            // time left until midnight in Panama, as "11h 48m 03s"
            var now = new Date();
            var panama = new Date(now.getTime() - 5 * 3600 * 1000);
            var left = 86400 - (panama.getUTCHours() * 3600 + panama.getUTCMinutes() * 60 + panama.getUTCSeconds());
            var h = Math.floor(left / 3600), m = Math.floor(left % 3600 / 60), sec = left % 60;
            this.countdown = h + "h " + (m < 10 ? "0" : "") + m + "m " + (sec < 10 ? "0" : "") + sec + "s";
        },
        keyDown(event) {
            if (event.key === "Escape") {
                this.showStatsModal = false;
                this.showAboutModal = false;
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
            var win_percentage = n_wins / (n_wins + n_losses) * 100;

            return {
                "n_wins": n_wins,
                "n_losses": n_losses,
                "n_games": n_games,
                "win_percentage": win_percentage,
                "longest_streak": longest_streak,
                "current_streak": current_streak,
            };
        },
        calculateTotalStats() {
            // calculates stats for all languages

            var total_games = 0; // total number of games played
            var languages_won = [];  // list of languages that have been won
            var total_win_percentage = 0; // percentage of games won by all languages
            var longest_overall_streak = 0; // the longest streak of consecutive wins for all languages
            var current_overall_streak = 0; // the current streak of won games in a row on all languages
            var longest_language_streak = 0; // the longest streak for a single language
            var current_longest_language_streak = 0; // the longest language streak for one individual language
            var current_longest_language_streak_language = ""; // the language that has the longest language streak
            var n_victories = 0; // total number of victories
            var n_losses = 0; // total number of losses

            // only Spanish and English count (saved results of removed languages are ignored)
            var language_keys = Object.keys(this.game_results).filter(function (code) {
                return code === "es" || code === "en";
            });

            // order all games by date and calculate overall streaks
            var all_results = [];
            for (var i = 0; i < language_keys.length; i++) {
                var language_code = language_keys[i];
                var language_results = this.game_results[language_code];
                for (let j = 0; j < language_results.length; j++) {
                    all_results.push(language_results[j]);
                }
            }
            all_results.sort(function(a, b) {
                var dateA = new Date(a.date);
                var dateB = new Date(b.date);
                if (dateA > dateB) {
                    return 1;
                } else if (dateA < dateB) {
                    return -1;
                } else {
                    return 0;
                }
            });

            for (let i = 0; i < all_results.length; i++) {
                var result = all_results[i];
                if (result.won) {
                    n_victories++;
                    current_overall_streak++;
                    if (current_overall_streak > longest_overall_streak) {
                        longest_overall_streak = current_overall_streak;
                    }
                } else {
                    n_losses++;
                    current_overall_streak = 0;
                }
            }

            total_games = n_victories + n_losses;
            total_win_percentage = n_victories / (total_games) * 100;

            // calculate stats for each language
            for (var i = 0; i < language_keys.length; i++) {
                var language_code = language_keys[i];
                var language_stats = this.calculateStats(language_code);
                if (language_stats.n_wins > 0) {
                    languages_won.push(language_code);
                }
                if (language_stats.longest_streak > longest_language_streak) {
                    longest_language_streak = language_stats.longest_streak;
                }
                if (language_stats.current_streak > current_longest_language_streak) {
                    current_longest_language_streak = language_stats.current_streak;
                    current_longest_language_streak_language = language_code;
                }
            }

            return {
                "total_games": total_games,
                "languages_won": languages_won,
                "total_win_percentage": total_win_percentage,
                "longest_overall_streak": longest_overall_streak,
                "current_overall_streak": current_overall_streak,
                "longest_language_streak": longest_language_streak,
                "current_longest_language_streak": current_longest_language_streak,
                "current_longest_language_streak_language": current_longest_language_streak_language,
                "n_victories": n_victories,
                "n_losses": n_losses,
            };
        }
    },
});

app.mount('#app');