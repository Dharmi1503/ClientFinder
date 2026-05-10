"""
migrate_db.py
=============
One-shot migration — adds any missing columns to the live DB.
Safe to run multiple times (checks before altering).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "clientfinder.db"

MIGRATIONS = [
    ("review_status",          "TEXT DEFAULT 'pending_review'"),
    ("review_note",            "TEXT DEFAULT NULL"),
    ("flags",                  "TEXT DEFAULT ''"),
    ("client_readiness_score", "INTEGER DEFAULT 0"),
    ("pain_signals_json",      "TEXT DEFAULT ''"),
    ("pain_template",          "TEXT DEFAULT ''"),
    ("instagram_handle",       "TEXT DEFAULT ''"),
]

def run():
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH} — it will be created fresh on first run.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    existing = {r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()}
    print(f"Existing columns: {len(existing)}")

    added = []
    for col, ddl in MIGRATIONS:
        if col not in existing:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {ddl}")
            added.append(col)
            print(f"  [+] Added column: {col}")
        else:
            print(f"  [=] Already exists: {col}")

    conn.commit()
    conn.close()

    if added:
        print(f"\nMigration complete — added {len(added)} column(s): {', '.join(added)}")
    else:
        print("\nNo changes needed — DB is up to date.")

if __name__ == "__main__":
    run()
