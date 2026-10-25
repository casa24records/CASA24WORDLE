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
})();
