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
    return {f for f in os.listdir(os.path.join(KOLO_DIR, name)) if not f.startswith(".")}


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
