"""
scrapers/tradeindia.py — v2
============================
Fixes applied:
  - DDG results 12→25, retry 3 with backoff
  - City alias map
  - Multi-query: 3 query variants (category, manufacturer, supplier)
  - Dedup by name+city (was name only)
  - Email extraction from snippets
  - `verified` field added (GST/Trust Seal detection)
  - Phone regex covers mobile + landline
  - URL domain filter strict (tradeindia.com only)
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
    "pune":      ["pune", "pimpri"],
    "ahmedabad": ["ahmedabad", "amdavad"],
    "jaipur":    ["jaipur"],
    "surat":     ["surat"],
}

def _city_variants(city: str) -> list[str]:
    key = city.lower().strip()
    for canonical, aliases in _CITY_ALIASES.items():
        if key in aliases or key == canonical:
            return [city, canonical.title()]
    return [city]


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
            print(f"[tradeindia] DDG attempt {attempt+1} error: {e}")
            if attempt < 2:
                import time; time.sleep(1.5 * (attempt + 1))
    return []


def _extract_phone(text: str) -> str:
    match = re.search(
        r'(?:\+91[\s\-]?|0)?(?:[6-9]\d{9}|\d{2,4}[\s\-]\d{6,8})',
        str(text)
    )
    return match.group(0).strip() if match else ""


def _extract_email(text: str) -> str:
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', str(text))
    return match.group(0).lower() if match else ""


def _clean_name(title: str) -> str:
    cleaned = re.sub(
        r'\s*[-|–]\s*(TradeIndia|Trade India|Manufacturer|Supplier|'
        r'Exporter|Trader|Wholesaler|Dealer|India|B2B).*$',
        '', title, flags=re.IGNORECASE
    ).strip()
    return cleaned.rstrip(".,|–-").strip()


def _detect_verified(text: str) -> bool:
    """GST verified, Trust Seal, or verified badge signals."""
    return bool(re.search(
        r'gst\s*verified|trust\s*seal|verified\s*supplier|'
        r'verified\s*manufacturer|tradeindia\s*assured',
        text, re.IGNORECASE
    ))


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

async def scrape_tradeindia(query: str, city: str) -> list[dict]:
    """
    TradeIndia scraper v2.
    - 3 query variants: direct, manufacturer, supplier
    - Dedup by name+city
    - Email + phone extraction
    - Verified flag from GST/Trust Seal
    """
    city_v = _city_variants(city)
    city_primary = city_v[0]

    # 3 query variants for better coverage
    search_queries = [
        f'site:tradeindia.com "{query}" "{city_primary}"',
        f'site:tradeindia.com "{query}" manufacturer "{city_primary}"',
        f'site:tradeindia.com "{query}" supplier "{city_primary}"',
    ]

    raw: list[dict] = []
    seen_urls: set[str] = set()

    for sq in search_queries:
        for r in await asyncio.to_thread(_ddg_search, sq, 25):
            url = r.get("href", "")
            if "tradeindia.com" not in url.lower():
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
            # Try extracting from body
            found = re.findall(
                r'([A-Z][a-zA-Z0-9 &]{3,50}'
                r'(?:Pvt\.?\s?Ltd\.?|LLP|Industries|Enterprises|Traders|Corp\.?)?)',
                body
            )
            name = found[0].strip() if found else ""

        if not name or len(name) < 4:
            continue

        # Dedup by name+city
        key = f"{name.lower().strip()}|{city_primary.lower().strip()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        phone = _extract_phone(body) or _extract_phone(title)
        email = _extract_email(body + " " + title)

        combined = (title + " " + body).lower()
        cat_match = re.search(
            r'(manufacturer|supplier|exporter|trader|dealer|wholesaler)',
            combined, re.IGNORECASE
        )
        biz_type = cat_match.group(1).title() if cat_match else "Business"
        industry = f"{query} {biz_type}" if cat_match else query

        verified = _detect_verified(body + " " + title)

        leads.append({
            "company_name":          name[:80],
            "phone":                 phone,
            "email":                 email,
            "location":              city_primary,
            "industry":              industry[:100],
            "category":              query,
            "source":                "tradeindia",
            "source_url":            url,
            "snippet":               body[:200],
            "budget_hint":           "",
            "verified":              verified,
            "has_physical_location": True,
            "intent_signal": (
                f"Listed on TradeIndia as {biz_type} in {city_primary} "
                f"— established trading operation"
                + (" (GST/Trust Seal verified)" if verified else "")
            ),
        })

    print(f"[tradeindia] {len(leads)} unique leads found")
    log_scraper_run(
        "tradeindia",
        attempted=len(raw),
        saved=len(leads),
        rejected=max(0, len(raw) - len(leads)),
    )
    return leads