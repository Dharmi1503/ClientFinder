#!/usr/bin/env python3
"""
scripts/source_report.py
========================
Generates a performance report for each lead source in the ClientFinder DB.
Includes Health Score, Smart Denominator, and Sync Monitoring.
"""

import sqlite3
from pathlib import Path

# Path to the database
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "clientfinder.db"

def get_report():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    # --- 0. Global DB Health Score ---
    raw_total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    if raw_total == 0:
        print("\n[!] Database is empty. Run some scrapers first.")
        return

    # Unique across all fields that define a single business
    unique_total = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT company_name, city, phone, email FROM leads
        )
    """).fetchone()[0]
    
    health_pct = (unique_total / raw_total) * 100
    overlap_pct = 100 - health_pct

    print("\n" + "="*80)
    print(f" CLIENTFINDER PERFORMANCE DASHBOARD")
    print(f" DB Health: {health_pct:.1f}% ({overlap_pct:.1f}% overlap)")
    print("="*80)
    
    # --- 1. Fetch Source Aggregates (Scraper Runs) ---
    scraper_data = {}
    total_runs = 0
    total_attempted = 0
    
    runs = conn.execute("""
        SELECT 
            source, 
            SUM(leads_attempted) as attempted,
            SUM(leads_rejected) as scraper_rejected,
            COUNT(*) as run_count
        FROM scraper_runs
        GROUP BY source
    """).fetchall()
    
    for row in runs:
        src = row['source']
        scraper_data[src] = {
            'attempted': row['attempted'] or 0,
            'scraper_rejected': row['scraper_rejected'] or 0,
            'runs': row['run_count']
        }
        total_runs += row['run_count']
        total_attempted += (row['attempted'] or 0)

    # --- 2. Fetch Detailed Metadata per Source ---
    # We fetch labels and rejection counts
    all_sources_q = conn.execute("SELECT DISTINCT source FROM leads").fetchall()
    all_sources = sorted(set([r['source'] for r in all_sources_q] + list(scraper_data.keys())))
    
    report_rows = []
    sync_issues_count = 0

    for src in all_sources:
        # Get lead counts for this source
        counts = conn.execute("""
            SELECT 
                label,
                COUNT(DISTINCT company_name || city || COALESCE(phone, '') || COALESCE(email, '')) as cnt
            FROM leads 
            WHERE source = ?
            GROUP BY label
        """, (src,)).fetchall()
        
        cd = {'HOT': 0, 'WARM': 0, 'COLD': 0}
        for r in counts:
            if r['label'] in cd:
                cd[r['label']] = r['cnt']
        
        # Get post-scrape rejections
        post_rejected = conn.execute("""
            SELECT COUNT(DISTINCT company_name || city || COALESCE(phone, '') || COALESCE(email, '')) 
            FROM leads WHERE source = ? AND review_status = 'rejected'
        """, (src,)).fetchone()[0] or 0

        # Get total row count in DB for this source (to identify overlaps/internal dupes)
        rows_in_db = conn.execute("SELECT COUNT(*) FROM leads WHERE source = ?", (src,)).fetchone()[0]
        
        # Calculate Overlap logic: 
        # (Total rows in source) - (Unique leads in source)
        unique_in_source = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT company_name, city, phone, email FROM leads WHERE source = ?
            )
        """, (src,)).fetchone()[0]
        
        overlap_count = rows_in_db - unique_in_source
        overlap_pct_src = (overlap_count / rows_in_db * 100) if rows_in_db > 0 else 0
        
        # --- SMART DENOMINATOR ---
        sd = scraper_data.get(src, {'attempted': 0, 'scraper_rejected': 0, 'runs': 0})
        # denominator = MAX(leads_attempted, total_unique_leads_in_db)
        # Note: we use unique leads in DB for the check to avoid inflating denominator with garbage
        denom = max(sd['attempted'], (cd['HOT'] + cd['WARM'] + cd['COLD'] + post_rejected))
        
        # --- SYNC GAP WARNING ---
        gap = abs(sd['attempted'] - rows_in_db)
        gap_ratio = gap / max(sd['attempted'], rows_in_db) if max(sd['attempted'], rows_in_db) > 0 else 0
        is_warn = gap_ratio > 0.2
        if is_warn: sync_issues_count += 1
        
        def pct(part):
            return (part / denom * 100) if denom > 0 else 0

        total_rejected = sd['scraper_rejected'] + post_rejected

        report_rows.append({
            'source': src,
            'total': denom,
            'hot': cd['HOT'], 'hot_pct': pct(cd['HOT']),
            'warm': cd['WARM'], 'warm_pct': pct(cd['WARM']),
            'cold': cd['COLD'], 'cold_pct': pct(cd['COLD']),
            'reject_pct': pct(total_rejected),
            'overlap_info': f"{overlap_count} overlapping ({overlap_pct_src:.1f}%)",
            'sync': "WARN" if is_warn else "OK",
            'sync_msg': "[LOGGING OUT OF SYNC]" if is_warn else ""
        })

    # --- 3. Print Data Sanity Check Section ---
    print(" DATA SANITY CHECK")
    print("-" * 80)
    print(f"  > Total Raw Leads:           {raw_total}")
    print(f"  > Total Unique Leads:        {unique_total}")
    print(f"  > Source Overlap Breakdown:")
    for r in report_rows:
        if "overlapping" in r['overlap_info'] and not r['overlap_info'].startswith("0"):
            print(f"    - {r['source']:<15}: {r['overlap_info']}")
    print("-" * 80)

    # --- 4. Print Table ---
    h = f"{'SOURCE':<15} | {'VOL':<6} | {'SYNC':<5} | {'HOT (%)':<12} | {'WARM (%)':<12} | {'COLD (%)':<12} | {'REJ %'}"
    sep = "-" * len(h)
    print("\n" + h)
    print(sep)
    
    for r in report_rows:
        hot_s  = f"{r['hot']} ({r['hot_pct']:>4.1f}%)"
        warm_s = f"{r['warm']} ({r['warm_pct']:>4.1f}%)"
        cold_s = f"{r['cold']} ({r['cold_pct']:>4.1f}%)"
        
        print(f"{r['source']:<15} | {r['total']:<6} | {r['sync']:<5} | {hot_s:<12} | {warm_s:<12} | {cold_s:<12} | {r['reject_pct']:>5.1f}% {r['sync_msg']}")
    
    print(sep)

    # --- 5. Summary ---
    if report_rows:
        # Only consider sources with at least 10 leads for quality insights
        qualified = [r for r in report_rows if r['total'] >= 10]
        avg_leads = total_attempted / total_runs if total_runs > 0 else 0
        
        print("\nQUICK INSIGHTS")
        if qualified:
            best_src = max(qualified, key=lambda x: x['hot_pct'])
            worst_src = min(qualified, key=lambda x: x['hot_pct'])
            print(f"  > Best Source:        {best_src['source']} ({best_src['hot_pct']:.1f}% HOT)")
            print(f"  > Worst Source:       {worst_src['source']} ({worst_src['hot_pct']:.1f}% HOT)")
        else:
            print(f"  > Best/Worst Source:  Not enough data (requires 10+ leads)")

        print(f"  > Pipeline Runs:      {total_runs}")
        print(f"  > Avg Lead Yield:     {avg_leads:.1f} per run")
        print(f"  > Sync Issues:        {sync_issues_count} source(s) detected")
    
    print("="*80 + "\n")
    conn.close()

if __name__ == "__main__":
    get_report()
