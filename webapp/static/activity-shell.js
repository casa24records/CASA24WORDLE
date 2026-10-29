// Casa 24 Wordle inside Discord: the Activity "shell" (templates/activity.html).
// Discord loads this page ONCE per launch (URL Mapping "/" with frame_id,
// instance_id and platform). It is the only page that talks to the Discord SDK:
//
//   ready() -> authorize(identify, prompt none) -> POST /api/activity/token
//   -> authenticate() -> session in memory (never in storage)
//
// The game runs in a same-origin <iframe> (/lb/<lang>?embed=1, without Discord's
// params), loading in parallel with the login; it waits for C24Activity.ready.
// The game page never loads the SDK: discord-activity.js there uses
// window.parent.C24Activity (this file) for the session, fetch and re-login.
// Changing language swaps the iframe (location.replace); this page never
// navigates, so the handshake runs once per launch. (Discord's "nested
// frameworks" pattern. A second handshake after a navigation can't work: the
// SDK posts to document.referrer, which is then our own origin.)
// Messages between the two pages are plain objects (the SDK ignores those; it
// reads arrays as its own opcodes).
//
// Language: the first launch shows a picker (10 languages); the choice is kept
// in localStorage "c24_activity_lang" (when storage works; else asked once per
// launch). The game's header button "ES ▾" asks for another one with
// postMessage({type: "c24-lang", code}).
//
// Layout mode (PIP / grid) is subscribed here and passed to the game page
// (postMessage {type: "c24-layout", mode, platform}); portrait lock is set here. Discord's
// safe-area variables exist only on this document: the iframe sits inside them
// (style.css .c24-shell padding), with the game's background around it.
//
// Never console.* anything secret: the SDK forwards the console to Discord.

import { DiscordSDK, Common } from "./vendor/discord-embedded-app-sdk-2.5.0/index.mjs";

const READY_MS = 10000;            // handshake with the Discord client
const AUTHORIZE_MS = 5 * 60000;    // the player may be reading Discord's permission window
const TOKEN_MS = 15000;            // our server <-> Discord token exchange
const AUTHENTICATE_MS = 10000;
const LANG_KEY = "c24_activity_lang";
const LOCALE_MS = 3000;            // optional: Discord's language, to suggest one in the picker

function readJson(id) {
    try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return null; }
}

const cfg = readJson("c24-shell") || {};
const LANGS = Array.isArray(cfg.langs) ? cfg.langs : [];
const overlay = document.getElementById("c24-activity-overlay");
const picker = document.getElementById("c24-picker");
const frame = document.getElementById("c24-game");
// Discord's launch query says desktop (Web/Desktop app) or mobile (phones, tablets).
// The game page gets it with the layout message: desktop never uses the
// side-by-side landscape layout and shows the live sidebar from 860px (style.css).
const PLATFORM = new URLSearchParams(window.location.search).get("platform") === "mobile" ? "mobile" : "desktop";
document.documentElement.classList.add("c24-plat-" + PLATFORM);

let sdk = null;
let handshakeDone = false;
let session = null;
let busy = false;
let auth = "loading";        // loading | denied | error | ready
let everReady = false;
let reloadGame = false;      // a re-login failed: reload the game once it works again
let lang = null;             // language of the game in the iframe (null: picker)
let frameLoaded = false;
let layoutMode = 0;
let resolveReady;
const ready = new Promise((resolve) => { resolveReady = resolve; });

class Timeout extends Error {}

function withTimeout(promise, ms) {
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Timeout("timeout")), ms);
        Promise.resolve(promise).then(
            (value) => { clearTimeout(timer); resolve(value); },
            (error) => { clearTimeout(timer); reject(error); });
    });
}

function langInfo(code) {
    for (const l of LANGS) { if (l.code === code) { return l; } }
    return null;
}

// ---------- what is on screen ----------

