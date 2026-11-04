// El Wordle by Casa 24 is dark only (rebrand 2026-11-04, no light mode or theme picker).
// Loaded in <head>: sets data-theme="dark" on <html> so the [data-theme="dark"] rules in
// style.css always apply, whatever the device setting.
(function () {
    document.documentElement.setAttribute("data-theme", "dark");
    try { localStorage.removeItem("casa24_theme"); } catch (e) { /* private mode */ }

    // Page control, wired here instead of an onchange= attribute (the Discord Activity's
    // CSP blocks inline handlers). Delegated on document, so it also works inside the Vue
    // apps, which re-create their DOM when mounting.
    //   select[data-nav-select]   goes to the chosen option's same-site URL (Activity language)
    document.addEventListener("change", function (e) {
        var el = e.target;
        if (!el || !el.hasAttribute) return;
        if (el.hasAttribute("data-nav-select") && /^\/(?!\/)/.test(el.value)) {
            window.location.assign(el.value);
        }
    });
})();
