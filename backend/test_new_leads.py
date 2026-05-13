import asyncio
import sqlite3
import sys

sys.path.append(".")

from app.pipeline import run_pipeline


async def test_new_leads():
    industry = "interior design"
    city = "Surat"

    print(f"Starting pipeline for {industry} in {city}...")

    result = await run_pipeline(
        service="AI automation and website development",
        city=city,
        industry=industry,
        max_leads=10,
        fast_mode=False,
    )

    print("\n=== RESULTS ===")
    print(f'Total scraped raw:      {result.get("total_scraped_raw", 0)}')
    print(f'Total after prefilter:  {result.get("total_after_prefilter", 0)}')
    print(f'Total after dedup:      {result.get("total_after_dedup", 0)}')
    print(f'Total after enrichment: {result.get("total_after_enrichment", 0)}')
    print(f'Total saved:            {result.get("total_saved", 0)}')
    print(f'HOT: {result.get("hot", 0)} | WARM: {result.get("warm", 0)} | COLD: {result.get("cold", 0)}')

    conn = sqlite3.connect("data/clientfinder.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT company_name, source, composite_score, label, email
        FROM leads
        WHERE industry = ? AND city = ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (industry, city),
    )

    print(f"\nLast 5 {industry} leads in {city}:")
    for row in cursor.fetchall():
        print(f"  {row[0]} | {row[1]} | score={row[2]} | {row[3]} | email={row[4]}")

    conn.close()


asyncio.run(test_new_leads())