function render() {
    // overlay: refused/error > picker > "Conectando…" > "Cargando juego…" > the game
    let state = "ready";
    let step = "connect";
    if (auth === "denied" || auth === "error") {
        state = auth;
    } else if (lang === null) {
        state = "ready";  // the language picker (the login goes on behind it)
    } else if (auth !== "ready") {
        state = "loading";
    } else if (!frameLoaded) {
        state = "loading";
        step = "game";
    }
    const was = overlay ? overlay.getAttribute("data-state") : null;
    if (overlay) {
        overlay.setAttribute("data-state", state);
        overlay.setAttribute("data-step", step);
    }
    document.documentElement.setAttribute("data-activity", auth);
    // the overlay just went away over the game: the keyboard goes to the board
    if (state === "ready" && was !== "ready" && gameShown() && document.hasFocus()) { focusGame(); }
}

function setAuth(state) {
    auth = state;
    render();
}

// ---------- language ----------

function savedLang() {
    try {
        const code = localStorage.getItem(LANG_KEY);
        return langInfo(code) ? code : null;
    } catch (e) { return null; }
}

function saveLang(code) {
    try { localStorage.setItem(LANG_KEY, code); } catch (e) { /* storage blocked: asked again next launch */ }
}

function gameUrl(code) {
    // no Discord params in the iframe: only the shell is "the Activity" to the SDK
    return "/lb/" + encodeURIComponent(code) + "?embed=1";
}

function openGame(code) {
    const info = langInfo(code);
    if (!info || !frame) { return; }
    lang = code;
    saveLang(code);
    if (picker) { picker.hidden = true; }
    const msg = overlay && overlay.querySelector("[data-loading-game]");
    if (msg) {
        msg.textContent = info.loading || "…";
        msg.setAttribute("lang", code);
        msg.setAttribute("dir", info.rtl ? "rtl" : "ltr");
    }
    frameLoaded = false;
    frame.hidden = false;
    const url = gameUrl(code);
    if (!frame.getAttribute("src")) {
        frame.src = url;
    } else {
        // replace(): no history entry, so "back" never returns to the old language
        try { frame.contentWindow.location.replace(url); } catch (e) { frame.src = url; }
    }
    render();
}

function showPicker() {
    lang = null;
    if (frame) { frame.hidden = true; }
    if (picker) { picker.hidden = false; }
    render();
}

if (picker) {
    picker.addEventListener("click", (e) => {
        const btn = e.target.closest ? e.target.closest("[data-pick-lang]") : null;
        if (btn) { openGame(btn.getAttribute("data-pick-lang")); }
    });
}

if (frame) {
    frame.addEventListener("load", () => {
        if (!frame.getAttribute("src")) { return; }  // the empty frame before the first game
        frameLoaded = true;
        sendLayout();
        render();
        // the keyboard types into the board (Tab/Esc are never captured here)
        focusGame();
    });
}

// ---------- the keyboard: always the game's ----------
// Keys pressed while focus is on this page (a click on the overlay, the picker or the
// safe-area margin around the iframe) would never reach the game's keydown listener
// (game.js listens on the iframe's window): pass them on and move focus into the game.

function gameShown() {
    return !!(frame && !frame.hidden && lang !== null && frameLoaded
        && overlay && overlay.getAttribute("data-state") === "ready");
}

function gameWindow() {
    try {
        const w = frame && frame.contentWindow;
        return w && w.document && w.document.body ? w : null;
    } catch (e) { return null; }
}

function focusGame() {
    const w = gameWindow();
    if (w) { try { w.focus(); } catch (e) { } }
}

document.addEventListener("keydown", (e) => {
    if (e.defaultPrevented || e.key === "Tab" || !gameShown()) { return; }
    const w = gameWindow();
    if (!w) { return; }
    let copy;
    try {
        copy = new w.KeyboardEvent("keydown", {
            key: e.key, code: e.code, location: e.location, repeat: e.repeat,
            isComposing: e.isComposing, ctrlKey: e.ctrlKey, shiftKey: e.shiftKey,
            altKey: e.altKey, metaKey: e.metaKey,
            modifierAltGraph: !!(e.getModifierState && e.getModifierState("AltGraph")),
            bubbles: true, cancelable: true,
        });
    } catch (err) { return; }
    w.document.body.dispatchEvent(copy);
    if (copy.defaultPrevented) { e.preventDefault(); }
    focusGame();  // the next keys go straight to the game
});

