// Casa 24 Wordle leaderboard page: the 3 tabs (Combined, Español, English) fit in one
// row; if a very narrow screen ever makes the row scroll, center the active tab
// without scrolling the page itself.
// (A file, not an inline script: the Discord Activity's CSP blocks inline code.)
(function () {
    var nav = document.querySelector("[data-lb-tabs]");
    var on = nav && nav.querySelector(".is-active");
    if (!on || nav.scrollWidth <= nav.clientWidth) return;
    var r = on.getBoundingClientRect(), n = nav.getBoundingClientRect();
    nav.scrollLeft += (r.left + r.width / 2) - (n.left + n.width / 2);
})();
