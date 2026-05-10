"""
instagram_hashtag.py
=====================
Instagram Hashtag Lead Scraper — FIXED (all 10 gaps patched)

Gap fixes:
  GAP 1  → DDG results 10 → 25 per query
  GAP 2  → retry with backoff on DDG failure
  GAP 3  → wider phone regex (mobile + landline)
  GAP 4  → city alias map, must match city/alias in snippet
  GAP 5  → 3 different DDG queries merged
  GAP 6  → aggregator URLs (gramho, insta.bio) accepted for data
  GAP 7  → hashtag actually used in query (was dead code)
  GAP 8  → personal account filter via handle pattern check
  GAP 9  → email extraction from snippet
  GAP 10 → contact_link = real instagram.com URL, not aggregator
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


# ── City aliases (GAP 4) ──────────────────────────────────────────────────────
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
    """GAP 4: city OR any alias must appear in text."""
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


# ── Email extraction (GAP 9) ──────────────────────────────────────────────────
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')


def _extract_email(text: str) -> str:
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else ""


# ── Aggregator domains (GAP 6) ────────────────────────────────────────────────
# These sites scrape Instagram and expose biz data in indexed pages
_AGGREGATORS = [
    "gramho.com", "insta.bio", "picuki.com",
    "imginn.com", "instaliga.com", "inflact.com",
]


def _is_instagram_or_aggregator(url: str) -> bool:
    """GAP 6: accept real IG pages AND known aggregators."""
    url_l = url.lower()
    if "instagram.com" in url_l:
        return True
    return any(agg in url_l for agg in _AGGREGATORS)


def _is_aggregator(url: str) -> bool:
    url_l = url.lower()
    return any(agg in url_l for agg in _AGGREGATORS)


# ── Handle extractor ──────────────────────────────────────────────────────────
def _extract_instagram_handle(url: str, body: str) -> str:
    """Extract @handle from URL or snippet."""
    url_match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', url)
    if url_match:
        handle = url_match.group(1)
        if handle not in ("p", "reel", "explore", "accounts", "stories", "reels"):
            return f"@{handle}"

    # Try aggregator URL patterns
    agg_match = re.search(r'/([a-zA-Z0-9_.]{3,30})/?$', url)
    if agg_match and _is_aggregator(url):
        return f"@{agg_match.group(1)}"

    at_match = re.search(r'@([a-zA-Z0-9_.]{3,30})', body)
    if at_match:
        return f"@{at_match.group(1)}"

    return ""


# ── Personal account filter (GAP 8) ───────────────────────────────────────────
# Personal handles: single common first name, no biz keywords, very short
_PERSONAL_NAME_RE = re.compile(
    r'^@(rahul|priya|amit|neha|ravi|anjali|raj|pooja|deepak|sunita|'
    r'vikram|anita|suresh|kavita|manish|rekha|arun|sonia|rohit|meena)$',
    re.IGNORECASE
)
_BIZ_KEYWORDS = re.compile(
    r'(store|shop|studio|official|design|tech|salon|cafe|food|'
    r'digital|media|brand|decor|fashion|wear|mart|hub|zone|world)',
    re.IGNORECASE
)


def _is_personal_account(handle: str, name: str) -> bool:
    """GAP 8: filter obvious personal accounts."""
    if _PERSONAL_NAME_RE.match(handle):
        return True
    # Very short handle with no biz keyword in name = likely personal
    bare = handle.lstrip("@")
    if len(bare) <= 5 and not _BIZ_KEYWORDS.search(name):
        return True
    return False


# ── Name cleaner ──────────────────────────────────────────────────────────────
def _clean_business_name(title: str, handle: str) -> str:
    name = re.sub(
        r'\s*[•·|–\-]\s*(Instagram|Photos|Videos|posts|followers|following).*$',
        '', title, flags=re.IGNORECASE
    ).strip()
    name = re.sub(r'\s*\(@[^)]+\)', '', name).strip()

    if name and len(name) > 3:
        return name

    if handle:
        return handle.lstrip("@").replace("_", " ").replace(".", " ").title()

    return ""


# ── DDG search with retry (GAP 2) ─────────────────────────────────────────────
def _ddg_search(query: str, max_results: int = 25) -> list[dict]:
    """GAP 1+2: 25 results, 3 retries with backoff."""
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
            print(f"[instagram_hashtag] DDG attempt {attempt+1} error: {e}")
        time.sleep(1.5 * (2 ** attempt))
    return []


# ── Main scraper ──────────────────────────────────────────────────────────────

async def scrape_instagram_hashtag(query: str, city: str) -> list[dict]:
    """
    3-query strategy (GAP 5):
      1. site:instagram.com + hashtag + city  → direct IG profile pages
      2. instagram city query phone           → IG pages with phone in snippet
      3. aggregator search                    → gramho/picuki indexed profiles
    All merged, deduped, city-validated.
    """
    # GAP 7: hashtag actually used now
    hashtag = "#" + query.replace(" ", "").lower()

    # GAP 5: 3 different queries
    queries = [
        f'site:instagram.com "{city}" "{query}" business',
        f'instagram.com "{city}" {hashtag} phone contact',
        f'(site:gramho.com OR site:picuki.com OR site:imginn.com) "{city}" "{query}"',
    ]

    seen_handles: set[str] = set()
    raw_all:      list[dict] = []
    seen_urls:    set[str] = set()

    for q in queries:
        results = await asyncio.to_thread(_ddg_search, q, 25)  # GAP 1
        for r in results:
            url = r.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                raw_all.append(r)
        await asyncio.sleep(0.8)

    leads: list[dict] = []

    for r in raw_all:
        title = r.get("title", "")
        body  = r.get("body", "")
        url   = r.get("href", "")

        # GAP 6: accept IG + aggregators
        if not _is_instagram_or_aggregator(url):
            continue

        handle = _extract_instagram_handle(url, body)
        name   = _clean_business_name(title, handle)

        if not name or len(name) < 4:
            continue
        if not handle:
            continue

        # GAP 8: personal account filter
        if _is_personal_account(handle, name):
            continue

        # Dedup on handle
        key = handle.lower()
        if key in seen_handles:
            continue
        seen_handles.add(key)

        # GAP 4: city alias match
        combined = (title + " " + body).lower()
        if not _city_match(combined, city):
            continue

        phone = _extract_phone(body)   # GAP 3
        email = _extract_email(body)   # GAP 9

        # GAP 10: contact_link = real IG URL even if found via aggregator
        if _is_aggregator(url):
            bare_handle = handle.lstrip("@")
            contact_link = f"https://www.instagram.com/{bare_handle}/"
        else:
            contact_link = url

        leads.append({
            "company_name":     name[:80],
            "phone":            phone,
            "email":            email,
            "location":         city,
            "industry":         query,
            "category":         query,
            "source":           "instagram",
            "source_url":       url,
            "contact_link":     contact_link,   # GAP 10: always real IG URL
            "snippet":          body[:200],
            "budget_hint":      "",
            "intent_signal":    (
                f"Active Instagram business page in {city} — "
                f"local business with social presence ({handle})"
            ),
            "instagram_handle": handle,
        })

    print(f"[instagram_hashtag] {len(leads)} leads found")
    log_scraper_run(
        "instagram",
        attempted=len(raw_all),
        saved=len(leads),
        rejected=max(0, len(raw_all) - len(leads)),
    )
    return leads