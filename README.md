# Casa 24 Wordle

Casa 24 Records' daily word game. Spanish and English, plus 8 more languages, with Casa 24's own words added to Spanish and English.

- **Daily word:** one word per language per day, the same for everyone, changing at midnight Panama time (UTC-5). About 1 day in 5 the Spanish or English word comes from the Casa 24 list. Details in `webapp/daily.py` and `.claude/skills/casa24-wordle/SKILL.md`.
- **Accents:** in Spanish you can type with or without accents (`cancion` finds `canción`); ñ always counts as its own letter.
- **Branding:** colors and fonts are CSS variables at the top of `webapp/static/style.css`; Kolo art is in `webapp/static/images/kolo/`.
- **Dark mode:** follows the device; players can switch it in Settings or with the moon button on the menu.
- **Claude skills:** `.claude/skills/casa24-*` explain every part of the project; start with `casa24-wordle`.

## Run locally

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cd webapp && ../.venv/bin/flask --app app run
```

- **Tests:** `.venv/bin/python -m pytest -q tests`
- **Add words:** `scripts/merge_words.py`, then `scripts/validate_words.py` and the tests.
- **Screenshots:** `.venv/bin/python scripts/screenshots.py` (phone size, light and dark).

## Deploy

Vercel. See `DEPLOY.md`.

## License and credits

See `LICENSE` and `CREDITS.md`.
