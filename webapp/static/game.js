// Casa 24 Wordle game page (Vue 3). Word lists, characters and config come
// from Jinja as globals in game.html.
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
            right_to_left: config.right_to_left == "true",
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

            // have to split it in two because of right to left text (arabic, hebrew, etc) and this was easiest way to do it
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

            // constantly updating time until next day
            time_until_next_day() {
                return this.get_time_until_next_day();
            },

            // true while the last guess is flipping, typing is ignored meanwhile
            revealing: false,
            revealing_row: -1,
            pending_key_classes: null,  // keyboard colors waiting for the flip to end

            emoji_board: "⬜⬜⬜⬜⬜\n",
            attempts: "0",

            stats: {},
        }
    },
    computed: {
        // computed properties
        key_classes: {
            get() {
                let keys = {};
                for (let i = 0; i < characters.length; i++) {
                    keys[characters[i]] = "";
                }
                keys["⇨"] = "";
                keys["⌫"] = "";
                return keys;
            },
            set(new_key_classes) {
                // this.key_classes = new_key_classes; // this doesn't work, recursive                
                // set key classes without recursion
                for (let i = 0; i < characters.length; i++) {
                    this.key_classes[characters[i]] = new_key_classes[characters[i]];
                }
            }
        },        
        
        acceptable_characters() {
            return characters.join("");
        },
    },
    created() {
        // remember the last language played, for the start screen
        try { localStorage.setItem("casa24_lang", this.config.language_code); } catch (e) { }
        // listen for any keypresses
        window.addEventListener('keydown', this.keyDown);

        // load results
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

        //calculate stats
        this.stats = this.calculateStats(this.config.language_code);

        this.time_until_next_day = this.get_time_until_next_day();
    },
    mounted() {
        // print time until next day every 5 seconds
        setInterval(() => {
            this.time_until_next_day = this.get_time_until_next_day();
        }, 1000);
        this.loadFromLocalStorage();
        this.showTiles();

        if (this.game_over) {
            this.show_stats_modal = true;
        }
    },
    beforeUpdate() {
        if (this.show_stats_modal) {
            this.emoji_board = this.getEmojiBoard();
        }
    },
    updated() {
        if (this.show_stats_modal) {
            // share text, e.g. "Casa 24 Wordle ES #123 3/6" + link + emoji grid
            var text_to_share = "Casa 24 Wordle " + this.config.language_code.toUpperCase() + " #" + this.todays_idx + " " + this.attempts + "/6" + "\n" + window.location.origin + "/" + this.config.language_code + "\n" + "\n" + this.emoji_board;
            document.querySelector('#copy_button').addEventListener('click', async event => {
                if (navigator.share) {
                    try {
                        await navigator.share({
                            text: text_to_share,
                        });
                    } catch (error) {
                        console.log('Error sharing: ', error);
                    }
                } else if (navigator.clipboard) {
                    try {
                        await navigator.clipboard.writeText(text_to_share);
                        this.showNotification(this.text("notification-copied", "Copied to clipboard"));
                    } catch (error) {
                        console.log('Error copying: ', error);
                    }
                } else {
                    console.log("No navigator.share or navigator.clipboard");
                    alert(this.text("notification-share-unsupported", "Sorry, your browser doesn't support sharing. Please copy the text and share it yourself."));
                }
            });
        }
    },
    methods: {
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
            this.tile_classes[this.active_row][this.active_cell] = "text-2xl tiny:text-4xl uppercase font-bold select-none border-2 border-neutral-500 pop";
            this.active_cell = Math.min(this.active_cell + 1, 5);
            if (this.active_cell == 5) {
                this.full_word_inputted = true;
            }
        },

        foldAccents(text) {
            // "canción" -> "cancion", but ñ stays ñ (it is its own letter)
            return text.split("").map(function (c) {
                return c === "ñ" ? c : c.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
            }).join("");
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
            var folded = this.foldAccents(word);
            if (folded === this.foldAccents(this.todays_word)) {
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
                        var key = this.foldAccents(lists[l][i]);
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
            // NOTE: if a character appears only once in the final word, but multiple times in submitted word
            // then we want to only color one. The hierarchy is correct first, then the semi-correct ones by position.
            // Letters are compared exactly: typing may skip accents (resolveAccents fixes the
            // spelling first), but a plain "a" never counts for an "á" in today's word.
            var todays_word = this.todays_word;
            const base_class = "text-2xl tiny:text-4xl uppercase font-bold select-none text-white";
            var charcounts = {};

            // count characters
            for (let i = 0; i < todays_word.length; i++) {
                var character = todays_word[i];
                if (charcounts[character] == undefined) {
                    charcounts[character] = 1;
                } else {
                    charcounts[character] += 1;
                }
            }

            // color correct characters
            for (let i = 0; i < this.tiles[this.active_row].length; i++) {
                var character = this.tiles[this.active_row][i];
                if (character == todays_word[i]) {
                    this.tile_classes[this.active_row][i] = "correct" + " " + base_class;
                    this.key_classes[character] = "correct"
                    charcounts[character] -= 1;
                }
            }
            for (let i = 0; i < this.tiles[this.active_row].length; i++) {
                var character = this.tiles[this.active_row][i];
                if (todays_word.indexOf(character) != -1 && charcounts[character] > 0 && this.tile_classes[this.active_row][i].indexOf("correct") == -1) {
                    // if the tile is not already colored
                    this.tile_classes[this.active_row][i] = "semicorrect" + " " + base_class;
                    if (this.key_classes[character] != "correct") {
                        this.key_classes[character] = "semicorrect"
                    }
                    charcounts[character] -= 1;
                } else if (this.tile_classes[this.active_row][i].indexOf("correct") == -1) {
                    this.tile_classes[this.active_row][i] = "incorrect" + " " + base_class;
                    if (this.key_classes[character] != "correct" && this.key_classes[character] != "semicorrect") {
                        this.key_classes[character] = "incorrect"
                    }
                }
            }
        },
        keyClick(key) {
            // emit event that key was pressed
            var event = new Event('keydown');
            event.key = key;
            this.keyDown(event);
        },
        keyDown(event) {
            key = event.key;
            if (key === "Escape") { // QoL
                this.showHelpModal = false;
                this.show_stats_modal = false;
                this.show_options_modal = false;
            }

            if (this.game_over || this.revealing) {
                return;
            }
            // console.log('keyDown', this.active_cell, this.active_row, event.key);
            if (key === "Enter" || key === "⇨") {
                if (!this.full_word_inputted) {
                    this.showNotification(this.text("notification-partial-word", "Please enter a full word"));
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
                if (word_is_valid) {
                    var row = this.active_row;
                    // color the keyboard only after the tiles finish flipping
                    var keys_before = Object.assign({}, this.key_classes);
                    this.updateColors();
                    var keys_after = Object.assign({}, this.key_classes);
                    Object.assign(this.key_classes, keys_before);
                    // saved right away, so a reload mid-flip keeps the keyboard colors
                    this.pending_key_classes = keys_after;
                    this.active_row++;
                    this.active_cell = 0;
                    this.full_word_inputted = false;

                    var won = word === this.todays_word;
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
                    } else if (this.active_row == 6) {
                        this.gameLost(reveal_ms);
                    }
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
                    if (this.acceptable_characters.indexOf(key) >= 0) {
                        this.addChar(key);
                    }
                }
            }
            this.showTiles();
            this.saveToLocalStorage();
        },
        showTiles() {
            // if left to right, then reverse the tiles visuals. else copy normally.
            // The row that is flipping keeps its own classes (revealRow handles it).
            if (!this.right_to_left) {
                for (let i = 0; i < this.tiles.length; i++) {
                    this.tiles_visual[i] = this.tiles[i].map(x => x)
                    if (i !== this.revealing_row) {
                        this.tile_classes_visual[i] = this.tile_classes[i].map(x => x)
                    }
                }
            } else {
                for (let i = 0; i < this.tiles.length; i++) {
                    this.tiles_visual[i] = this.tiles[i].map(x => x).reverse();
                    if (i !== this.revealing_row) {
                        this.tile_classes_visual[i] = this.tile_classes[i].map(x => x).reverse();
                    }
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
            const typed = "text-2xl tiny:text-4xl uppercase font-bold select-none border-2 border-neutral-500";
            const vis = (i) => this.right_to_left ? final.length - 1 - i : i;
            const classes = this.tile_classes_visual[row];
            this.revealing = true;
            this.revealing_row = row;
            for (let i = 0; i < final.length; i++) {
                classes[vis(i)] = typed;
                setTimeout(() => { classes[vis(i)] = typed + " flip"; }, i * STAGGER);
                setTimeout(() => { classes[vis(i)] = final[i] + " flip"; }, i * STAGGER + FLIP / 2);
                setTimeout(() => { classes[vis(i)] = final[i]; }, i * STAGGER + FLIP);
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
                // bounce-dN delays follow reading order, so right-to-left rows bounce from the right
                var order = this.right_to_left ? classes.length - 1 - i : i;
                classes[i] = classes[i] + " bounce bounce-d" + order;
            }
            setTimeout(() => { this.showTiles(); }, 1500);
        },
        gameWon(delay = 0) {
            // the game ends now (and is saved); the word and stats show after the tiles flip
            this.game_over = true;
            this.game_won = true;
            this.emoji_board = this.getEmojiBoard();
            setTimeout(() => {
                this.showNotification(this.todays_word.toUpperCase(), 12);
            }, delay);
            setTimeout(() => {
                this.show_stats_modal = true;
            }, delay + (delay > 0 ? 1600 : 400));

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
            this.attempts = "X";
            setTimeout(() => {
                this.show_stats_modal = true;
            }, delay + 400);
            // save a loss to local storage game results
            this.game_results[this.config.language_code].push({ "won": false, "attempts": this.attempts, "date": new Date() });
            localStorage.setItem("game_results", JSON.stringify(this.game_results));

            // refresh stats
            this.stats = this.calculateStats(this.config.language_code);

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
            // saves tiles, tile_classes, active_row and active_cell to local storage with key: page_name
            var url = window.location.href;
            var page_name = url.substring(url.lastIndexOf('/') + 1);
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
            };
            localStorage.setItem(page_name, JSON.stringify(data));
        },
        loadFromLocalStorage() {
            // if local storage has data and the daily word is the same as the todays word, then load data
            var url = window.location.href;
            var page_name = url.substring(url.lastIndexOf('/') + 1);
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
