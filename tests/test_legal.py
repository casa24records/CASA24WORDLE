"""Public legal pages for Discord App Verification / Discovery: /terms and /privacy.

Full texts in Spanish and English (?lang=es|en, else Accept-Language; any other
language reads English), one contact constant (app.LEGAL_CONTACT_EMAIL), CSP-safe
(no inline JS), versioned assets, in the sitemap, linked (small) from the start
screen, /leaderboard and the game's Settings. Inside the Discord Activity those
links open through the shell's SDK openExternalLink (browser test in
test_activity.py: test_browser_settings_legal_links_and_delete_my_data)."""

import os
import re

import pytest

import app
from lb_testlib import client, discord, lb_env, login, mem, today  # noqa: F401 (fixtures)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "webapp", "static")
ACT = "frame_id=f1&instance_id=i1&platform=desktop"
INLINE_HANDLER = re.compile(r"<[a-zA-Z][^>]*\son[a-z]+\s*=", re.S)
SCRIPT_TAG = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)


def page(client, path, **headers):
    r = client.get(path, headers=headers)
    assert r.status_code == 200, path
    return r.get_data(as_text=True)


def test_contact_is_one_constant():
    assert app.LEGAL_CONTACT_EMAIL == "casa24records@gmail.com"
    assert app.LEGAL_OPERATOR == "Casa 24 Records"
    # the address lives only in app.py (templates get it as `contact`)
    folder = os.path.join(ROOT, "webapp", "templates")
    for name in os.listdir(folder):
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            src = f.read()
        assert "@gmail.com" not in src and "admin@" not in src, name


@pytest.mark.parametrize("path", ["/terms", "/privacy"])
@pytest.mark.parametrize("lang", ["es", "en"])
def test_legal_pages_render_in_es_and_en(client, path, lang):
    html = page(client, f"{path}?lang={lang}")
    assert f'<html lang="{lang}">' in html
    assert app.LEGAL_CONTACT_EMAIL in html and f"mailto:{app.LEGAL_CONTACT_EMAIL}" in html
    assert "Casa 24 Records" in html
    assert "2026-10-29" in html  # <time datetime>
    other = "en" if lang == "es" else "es"
    assert f'href="{path}?lang={other}"' in html  # ES / EN switch
    assert 'href="/terms?lang=' in html and 'href="/privacy?lang=' in html
    assert "kolo-face.webp?v=" in html  # header logo


@pytest.mark.parametrize("accept, lang", [("es-PA,es;q=0.9", "es"), ("en-US", "en"), ("fr-FR", "en"),
                                          ("ko", "en"), ("", "en")])
def test_language_from_accept_language(client, accept, lang):
    for path in ("/terms", "/privacy"):
        html = page(client, path, **({"Accept-Language": accept} if accept else {}))
        assert f'<html lang="{lang}">' in html
    # ?lang= wins over the browser
    assert '<html lang="en">' in page(client, "/privacy?lang=en", **{"Accept-Language": "es"})
    assert '<html lang="es">' in page(client, "/privacy?lang=xx", **{"Accept-Language": "es"})


def test_privacy_says_what_the_code_does(client):
    es = page(client, "/privacy?lang=es")
    en = page(client, "/privacy?lang=en")
    for html in (es, en):
        assert "<code>identify</code>" in html
        assert "Borrar mis datos" in html
        for cookie in ("c24_lb", "c24_oauth", "c24_avr", "keyboard_layout_"):
            assert cookie in html
        for provider in ("Discord", "Vercel", "Neon"):
            assert provider in html
        assert "13" in html
    assert "2 días" in es and "2 days" in en
    assert "nunca tus palabras" in es and "never your words" in en
    assert "correo ni tu contraseña" in es and "email or your password" in en
    # matches the code: identify only, guesses kept 2 days
    import discord_auth
    assert "scope=identify" in discord_auth.authorize_url("https://x/cb", "s")


