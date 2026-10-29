// Casa 24 Wordle: Discord pieces of every page (loaded in <head> by dc.script() in
// _discord.html, only when the leaderboard is on). Handles the #dc=<avatar hash>
// fragment left by the web login (kept in localStorage "c24_dc_avatar", this browser
// only) and fills every img[data-dc-avatar]; the header avatar menu; the privacy
// dialog; notices that close themselves; and the "Delete my data" confirmation
// (an in-page dialog, not the browser confirm box). No inline handlers anywhere: the
// Discord Activity's CSP blocks them. The logged-in player's ID comes from the
// JSON block #c24-dc-me right before this script.
(function () {
    var ME = null;
    try { ME = JSON.parse(document.getElementById("c24-dc-me").textContent); } catch (e) { }
    var KEY = "c24_dc_avatar", HASH = /^(a_)?[0-9a-f]{32}$/;
    function load() { try { return JSON.parse(localStorage.getItem(KEY)); } catch (e) { return null; } }
    function save(v) { try { if (v) { localStorage.setItem(KEY, JSON.stringify(v)); } else { localStorage.removeItem(KEY); } } catch (e) { } }
    // after the Discord login the server sends us to <page>#dc=<avatar hash>
    var m = /^#dc=([^&]*)$/.exec(window.location.hash);
    if (m) {
        var h = m[1];
        if (ME && HASH.test(h)) { save({ id: ME, hash: h }); }
        else if (ME && h === "") { save(null); }  // no picture on Discord: default avatar
        if (window.history.replaceState) { window.history.replaceState(null, "", window.location.pathname + window.location.search); }
    }
    function avatarUrl(id) {
        var s = load();
        if (s && s.id === id && HASH.test(s.hash || "")) {
            return "https://cdn.discordapp.com/avatars/" + id + "/" + s.hash + ".png?size=64";
        }
        return null;  // keep the picture the server rendered (saved avatar or Discord default)
    }
    window.c24DcAvatars = function () {
        var imgs = document.querySelectorAll("img[data-dc-avatar]");
        for (var k = 0; k < imgs.length; k++) {
            var url = avatarUrl(imgs[k].getAttribute("data-dc-id"));
            if (url && imgs[k].getAttribute("src") !== url) { imgs[k].setAttribute("src", url); }
        }
    };
    // deferred scripts (Vue apps) have mounted by now
    document.addEventListener("DOMContentLoaded", window.c24DcAvatars);
    function closeMenus(except) {
        var open = document.querySelectorAll("[data-dc-pop]:not([hidden])");
        for (var k = 0; k < open.length; k++) {
            if (open[k] === except) { continue; }
            open[k].hidden = true;
            var b = open[k].parentNode.querySelector("[data-dc-toggle]");
            if (b) { b.setAttribute("aria-expanded", "false"); }
        }
    }
    document.addEventListener("click", function (e) {
        var t = e.target.closest ? e.target.closest("[data-dc-toggle]") : null;
        if (t) {
            var pop = t.parentNode.querySelector("[data-dc-pop]");
            closeMenus(pop);
            pop.hidden = !pop.hidden;
            t.setAttribute("aria-expanded", pop.hidden ? "false" : "true");
            t.blur();
            return;
        }
        if (!(e.target.closest && e.target.closest("[data-dc-pop]"))) { closeMenus(null); }
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeMenus(null); } });
    document.addEventListener("click", function (e) {
        if (!e.target.closest) { return; }
        if (e.target.closest("[data-dc-privacy]")) {
            var d = document.getElementById("c24-privacy");
            closeMenus(null);
            if (d && d.showModal) { d.showModal(); } else if (d) { d.setAttribute("open", ""); }
            return;
        }
        var d2 = document.getElementById("c24-privacy");
        if (d2 && e.target === d2) { d2.close(); }  // tap on the backdrop
        var x = e.target.closest("[data-c24-toast-close]");
        if (x) { x.parentNode.remove(); }
    });
    // notices close themselves
    document.addEventListener("DOMContentLoaded", function () {
        var toasts = document.querySelectorAll("[data-c24-toast]");
        for (var k = 0; k < toasts.length; k++) {
            (function (el) { setTimeout(function () { el.classList.add("is-leaving"); setTimeout(function () { el.remove(); }, 300); }, 6000); })(toasts[k]);
        }
    });

    // In-page confirmation (not the browser confirm box: sandboxed iframes may not show it).
    // <form data-confirm="question" data-confirm-ok="Delete" data-confirm-cancel="Cancel">
    function confirmDialog(message, okLabel, cancelLabel, done) {
        var dialog = document.createElement("dialog");
        dialog.className = "c24-privacy c24-confirm";
        dialog.setAttribute("data-c24-confirm", "");
        var box = document.createElement("form");
        box.method = "dialog";
        box.className = "c24-privacy-box";
        var text = document.createElement("p");
        text.className = "c24-confirm-text";
        text.textContent = message;
        var actions = document.createElement("div");
        actions.className = "c24-confirm-actions";
        var cancel = document.createElement("button");
        cancel.value = "cancel";
        cancel.className = "c24-privacy-close";
        cancel.textContent = cancelLabel || "Cancel";
        cancel.setAttribute("data-confirm-no", "");
        var ok = document.createElement("button");
        ok.value = "ok";
        ok.className = "c24-privacy-close c24-confirm-danger";
        ok.textContent = okLabel || "OK";
        ok.setAttribute("data-confirm-yes", "");
        actions.appendChild(cancel);
        actions.appendChild(ok);
        box.appendChild(text);
        box.appendChild(actions);
        dialog.appendChild(box);
        document.body.appendChild(dialog);
        dialog.addEventListener("close", function () {
            var yes = dialog.returnValue === "ok";
            dialog.remove();
            done(yes);
        });
        dialog.addEventListener("click", function (e) { if (e.target === dialog) { dialog.close(); } });
        if (dialog.showModal) { dialog.showModal(); } else { dialog.setAttribute("open", ""); }
        cancel.focus();
    }
    document.addEventListener("submit", function (e) {
        var form = e.target;
        if (!form.hasAttribute || !form.hasAttribute("data-confirm") || form.__c24Confirmed) { return; }
        e.preventDefault();
        closeMenus(null);
        confirmDialog(form.getAttribute("data-confirm"), form.getAttribute("data-confirm-ok"),
            form.getAttribute("data-confirm-cancel"), function (yes) {
                if (!yes) { return; }
                if (form.hasAttribute("data-confirm-event")) {
                    // no page load (the Discord Activity's "Delete my data"): discord-activity.js
                    // listens for "c24-confirmed" and posts with the Bearer session
                    form.dispatchEvent(new CustomEvent("c24-confirmed", { bubbles: true }));
                    return;
                }
                if (form.hasAttribute("data-dc-clear")) { save(null); }
                form.__c24Confirmed = true;
                HTMLFormElement.prototype.submit.call(form);  // no submit event: no second dialog
            });
    });
    document.addEventListener("submit", function (e) {
        // log out / delete my data: forget the picture too
        if (!e.defaultPrevented && e.target.hasAttribute && e.target.hasAttribute("data-dc-clear")) { save(null); }
    });
})();