// a click on this page outside the game (e.g. the safe-area margin): back to the board
document.addEventListener("pointerdown", (e) => {
    if (gameShown() && e.target && !(e.target.closest && e.target.closest("button, a"))) {
        setTimeout(focusGame, 0);
    }
});

// ---------- messages from the game page (same origin only) ----------

window.addEventListener("message", (e) => {
    if (e.origin !== window.location.origin || !frame || e.source !== frame.contentWindow) { return; }
    const data = e.data || {};
    if (data.type === "c24-lang" && typeof data.code === "string" && langInfo(data.code)) {
        if (data.code !== lang) { openGame(data.code); }
    } else if (data.type === "c24-layout-request") {
        sendLayout();
    } else if (data.type === "c24-log" && typeof data.message === "string") {
        // the game's errors, into Discord's debug logs (the SDK forwards this console)
        console.warn("Casa 24 game: " + data.message.slice(0, 300));
    }
});

// the theme chosen in the game's settings (same localStorage): follow it here too
window.addEventListener("storage", (e) => {
    if (e.key === "casa24_theme" && window.casa24SetTheme) {
        const v = e.newValue;
        if (v === "light" || v === "dark") { document.documentElement.setAttribute("data-theme", v); }
        else { document.documentElement.removeAttribute("data-theme"); }
    }
});

// ---------- layout mode (passed to the game page) ----------

function layoutInfo() {
    return { type: "c24-layout", mode: layoutMode, platform: PLATFORM };
}

function sendLayout() {
    if (!frame || !frame.contentWindow || !frame.getAttribute("src")) { return; }
    try { frame.contentWindow.postMessage(layoutInfo(), window.location.origin); } catch (e) { }
}

function onLayout(event) {
    // 0 focused (normal), 1 picture-in-picture, 2 grid: compact board only
    const mode = event && Number.isInteger(event.layout_mode) ? event.layout_mode : 0;
    layoutMode = mode;
    document.documentElement.classList.toggle("c24-pip", mode === 1 || mode === 2);
    document.documentElement.setAttribute("data-layout-mode", String(mode));
    sendLayout();
}

// ---------- login ----------

async function login() {
    // authorize -> our server -> authenticate. true when the session is ready.
    let code = null;
    try {
        const result = await withTimeout(sdk.commands.authorize({
            client_id: cfg.client_id,
            response_type: "code",
            state: "",
            prompt: "none",
            scope: ["identify"],
        }), AUTHORIZE_MS);
        code = result && typeof result.code === "string" ? result.code : null;
    } catch (e) {
        setAuth(e instanceof Timeout ? "error" : "denied");
        return false;
    }
    if (!code) {
        setAuth("denied");
        return false;
    }
    let data = null;
    try {
        const post = () => withTimeout(fetch("/api/activity/token", {
            method: "POST",
            credentials: "omit",
            cache: "no-store",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ code: code }),
        }), TOKEN_MS);
        let response = await post();
        if (response.status === 429) {
            // busy: wait what the server asks (at most 5 s) and try once more
            const wait = Math.min(5, Math.max(1, parseInt(response.headers.get("Retry-After") || "2", 10) || 2));
            await new Promise((resolve) => setTimeout(resolve, wait * 1000));
            response = await post();
        }
        data = response.ok ? await response.json() : null;
    } catch (e) {
        data = null;
    }
    code = null;
    if (!data || typeof data.access_token !== "string" || typeof data.session !== "string") {
        setAuth("error");
        return false;
    }
    try {
        await withTimeout(sdk.commands.authenticate({ access_token: data.access_token }), AUTHENTICATE_MS);
    } catch (e) {
        data = null;
        setAuth("error");
        return false;
    }
    session = data.session;
    data = null;  // the access token is not kept anywhere
    return true;
}

