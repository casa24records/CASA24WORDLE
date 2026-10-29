// Casa 24 Wordle inside Discord (Discord Activity). An ES module that game.html
// loads ONLY when the URL has Discord's launch params (app.py is_activity()); the
// web never loads it or the SDK.
//
// Automatic login, no button: ready() -> authorize(identify) -> POST
// /api/activity/token -> authenticate(). The access token is used once for
// authenticate() and dropped; the server's signed `session` stays in memory only
// (never in storage) and goes with every request as `Authorization: Bearer`.
// The server stays the single source of truth: game.js waits for
// window.C24Activity.ready, then reads /api/state and posts /api/guess through
// C24Activity.fetch().
//
// The only button is "Try again", shown after the player refuses Discord's
// permission window or something times out (the SDK itself has no timeouts).
// Also: layout mode (picture-in-picture / grid -> compact board), portrait lock on
// phones, and every same-site link or GET form keeps Discord's query (the SDK
// reads frame_id / instance_id / platform on every page load).
//
// Never console.* anything secret: the SDK forwards the console to Discord.

import { DiscordSDK, Common } from "./vendor/discord-embedded-app-sdk-2.5.0/index.mjs";

const READY_MS = 10000;            // handshake with the Discord client
const AUTHORIZE_MS = 5 * 60000;    // the player may be reading Discord's permission window
const TOKEN_MS = 15000;            // our server <-> Discord token exchange
const AUTHENTICATE_MS = 10000;
const OUR_PARAMS = ["layout", "tab", "lang", "c24_root", "login", "deleted", "skip", "next"];  // = app.ACTIVITY_OWN_PARAMS

function readJson(id) {
    try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return null; }
}

const cfg = readJson("c24-activity") || {};
const overlay = document.getElementById("c24-activity-overlay");

let sdk = null;
let handshakeDone = false;
let session = null;
let busy = false;
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

function setState(state) {
    // loading | denied | error | ready (style.css shows the matching message)
    if (overlay) { overlay.setAttribute("data-state", state); }
    document.documentElement.setAttribute("data-activity", state);
}

// ---------- Discord's query on every same-site navigation ----------

function keptParams() {
    const out = [];
    new URLSearchParams(window.location.search).forEach((value, key) => {
        if (OUR_PARAMS.indexOf(key) < 0) { out.push([key, value]); }
    });
    return out;
}

function withDiscordQuery(href) {
    // same-site URL plus Discord's launch params it lacks; other sites untouched
    let url;
    try { url = new URL(href, window.location.href); } catch (e) { return null; }
    if (url.origin !== window.location.origin) { return null; }
    for (const [key, value] of keptParams()) {
        if (!url.searchParams.has(key)) { url.searchParams.append(key, value); }
    }
    return url.pathname + url.search + url.hash;
}

document.addEventListener("click", (e) => {
    const link = e.target.closest ? e.target.closest("a[href]") : null;
    if (!link) { return; }
    const href = link.getAttribute("href");
    if (!href || href.charAt(0) === "#") { return; }
    const fixed = withDiscordQuery(href);
    if (fixed && fixed !== href) { link.setAttribute("href", fixed); }
}, true);

document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form || (form.method || "get").toLowerCase() !== "get") { return; }
    for (const [key, value] of keptParams()) {
        if (!form.querySelector("input[name='" + CSS.escape(key) + "']")) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = key;
            input.value = value;
            form.appendChild(input);
        }
    }
}, true);

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
        setState(e instanceof Timeout ? "error" : "denied");
        return false;
    }
    if (!code) {
        setState("denied");
        return false;
    }
    let data = null;
    try {
        const response = await withTimeout(fetch("/api/activity/token", {
            method: "POST",
            credentials: "omit",
            cache: "no-store",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ code: code }),
        }), TOKEN_MS);
        data = response.ok ? await response.json() : null;
    } catch (e) {
        data = null;
    }
    code = null;
    if (!data || typeof data.access_token !== "string" || typeof data.session !== "string") {
        setState("error");
        return false;
    }
    try {
        await withTimeout(sdk.commands.authenticate({ access_token: data.access_token }), AUTHENTICATE_MS);
    } catch (e) {
        data = null;
        setState("error");
        return false;
    }
    session = data.session;
    data = null;  // the access token is not kept anywhere
    return true;
}

function onLayout(event) {
    // 0 focused (normal), 1 picture-in-picture, 2 grid: compact board only
    const mode = event && Number.isInteger(event.layout_mode) ? event.layout_mode : 0;
    document.documentElement.classList.toggle("c24-pip", mode === 1 || mode === 2);
    document.documentElement.setAttribute("data-layout-mode", String(mode));
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

let started = false;

async function connect() {
    if (busy) { return; }
    busy = true;
    setState("loading");
    try {
        if (!sdk) {
            sdk = new DiscordSDK(cfg.client_id);
        }
        if (!handshakeDone) {
            await withTimeout(sdk.ready(), READY_MS);
            handshakeDone = true;
        }
        if (await login()) {
            setState("ready");
            if (!started) {
                started = true;
                extras();
            }
            resolveReady();
        }
    } catch (e) {
        console.warn("Casa 24: could not connect to Discord");
        setState("error");
    } finally {
        busy = false;
    }
}

let reauthing = null;

window.C24Activity = {
    get session() { return session; },
    ready: ready,
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
                if (ok) { setState("ready"); }
                return ok;
            })().finally(() => { setTimeout(() => { reauthing = null; }, 0); });
        }
        return reauthing;
    },
    url(path) { return withDiscordQuery(path) || path; },
};
window.dispatchEvent(new Event("c24activity"));

if (overlay) {
    const retry = overlay.querySelector("[data-activity-retry]");
    if (retry) { retry.addEventListener("click", () => { connect(); }); }
}

if (!window.C24_LEAVING) {
    connect();
}
