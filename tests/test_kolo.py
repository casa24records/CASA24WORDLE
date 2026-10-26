"""The end-screen Kolo pools in game.js match the image folders and brand_assets.py."""

import os
import re

import brand_assets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOLO_DIR = os.path.join(ROOT, "webapp", "static", "images", "kolo")
GAME_JS = os.path.join(ROOT, "webapp", "static", "game.js")


def js_pool(name):
    with open(GAME_JS, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"const\s+" + name + r"\s*=\s*\[(.*?)\];", src, re.S)
    assert m, f"{name} not found in game.js"
    return re.findall(r"""["']([^"']+)["']""", m.group(1))


def folder(name):
    """WebP files in win/ or lose/."""
    return {f for f in os.listdir(os.path.join(KOLO_DIR, name)) if f.endswith(".webp")}


def test_kolo_images_are_webp_only():
    """The Kolo PNGs were removed (WebP everywhere); only kolo-hero.png stays, for og:image."""
    for name in ("win", "lose"):
        pngs = [f for f in os.listdir(os.path.join(KOLO_DIR, name)) if f.endswith(".png")]
        assert not pngs, f"{name}/ still has PNGs: {pngs}"
    top = sorted(f for f in os.listdir(KOLO_DIR) if f.endswith(".png"))
    assert top == ["kolo-hero.png"], top
    assert os.path.exists(os.path.join(KOLO_DIR, "kolo-face.webp"))
    assert os.path.exists(os.path.join(KOLO_DIR, "kolo-hero.webp"))
    assert all(n.endswith(".webp") for n in list(brand_assets.IMAGES) + list(brand_assets.WIN) + list(brand_assets.LOSE))
    assert brand_assets.ALSO_PNG == {"kolo-hero.webp"}


def test_brand_assets_is_the_script():
    assert brand_assets.__file__.startswith(os.path.join(ROOT, "scripts"))


def test_win_pool_matches_everywhere():
    pool = js_pool("KOLO_WIN")
    assert len(pool) == len(set(pool)), "duplicate in KOLO_WIN"
    assert set(pool) == folder("win") == set(brand_assets.WIN)


def test_lose_pool_matches_everywhere():
    pool = js_pool("KOLO_LOSE")
    assert len(pool) == len(set(pool)), "duplicate in KOLO_LOSE"
    assert set(pool) == folder("lose") == set(brand_assets.LOSE)


def test_pools_do_not_overlap():
    assert not set(js_pool("KOLO_WIN")) & set(js_pool("KOLO_LOSE"))
    assert not folder("win") & folder("lose")
    assert not set(brand_assets.WIN) & set(brand_assets.LOSE)


def test_no_pikachu():
    names = (
        js_pool("KOLO_WIN") + js_pool("KOLO_LOSE")
        + sorted(folder("win") | folder("lose"))
        + list(brand_assets.WIN) + list(brand_assets.WIN.values())
        + list(brand_assets.LOSE) + list(brand_assets.LOSE.values())
        + [src for src, _ in brand_assets.IMAGES.values()] + list(brand_assets.IMAGES)
    )
    bad = [n for n in names if "pikachu" in n.lower()]
    assert not bad, bad
