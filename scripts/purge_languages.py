"""Delete leaderboard rows of the languages Casa 24 Wordle no longer has.

Since 2026-10-29 the game is only Spanish (es) and English (en). Rows with any
other `lang` in wordle_results and wordle_games no longer count anywhere (store.py
filters them out), but they still sit in the database. This script removes them.

    DATABASE_URL=... .venv/bin/python scripts/purge_languages.py
        dry run (default): row counts per language, nothing changes
    ... --export DIR
        also write the rows that would be deleted to DIR/wordle_results.csv and
        DIR/wordle_games.csv (they contain Discord IDs: keep them private)
    ... --execute --yes-i-have-owner-approval
        delete them in ONE transaction, then print the counts again

DATABASE_URL is read from the environment only. --env-file PATH loads it from a
file, but only when you pass that flag. Never run --execute without the owner's
go-ahead (and an --export first is a good idea).
"""

import argparse
import csv
import os
import sys

KEEP_LANGS = ("es", "en")
TABLES = ("wordle_results", "wordle_games")

# Constant SQL; the only values are passed as parameters.
SQL_COUNTS = {
    "wordle_results": "SELECT lang, COUNT(*) FROM wordle_results GROUP BY lang ORDER BY lang",
    "wordle_games": "SELECT lang, COUNT(*) FROM wordle_games GROUP BY lang ORDER BY lang",
}
SQL_EXPORT = {
    "wordle_results": ("SELECT discord_id, lang, day, won, attempts, points, finished_at "
                       "FROM wordle_results WHERE lang <> ALL(%(keep)s) ORDER BY lang, day, discord_id"),
    "wordle_games": ("SELECT discord_id, lang, day, guesses, updated_at "
                     "FROM wordle_games WHERE lang <> ALL(%(keep)s) ORDER BY lang, day, discord_id"),
}
# games first, then results (no foreign key between them; order is cosmetic)
SQL_DELETE = (
    ("wordle_games", "DELETE FROM wordle_games WHERE lang <> ALL(%(keep)s)"),
    ("wordle_results", "DELETE FROM wordle_results WHERE lang <> ALL(%(keep)s)"),
)
APPROVAL_FLAG = "--yes-i-have-owner-approval"


def read_env_file(path):
    """DATABASE_URL from a KEY=VALUE file (only that key is read)."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            key, sep, value = line.strip().partition("=")
            if sep and key.strip().removeprefix("export ").strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")
    return None


def counts(conn):
    """{table: {lang: n}}"""
    out = {}
    with conn.transaction(), conn.cursor() as cur:
        for table in TABLES:
            cur.execute(SQL_COUNTS[table])
            out[table] = {lang: int(n) for lang, n in cur.fetchall()}
    return out


def print_counts(title, data, out):
    print(title, file=out)
    for table in TABLES:
        per_lang = data.get(table, {})
        gone = sum(n for lang, n in per_lang.items() if lang not in KEEP_LANGS)
        listing = ", ".join(f"{lang}={n}" for lang, n in sorted(per_lang.items())) or "(empty)"
        print(f"  {table}: {listing}  -> to delete: {gone}", file=out)


def export(conn, directory, out):
    os.makedirs(directory, exist_ok=True)
    with conn.transaction(), conn.cursor() as cur:
        for table in TABLES:
            cur.execute(SQL_EXPORT[table], {"keep": list(KEEP_LANGS)})
            rows = cur.fetchall()
            header = [col[0] for col in (cur.description or [])]
            path = os.path.join(directory, f"{table}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if header:
                    writer.writerow(header)
                writer.writerows(rows)
            print(f"exported {len(rows)} rows to {path}", file=out)


def delete(conn, out):
    """Both deletes in one transaction: all or nothing."""
    deleted = {}
    with conn.transaction(), conn.cursor() as cur:
        for table, sql in SQL_DELETE:
            cur.execute(sql, {"keep": list(KEEP_LANGS)})
            deleted[table] = cur.rowcount
    for table, n in deleted.items():
        print(f"deleted {n} rows from {table}", file=out)
    return deleted


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--export", metavar="DIR", help="write the rows to delete as CSV files in DIR")
    parser.add_argument("--execute", action="store_true", help="really delete (needs owner approval)")
    parser.add_argument(APPROVAL_FLAG, dest="approved", action="store_true",
                        help="confirms the owner approved deleting these rows")
    parser.add_argument("--env-file", metavar="PATH",
                        help="read DATABASE_URL from this file (never read unless given)")
    return parser.parse_args(argv)


def main(argv=None, connect=None, out=None):
    out = out or sys.stdout
    args = parse_args(argv)
    if args.execute and not args.approved:
        print(f"refusing to delete: --execute needs {APPROVAL_FLAG}", file=sys.stderr)
        return 2
    url = os.environ.get("DATABASE_URL")
    if args.env_file:
        url = read_env_file(args.env_file) or url
    if not url:
        print("DATABASE_URL is not set (environment, or --env-file PATH)", file=sys.stderr)
        return 2
    if connect is None:
        import psycopg

        def connect(u):
            return psycopg.connect(u, connect_timeout=10, autocommit=True, prepare_threshold=None)  # each transaction() block is its own BEGIN/COMMIT

    conn = connect(url)
    try:
        print_counts("Before:" if args.execute else "Dry run (nothing changes):", counts(conn), out)
        if args.export:
            export(conn, args.export, out)
        if args.execute:
            delete(conn, out)
            print_counts("After:", counts(conn), out)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
