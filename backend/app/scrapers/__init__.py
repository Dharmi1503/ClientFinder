import asyncio
import re

from .freelancer import scrape_freelancer
from .truelancer import scrape_truelancer
from .justdial import scrape_justdial
from .google_maps import scrape_google_maps
from .clutch import scrape_clutch


def _is_junk_name(name: str) -> bool:
    """Return True if name looks like a directory page, not a real company."""
    name_lower = name.lower().strip()
    if re.search(r'\.(com|in|org|net|co)$', name_lower):
        return True
    if re.match(r'^(list of|top \d+|\d+ best|best |all |find |get )', name_lower):
        return True
    if len(name_lower) < 4:
        return True
    return False


async def run_all_scrapers(query: str, city: str) -> list[dict]:
    """
    Orchestrator: run all 5 scrapers concurrently, deduplicate, and return
    a unified list of raw leads tagged with their source.
    """
    results = await asyncio.gather(
        scrape_freelancer(query, city),
        scrape_truelancer(query, city),
        scrape_justdial(query, city),
        scrape_google_maps(query, city),
        scrape_clutch(query, city),
        return_exceptions=True,
    )

    all_leads: list[dict] = []
    source_names = ["freelancer", "truelancer", "justdial", "google_maps", "clutch"]
    for source, res in zip(source_names, results):
        if isinstance(res, list):
            for lead in res:
                lead["source"] = lead.get("source", source)
            all_leads.extend(res)
        else:
            print(f"[SCRAPERS] {source} failed: {res}")

    # Deduplicate: prefer phone key, fall back to normalised company name
    unique: dict[str, dict] = {}
    for lead in all_leads:
        phone = lead.get("phone", "").strip()
        key = phone if phone else lead.get("company_name", "").strip().lower()
        if key and key not in unique:
            unique[key] = lead

    final = [l for l in unique.values() if not _is_junk_name(l.get("company_name", ""))]

    print(f"[SCRAPERS] {len(final)} unique leads from all sources")
    for l in final:
        print(f"  [{l.get('source','?'):12}] {l['company_name']} | {l.get('phone') or 'no phone'}")

    return final[:30]
