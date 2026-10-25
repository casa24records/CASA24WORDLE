import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
# app.py reads its data with paths relative to webapp/
os.chdir(os.path.join(ROOT, "webapp"))
