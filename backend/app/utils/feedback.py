"""
utils/feedback.py
==================
Feedback Loop & Score Calibration
-----------------------------------
Problem: A lead that closes and a lead that ghosts look identical
forever. The system can't learn which sources produce real clients.

Solution: Every time a lead status changes to Closed or Dead,
we log the outcome. Over time we can compute:
  - Close rate by source    (Freelancer closes 40%, JustDial 12%)
  - Close rate by industry  (hospitals close faster than retail)
  - Avg deal size by source

These become SCORE FLOOR ADJUSTMENTS in ai.py — automatically
making the system smarter as data accumulates.

Usage:
  # When you mark a lead closed:
  log_outcome(lead_id, "Closed")

  # Get calibration data for the AI:
  floors = get_adjusted_score_floors()
  # → {"freelancer": {"intent_boost": +15, "min_intent": 70}, ...}

  # Print a report:
  print_calibration_report()
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "clientfinder.db"

_OUTCOME_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS outcome_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL,
    company_name    TEXT    DEFAULT '',
    city            TEXT    DEFAULT '',
    source          TEXT    DEFAULT '',
    industry        TEXT    DEFAULT '',
    label_at_close  TEXT    DEFAULT '',   -- HOT/WARM/COLD when we first found it
    fit_score       INTEGER DEFAULT 0,
    intent_score    INTEGER DEFAULT 0,
    contact_score   INTEGER DEFAULT 0,
    composite_score REAL    DEFAULT 0.0,
    outcome         TEXT    NOT NULL,     -- 'Closed' or 'Dead'
    days_to_outcome INTEGER DEFAULT 0,   -- days from created_at to outcome
    logged_at       TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_outcome_source   ON outcome_log (source);
CREATE INDEX IF NOT EXISTS idx_outcome_industry ON outcome_log (industry);
CREATE INDEX IF NOT EXISTS idx_outcome_outcome  ON outcome_log (outcome);
"""


def _ensure_outcome_table():
    """Create outcome_log table if it doesn't exist."""
    if not DB_PATH.exists():
        return
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.executescript(_OUTCOME_TABLE_SQL)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[feedback] Table creation error: {e}")


