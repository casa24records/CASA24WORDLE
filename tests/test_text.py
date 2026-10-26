"""Every language has the end-screen result texts and the repeated-word notification."""

import glob
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIGS = sorted(glob.glob(os.path.join(ROOT, "webapp", "data", "languages", "*", "language_config.json")))
KEYS = ["result_won", "result_lost", "notification-repeated"]


def test_all_languages_found():
    assert len(CONFIGS) == 10


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_new_text_keys_present(path):
    with open(path, encoding="utf-8") as f:
        text = json.load(f).get("text", {})
    for key in KEYS:
        value = text.get(key)
        assert isinstance(value, str) and value.strip(), (path, key)
