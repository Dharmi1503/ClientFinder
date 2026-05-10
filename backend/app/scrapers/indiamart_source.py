"""
indiamart_source.py
====================
IndiaMART Lead Source Scraper — FIXED (all 10 gaps patched)

Gap fixes:
  GAP 1  → DDG results 12 → 30 per query
  GAP 2  → retry with backoff on DDG failure
  GAP 3  → wider phone regex (mobile + landline)
  GAP 4  → dedup on name+city not name only
  GAP 5  → city alias map, must match city/alias in snippet
  GAP 6  → email extraction from snippet
  GAP 7  → 3 different DDG queries merged (company + rfq + general)
  GAP 8  → /want/ RFQ pages targeted separately, +HIGH intent signal
  GAP 9  → industry = query only, role stored in intent_signal
  GAP 10 → GST/TrustSEAL verified flag captured
"""

import asyncio
import re
import time
from app.database import log_scraper_run

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


# ── City aliases (GAP 5) ──────────────────────────────────────────────────────
CITY_ALIASES: dict[str, list[str]] = {
    "surat":      ["surat", "udhna", "adajan", "vesu", "katargam"],
    "mumbai":     ["mumbai", "bombay", "thane", "navi mumbai", "kalyan"],
    "delhi":      ["delhi", "new delhi", "noida", "gurugram", "gurgaon"],
    "bengaluru":  ["bengaluru", "bangalore", "whitefield"],
    "hyderabad":  ["hyderabad", "secunderabad", "cyberabad"],
    "pune":       ["pune", "pimpri", "chinchwad"],
    "ahmedabad":  ["ahmedabad", "gandhinagar"],
    "chennai":    ["chennai", "madras", "tambaram"],
    "kolkata":    ["kolkata", "calcutta", "howrah"],
    "jaipur":     ["jaipur", "pink city"],
}


def _city_match(text: str, city: str) -> bool:
    """GAP 5: city OR any alias must appear in text."""
    text_l = text.lower()
    variants = CITY_ALIASES.get(city.lower(), [city.lower()])
    return any(v in text_l for v in variants)


# ── Phone regex (GAP 3) ───────────────────────────────────────────────────────
_PHONE_RE = re.compile(
    r'(\+91[\s\-]?)?(\(\d{2,5}\)[\s\-]?)?\b[6-9]\d{4}[\s\-]?\d{5}\b'
    r'|0\d{2,4}[\s\-]\d{6,8}'
)


def _extract_phone(text: str) -> str:
    m = _PHONE_RE.search(text)
    return re.sub(r'\s+', ' ', m.group(0)).strip() if m else ""


# ── Email extraction (GAP 6) ──────────────────────────────────────────────────
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')


def _extract_email(text: str) -> str:
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else ""


# ── GST / trust signal (GAP 10) ───────────────────────────────────────────────
_VERIFIED_RE = re.compile(
    r'(gst\s*verified|trustseal|trust\s*seal|indiamart\s*member|verified\s*supplier)',
    re.IGNORECASE
)


def _is_verified(text: str) -> bool:
    return bool(_VERIFIED_RE.search(text))


# ── DDG search with retry (GAP 2) ─────────────────────────────────────────────
def _ddg_search(query: str, max_results: int = 30) -> list[dict]:
    """GAP 1 + 2: 30 results, 3 retries with backoff."""
    if not DDGS_AVAILABLE:
        return []
    for attempt in range(3):
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(r)
            if results:
                return results
        except Exception as e:
            print(f"[indiamart_source] DDG attempt {attempt+1} error: {e}")
        time.sleep(1.5 * (2 ** attempt))
    return []


# ── Name cleaner ──────────────────────────────────────────────────────────────
def _clean_company_name(title: str) -> str:
    title = re.sub(
        r'\s*[-|–]\s*(IndiaMART|Indiamart|india mart|Manufacturer|'
        r'Supplier|Exporter|Trader|Wholesaler|Dealer).*$',
        '', title, flags=re.IGNORECASE
    ).strip().rstrip(".,|–-").strip()
    return title


