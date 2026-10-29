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
        if VERSIONED_VENDOR.match(rule["source"]):
            continue  # the version is in the folder name (test_vercel_json_caches_versioned_sdk)
        assert {"type": "query", "key": "v"} in rule.get("has", []), rule


# /static/vendor/<name>-<x.y.z>/(.*): a folder whose name carries the version
VERSIONED_VENDOR = re.compile(r"^/static/vendor/[a-z0-9-]+-\d+\.\d+\.\d+/\(\.\*\)$")


def source_regex(source):
    """Vercel `source` (path-to-regexp; we only use literal text and (.*)) as a regex."""
    return re.compile("^" + re.escape(source).replace(re.escape("(.*)"), "(.*)") + "$")


def test_vercel_json_caches_versioned_sdk():
    """The vendored Discord SDK is loaded by bare ES-module imports (no ?v=), so it
    gets a year-long immutable cache by folder: the SDK version is in the path,
    an update is a new folder and a new URL. Only versioned vendor folders."""
    with open(os.path.join(ROOT, "vercel.json")) as f:
        config = json.load(f)
    sys.path.insert(0, os.path.join(ROOT, "webapp"))
    import preload
    sdk_source = "/static/" + preload.SDK_DIR + "/(.*)"
    rules = [h for h in config["headers"] if h["source"] == sdk_source]
    assert len(rules) == 1, sdk_source
    assert "has" not in rules[0]
    assert {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in rules[0]["headers"]
    assert os.path.isdir(os.path.join(ROOT, "webapp", "static", preload.SDK_DIR))
    for rule in config["headers"]:
        if "has" in rule:
            continue
        assert VERSIONED_VENDOR.match(rule["source"]), rule["source"]
        rx = source_regex(rule["source"])
        assert rx.match("/static/" + preload.SDK_DIR + "/lib/tslib/tslib.es6.mjs")
        for path in ("/static/game.js", "/static/style.css", "/static/vendor/vue.global.prod.js",
                     "/static/vendor/discord-embedded-app-sdk/index.mjs",
                     "/static/vendor/discord-embedded-app-sdk-2.4.0/index.mjs",
                     "/static/discord-activity.js", "/lb/es"):
            assert not rx.match(path), (rule["source"], path)


def test_sdk_modulepreloads():
    """Every module reachable from the SDK's index.mjs, BFS from index, all on disk and in git."""
    sys.path.insert(0, os.path.join(ROOT, "webapp"))
    import preload
    paths = preload.sdk_modulepreloads()
    assert paths and paths[0] == preload.SDK_DIR + "/index.mjs"
    assert preload.SDK_DIR + "/lib/tslib/tslib.es6.mjs" in paths
    assert len(paths) == len(set(paths))
    assert preload.sdk_modulepreloads() is paths  # computed once
    static = os.path.join(ROOT, "webapp", "static")
    tracked = set(subprocess.run(
        ["git", "ls-files", "webapp/static/vendor"], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split())
    for p in paths:
        assert p.endswith(".mjs") and not p.startswith("/") and ".." not in p, p
        assert os.path.isfile(os.path.join(static, *p.split("/"))), p
        assert "webapp/static/" + p in tracked, p
    # the graph really is closed: every relative import of every listed module is listed
    for p in paths:
        with open(os.path.join(static, *p.split("/")), encoding="utf-8") as f:
            for spec in preload._imports(f.read()):
                target = os.path.normpath(os.path.join(os.path.dirname(p), spec)).replace(os.sep, "/")
                assert target in paths, (p, spec)


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
