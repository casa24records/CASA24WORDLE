"""Phone-size screenshots of the menu and both games, light and dark.

Usage:
    .venv/bin/python scripts/screenshots.py [output_folder]   (default: screenshots/)

Starts the app on a free local port, types two guesses in each game, and saves
menu/es/en screenshots for light and dark mode. Prints any JavaScript errors.
Needs Playwright (requirements-dev.txt) and internet (Vue/Tailwind CDNs).
"""

import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from webapp.app import app  # noqa: E402

GUESSES = {"es": ["cosas", "jamon"], "en": ["crane", "music"]}


def main(out):
    os.makedirs(out, exist_ok=True)
    server = make_server("127.0.0.1", 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ["light", "dark"]:
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme=scheme)
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/")
            page.wait_for_timeout(800)
            page.screenshot(path=os.path.join(out, f"menu_{scheme}.png"))
            for lang, words in GUESSES.items():
                page.goto(f"{base}/{lang}")
                page.wait_for_timeout(800)
                page.keyboard.press("Escape")
                for word in words:
                    for letter in word:
                        page.keyboard.press(letter)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)
                page.wait_for_timeout(500)
                page.screenshot(path=os.path.join(out, f"game_{lang}_{scheme}.png"))
            ctx.close()
        browser.close()
    server.shutdown()
    print(f"Saved 6 screenshots to {out}")
    print("JavaScript errors:", errors or "none")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots"))
