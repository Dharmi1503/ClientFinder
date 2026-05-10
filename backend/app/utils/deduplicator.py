"""
utils/deduplicator.py
======================
Duplicate Lead Guard
---------------------
Before enriching or scoring a lead, check if a lead with the
same (company_name + city) already exists in the database.

Why this matters:
  - Multiple scrapers often find the same company
  - Re-running a search would re-scrape the same leads
  - Saves Ollama LLM calls + avoids spamming the DB

Uses the database module so it's always in sync with the real data.
"""

import re
import sqlite3
from pathlib import Path

# Default DB path — can be overridden by passing db_path explicitly
_DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "clientfinder.db"


def _normalise(text: str) -> str:
    """
    Normalise company name / city for fuzzy comparison.
    Removes punctuation, lowercases, collapses spaces.
    e.g. "Apex Pvt. Ltd." → "apex pvt ltd"
    """
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)       # remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # collapse spaces
    # Strip common corporate suffixes that don't distinguish companies
    for suffix in ('pvt ltd', 'private limited', 'llp', 'inc', 'ltd'):
        text = re.sub(rf'\b{suffix}\b', '', text).strip()
    return text


def is_duplicate(
    company_name: str,
    city: str,
    db_path: str | Path | None = None,
) -> bool:
    """
    Return True if a lead with this (company_name, city) already exists
    in the database (case-insensitive, punctuation-tolerant).

    Args:
        company_name: Raw company name from scraper
        city:         City string from scraper
        db_path:      Path to SQLite DB file (defaults to clientfinder.db)

    Returns:
        True  → lead is already in DB, skip it
        False → lead is new, proceed with pipeline
    """
    db_path = Path(db_path) if db_path else _DEFAULT_DB

    # DB doesn't exist yet → definitely not a duplicate
    if not db_path.exists():
        return False

    norm_name = _normalise(company_name)
    norm_city = _normalise(city)

    if not norm_name:  # empty name → treat as not duplicate (validator will catch it)
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Fetch all (company_name, city) pairs and compare normalised
        # We do this in Python rather than SQL LIKE to handle punctuation differences
        cursor.execute("SELECT company_name, city FROM leads")
        rows = cursor.fetchall()
        conn.close()

        for db_name, db_city in rows:
            if (
                _normalise(db_name or "") == norm_name
                and _normalise(db_city or "") == norm_city
            ):
                return True

        return False

    except sqlite3.OperationalError:
        # Table doesn't exist yet → not a duplicate
        return False
    except Exception as e:
        print(f"[deduplicator] DB error: {e}")
        return False  # On error, let the lead through (fail open)


def batch_filter_duplicates(
    leads: list[dict],
    db_path: str | Path | None = None,
) -> list[dict]:
    """
    Filter a list of leads, removing any that already exist in the DB.
    More efficient than calling is_duplicate() per lead — loads DB once.

    Args:
        leads:   List of lead dicts (must have 'company_name' and 'location')
        db_path: Path to SQLite DB

    Returns:
        Filtered list of non-duplicate leads
    """
    db_path = Path(db_path) if db_path else _DEFAULT_DB

    if not db_path.exists():
        return leads  # Nothing in DB yet

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT company_name, city FROM leads")
        existing = {
            (_normalise(name or ""), _normalise(city or ""))
            for name, city in cursor.fetchall()
        }
        conn.close()
    except Exception as e:
        print(f"[deduplicator] batch load error: {e}")
        return leads  # Fail open

    new_leads = []
    skipped = 0
    for lead in leads:
        key = (
            _normalise(lead.get("company_name", "")),
            _normalise(lead.get("location", "")),
        )
        if key[0] and key not in existing:
            new_leads.append(lead)
        else:
            skipped += 1

    if skipped:
        print(f"[deduplicator] skipped {skipped} duplicate(s), {len(new_leads)} new leads")

    return new_leads
