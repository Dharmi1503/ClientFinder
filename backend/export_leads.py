import sqlite3, csv
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "clientfinder.db"
OUT_PATH = Path(__file__).resolve().parent / "mock_leads_export.csv"

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT
        id,
        company_name         AS business_name,
        city,
        industry             AS service_needed,
        label                AS lead_tier,
        composite_score      AS lead_score,
        phone,
        email,
        website,
        CASE website_alive WHEN 1 THEN 'Live' ELSE 'Missing' END AS website_status,
        source,
        decision_maker,
        pain_point           AS ai_recommendation,
        description          AS industry_context,
        status,
        created_at
    FROM leads
    ORDER BY composite_score DESC
""").fetchall()

with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows([dict(r) for r in rows])

print(f"Exported {len(rows)} leads -> {OUT_PATH}")
