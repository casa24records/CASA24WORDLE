// Tailwind v3.4.17 (the version the Play CDN served), compiled by scripts/build_css.py
// into webapp/static/tailwind.css. Defaults only, like the Play CDN (preflight included).
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: {
    relative: true,
    files: [
      "./webapp/templates/**/*.html",
      "./webapp/static/*.js",
    ],
  },
  // Classes that game.js puts together at runtime. They also appear as whole
  // words in game.js (so the scan finds them); listed here so a refactor that
  // builds them from pieces can't drop them silently.
  safelist: [
    "uppercase", "font-bold", "select-none", "text-white",
    "border-2", "border-neutral-300", "border-neutral-500",
  ],
  theme: { extend: {} },
  plugins: [],
};
