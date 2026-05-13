"""
database.py
============
SQLite Database Layer for ClientFinder
----------------------------------------
Single source of truth for all lead data.

Table: leads
  All fields from the spec + internal tracking fields.

Functions:
  create_tables()        → initialise schema
  save_lead(lead)        → insert or update a lead
  get_all_leads(filters) → fetch with optional filters
  is_duplicate(name, city) → fast DB-level dedup check
  update_status(id, st)  → update pipeline status
  set_follow_up(id, date)→ set a follow-up date + notes
"""

import sqlite3
import json
from datetime import date, datetime
from pathlib import Path

from app.review_config import (
    LEAD_SCORE_THRESHOLD,
    LEAD_AUTO_REJECT_THRESHOLD,
    VALID_REVIEW_STATUSES,
    NOISY_SOURCES,
)
from app.utils.lead_input import sanitize_lead, validate_lead


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "clientfinder.db"

_VALID_STATUSES = {"New", "Contacted", "Replied", "Meeting", "Closed", "Dead"}
_VALID_REVIEW_ACTIONS = {"approved", "rejected"}


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent writes
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    -- Identity
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name        TEXT    NOT NULL,
    city                TEXT    NOT NULL DEFAULT '',
    industry            TEXT    DEFAULT '',

    -- Source
    source              TEXT    DEFAULT '',
    source_url          TEXT    DEFAULT '',
    contact_link        TEXT    DEFAULT '',

    -- Contact info
    phone               TEXT    DEFAULT '',
    email               TEXT    DEFAULT '',
    linkedin_url        TEXT    DEFAULT '',
    website             TEXT    DEFAULT '',
    website_alive       INTEGER DEFAULT 0,   -- 0/1 boolean

    -- AI Scores
    fit_score           INTEGER DEFAULT 0,
    intent_score        INTEGER DEFAULT 0,
    contact_score       INTEGER DEFAULT 0,
    composite_score     REAL    DEFAULT 0.0,

    -- AI Output
    label               TEXT    DEFAULT 'COLD',  -- HOT / WARM / COLD
    hot_reason          TEXT    DEFAULT '',
    pain_point          TEXT    DEFAULT '',
    buying_signals      TEXT    DEFAULT '',   -- JSON array of signal strings
    decision_maker      TEXT    DEFAULT '',
    company_size        TEXT    DEFAULT '',
    estimated_deal_size TEXT    DEFAULT '',
    speed_to_close      TEXT    DEFAULT '',

    -- Objections + Rebuttals
    objection_1         TEXT    DEFAULT '',
    rebuttal_1          TEXT    DEFAULT '',
    objection_2         TEXT    DEFAULT '',
    rebuttal_2          TEXT    DEFAULT '',

    -- Channel recommendation
    best_channel        TEXT    DEFAULT '',
    channel_reason      TEXT    DEFAULT '',

    -- Ready-to-send opener (from analyst)
    personalized_opener TEXT    DEFAULT '',

    -- Messages
    whatsapp_msg        TEXT    DEFAULT '',
    linkedin_msg        TEXT    DEFAULT '',
    email_subject       TEXT    DEFAULT '',
    email_msg           TEXT    DEFAULT '',

    -- Pipeline tracking
    status              TEXT    DEFAULT 'New',
    review_status       TEXT    DEFAULT 'pending_review',
    review_note         TEXT    DEFAULT NULL,
    flags               TEXT    DEFAULT '',
    follow_up_date      TEXT    DEFAULT '',
    notes               TEXT    DEFAULT '',

    -- Internal
    intent_signal       TEXT    DEFAULT '',
    description         TEXT    DEFAULT '',
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now'))
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_leads_city      ON leads (city);
CREATE INDEX IF NOT EXISTS idx_leads_label     ON leads (label);
CREATE INDEX IF NOT EXISTS idx_leads_status    ON leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_review    ON leads (review_status);
CREATE INDEX IF NOT EXISTS idx_leads_followup  ON leads (follow_up_date);
CREATE INDEX IF NOT EXISTS idx_leads_source    ON leads (source);
CREATE INDEX IF NOT EXISTS idx_leads_name_city ON leads (company_name, city);

CREATE TABLE IF NOT EXISTS review_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id      INTEGER NOT NULL,
    action       TEXT    NOT NULL,
    note         TEXT    DEFAULT '',
    reviewed_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_log_lead_id ON review_log (lead_id);

