"""Vercel build step: copy webapp/static/ to public/static/.

Vercel serves everything in public/ from its CDN, so /static/... requests
never reach Flask. Locally Flask serves webapp/static/ itself, so you never
need to run this by hand (public/ is git-ignored).
"""

import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "webapp", "static")
DST = os.path.join(ROOT, "public", "static")

if os.path.exists(DST):
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
count = sum(len(files) for _, _, files in os.walk(DST))
print(f"Copied {count} static files to public/static")
