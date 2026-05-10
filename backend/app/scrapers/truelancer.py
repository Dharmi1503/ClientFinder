"""
scrapers/truelancer.py — v2
============================
Fixes applied:
  - DDG results 10→25, retry 3 with backoff
  - City alias map
  - Multi-query: 3 query variants
  - Dedup by name+city (was absent entirely)
  - `industry` field added (was missing)
  - Budget regex: added lakh/crore/K patterns
  - Email extraction from snippets
  - URL filter strict (truelancer.com only)
  - `source_url` domain validated per result
"""

import asyncio
import re
from app.database import log_scraper_run

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


# ---------------------------------------------------------------------------
# City alias map
# ---------------------------------------------------------------------------
_CITY_ALIASES: dict[str, list[str]] = {
    "mumbai":    ["mumbai", "bombay", "navi mumbai", "thane"],
    "delhi":     ["delhi", "new delhi", "ncr", "gurgaon", "noida"],
    "bangalore": ["bangalore", "bengaluru", "blr"],
    "hyderabad": ["hyderabad", "secunderabad"],
    "chennai":   ["chennai", "madras"],
    "kolkata":   ["kolkata", "calcutta"],
    "pune":      ["pune"],
    "ahmedabad": ["ahmedabad", "amdavad"],
    "jaipur":    ["jaipur"],
    "surat":     ["surat"],
}

def _city_primary(city: str) -> str:
    key = city.lower().strip()
    for canonical, aliases in _CITY_ALIASES.items():
        if key in aliases or key == canonical:
            return canonical.title()
    return city


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ddg_search(query: str, max_results: int = 25) -> list[dict]:
    if not DDGS_AVAILABLE:
        return []
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            print(f"[truelancer] DDG attempt {attempt+1} error: {e}")
            if attempt < 2:
                import time; time.sleep(1.5 * (attempt + 1))
    return []


def _extract_budget(text: str) -> str:
    """Extract budget: handles ₹, INR, lakh, crore, K shorthand."""
    # Lakh / crore
    lakh_m = re.search(r'(?:INR|₹|Rs\.?)\s?(\d+(?:\.\d+)?)\s*(?:lakh|lac)', text, re.IGNORECASE)
    if lakh_m:
        return f"₹{lakh_m.group(1)} Lakh"
    crore_m = re.search(r'(?:INR|₹|Rs\.?)\s?(\d+(?:\.\d+)?)\s*crore', text, re.IGNORECASE)
    if crore_m:
        return f"₹{crore_m.group(1)} Crore"
    # Standard range e.g. ₹5,000 - ₹15,000 or INR 10000
    range_m = re.search(
        r'(INR|₹|\$|USD|Rs\.?)\s?[\d,]+(?:K)?(?:\s?[-–]\s?[\d,]+(?:K)?)?',
        text, re.IGNORECASE
    )
    return range_m.group(0).strip() if range_m else ""


def _extract_email(text: str) -> str:
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', str(text))
    return match.group(0).lower() if match else ""


def _clean_name(title: str) -> str:
    cleaned = re.sub(
        r'\s*[-|–]\s*(Truelancer|Freelance|Project|Freelancer\.com|'
        r'Hire|Job|Gig|Work|Task).*$',
        '', title, flags=re.IGNORECASE
    ).strip()
    return cleaned.rstrip(".,|–-").strip()


def _infer_industry(query: str, text: str) -> str:
    industry_map = {
        "web":        "Web Development",
        "app":        "App Development",
        "mobile":     "Mobile Development",
        "seo":        "SEO / Digital Marketing",
        "marketing":  "Digital Marketing",
        "design":     "UI/UX Design",
        "logo":       "Graphic Design",
        "content":    "Content Writing",
        "social":     "Social Media Management",
        "video":      "Video Editing",
        "data entry": "Data Entry",
        "excel":      "Data Entry",
        "python":     "Software Development",
        "react":      "Web Development",
        "wordpress":  "Web Development",
    }
    low = text.lower()
    for kw, label in industry_map.items():
        if kw in low:
            return label
    return query


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

async def scrape_truelancer(query: str, city: str) -> list[dict]:
    """
    Truelancer scraper v2.
    - 3 DDG query variants
    - Budget extraction (lakh/crore/K aware)
    - Dedup by name+city
    - Email + industry fields
    - Strict truelancer.com URL filter
    """
    city_norm = _city_primary(city)

    search_queries = [
        f'site:truelancer.com "{query}" India budget project',
        f'site:truelancer.com "{query}" "{city_norm}" posted',
        f'site:truelancer.com {query} freelancer India fixed price',
    ]

    raw: list[dict] = []
    seen_urls: set[str] = set()

    for sq in search_queries:
        for r in await asyncio.to_thread(_ddg_search, sq, 25):
            url = r.get("href", "")
            if "truelancer.com" not in url.lower():
                continue
            if url not in seen_urls:
                seen_urls.add(url)
                raw.append(r)

    leads: list[dict] = []
    seen_keys: set[str] = set()

    for r in raw:
        title = r.get("title", "")
        body  = r.get("body", "")
        url   = r.get("href", "")

        name = _clean_name(title)
        if not name or len(name) < 4:
            found = re.search(r'([A-Z][a-zA-Z\s&]{3,50})', body)
            name = found.group(0).strip() if found else title[:60].strip()

        if not name or len(name) < 4:
            continue

        # Dedup by name+city
        key = f"{name.lower().strip()}|{city_norm.lower().strip()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        combined = f"{title} {body}"
        budget  = _extract_budget(combined)
        email   = _extract_email(combined)
        industry = _infer_industry(query, combined)

        leads.append({
            "company_name": name[:80],
            "phone":        "",
            "email":        email,
            "location":     city_norm,
            "industry":     industry[:100],
            "category":     query,
            "source":       "truelancer",
            "source_url":   url,
            "snippet":      body[:200],
            "budget_hint":  budget,
            "intent_signal": (
                f"Active Truelancer project: \"{title[:80]}\" — "
                f"SMB already spending on {industry} in India"
                + (f" | Budget: {budget}" if budget else "")
            ),
        })

    print(f"[truelancer] {len(leads)} unique leads found")
    log_scraper_run(
        "truelancer",
        attempted=len(raw),
        saved=len(leads),
        rejected=max(0, len(raw) - len(leads)),
    )
    return leads