CREATE TABLE IF NOT EXISTS rejected_leads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_data     TEXT    NOT NULL,
    reasons      TEXT    NOT NULL,
    rejected_at  TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rejected_leads_rejected_at ON rejected_leads (rejected_at);

CREATE TABLE IF NOT EXISTS scraper_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT    NOT NULL,
    run_at           TEXT    DEFAULT (datetime('now')),
    leads_attempted  INTEGER NOT NULL DEFAULT 0,
    leads_saved      INTEGER NOT NULL DEFAULT 0,
    leads_rejected   INTEGER NOT NULL DEFAULT 0,
    success_rate     REAL    NOT NULL DEFAULT 0.0,
    status           TEXT    NOT NULL DEFAULT 'broken'
);

CREATE INDEX IF NOT EXISTS idx_scraper_runs_source_run_at ON scraper_runs (source, run_at DESC);

CREATE TABLE IF NOT EXISTS source_quality (
    source         TEXT PRIMARY KEY,
    total_leads    INTEGER NOT NULL DEFAULT 0,
    approved_leads INTEGER NOT NULL DEFAULT 0,
    quality_score  REAL    NOT NULL DEFAULT 0.0,
    last_updated   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS llm_health_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tier_used         INTEGER NOT NULL,
    lead_id           INTEGER,
    response_time_ms  INTEGER NOT NULL DEFAULT 0,
    success           INTEGER NOT NULL DEFAULT 0,
    logged_at         TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_llm_health_log_logged_at ON llm_health_log (logged_at DESC);
"""

_TRIGGER_UPDATED_AT = """
CREATE TRIGGER IF NOT EXISTS trg_leads_updated_at
AFTER UPDATE ON leads
BEGIN
    UPDATE leads SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""


def create_tables() -> None:
    """Create the leads table and indexes if they don't exist."""
    with _get_conn() as conn:
        conn.executescript(_CREATE_SQL)
        conn.executescript(_TRIGGER_UPDATED_AT)
        # Ensure all columns exist — safe to run on both new and existing DBs
        _ensure_column(conn, "leads", "review_status",          "TEXT DEFAULT 'pending_review'")
        _ensure_column(conn, "leads", "review_note",            "TEXT DEFAULT NULL")
        _ensure_column(conn, "leads", "flags",                  "TEXT DEFAULT ''")
        _ensure_column(conn, "leads", "client_readiness_score", "INTEGER DEFAULT 0")
        _ensure_column(conn, "leads", "pain_signals_json",      "TEXT DEFAULT ''")
        _ensure_column(conn, "leads", "pain_template",          "TEXT DEFAULT ''")
        _ensure_column(conn, "leads", "instagram_handle",       "TEXT DEFAULT ''")
    print("[database] Tables ready.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_json(value) -> str:
    """Safely convert a list/dict to a JSON string for TEXT column storage."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:1000]
    try:
        return json.dumps(value, ensure_ascii=False)[:1000]
    except Exception:
        return str(value)[:1000]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add a column if it doesn't exist already."""
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _log_rejected_lead(lead: dict, reasons: list[str]) -> None:
    """Persist rejected leads for manual inspection."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO rejected_leads (raw_data, reasons) VALUES (?, ?)",
            (
                json.dumps(lead, ensure_ascii=False, default=str),
                json.dumps(reasons, ensure_ascii=False),
            ),
        )


def compute_source_quality(source: str) -> float:
    """
    Compute approved_leads / total_leads * 100 for one source and upsert it.
    """
    source = (source or "").strip().lower()
    if not source:
        return 0.0

    with _get_conn() as conn:
        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total_leads,
                SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) AS approved_leads
            FROM leads
            WHERE LOWER(source) = ?
            """,
            (source,),
        ).fetchone()

        total_leads = int(stats["total_leads"] or 0)
        approved_leads = int(stats["approved_leads"] or 0)
        quality_score = round((approved_leads / total_leads) * 100, 2) if total_leads > 0 else 0.0

        conn.execute(
            """
            INSERT INTO source_quality (source, total_leads, approved_leads, quality_score, last_updated)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(source) DO UPDATE SET
                total_leads = excluded.total_leads,
                approved_leads = excluded.approved_leads,
                quality_score = excluded.quality_score,
                last_updated = excluded.last_updated
            """,
            (source, total_leads, approved_leads, quality_score),
        )

    return quality_score


def get_source_weight(source: str) -> float:
    """
    Return source downweight based on quality score.
    Default to 1.0 until there are at least 20 leads for that source.
    """
    source = (source or "").strip().lower()
    if not source:
        return 1.0

    with _get_conn() as conn:
        row = conn.execute(
            "SELECT total_leads, quality_score FROM source_quality WHERE source = ?",
            (source,),
        ).fetchone()

    if not row or int(row["total_leads"] or 0) < 20:
        return 1.0

    quality_score = float(row["quality_score"] or 0.0)
    if quality_score >= 70:
        return 1.0
    if quality_score >= 40:
        return 0.6
    return 0.3


def maybe_refresh_source_quality() -> None:
    """
    Refresh source quality automatically after every 50 saved leads.
    """
    with _get_conn() as conn:
        total = int(conn.execute("SELECT COUNT(*) AS total FROM leads").fetchone()["total"] or 0)
        if total == 0 or total % 50 != 0:
            return
        rows = conn.execute(
            "SELECT DISTINCT LOWER(source) AS source FROM leads WHERE TRIM(source) != ''"
        ).fetchall()

    for row in rows:
        compute_source_quality(row["source"])


def get_all_source_quality() -> list[dict]:
    """
    Return source quality rows with current source weight, worst first.
    """
    with _get_conn() as conn:
        existing = int(conn.execute("SELECT COUNT(*) AS total FROM source_quality").fetchone()["total"] or 0)
        if existing == 0:
            sources = conn.execute(
                "SELECT DISTINCT LOWER(source) AS source FROM leads WHERE TRIM(source) != ''"
            ).fetchall()
        else:
            sources = []

    for row in sources:
        compute_source_quality(row["source"])

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT source, total_leads, approved_leads, quality_score, last_updated
            FROM source_quality
            ORDER BY quality_score ASC, total_leads DESC, source ASC
            """
        ).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        item["weight"] = get_source_weight(item["source"])
        results.append(item)
    return results


def log_llm_health(tier_used: int, lead_id: int | None, response_time_ms: int, success: bool) -> None:
    """Persist one LLM tier usage event."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO llm_health_log (tier_used, lead_id, response_time_ms, success)
            VALUES (?, ?, ?, ?)
            """,
            (tier_used, lead_id, int(response_time_ms or 0), 1 if success else 0),
        )


def get_llm_health_summary() -> list[dict]:
    """Return usage count, avg response time, and failure rate per tier for the last 24h."""
    sql = """
        SELECT
            tier_used,
            COUNT(*) AS usage_count,
            AVG(response_time_ms) AS avg_response_time_ms,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS failure_rate
        FROM llm_health_log
        WHERE logged_at >= datetime('now', '-1 day')
        GROUP BY tier_used
        ORDER BY tier_used ASC
    """
    with _get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def compute_flags(lead: dict, score: float | None = None) -> list[str]:
    """
    Compute review flags for a lead.
    Returns a list like ['low_score', 'missing_contact', 'noisy_source'].
    """
    composite = float(score if score is not None else lead.get("composite_score", 0.0) or 0.0)
    flags: list[str] = []

    if composite < LEAD_SCORE_THRESHOLD:
        flags.append("low_score")

    has_contact = bool(
        (lead.get("phone") or "").strip()
        or (lead.get("email") or "").strip()
        or ((lead.get("website") or "").strip() and lead.get("website_alive"))
        or (lead.get("linkedin_url") or "").strip()
    )
    if not has_contact:
        flags.append("missing_contact")

    source = (lead.get("source") or "").strip().lower()
    if source in NOISY_SOURCES:
        flags.append("noisy_source")

    return flags


def _compute_review_status(score: float) -> str:
    """Assign review status from the lead score."""
    if score < LEAD_AUTO_REJECT_THRESHOLD:
        return "rejected"
    if score < LEAD_SCORE_THRESHOLD:
        return "pending_review"
    return "approved"


# ---------------------------------------------------------------------------
# Save / Upsert
# ---------------------------------------------------------------------------

def save_lead(lead: dict) -> int:
    """
    Insert a new lead into the DB.
    If (company_name, city) already exists → UPDATE that row instead.

    Returns the row id.

    Args:
        lead: Dict with any subset of the schema columns.
    """
    lead = sanitize_lead(lead)
    is_valid, errors = validate_lead(lead)
    if not is_valid:
        _log_rejected_lead(lead, errors)
        raise ValueError(f"lead rejected: {', '.join(errors)}")

    # Normalise booleans
    website_alive = 1 if lead.get("website_alive") else 0

    # Clamp scores to 0–100
    def _clamp(val, lo=0, hi=100):
        try:
            return max(lo, min(hi, int(val or 0)))
        except (TypeError, ValueError):
            return 0

    fit       = _clamp(lead.get("fit_score", 0))
    intent    = _clamp(lead.get("intent_score", lead.get("buying_intent_score", 0)))
    contact   = _clamp(lead.get("contact_score", lead.get("contactability_score", 0)))
    composite = float(lead.get("composite_score", 0.0) or 0.0)
    review_status = _compute_review_status(composite)
    flags = compute_flags(lead, score=composite)

    # Messages may be in a nested dict
    msgs = lead.get("messages") or {}
    whatsapp = lead.get("whatsapp_msg") or msgs.get("whatsapp") or ""
    linkedin = lead.get("linkedin_msg") or msgs.get("linkedin") or ""
    email_m  = lead.get("email_msg") or msgs.get("email_body") or ""

    row = {
        "company_name":        (lead.get("company_name") or "")[:200],
        "city":                (lead.get("location") or lead.get("city") or "")[:100],
        "industry":            (lead.get("industry") or lead.get("category") or "")[:150],
        "source":              (lead.get("source") or "")[:50],
        "source_url":          (lead.get("source_url") or "")[:500],
        "contact_link":        (lead.get("contact_link") or lead.get("source_url") or "")[:500],
        "phone":               (lead.get("phone") or "")[:30],
        "email":               (lead.get("email") or "")[:150],
        "linkedin_url":        (lead.get("linkedin_url") or "")[:300],
        "website":             (lead.get("website") or "")[:300],
        "website_alive":       website_alive,
        "fit_score":           fit,
        "intent_score":        intent,
        "contact_score":       contact,
        "composite_score":     composite,
        "label":               (lead.get("label") or lead.get("priority_tag") or "COLD")[:10],
        "hot_reason":          (lead.get("hot_reason") or lead.get("score_reason") or "")[:500],
        "pain_point":          (lead.get("pain_point") or "")[:300],
        "buying_signals":      _to_json(lead.get("buying_signals")),
        "decision_maker":      (lead.get("decision_maker") or "")[:150],
        "company_size":        (lead.get("company_size") or lead.get("company_size_tag") or "")[:50],
        "estimated_deal_size": (lead.get("estimated_deal_size") or lead.get("estimated_deal") or "")[:100],
        "speed_to_close":      (lead.get("speed_to_close") or "")[:20],
        "objection_1":         (lead.get("objection_1") or lead.get("objection_prediction") or "")[:300],
        "rebuttal_1":          (lead.get("rebuttal_1") or "")[:300],
        "objection_2":         (lead.get("objection_2") or "")[:300],
        "rebuttal_2":          (lead.get("rebuttal_2") or "")[:300],
        "best_channel":        (lead.get("best_channel") or "")[:30],
        "channel_reason":      (lead.get("channel_reason") or "")[:200],
        "personalized_opener": (lead.get("personalized_opener") or "")[:1000],
        "whatsapp_msg":        whatsapp[:1000],
        "linkedin_msg":        linkedin[:1000],
        "email_subject":       (lead.get("email_subject") or msgs.get("email_subject") or "")[:200],
        "email_msg":           email_m[:1000],
        "status":              (lead.get("status") or "New")[:20],
        "review_status":       (lead.get("review_status") or review_status)[:20],
        "review_note":         (lead.get("review_note") or "")[:1000] or None,
        "flags":               _to_json(lead.get("flags") or flags),
        "follow_up_date":      (lead.get("follow_up_date") or "")[:10],
        "notes":               (lead.get("notes") or "")[:1000],
        "intent_signal":       (lead.get("intent_signal") or "")[:500],
        "description":         (lead.get("description") or lead.get("snippet") or "")[:500],
    }

    with _get_conn() as conn:
        # Check if row exists
        cur = conn.execute(
            "SELECT id FROM leads WHERE company_name = ? AND city = ? LIMIT 1",
            (row["company_name"], row["city"]),
        )
        existing = cur.fetchone()

        if existing:
            row_id = existing["id"]
            # Update non-empty fields only (don't overwrite good data with empty)
            set_clauses = []
            values = []
            for col, val in row.items():
                if col in ("company_name", "city"):
                    continue  # these are the key — don't update
                if val or val == 0:   # allow 0 scores to update
                    set_clauses.append(f"{col} = ?")
                    values.append(val)
            if set_clauses:
                values.append(row_id)
                conn.execute(
                    f"UPDATE leads SET {', '.join(set_clauses)} WHERE id = ?",
                    values,
                )
            return row_id
        else:
            cols = ", ".join(row.keys())
            placeholders = ", ".join("?" * len(row))
            cur = conn.execute(
                f"INSERT INTO leads ({cols}) VALUES ({placeholders})",
                list(row.values()),
            )
            row_id = cur.lastrowid

    maybe_refresh_source_quality()
    return row_id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_all_leads(
    city: str | None = None,
    category: str | None = None,
    label: str | None = None,
    min_score: int = 0,
    max_score: int = 100,
    review_status: str | None = None,
    source: str | None = None,
    has_email: bool = False,
    has_phone: bool = False,
    sort_by: str = "recent",
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[dict]]:
    """
    Fetch leads from DB with dynamic filters and pagination.

    Returns:
        (total_count, results)
    """
    conditions: list[str] = ["composite_score >= ?", "composite_score <= ?"]
    values: list = [min_score, max_score]

    if city:
        conditions.append("LOWER(city) LIKE ?")
        values.append(f"%{city.strip().lower()}%")

    if category:
        conditions.append("LOWER(industry) LIKE ?")
        values.append(f"%{category.strip().lower()}%")

    if label:
        conditions.append("UPPER(label) = ?")
        values.append(label.strip().upper())

    if review_status:
        conditions.append("LOWER(review_status) = ?")
        values.append(review_status.strip().lower())

    if source:
        conditions.append("LOWER(source) = ?")
        values.append(source.strip().lower())

    if has_email:
        conditions.append("email IS NOT NULL AND TRIM(email) != ''")

    if has_phone:
        conditions.append("phone IS NOT NULL AND TRIM(phone) != ''")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    sort_mode = (sort_by or "recent").strip().lower()
    if sort_mode == "score":
        order_by = "ORDER BY composite_score DESC, created_at DESC"
    elif sort_mode == "oldest":
        order_by = "ORDER BY created_at ASC, id ASC"
    else:
        order_by = "ORDER BY created_at DESC, composite_score DESC"

    count_sql = f"SELECT COUNT(*) AS total FROM leads {where}"
    data_sql = f"""
        SELECT * FROM leads
        {where}
        {order_by}
        LIMIT ? OFFSET ?
    """

    with _get_conn() as conn:
        total = conn.execute(count_sql, values).fetchone()["total"]
        rows = conn.execute(data_sql, [*values, page_size, offset]).fetchall()

    return total, [dict(row) for row in rows]


def get_review_queue(limit: int = 200) -> list[dict]:
    """Return leads waiting for human review, highest score first."""
    sql = """
        SELECT * FROM leads
        WHERE review_status = 'pending_review'
        ORDER BY composite_score DESC, created_at DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_rejected_leads(limit: int = 200) -> list[dict]:
    """Return the most recently rejected leads and reasons."""
    sql = """
        SELECT * FROM rejected_leads
        ORDER BY rejected_at DESC, id DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(row) for row in rows]


def log_scraper_run(source: str, attempted: int, saved: int, rejected: int) -> None:
    """
    Persist a scraper health snapshot for one run.
    success_rate = saved / attempted * 100
    """
    attempted = max(0, int(attempted or 0))
    saved = max(0, int(saved or 0))
    rejected = max(0, int(rejected or 0))

    success_rate = round((saved / attempted) * 100, 2) if attempted > 0 else 0.0
    if success_rate >= 70:
        status = "healthy"
    elif success_rate >= 30:
        status = "degraded"
    else:
        status = "broken"

    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO scraper_runs
                (source, leads_attempted, leads_saved, leads_rejected, success_rate, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, attempted, saved, rejected, success_rate, status),
        )

    if status == "broken":
        print(
            f"SOURCE [{source}] success rate dropped to {success_rate:.2f}%. "
            f"Possible site structure change."
        )


def get_scraper_health() -> list[dict]:
    """Return the latest run stats for all sources."""
    sql = """
        SELECT sr.*
        FROM scraper_runs sr
        INNER JOIN (
            SELECT source, MAX(id) AS latest_id
            FROM scraper_runs
            GROUP BY source
        ) latest
          ON sr.id = latest.latest_id
        ORDER BY sr.source
    """
    with _get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def get_scraper_health_for_source(source: str, limit: int = 10) -> list[dict]:
    """Return the last N scraper runs for one source."""
    sql = """
        SELECT *
        FROM scraper_runs
        WHERE LOWER(source) = ?
        ORDER BY run_at DESC, id DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (source.strip().lower(), limit)).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Duplicate check (DB-level — fast)
