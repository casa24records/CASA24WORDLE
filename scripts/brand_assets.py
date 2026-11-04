"""Rebuild the Kolo images and favicons from the brand pack.

Usage:
    .venv/bin/python scripts/brand_assets.py "/path/to/brand pack"
    .venv/bin/python scripts/brand_assets.py --rebrand design/rebrand-v1.1

The --rebrand path ("El Wordle by Casa 24", 2026-11-04) is separate: see
rebrand() below. It writes images/brand/ and replaces the favicons; it does
not touch the Kolo images.

The brand pack folder must contain KOLO/ with the PNGs named below. Change
the IMAGES, WIN and LOSE tables to use different Kolo art. Outputs go to
webapp/static/. Kolo images are written as WebP only (quality 85, alpha
kept; every browser the game supports shows WebP). The one exception is
kolo-hero.png, also written as PNG for og:image/twitter:image link previews
(some crawlers want PNG/JPEG). Favicons stay PNG/ICO. WIN and LOSE must
match KOLO_WIN and KOLO_LOSE in game.js (tests/test_kolo.py checks this).
"""

import os
import shutil
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "webapp", "static")
CREAM = (244, 239, 230, 255)

# output file -> (source file in KOLO/, max height in px)
IMAGES = {
    "kolo-face.webp": ("Kolo Face.png", 256),          # header logo slot + favicon
    "kolo-hero.webp": ("Young Kolo.png", 360),          # menu
}
# end screen: one picked at random per game. Never add "Kolo ft. Pikachu" (trademark).
WIN = {  # output file in images/kolo/win/ -> source file in KOLO/
    "car.webp": "Car Kolo.png",
    "chill.webp": "Chill Kolo.png",
    "dj.webp": "DJ Kolo.png",
    "face.webp": "Kolo Face.png",
    "hoodie.webp": "Hoodie Kolo.png",
    "montuno.webp": "Montuno.png",
    "pizza.webp": "Pizza Kolo.png",
    "prod.webp": "Prod by Kolo.png",
    "rap-battle.webp": "Rap Battle Kolo.png",
    "ross.webp": "Kolo Ross (Stained).png",
    "young.webp": "Young Kolo.png",
    "young-cropped.webp": "Cropped - Young Kolo.png",
}
LOSE = {  # output file in images/kolo/lose/ -> source file in KOLO/
    "baby.webp": "Baby Kolo.png",
    "toilet.webp": "Kolo Toilet.png",
}
WIN_HEIGHT, LOSE_HEIGHT = 300, 240
FAVICONS = [(180, "apple-touch-icon.png"), (192, "android-chrome-192x192.png"), (512, "android-chrome-512x512.png")]


WEBP_QUALITY = 85
# also written as PNG (social link previews: og:image / twitter:image)
ALSO_PNG = {"kolo-hero.webp"}


def save(im, path):
    """Write the WebP (plus a PNG copy for the files in ALSO_PNG)."""
    im.save(path, "WEBP", quality=WEBP_QUALITY, method=6, exact=False)
    if os.path.basename(path) in ALSO_PNG:
        im.save(os.path.splitext(path)[0] + ".png", optimize=True)


def load(path):
    im = Image.open(path).convert("RGBA")
    return im.crop(im.getbbox())  # trim transparent edges


def main(pack):
    from PIL import features
    if not features.check("webp"):
        sys.exit("This Pillow build has no WebP support")
    kolo = os.path.join(pack, "KOLO")
    out_dir = os.path.join(STATIC, "images", "kolo")
    os.makedirs(out_dir, exist_ok=True)
    for out, (src, height) in IMAGES.items():
        im = load(os.path.join(kolo, src))
        im.thumbnail((height * 2, height))
        save(im, os.path.join(out_dir, out))
        print(f"{out}: {im.size}")
    for folder, table, height in (("win", WIN, WIN_HEIGHT), ("lose", LOSE, LOSE_HEIGHT)):
        sub = os.path.join(out_dir, folder)
        os.makedirs(sub, exist_ok=True)
        for out, src in table.items():
            im = load(os.path.join(kolo, src))
            im.thumbnail((height * 2, height))
            save(im, os.path.join(sub, out))
            print(f"{folder}/{out}: {im.size}")

    face = load(os.path.join(kolo, IMAGES["kolo-face.webp"][0]))

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


# --rebrand: output in images/brand/ -> (source in the rebrand folder, height, WebP quality)
REBRAND_IMAGES = {
    "el-wordle.webp": ("el-wordle-titler.png", 160, 90),        # header title
    "kolo-hoodie.webp": ("hoodie-kolo-cropped.png", 192, 85),   # header mascot
    "kolo-hoodie-full.webp": ("hoodie-kolo.png", 420, 85),      # full-body Kolo
    "casa24-door.webp": ("casa24-door-white.png", 96, 90),      # header link to casa24records.com
}
REBRAND_OG = ("banner-680x240.png", "og-image.png")  # og:image / twitter:image (PNG for crawlers)
REBRAND_ICON = "icon-1024.png"  # Activity icon (opaque) -> favicons


def rebrand(src_dir):
    """Build the "El Wordle by Casa 24" assets from design/rebrand-v1.1/.

    Writes webapp/static/images/brand/{el-wordle,kolo-hoodie,kolo-hoodie-full,
    casa24-door}.webp
    (trimmed to their alpha bbox, resized to a fixed height, alpha kept),
    images/brand/og-image.png, and replaces the favicons (same names as
    main()) with downscales of icon-1024.png. Portal art (icon/banners) is
    uploaded by hand, see docs/discord-activity-checklist.md.
    """
    from PIL import features
    if not features.check("webp"):
        sys.exit("This Pillow build has no WebP support")
    out_dir = os.path.join(STATIC, "images", "brand")
    os.makedirs(out_dir, exist_ok=True)
    for out, (src, height, quality) in REBRAND_IMAGES.items():
        im = load(os.path.join(src_dir, src))
        width = max(1, round(im.width * height / im.height))
        im = im.resize((width, height), Image.LANCZOS)
        path = os.path.join(out_dir, out)
        im.save(path, "WEBP", quality=quality, method=6, exact=False)
        print(f"brand/{out}: {im.size} {os.path.getsize(path)} B")

    src, out = REBRAND_OG
    path = os.path.join(out_dir, out)
    Image.open(os.path.join(src_dir, src)).convert("RGB").save(path, optimize=True)
    if os.path.getsize(path) > os.path.getsize(os.path.join(src_dir, src)):
        shutil.copyfile(os.path.join(src_dir, src), path)  # designer's file was already smaller
    print(f"brand/{out}: {os.path.getsize(path)} B")

    icon = Image.open(os.path.join(src_dir, REBRAND_ICON)).convert("RGB")
    fav = os.path.join(STATIC, "favicon")
    for size, name in FAVICONS:
        path = os.path.join(fav, name)
        icon.resize((size, size), Image.LANCZOS).save(path, optimize=True)
        print(f"favicon/{name}: {os.path.getsize(path)} B")
    path = os.path.join(fav, "favicon.ico")
    icon.resize((256, 256), Image.LANCZOS).save(path, sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"favicon/favicon.ico: {os.path.getsize(path)} B")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--rebrand":
        rebrand(sys.argv[2])
    elif len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        main(sys.argv[1])
    else:
        sys.exit(__doc__)
