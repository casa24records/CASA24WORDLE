// Casa 24 Wordle inside Discord: the game page's side (an ES module that game.html
// loads ONLY inside the Activity, as /lb/<lang>?embed=1; the web never loads it).
// The game runs in the Activity shell's same-origin <iframe> (templates/
// activity.html + static/activity-shell.js). This file does NOT load the Discord
// SDK (and the iframe URL has no Discord params): the shell connected once for
// the whole launch, and this page borrows its session via window.parent.C24Activity.
//
// It exposes window.C24Activity for game.js = {session, ready, fetch, reauth,
// log, url, setLang, invite, onParticipants}. Links with data-c24-external (Terms / Privacy) and links to
// other sites open through the shell's openExternal (SDK openExternalLink); the
// Settings "Delete my data" form posts /api/me/delete with the session, then the
// shell shows "data deleted" (dataDeleted()). Nothing here navigates the shell.
//   - ready: the shell's login Promise;
//   - fetch(url, opts): this page's fetch with "Authorization: Bearer <session>";
//     a 401 asks the shell to log in again (silently), then retries ONCE;
//   - setLang(code): asks the shell for another language (postMessage "c24-lang");
//     the shell swaps this iframe, the Discord connection stays;
//   - invite(): asks the shell to open Discord's invite dialog (postMessage
//     "c24-invite"; the shell calls the SDK's openInviteDialog, no extra scope).
// Layout mode (PIP / grid) and platform (desktop / mobile) come from the shell
// (postMessage {type: "c24-layout"}) and become classes on <html> (c24-pip,
// c24-plat-desktop / c24-plat-mobile). Discord's safe areas are applied by the
// shell around this iframe. Messages are plain objects only (never arrays: the
// SDK in the shell reads arrays from our origin as its own opcodes).
//
// Never console.* anything secret: the SDK forwards the console to Discord.

const OUR_PARAMS = ["layout", "tab", "lang", "c24_root", "login", "deleted", "skip", "next"];  // = app.ACTIVITY_OWN_PARAMS

const overlay = document.getElementById("c24-activity-overlay");

function setState(state) {
    // loading | denied | error | ready (style.css shows the matching message)
    if (overlay) { overlay.setAttribute("data-state", state); }
    document.documentElement.setAttribute("data-activity", state);
}

function shell() {
    // the Activity shell around this page (same origin), or null
    try {
        if (window.parent && window.parent !== window && window.parent.C24Activity
            && window.parent.location.origin === window.location.origin) {
            return window.parent.C24Activity;
        }
    } catch (e) { }
    return null;
}

const host = shell();

// ---------- Discord's query on every same-site navigation (inside this iframe) ----------

function keptParams() {
    const out = [];
    new URLSearchParams(window.location.search).forEach((value, key) => {
        if (OUR_PARAMS.indexOf(key) < 0) { out.push([key, value]); }
    });
    return out;
}

function otherSite(href) {
    // an http(s) link to another site, else null
    let url;
    try { url = new URL(href, window.location.href); } catch (e) { return null; }
    if (url.protocol !== "https:" && url.protocol !== "http:") { return null; }
    return url.origin !== window.location.origin ? url.href : null;
}