function extras() {
    // optional commands: an older Discord client may not know them (4002 / 4004)
    try {
        sdk.subscribe("ACTIVITY_LAYOUT_MODE_UPDATE", onLayout).catch(() => { });
    } catch (e) { }
    try {
        if (sdk.platform === "mobile") {
            const PORTRAIT = (Common && Common.OrientationLockStateTypeObject
                && Common.OrientationLockStateTypeObject.PORTRAIT) || 2;
            sdk.commands.setOrientationLockState({ lock_state: PORTRAIT }).catch(() => { });
        }
    } catch (e) { }
}

function suggestLanguage() {
    // first launch: mark Discord's own language in the picker (optional command)
    if (lang !== null || !picker) { return; }
    let asked;
    try { asked = withTimeout(sdk.commands.userSettingsGetLocale(), LOCALE_MS); } catch (e) { return; }
    Promise.resolve(asked).then((result) => {
        const locale = result && typeof result.locale === "string" ? result.locale.toLowerCase() : "";
        const code = locale.split(/[-_]/)[0];
        if (!code || lang !== null || !langInfo(code)) { return; }
        const btn = picker.querySelector("[data-pick-lang='" + code + "']");
        if (!btn) { return; }
        btn.classList.add("is-suggested");
        const active = document.activeElement;
        if (!active || active === document.body || (active.hasAttribute && active.hasAttribute("data-pick-lang"))) {
            try { btn.focus({ preventScroll: true }); } catch (e) { }
        }
    }).catch(() => { });
}

function loggedIn() {
    setAuth("ready");
    if (!everReady) {
        everReady = true;
        extras();
        resolveReady();
        suggestLanguage();
    } else if (reloadGame && lang !== null) {
        reloadGame = false;
        openGame(lang);  // the game gave up while logged out: start it again
    }
}

async function connect() {
    if (busy) { return; }
    busy = true;
    setAuth("loading");
    try {
        if (!sdk) {
            sdk = new DiscordSDK(cfg.client_id);
        }
        if (!handshakeDone) {
            await withTimeout(sdk.ready(), READY_MS);
            handshakeDone = true;
        }
        if (await login()) {
            loggedIn();
        }
    } catch (e) {
        console.warn("Casa 24: could not connect to Discord");
        setAuth("error");
    } finally {
        busy = false;
    }
}

let reauthing = null;

window.C24Activity = {
    get session() { return session; },
    ready: ready,
    get lang() { return lang; },
    get layout() { return layoutInfo(); },
    fetch(url, opts) {
        // fetch() with the session header; waits for the login
        return ready.then(() => {
            const options = Object.assign({}, opts || {});
            const headers = new Headers(options.headers || {});
            headers.set("Authorization", "Bearer " + session);
            options.headers = headers;
            options.credentials = "omit";  // our cookies don't travel in Discord's iframe anyway
            return fetch(url, options);
        });
    },
    reauth() {
        // the server refused the session (401): authorize again, silently if possible
        if (!reauthing) {
            reauthing = (async () => {
                if (!sdk || !handshakeDone) { return false; }
                const ok = await login();
                if (ok) { setAuth("ready"); } else { reloadGame = true; }
                return ok;
            })().finally(() => { setTimeout(() => { reauthing = null; }, 0); });
        }
        return reauthing;
    },
    setLang(code) { if (langInfo(code) && code !== lang) { openGame(code); } },
};

if (overlay) {
    const retry = overlay.querySelector("[data-activity-retry]");
    if (retry) {
        retry.addEventListener("click", () => {
            if (sdk && !handshakeDone) {
                // ready() itself failed: only a reload (same URL, same referrer) can start
                // the SDK again; this page never navigates anywhere else
                window.location.reload();
                return;
            }
            connect();  // authorize / token / authenticate again on the same SDK
        });
    }
}

// start: connect to Discord and, at the same time, load the game (or show the picker)
const first = langInfo(cfg.lang) ? cfg.lang : savedLang();
connect();
if (first) { openGame(first); } else { showPicker(); }