def test_terms_content(client):
    es = page(client, "/terms?lang=es")
    en = page(client, "/terms?lang=en")
    for html in (es, en):
        assert app.LEGAL_LICENSE_URL in html and "MIT" in html
        assert "https://discord.com/terms" in html
        assert "Kolo" in html
    assert "República de Panamá" in es and "Republic of Panama" in en


def test_legal_pages_are_csp_safe_and_versioned(client):
    for path in ("/terms?lang=es", "/terms?lang=en", "/privacy?lang=es", "/privacy?lang=en",
                 "/privacy?embed=1", "/terms?" + ACT):
        html = page(client, path)
        assert not INLINE_HANDLER.search(html), path
        assert "javascript:" not in html.lower(), path
        for attrs, body in SCRIPT_TAG.findall(html):
            assert "src=" in attrs, (path, body[:60])
        urls = re.findall(r"""/static/[^"'\s)]*""", html)
        assert urls and all("?v=" in u for u in urls), (path, urls)
        assert "cdn." not in html and "fonts.googleapis" not in html


def test_sitemap_lists_legal_pages(client):
    xml = page(client, "/sitemap.xml")
    assert "<loc>http://localhost/terms</loc>" in xml and "<loc>http://localhost/privacy</loc>" in xml


def test_links_on_start_screen_and_leaderboard(lb_env, client):
    menu = page(client, "/")
    assert 'href="/terms?lang=es"' in menu and 'href="/privacy?lang=es"' in menu
    assert 'href="/terms?lang=en"' in menu and 'href="/privacy?lang=en"' in menu
    board = page(client, "/leaderboard?tab=all", **{"Accept-Language": "es"})
    assert 'href="/terms?lang=es"' in board and 'href="/privacy?lang=es"' in board
    assert "Términos" in board
    board_en = page(client, "/leaderboard?tab=en")
    assert 'href="/privacy?lang=en"' in board_en and 'href="/terms?lang=en"' in board_en
    # also without the leaderboard (guest-only site)
    assert 'href="/privacy?lang=es"' in page(app.app.test_client(), "/")


def test_game_settings_links(lb_env, client):
    web = page(client, "/es")
    assert 'href="/privacy?lang=es"' in web and 'data-c24-external="http://localhost/privacy?lang=es"' in web
    assert "data-activity-delete" not in web  # Activity only
    assert 'href="/privacy?lang=en"' in page(client, "/en")
    act = page(client, "/lb/es?embed=1")
    assert 'data-c24-external="http://localhost/privacy?lang=es"' in act
    assert 'data-c24-external="http://localhost/terms?lang=es"' in act
    assert "data-activity-delete" in act and "data-confirm-event" in act
    assert "Borrar mis datos" in act


def test_activity_legal_links_use_the_bridge():
    with open(os.path.join(STATIC, "discord-activity.js"), encoding="utf-8") as f:
        game = f.read()
    with open(os.path.join(STATIC, "activity-shell.js"), encoding="utf-8") as f:
        shell = f.read()
    assert "data-c24-external" in game and "host.openExternal(" in game and "e.preventDefault()" in game
    assert "sdk.commands.openExternalLink({ url: href.href })" in shell
    for src in (game, shell):
        for bad in ("window.open", 'target="_top"', "top.location", "parent.location.href",
                    "location.href =", "location.assign"):
            assert bad not in src, bad
    # the delete goes through the session fetch, never a page load
    assert 'window.C24Activity.fetch("/api/me/delete"' in game and "host.dataDeleted()" in game


def test_delete_json_for_fetch_but_redirect_for_the_form(lb_env, client, discord, mem):
    login(client, discord)
    r = client.post("/api/me/delete")
    assert r.status_code == 302 and r.headers["Location"].endswith("/?deleted=1")
    login(client, discord)
    r = client.post("/api/me/delete", headers={"Accept": "application/json"})
    assert r.status_code == 200 and r.get_json() == {"deleted": True}