# ---------------------------------------------------------------------------

def is_duplicate(company_name: str, city: str) -> bool:
    """
    Fast DB-level duplicate check.
    Uses exact match on company_name + city (case-insensitive via COLLATE NOCASE).
    For fuzzy matching, use utils/deduplicator.py instead.

    Returns True if already exists.
    """
    if not DB_PATH.exists():
        return False
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM leads WHERE company_name = ? COLLATE NOCASE "
                "AND city = ? COLLATE NOCASE LIMIT 1",
                (company_name.strip(), city.strip()),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pipeline tracking
# ---------------------------------------------------------------------------

def update_status(lead_id: int, status: str) -> None:
    """
    Update the pipeline status of a lead.
    If status is 'Closed' or 'Dead', automatically logs to the feedback loop
    so the system can learn which sources produce real clients over time.

    Valid statuses: New, Contacted, Replied, Meeting, Closed, Dead
    """
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. "
            f"Must be one of: {', '.join(sorted(_VALID_STATUSES))}"
        )
    with _get_conn() as conn:
        conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?",
            (status, lead_id),
        )

    # Auto-log outcome for feedback loop calibration
    if status in ("Closed", "Dead"):
        try:
            from app.utils.feedback import log_outcome
            log_outcome(lead_id, status)
        except Exception as e:
            print(f"[database] feedback log error: {e}")


