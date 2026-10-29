// Casa 24 theme: "auto" follows the phone/computer setting, or force "light"/"dark".
// Loaded in <head> so the page never flashes the wrong colors.
(function () {
    var KEY = "casa24_theme";

    function stored() {
        try { return localStorage.getItem(KEY) || "auto"; } catch (e) { return "auto"; }
    }

    function apply(theme) {
        if (theme === "light" || theme === "dark") {
            document.documentElement.setAttribute("data-theme", theme);
        } else {
            document.documentElement.removeAttribute("data-theme");
        }
    }

    function isDark() {
        var forced = document.documentElement.getAttribute("data-theme");
        if (forced) return forced === "dark";
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    window.casa24SetTheme = function (theme) {
        try { localStorage.setItem(KEY, theme); } catch (e) { /* private mode: still apply */ }
        apply(theme);
    };
    window.casa24GetTheme = stored;
    // menu button: switch to the opposite of what is showing now
    window.casa24ToggleTheme = function () {
        window.casa24SetTheme(isDark() ? "light" : "dark");
    };

    apply(stored());

    // Page controls, wired here instead of onclick= / onchange= attributes (the
    // Discord Activity's CSP blocks inline handlers). Delegated on document, so
    // they also work inside the Vue apps, which re-create their DOM when mounting.
    //   [data-theme-toggle]      button: light <-> dark (menu, leaderboard)
    //   select[data-theme-select] Automatic / Light / Dark (game settings)
    //   select[data-autosubmit]   submits its form on change (keyboard layout)
    //   select[data-nav-select]   goes to the chosen option's same-site URL (Activity language)
    document.addEventListener("click", function (e) {
        var button = e.target.closest ? e.target.closest("[data-theme-toggle]") : null;
        if (button) { window.casa24ToggleTheme(); }
    });
    document.addEventListener("change", function (e) {
        var el = e.target;
        if (!el || !el.hasAttribute) return;
        if (el.hasAttribute("data-theme-select")) {
            window.casa24SetTheme(el.value);
        } else if (el.hasAttribute("data-autosubmit") && el.form) {
            el.form.submit();
        } else if (el.hasAttribute("data-nav-select") && /^\/(?!\/)/.test(el.value)) {
            window.location.assign(el.value);
        }
    });
    // the theme menu shows the saved choice (after the deferred Vue apps have mounted)
    document.addEventListener("DOMContentLoaded", function () {
        var selects = document.querySelectorAll("select[data-theme-select]");
        for (var i = 0; i < selects.length; i++) selects[i].value = stored();
    });
})();
