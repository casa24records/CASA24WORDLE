"""<link rel="modulepreload"> list for the vendored Discord Embedded App SDK.

The SDK is ~70 small ES modules. Without preloads the browser finds each import
only after its parent has loaded (a waterfall, and inside Discord every request
goes through Discord's proxy). The Activity shell lists them all up front so
they download in parallel.

sdk_modulepreloads() walks the import graph statically from index.mjs (relative
imports only), breadth-first, and returns static-relative paths such as
"vendor/discord-embedded-app-sdk-2.5.0/index.mjs" (use with asset()/url_for
('static', ...)). Computed once per process (lru_cache). Paths are relative to
this file, so it works from any working directory and on Vercel.
"""

import functools
import os
import posixpath
import re

SDK_VERSION = "2.5.0"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SDK_DIR = posixpath.join("vendor", "discord-embedded-app-sdk-" + SDK_VERSION)

# `import x from './a.mjs'`, `export * from "./b.mjs"`, `import './c.mjs'`,
# multi-line import lists, and dynamic `import('./d.mjs')`.
_IMPORT_RE = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*)(['"])(\.{1,2}/[^'"]+)\1""")


def _imports(source):
    return [m.group(2) for m in _IMPORT_RE.finditer(source)]


@functools.lru_cache(maxsize=None)
def sdk_modulepreloads(entry="index.mjs"):
    """Static-relative paths of every .mjs reachable from the SDK's entry, BFS order."""
    start = posixpath.join(SDK_DIR, entry)
    seen, order, queue = {start}, [], [start]
    while queue:
        rel = queue.pop(0)
        path = os.path.join(STATIC_DIR, *rel.split("/"))
        if not os.path.isfile(path):
            continue  # a missing file is not ours to preload (the browser reports it)
        order.append(rel)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        for spec in _imports(source):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec))
            if not target.endswith(".mjs") or not target.startswith(SDK_DIR + "/"):
                continue
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return tuple(order)