def set_follow_up(lead_id: int, follow_up_date: str, notes: str = "") -> None:
    """
    Set or update the follow-up date + notes for a lead.

    Args:
        lead_id:        Row ID in leads table
        follow_up_date: Date string in YYYY-MM-DD format
        notes:          Optional note to append (doesn't overwrite existing)
    """
    # Validate date format
    try:
        datetime.strptime(follow_up_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"follow_up_date must be YYYY-MM-DD, got '{follow_up_date}'")

    with _get_conn() as conn:
        if notes:
            # Append to existing notes
            conn.execute(
                "UPDATE leads SET follow_up_date = ?, "
                "notes = CASE WHEN notes = '' THEN ? ELSE notes || ' | ' || ? END "
                "WHERE id = ?",
                (follow_up_date, notes, notes, lead_id),
            )
        else:
            conn.execute(
                "UPDATE leads SET follow_up_date = ? WHERE id = ?",
                (follow_up_date, lead_id),
            )


def get_followups_today() -> list[dict]:
    """Return all leads with a follow-up scheduled for today."""
    today = date.today().isoformat()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE follow_up_date = ? ORDER BY composite_score DESC",
            (today,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_review(lead_id: int, action: str, note: str = "") -> None:
    """
    Approve or reject a lead and append a review note.
    Also writes an immutable record into review_log.
    """
    action = action.strip().lower()
    if action not in _VALID_REVIEW_ACTIONS:
        raise ValueError(
            f"Invalid action '{action}'. Must be one of: {', '.join(sorted(_VALID_REVIEW_ACTIONS))}"
        )

    with _get_conn() as conn:
        lead_row = conn.execute("SELECT source FROM leads WHERE id = ? LIMIT 1", (lead_id,)).fetchone()
        if not lead_row:
            raise ValueError(f"Lead {lead_id} not found.")

        conn.execute(
            "UPDATE leads SET review_status = ?, review_note = ? WHERE id = ?",
            (action, note[:1000] or None, lead_id),
        )
        conn.execute(
            "INSERT INTO review_log (lead_id, action, note) VALUES (?, ?, ?)",
            (lead_id, action, note[:1000]),
        )

    compute_source_quality(lead_row["source"] or "")


# ---------------------------------------------------------------------------
# Convenience: initialise on import if needed
# ---------------------------------------------------------------------------

def ensure_db() -> None:
    """Safe to call repeatedly — only creates tables if missing."""
    create_tables()
