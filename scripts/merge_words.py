"""Add reviewed words to the Casa 24 word files.

Usage:
    python scripts/merge_words.py scripts/casa24/seed_words.csv
    python scripts/merge_words.py mined_candidates.csv

The CSV needs the columns: lang, word, decision
  decision = answer      -> can be the daily word (about 1 day in 5) and is a valid guess
  decision = guess-only  -> accepted as a guess, never the daily word
  decision = alias       -> member alias, kept in a private file that is NOT loaded
                            unless CASA24_ENABLE_ALIASES=1 (and never committed)
  decision = reject / empty -> ignored

lang can be es, en, or mixed (both). A word is also added to the other language
(es <-> en) when that language's main word list already has it, e.g. radio, video.

The script only ever ADDS words; it never removes anything. Run
scripts/validate_words.py afterwards.
"""

import csv
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_DIR = os.path.join(ROOT, "webapp", "data", "languages")
LANGS = ["es", "en"]
FILES = {
    "answer": "{lang}_5words_casa24_answers.txt",
    "guess-only": "{lang}_5words_casa24_guesses.txt",
    "alias": "{lang}_5words_casa24_aliases.txt",
}


def path(lang, name):
    return os.path.join(LANG_DIR, lang, name.format(lang=lang))


def read_words(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def write_words(file_path, header, words):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(header)
        for word in sorted(set(words)):
            f.write(word + "\n")


def dictionary(lang):
    # Only the main list: the big guess lists include obscure and foreign words.
    return set(read_words(path(lang, "{lang}_5words.txt")))


HEADERS = {
    "answer": "# Casa 24 words that can be the daily answer (about 1 day in 5). Also valid guesses.\n",
    "guess-only": "# Casa 24 slang and names: accepted as guesses, never the daily answer.\n",
    "alias": "# PRIVATE member aliases. Not committed, not loaded unless CASA24_ENABLE_ALIASES=1.\n",
}


def main(csv_path):
    tiers = {lang: {t: set(read_words(path(lang, f))) for t, f in FILES.items()} for lang in LANGS}
    dicts = {lang: dictionary(lang) for lang in LANGS}
    added = 0

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            decision = (row.get("decision") or "").strip().lower()
            if decision not in FILES:
                continue
            word = unicodedata.normalize("NFC", row["word"].strip().lower())
            lang = row["lang"].strip().lower()
            targets = LANGS if lang == "mixed" else [lang]
            # shared words (radio, video...) also count in the other language
            if decision != "alias":
                targets += [o for o in LANGS if o not in targets and word in dicts[o]]
            for t in targets:
                if t not in LANGS:
                    continue
                # an answer beats guess-only; a word lives in exactly one tier
                if decision == "guess-only" and word in tiers[t]["answer"]:
                    continue
                if decision == "answer":
                    tiers[t]["guess-only"].discard(word)
                if word not in tiers[t][decision]:
                    tiers[t][decision].add(word)
                    added += 1

    for lang in LANGS:
        for tier, words in tiers[lang].items():
            if words or tier != "alias":
                write_words(path(lang, FILES[tier]), HEADERS[tier], words)
        print(lang, {t: len(w) for t, w in tiers[lang].items()})
    print(f"added {added} word entries")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
