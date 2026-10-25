"""Checks the Casa 24 word files and prints word counts.

Rules for every Casa 24 word (answers, guesses, aliases):
  - exactly 5 letters, lowercase, letters only (a-z, ñ, accented vowels)
  - no duplicates inside a file or across tiers
Also checks that the main lists and supplements of es/en are not empty.

Run:  python scripts/validate_words.py      (exit code 1 if anything is wrong)
"""

import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_DIR = os.path.join(ROOT, "webapp", "data", "languages")
LANGS = ["es", "en"]
ALLOWED = set("abcdefghijklmnopqrstuvwxyzñáéíóúü")
TIERS = ["answers", "guesses", "aliases"]


def read(lang, name):
    path = os.path.join(LANG_DIR, lang, name.format(lang=lang))
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def word_problem(word):
    if word != unicodedata.normalize("NFC", word):
        return "not NFC-normalized"
    if word != word.lower():
        return "not lowercase"
    if len(word) != 5:
        return f"{len(word)} letters"
    bad = [c for c in word if c not in ALLOWED]
    if bad:
        return f"bad characters {bad}"
    return None


def check():
    errors = []
    counts = {}
    for lang in LANGS:
        base = read(lang, "{lang}_5words.txt") or []
        supplement = read(lang, "{lang}_5words_supplement.txt") or []
        if not base:
            errors.append(f"{lang}: main word list is empty")
        if not supplement:
            errors.append(f"{lang}: supplement (guess list) is empty")
        counts[lang] = {"main": len(base), "supplement": len(supplement)}

        seen = {}
        for tier in TIERS:
            words = read(lang, "{lang}_5words_casa24_" + tier + ".txt")
            if words is None:
                continue
            counts[lang]["casa24_" + tier] = len(words)
            for word in words:
                problem = word_problem(word)
                if problem:
                    errors.append(f"{lang} {tier}: '{word}' {problem}")
                if word in seen:
                    errors.append(f"{lang}: '{word}' is in both {seen[word]} and {tier}")
                seen[word] = tier
        if not read(lang, "{lang}_5words_casa24_answers.txt"):
            errors.append(f"{lang}: no Casa 24 answer words")
    return counts, errors


if __name__ == "__main__":
    counts, errors = check()
    for lang, c in counts.items():
        print(lang, ", ".join(f"{k}={v}" for k, v in c.items()))
    for e in errors:
        print("ERROR:", e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    sys.exit(1 if errors else 0)
