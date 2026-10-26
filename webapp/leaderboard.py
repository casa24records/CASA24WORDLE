"""Pure leaderboard rules (no Flask, no storage), so they are easy to test.

- points(): 6 points for a win in 1 guess ... 1 point in 6, 0 for a loss.
- fold_accents / resolve_accents / color_guess: 1:1 ports of foldAccents,
  resolveAccents and updateColors in static/game.js. The server colors
  leaderboard guesses itself, so the browser never needs the answer.
- update_streak / effective_streak / streaks: streak = consecutive Panama days
  with a win, recomputed from the player's results whenever it is shown.
- Ranking order (computed in SQL by store.py): points, then wins, then whoever
  reached that total on an earlier day.
"""

import unicodedata

MAX_GUESSES = 6
CORRECT, SEMICORRECT, INCORRECT = "correct", "semicorrect", "incorrect"


def points(won, attempts):
    """Win in 1 guess -> 6 ... win in 6 -> 1; loss -> 0."""
    if not won or not 1 <= attempts <= MAX_GUESSES:
        return 0
    return MAX_GUESSES + 1 - attempts


def fold_accents(text):
    """'canción' -> 'cancion', but ñ stays ñ (game.js foldAccents)."""
    out = []
    for c in text:
        if c == "ñ":
            out.append(c)
        else:
            out.append("".join(ch for ch in unicodedata.normalize("NFD", c)
                               if not 0x300 <= ord(ch) <= 0x36F))
    return "".join(out)


def resolve_accents(word, answer, word_list, supplement, accent_insensitive, fold_map=None):
    """The real (accented) word the player meant (game.js resolveAccents).

    Today's answer wins; then the word itself if valid; then the first word in
    word_list + supplement with the same folded spelling; else the word as typed.
    fold_map can be passed in (built by build_fold_map) to avoid rebuilding it.
    """
    if not accent_insensitive:
        return word
    folded = fold_accents(word)
    if folded == fold_accents(answer):
        return answer
    if word in word_list or word in supplement:
        return word
    if fold_map is None:
        fold_map = build_fold_map(word_list, supplement)
    return fold_map.get(folded, word)


def build_fold_map(word_list, supplement):
    fold_map = {}
    for words in (word_list, supplement):
        for w in words:
            fold_map.setdefault(fold_accents(w), w)
    return fold_map


def color_guess(guess, answer):
    """Exact-letter colors (game.js updateColors): greens first, then yellows
    from the letters left over, left to right; the rest gray."""
    counts = {}
    for ch in answer:
        counts[ch] = counts.get(ch, 0) + 1
    colors = [None] * len(guess)
    for i, ch in enumerate(guess):
        if i < len(answer) and ch == answer[i]:
            colors[i] = CORRECT
            counts[ch] -= 1
    for i, ch in enumerate(guess):
        if colors[i] is not None:
            continue
        if ch in answer and counts.get(ch, 0) > 0:
            colors[i] = SEMICORRECT
            counts[ch] -= 1
        else:
            colors[i] = INCORRECT
    return colors


def update_streak(cur, best, last_win_day, today, won, combined=False):
    """New (cur, best, last_win_day) after a finished game on day `today`.

    Per language a loss ends the streak. Combined ("all") counts days with a
    win in any language, so a loss changes nothing and a second win on the
    same day doesn't count twice.
    """
    cur, best = int(cur or 0), int(best or 0)
    last = None if last_win_day in (None, "") else int(last_win_day)
    if won:
        if last == today:
            pass
        elif last == today - 1:
            cur += 1
        else:
            cur = 1
        last = today
    elif not combined:
        cur = 0
    best = max(best, cur)
    return cur, best, last


def effective_streak(cur, last_win_day, today):
    """Current streak as shown today: 0 once a whole day passed without a win."""
    if last_win_day in (None, ""):
        return 0
    return int(cur or 0) if int(last_win_day) >= today - 1 else 0


def streaks(history, today, combined=False):
    """(current, best) from [(day_number, won), ...] in any order."""
    cur, best, last = 0, 0, None
    for day, won in sorted(history):
        cur, best, last = update_streak(cur, best, last, day, won, combined)
    return effective_streak(cur, last, today), best
