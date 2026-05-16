import sqlite3
from pathlib import Path

db_path = Path("data/clientfinder.db")
if not db_path.parent.exists():
    db_path.parent.mkdir(parents=True)

conn = sqlite3.connect(str(db_path))
conn.execute("CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, name TEXT DEFAULT '', created_by TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')), is_active INTEGER NOT NULL DEFAULT 1)")
try:
    conn.execute("INSERT OR IGNORE INTO api_keys (key, name, created_by, is_active) VALUES (?, ?, ?, ?)", ("cf_D6yNH96rfM0YdVkEe12neND4rYYzU3E-FEqZHnimw8A", "User Key", "admin", 1))
    conn.commit()
    print("Key added successfully!")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
