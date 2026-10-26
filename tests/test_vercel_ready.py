"""The app must load the way Vercel loads it: `webapp.app:app` from the repo root."""

import os
import subprocess
import sys
import json
import re
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECK = """
import importlib
app = importlib.import_module("webapp.app").app
c = app.test_client()
for path in ["/", "/es", "/en", "/sitemap.xml"]:
    r = c.get(path, base_url="http://x.vercel.app", headers={"X-Forwarded-Proto": "https"})
    assert r.status_code == 200, (path, r.status_code)
# the sitemap uses the visitor's own address, never an upstream domain
sitemap = c.get("/sitemap.xml", base_url="http://x.vercel.app", headers={"X-Forwarded-Proto": "https"}).text
assert "wordle.global" not in sitemap, sitemap
assert "<loc>https://x.vercel.app</loc>" in sitemap, sitemap
assert "<loc>https://x.vercel.app/es</loc>" in sitemap, sitemap
print("ok")
"""


def test_entrypoint_in_pyproject():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        config = tomllib.load(f)
    assert config["tool"]["vercel"]["entrypoint"] == "webapp.app:app"


def test_app_loads_from_repo_root_behind_proxy():
    result = subprocess.run(
        [sys.executable, "-c", CHECK], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "VERCEL": "1"},
    )
    assert result.stdout.strip().endswith("ok"), result.stderr[-2000:]


def test_build_step_copies_static(tmp_path):
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "vercel_build.py")], check=True, cwd=ROOT)
    try:
        assert os.path.exists(os.path.join(ROOT, "public", "static", "style.css"))
        assert os.path.exists(os.path.join(ROOT, "public", "static", "images", "kolo", "kolo-face.webp"))
    finally:
        import shutil
        shutil.rmtree(os.path.join(ROOT, "public"), ignore_errors=True)


def test_vercel_json_caches_only_versioned_static():
    """Year-long immutable caching only for /static/ URLs that carry ?v=<hash>
    (asset() in app.py); unversioned URLs keep Vercel's default revalidation."""
    with open(os.path.join(ROOT, "vercel.json")) as f:
        config = json.load(f)
    immutable = [h for h in config.get("headers", [])
                 if any("immutable" in x["value"] for x in h["headers"])]
    assert immutable, "no immutable rule"
    for rule in immutable:
        assert {"type": "query", "key": "v"} in rule.get("has", []), rule


def test_every_static_url_is_versioned():
    """Every /static/ link in the rendered pages has ?v= (else immutable caching
    is never applied, or worse, an old copy sticks)."""
    import importlib
    import sys
    sys.path.insert(0, ROOT)
    app = importlib.import_module("webapp.app").app
    c = app.test_client()
    for path in ["/", "/es", "/en", "/ar", "/ko"]:
        html = c.get(path).get_data(as_text=True)
        urls = re.findall(r"""/static/[^"'\s)]*""", html)
        assert urls, path
        # KOLO_BASE is a folder prefix; game.js adds ?v=ASSET_V to each Kolo URL
        bad = [u for u in urls if "?v=" not in u and not u.endswith("/kolo/")]
        assert not bad, (path, bad)