def log_outcome(lead_id: int, outcome: str) -> bool:
    """
    Log the outcome of a lead when its status changes to Closed or Dead.

    Call this from update_status() or the API endpoint whenever
    status is set to 'Closed' or 'Dead'.

    Args:
        lead_id: DB row ID of the lead
        outcome: 'Closed' (won) or 'Dead' (lost/ghosted)

    Returns:
        True if logged successfully, False otherwise.
    """
    if outcome not in ("Closed", "Dead"):
        return False

    _ensure_outcome_table()

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Fetch lead details
        lead = conn.execute(
            """SELECT company_name, city, source, industry, label,
                      fit_score, intent_score, contact_score, composite_score,
                      created_at
               FROM leads WHERE id = ?""",
            (lead_id,)
        ).fetchone()

        if not lead:
            conn.close()
            print(f"[feedback] Lead id={lead_id} not found")
            return False

        # Calculate days from creation to outcome
        days_to_outcome = 0
        try:
            created = datetime.fromisoformat(lead["created_at"])
            days_to_outcome = (datetime.utcnow() - created).days
        except Exception:
            pass

        # Insert into outcome_log
        conn.execute("""
            INSERT INTO outcome_log
              (lead_id, company_name, city, source, industry, label_at_close,
               fit_score, intent_score, contact_score, composite_score,
               outcome, days_to_outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_id,
            lead["company_name"],
            lead["city"],
            lead["source"],
            lead["industry"],
            lead["label"],
            lead["fit_score"],
            lead["intent_score"],
            lead["contact_score"],
            lead["composite_score"],
            outcome,
            days_to_outcome,
        ))
        conn.commit()
        conn.close()

        print(f"[feedback] Logged: '{lead['company_name']}' → {outcome} ({days_to_outcome}d)")
        return True

    except Exception as e:
        print(f"[feedback] log_outcome error: {e}")
        return False


def get_calibration_data() -> dict:
    """
    Compute close rates and avg scores by source and industry.

    Returns a nested dict:
    {
      "by_source": {
        "freelancer": {
          "total": 45, "closed": 18, "close_rate": 0.40,
          "avg_days_to_close": 12, "avg_composite_at_close": 78.5
        },
        ...
      },
      "by_industry": {...},
      "total_outcomes": 120,
      "total_closed": 45,
      "overall_close_rate": 0.375
    }
    """
    _ensure_outcome_table()

    if not DB_PATH.exists():
        return {"total_outcomes": 0, "by_source": {}, "by_industry": {}}

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM outcome_log ORDER BY logged_at DESC"
        ).fetchall()
        conn.close()
    except Exception as e:
        print(f"[feedback] calibration error: {e}")
        return {"total_outcomes": 0, "by_source": {}, "by_industry": {}}

    if not rows:
        return {"total_outcomes": 0, "by_source": {}, "by_industry": {}}

    # Aggregate by source
    by_source: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "closed": 0, "total_days": 0, "total_composite": 0.0
    })
    # Aggregate by industry
    by_industry: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "closed": 0
    })

    total = 0
    total_closed = 0

    for row in rows:
        source   = row["source"] or "unknown"
        industry = row["industry"] or "unknown"
        is_closed = row["outcome"] == "Closed"

        by_source[source]["total"]            += 1
        by_source[source]["total_days"]       += row["days_to_outcome"] or 0
        by_source[source]["total_composite"]  += float(row["composite_score"] or 0)
        if is_closed:
            by_source[source]["closed"] += 1

        by_industry[industry]["total"] += 1
        if is_closed:
            by_industry[industry]["closed"] += 1

        total += 1
        if is_closed:
            total_closed += 1

    # Build final result with rates
    source_result = {}
    for src, d in by_source.items():
        t = d["total"]
        c = d["closed"]
        source_result[src] = {
            "total":                t,
            "closed":               c,
            "close_rate":           round(c / t, 3) if t > 0 else 0.0,
            "avg_days_to_close":    round(d["total_days"] / t) if t > 0 else 0,
            "avg_composite":        round(d["total_composite"] / t, 1) if t > 0 else 0.0,
        }

    industry_result = {}
    for ind, d in by_industry.items():
        t = d["total"]
        c = d["closed"]
        industry_result[ind] = {
            "total":      t,
            "closed":     c,
            "close_rate": round(c / t, 3) if t > 0 else 0.0,
        }

    return {
        "total_outcomes":    total,
        "total_closed":      total_closed,
        "overall_close_rate": round(total_closed / total, 3) if total > 0 else 0.0,
        "by_source":         source_result,
        "by_industry":       industry_result,
        "as_of":             date.today().isoformat(),
    }


def get_adjusted_score_floors() -> dict:
    """
    Convert calibration data into score floor adjustments for ai.py.

    Sources with high close rates get an intent_boost (+N to intent_score floor).
    Sources with low close rates get a penalty.

    Returns:
    {
      "freelancer":  {"intent_boost": +15, "floor_note": "40% close rate (18/45)"},
      "justdial":    {"intent_boost": -5,  "floor_note": "12% close rate (3/25)"},
      ...
      "has_data":    True,
      "min_outcomes_for_calibration": 10   — need at least 10 samples to trust
    }
    """
    cal = get_calibration_data()
    floors = {
        "has_data": cal.get("total_outcomes", 0) >= 10,
        "min_outcomes_for_calibration": 10,
        "overall_close_rate": cal.get("overall_close_rate", 0.0),
    }

    if not floors["has_data"]:
        floors["note"] = (
            f"Only {cal.get('total_outcomes', 0)} outcomes recorded. "
            f"Need 10+ to calibrate. Using default scoring."
        )
        return floors

    overall_rate = cal.get("overall_close_rate", 0.0)
    by_source = cal.get("by_source", {})

    for source, data in by_source.items():
        if data["total"] < 5:
            # Not enough data for this source
            floors[source] = {
                "intent_boost": 0,
                "floor_note": f"Insufficient data ({data['total']} outcomes)",
            }
            continue

        rate = data["close_rate"]
        # Boost/penalise relative to overall
        diff = rate - overall_rate
        boost = round(diff * 50)   # e.g. +0.20 → +10 points; -0.15 → -7 points
        boost = max(-20, min(+25, boost))   # cap at ±25

        floors[source] = {
            "intent_boost": boost,
            "close_rate":   rate,
            "floor_note":   (
                f"{rate*100:.0f}% close rate "
                f"({data['closed']}/{data['total']}) | "
                f"avg {data['avg_days_to_close']}d to close"
            ),
        }

    return floors


def print_calibration_report() -> None:
    """Print a human-readable calibration report to stdout."""
    cal  = get_calibration_data()
    adj  = get_adjusted_score_floors()

    print("\n" + "=" * 60)
    print(f"CLIENTFINDER — CALIBRATION REPORT ({cal.get('as_of', 'today')})")
    print("=" * 60)
    print(f"Total outcomes logged : {cal['total_outcomes']}")
    print(f"Total closed (won)    : {cal['total_closed']}")
    print(f"Overall close rate    : {cal['overall_close_rate']*100:.1f}%")

    if not adj.get("has_data"):
        print(f"\n⚠  {adj.get('note', 'Not enough data yet.')}")
        print("=" * 60)
        return

    print("\n── By Source ──")
    for src, d in sorted(cal["by_source"].items(), key=lambda x: -x[1]["close_rate"]):
        boost = adj.get(src, {}).get("intent_boost", 0)
        bar   = "▓" * d["closed"] + "░" * (d["total"] - d["closed"])
        print(
            f"  {src:15} {bar[:20]:20} "
            f"{d['close_rate']*100:5.1f}%  "
            f"(score adj: {'+' if boost >= 0 else ''}{boost})"
        )

    print("\n── By Industry ──")
    for ind, d in sorted(cal["by_industry"].items(), key=lambda x: -x[1]["close_rate"])[:8]:
        print(f"  {ind[:25]:26} {d['close_rate']*100:5.1f}%  ({d['closed']}/{d['total']})")

    print("=" * 60 + "\n")
