# Credits

Casa 24 Wordle is based on [Hugo0/wordle](https://github.com/Hugo0/wordle)
(code under the MIT license, see `LICENSE` and `CONTRIBUTORS.md`).
New work © 2026 Casa 24 Records, also under the MIT license.

## Word lists

| File | Source | License |
|---|---|---|
| `*/<lang>_5words.txt`, `en_5words_supplement.txt` and the other language files | Upstream Hugo0/wordle, built from [wooorm/dictionaries](https://github.com/wooorm/dictionaries) (Hunspell) and frequency data | Each dictionary keeps its own license; see wooorm/dictionaries per language |
| `es/es_5words_supplement.txt` (Spanish valid guesses, new) | Five-letter words from [FrequencyWords](https://github.com/hermitdave/FrequencyWords) (OpenSubtitles 2018, Spanish, seen 20+ times), kept only if the [Spanish Hunspell dictionary (RLA-ES)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/es) accepts them | **CC BY-SA 4.0** (FrequencyWords content). This file is shared under the same license. The Hunspell dictionary (GPL-3.0 / LGPL-3.0 / MPL-1.1) was only used as a filter and is not included. |
| `es/`, `en/` `*_5words_casa24_*.txt` | Casa 24 Records | © Casa 24 Records |

## Art and fonts

| File | Source | License |
|---|---|---|
| `webapp/static/images/kolo/*`, `webapp/static/favicon/*` | Kolo, Casa 24 Records mascot artwork | © Casa 24 Records, all rights reserved (not covered by the MIT license) |
| `webapp/static/fonts/VT323-Regular.ttf` | VT323 by Peter Hull | SIL Open Font License 1.1 (`VT323-OFL.txt`) |
| Gilroy (`webapp/static/fonts/Gilroy-*.ttf`, not in git) | Gilroy by Radomir Tinkov | Commercial. Only used locally until Casa 24 has a webfont license; without the files the site falls back to the system font. |