function withDiscordQuery(href) {
    // same-site URL plus Discord's launch params it lacks (and embed=1); other sites untouched
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
    // Terms / Privacy (data-c24-external = the public https address) and links to other
    // sites open in the player's browser through Discord (SDK openExternalLink in the shell)
    const external = link.getAttribute("data-c24-external") || otherSite(href);
    if (external && host && typeof host.openExternal === "function") {
        e.preventDefault();
        host.openExternal(external);
        return;
    }
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

// ---------- layout mode, from the shell ----------

function applyLayout(info) {
    if (!info || typeof info !== "object") { return; }
    const mode = Number.isInteger(info.mode) ? info.mode : 0;
    document.documentElement.classList.toggle("c24-pip", mode === 1 || mode === 2);
    document.documentElement.setAttribute("data-layout-mode", String(mode));
    // c24-plat-desktop | c24-plat-mobile (style.css: the Activity's desktop layout)
    const platform = info.platform === "mobile" ? "mobile" : "desktop";
    document.documentElement.classList.toggle("c24-plat-mobile", platform === "mobile");
    document.documentElement.classList.toggle("c24-plat-desktop", platform === "desktop");
}

// ---------- who is in this Activity, from the shell (live view) ----------

const PARTICIPANT_ID_RE = /^\d{1,20}$/;
const AVATAR_HASH_RE = /^(a_)?[0-9a-f]{32}$/;
let participants = null;            // null until the shell has said anything
const participantListeners = [];

function applyParticipants(list) {
    if (!Array.isArray(list)) { return; }
    participants = list.filter((p) => p && typeof p.id === "string" && PARTICIPANT_ID_RE.test(p.id)
        && typeof p.username === "string" && p.username).slice(0, 50).map((p) => ({
        id: p.id,
        username: p.username.slice(0, 32),
        avatar: typeof p.avatar === "string" && AVATAR_HASH_RE.test(p.avatar) ? p.avatar : null,
    }));
    for (const cb of participantListeners) {
        try { cb(participants.slice()); } catch (e) { }
    }
}

window.addEventListener("message", (e) => {
    if (e.origin !== window.location.origin || e.source !== window.parent) { return; }
    const data = e.data || {};
    if (data.type === "c24-layout") { applyLayout(data); }
    else if (data.type === "c24-participants") { applyParticipants(data.participants); }
});

// ---------- the session, borrowed from the shell ----------

let ready;
if (host) {
    try { applyLayout(host.layout); } catch (e) { }
    ready = Promise.resolve(host.ready);
} else {
    // opened on its own (not in the shell): no Discord connection here
    ready = new Promise(() => { });
    setState("error");
    const retry = overlay && overlay.querySelector("[data-activity-retry]");
    if (retry) { retry.addEventListener("click", () => { window.location.reload(); }); }
}

// this page's errors, into Discord's debug logs through the shell (never secrets:
// only the message text, cut short)
function report(message) {
    if (!host || !window.parent) { return; }
    try {
        window.parent.postMessage({ type: "c24-log", message: String(message || "error").slice(0, 300) },
            window.location.origin);
    } catch (e) { }
}
window.addEventListener("error", (e) => { report(e && e.message); });
window.addEventListener("unhandledrejection", (e) => {
    report(e && e.reason && e.reason.message ? e.reason.message : "unhandled rejection");
});

let reauthFailed = false;  // the shell could not log in again: don't ask Discord twice per page

function reauth() {
    if (!host || reauthFailed) { return Promise.resolve(false); }
    return Promise.resolve(host.reauth()).then((ok) => {
        if (!ok) { reauthFailed = true; }  // the shell shows "Try again" and reloads this page after it
        return !!ok;
    }, () => { reauthFailed = true; return false; });
}

function withSession(opts) {
    const options = Object.assign({}, opts || {});
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", "Bearer " + (host ? host.session : ""));
    options.headers = headers;
    options.credentials = "omit";  // our cookies don't travel in Discord's iframe anyway
    return options;
}

window.C24Activity = {
    get session() { return host ? host.session : null; },
    ready: ready,
    fetch(url, opts) {
        // this page's fetch with the shell's session; a 401: log in again, retry once
        return ready.then(() => fetch(url, withSession(opts))).then((response) => {
            if (response.status !== 401 || !host) { return response; }
            return reauth().then((ok) => (ok ? fetch(url, withSession(opts)) : response));
        });
    },
    reauth: reauth,
    log: report,  // a short message into Discord's debug console (never secrets)
    url(path) { return withDiscordQuery(path) || path; },
    setLang(code) {
        // the shell swaps this iframe to the other language (no new Discord login)
        if (host && window.parent) {
            window.parent.postMessage({ type: "c24-lang", code: String(code) }, window.location.origin);
        }
    },
    onParticipants(cb) {
        // live view: cb([{id, username, avatar}]) now (if known) and on every join / leave
        if (typeof cb !== "function") { return; }
        participantListeners.push(cb);
        if (participants) { try { cb(participants.slice()); } catch (e) { } }
    },
    invite() {
        // Discord's "invite friends to this Activity" window, opened by the shell
        if (host && window.parent) {
            window.parent.postMessage({ type: "c24-invite" }, window.location.origin);
        }
    },
};

// ---------- Settings: "Delete my data" (discord.js asks first, then fires "c24-confirmed") ----------

document.addEventListener("c24-confirmed", (e) => {
    const form = e.target;
    if (!form || !form.hasAttribute || !form.hasAttribute("data-activity-delete")) { return; }
    const status = form.querySelector("[data-activity-delete-status]");
    const button = form.querySelector("button");
    if (button) { button.disabled = true; }
    if (status) { status.textContent = "…"; }
    window.C24Activity.fetch("/api/me/delete", {
        method: "POST", cache: "no-store", headers: { "Accept": "application/json" },
    }).then((response) => {
        if (!response.ok) { throw new Error("delete " + response.status); }
        if (status) { status.textContent = ""; }
        if (host && typeof host.dataDeleted === "function") { host.dataDeleted(); }
    }).catch((err) => {
        report("delete failed: " + (err && err.message ? err.message : "error"));
        if (status) { status.textContent = form.getAttribute("data-error") || "Error"; }
        if (button) { button.disabled = false; }
    });
});

ready.then(() => { setState("ready"); });
window.dispatchEvent(new Event("c24activity"));
