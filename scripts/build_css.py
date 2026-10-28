"""Compile webapp/static/tailwind.css with the Tailwind standalone CLI (no Node).

    .venv/bin/python scripts/build_css.py

Downloads the pinned CLI once into .cache/tailwind/ (git-ignored, never uploaded),
checks its SHA-256 against the official release, and writes a minified CSS file.
Run it after adding Tailwind classes to a template or to static/*.js, and commit
the result: Vercel does not run this script.
"""
import hashlib
import os
import platform
import stat
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "v3.4.17"
# official sha256sums.txt of the v3.4.17 release
SHA256 = {
    "macos-arm64": "a1d0c7985759accca0bf12e51ac1dcbf0f6cf2fffb62e6e0f62d091c477a10a3",
    "macos-x64": "6cbdad74be776c087ffa5e9a057512c54898f9fe8828d3362212dfe32fc933a3",
    "linux-arm64": "69b1378b8133192d7d2feb12a116fa12d035594f58db3eff215879e4ad8cf39b",
    "linux-x64": "7d24f7fa191d2193b78cd5f5a42a6093e14409521908529f42d80b11fde1f1d4",
}
CACHE = os.path.join(ROOT, ".cache", "tailwind")
CONFIG = os.path.join(ROOT, "tailwind.config.js")
INPUT = os.path.join(ROOT, "webapp", "static", "src", "tailwind.input.css")
OUTPUT = os.path.join(ROOT, "webapp", "static", "tailwind.css")


def target():
    system = {"Darwin": "macos", "Linux": "linux"}.get(platform.system())
    machine = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}.get(platform.machine())
    name = f"{system}-{machine}"
    if name not in SHA256:
        sys.exit(f"No pinned Tailwind CLI for {platform.system()} {platform.machine()}")
    return name


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cli():
    name = target()
    path = os.path.join(CACHE, f"tailwindcss-{name}-{VERSION}")
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        url = f"https://github.com/tailwindlabs/tailwindcss/releases/download/{VERSION}/tailwindcss-{name}"
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)
    if sha256(path) != SHA256[name]:
        os.remove(path)
        sys.exit("Tailwind CLI checksum mismatch; deleted it. Run again to re-download.")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def main():
    env = dict(os.environ, BROWSERSLIST_IGNORE_OLD_DATA="1")  # the CLI bundles its own data
    subprocess.run([cli(), "-c", CONFIG, "-i", INPUT, "-o", OUTPUT, "--minify"], cwd=ROOT, env=env, check=True)
    print(f"Wrote {os.path.relpath(OUTPUT, ROOT)} ({os.path.getsize(OUTPUT)} bytes)")


if __name__ == "__main__":
    main()
