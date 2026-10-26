"""Rebuild the Kolo images and favicons from the brand pack.

Usage:
    .venv/bin/python scripts/brand_assets.py "/path/to/brand pack"

The brand pack folder must contain KOLO/ with the PNGs named below. Change
the IMAGES, WIN and LOSE tables to use different Kolo art. Outputs go to
webapp/static/. WIN and LOSE must match KOLO_WIN and KOLO_LOSE in game.js
(tests/test_kolo.py checks this).
"""

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "webapp", "static")
CREAM = (244, 239, 230, 255)

# output file -> (source file in KOLO/, max height in px)
IMAGES = {
    "kolo-face.png": ("Kolo Face.png", 256),          # header logo slot + favicon
    "kolo-hero.png": ("Young Kolo.png", 360),          # menu
}
# end screen: one picked at random per game. Never add "Kolo ft. Pikachu" (trademark).
WIN = {  # output file in images/kolo/win/ -> source file in KOLO/
    "car.png": "Car Kolo.png",
    "chill.png": "Chill Kolo.png",
    "dj.png": "DJ Kolo.png",
    "face.png": "Kolo Face.png",
    "hoodie.png": "Hoodie Kolo.png",
    "montuno.png": "Montuno.png",
    "pizza.png": "Pizza Kolo.png",
    "prod.png": "Prod by Kolo.png",
    "rap-battle.png": "Rap Battle Kolo.png",
    "ross.png": "Kolo Ross (Stained).png",
    "young.png": "Young Kolo.png",
    "young-cropped.png": "Cropped - Young Kolo.png",
}
LOSE = {  # output file in images/kolo/lose/ -> source file in KOLO/
    "baby.png": "Baby Kolo.png",
    "toilet.png": "Kolo Toilet.png",
}
WIN_HEIGHT, LOSE_HEIGHT = 300, 240
FAVICONS = [(180, "apple-touch-icon.png"), (192, "android-chrome-192x192.png"), (512, "android-chrome-512x512.png")]


def load(path):
    im = Image.open(path).convert("RGBA")
    return im.crop(im.getbbox())  # trim transparent edges


def main(pack):
    kolo = os.path.join(pack, "KOLO")
    out_dir = os.path.join(STATIC, "images", "kolo")
    os.makedirs(out_dir, exist_ok=True)
    for out, (src, height) in IMAGES.items():
        im = load(os.path.join(kolo, src))
        im.thumbnail((height * 2, height))
        im.save(os.path.join(out_dir, out), optimize=True)
        print(f"{out}: {im.size}")
    for folder, table, height in (("win", WIN, WIN_HEIGHT), ("lose", LOSE, LOSE_HEIGHT)):
        sub = os.path.join(out_dir, folder)
        os.makedirs(sub, exist_ok=True)
        for out, src in table.items():
            im = load(os.path.join(kolo, src))
            im.thumbnail((height * 2, height))
            im.save(os.path.join(sub, out), optimize=True)
            print(f"{folder}/{out}: {im.size}")

    face = load(os.path.join(kolo, IMAGES["kolo-face.png"][0]))

    def icon(size):
        canvas = Image.new("RGBA", (size, size), CREAM)
        f = face.copy()
        f.thumbnail((int(size * 0.9), int(size * 0.9)))
        canvas.alpha_composite(f, ((size - f.width) // 2, (size - f.height) // 2))
        return canvas

    fav = os.path.join(STATIC, "favicon")
    for size, name in FAVICONS:
        icon(size).save(os.path.join(fav, name), optimize=True)
    icon(64).save(os.path.join(fav, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("favicons updated")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