# ── Role extractor (GAP 9) ────────────────────────────────────────────────────
def _extract_role(text: str) -> str:
    """Extract biz role without polluting industry field."""
    m = re.search(
        r'(manufacturer|supplier|exporter|trader|dealer|wholesaler|importer)',
        text, re.IGNORECASE
    )
    return m.group(1).title() if m else "Vendor"


# ── RFQ page detector (GAP 8) ─────────────────────────────────────────────────
def _is_rfq(url: str) -> bool:
    """
    IndiaMART /want/ pages = buyer posted a purchase requirement.
    Highest intent signal in the entire pipeline.
    """
    return "/want/" in url.lower()


# ── Main scraper ──────────────────────────────────────────────────────────────

async def scrape_indiamart(query: str, city: str) -> list[dict]:
    """
    3-query strategy (GAP 7):
      1. Company pages  → established biz listings
      2. RFQ /want/ pages → active buyers posting requirements
      3. General search → catch remaining phone-listed pages
    All merged, deduped, city-validated.
    """

    # GAP 7: 3 different queries targeting different IndiaMART page types
    queries = [
        f'site:indiamart.com/companyprofile "{query}" "{city}"',   # company pages
        f'site:indiamart.com/want "{query}" "{city}"',              # RFQ buyer pages
        f'site:indiamart.com "{query}" "{city}" phone',             # general + phone
    ]

    # Fetch all 3 queries, merge unique URLs
    seen_urls: set[str] = set()
    raw_all:   list[dict] = []

    for q in queries:
        results = await asyncio.to_thread(_ddg_search, q, 30)  # GAP 1: 30 per query
        for r in results:
            url = r.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                raw_all.append(r)
        await asyncio.sleep(0.8)   # polite gap between DDG calls

    leads: list[dict] = []
    seen_keys: set[str] = set()

    for r in raw_all:
        title = r.get("title", "")
        body  = r.get("body", "")
        url   = r.get("href", "")

        if "indiamart.com" not in url.lower():
            continue

        name = _clean_company_name(title)
        if not name or len(name) < 4:
            continue

        # GAP 5: city must match
        combined = (title + " " + body).lower()
        if not _city_match(combined, city):
            continue

        # GAP 4: dedup on name+city (not name alone)
        # Strip city from name first — "Raj Textiles Surat" and "Raj Textiles" = same biz
        name_stripped = re.sub(re.escape(city), '', name, flags=re.IGNORECASE).strip()
        key = re.sub(r'\s+', '', name_stripped.lower()) + city.lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)

        phone = _extract_phone(body) or _extract_phone(title)  # GAP 3
        email = _extract_email(body)                            # GAP 6

        role      = _extract_role(combined)                    # GAP 9
        rfq       = _is_rfq(url)                               # GAP 8
        verified  = _is_verified(body)                         # GAP 10

        # GAP 8: RFQ = highest intent, give clear signal
        if rfq:
            intent = (
                f"BUYER RFQ on IndiaMART — {city} buyer actively posted "
                f"purchase requirement for {query}. Hottest lead type."
            )
        else:
            intent = (
                f"Listed on IndiaMART as {role} in {city} — "
                f"verified business with buying/selling activity"
                + (" [GST Verified]" if verified else "")
            )

        leads.append({
            "company_name":          name[:80],
            "phone":                 phone,
            "email":                 email,
            "location":              city,
            "industry":              query,        # GAP 9: pure query, no role pollution
            "category":              query,
            "source":                "indiamart",
            "source_url":            url,
            "snippet":               body[:200],
            "budget_hint":           "",
            "intent_signal":         intent,
            "has_physical_location": True,
            "is_rfq":                rfq,          # GAP 8: flag for scorer
            "gst_verified":          verified,     # GAP 10: flag for scorer
        })

    print(f"[indiamart_source] {len(leads)} leads found "
          f"({sum(1 for l in leads if l['is_rfq'])} RFQ buyers)")
    log_scraper_run(
        "indiamart",
        attempted=len(raw_all),
        saved=len(leads),
        rejected=max(0, len(raw_all) - len(leads)),
    )
    return leads