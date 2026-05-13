"""
pain_signals.py
================
Pain Signal Detector — Step 2.5 in the pipeline.

Runs AFTER raw lead collection, BEFORE clean/validate.
No LLM calls — pure DDG search + HTTP checks.
Adds "pain signal" booleans to each lead so the AI scorer
and message generator can reference SPECIFIC observations.

Signals detected:
  has_maps_listing        → business is findable on Google Maps
  no_google_maps_listing  → NOT findable = invisible online
  negative_reviews_found  → customers are complaining publicly
  review_complaint        → the actual complaint phrase extracted
  google_reviews_count    → rough count of reviews found
  website_is_outdated     → website with no mobile viewport / old signals
  website_not_mobile      → no viewport meta tag found
  last_social_post_old    → social page exists but looks inactive (>90 days)
  has_physical_location   → address / phone on Maps = established business
  whatsapp_hint           → WhatsApp number hint found (India-specific)
  hiring_manual_roles     → recent job posting for manual entry/support roles
"""

import asyncio
import re

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# ---------------------------------------------------------------------------
# DDG helper (threaded — DDGS is sync)
# ---------------------------------------------------------------------------

def _ddg_text(query: str, max_results: int = 5) -> list[dict]:
    if not DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"[pain_signals] DDG error: {e}")
        return []


# ---------------------------------------------------------------------------
# Individual signal checks
# ---------------------------------------------------------------------------

_NEGATIVE_KEYWORDS = [
    "rude staff", "bad service", "terrible", "worst", "fraud", "cheated",
    "not good", "very bad", "avoid", "poor quality", "waste of money",
    "no response", "unprofessional", "disappointing", "pathetic",
    "horrible", "fake", "scam",
]

_POSITIVE_KEYWORDS = ["excellent", "amazing", "best", "highly recommend", "5 star", "great"]

_OUTDATED_SIGNALS = [
    "2018", "2019", "2020", "copyright 2018", "last updated 2019",
    "under construction", "coming soon", "flash player",
]


async def _check_google_reviews(company_name: str, city: str) -> dict:
    """
    DDG search for the company's Google reviews.
    Returns:
      has_maps_listing, no_google_maps_listing, negative_reviews_found,
      review_complaint, google_reviews_count, has_physical_location
    """
    query = f'"{company_name}" {city} reviews'
    results = await asyncio.to_thread(_ddg_text, query, 5)

    if not results:
        return {
            "has_maps_listing":       "unknown",
            "no_google_maps_listing": "unknown",
            "negative_reviews_found": "unknown",
            "review_complaint":       "",
            "google_reviews_count":   "unknown",
            "has_physical_location":  "unknown",
        }

    negative_found = False
    complaint_phrase = ""
    review_count = 0
    has_maps = False
    has_address = False

    combined_text = " ".join(
        (r.get("title", "") + " " + r.get("body", "")) for r in results
    ).lower()

    # Maps presence
    if "google.com/maps" in combined_text or "maps.google" in combined_text:
        has_maps = True
    if re.search(r'site:google\.com/maps', combined_text):
        has_maps = True

    # Address / phone = physical business
    if re.search(r'\+91|\b\d{10}\b|address|located at|near', combined_text):
        has_address = True

    # Review count
    count_match = re.search(r'(\d[\d,]*)\s*(?:google\s*)?reviews?', combined_text)
    if count_match:
        try:
            review_count = int(count_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Negative signals
    for kw in _NEGATIVE_KEYWORDS:
        if kw in combined_text:
            negative_found = True
            complaint_phrase = kw
            break

    # Also check for low-rating patterns
    low_rating = re.search(r'[1-2](\.\d)?\s*(?:out of\s*5|/5|stars?)', combined_text)
    if low_rating:
        negative_found = True
        complaint_phrase = complaint_phrase or f"low rating ({low_rating.group(0)})"

    return {
        "has_maps_listing":       has_maps,
        "no_google_maps_listing": not has_maps,
        "negative_reviews_found": negative_found,
        "review_complaint":       complaint_phrase,
        "google_reviews_count":   review_count,
        "has_physical_location":  has_address,
    }


async def _check_website_freshness(website_url: str) -> dict:
    """
    Fetch the website homepage and check for mobile-friendliness and staleness.
    Returns: website_is_outdated, website_not_mobile
    """
    if not website_url or not HTTPX_AVAILABLE:
        return {"website_is_outdated": "unknown", "website_not_mobile": "unknown"}

    url = website_url if website_url.startswith("http") else f"https://{website_url}"
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"}
            resp = await client.get(url, headers=headers)
            html = resp.text.lower()

            # Mobile check — look for viewport meta
            has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
            not_mobile = not has_viewport

            # Outdated check
            is_outdated = any(sig in html for sig in _OUTDATED_SIGNALS)

            # Very small homepage often means a parked/broken domain
            if len(html.strip()) < 500:
                is_outdated = True

            return {
                "website_is_outdated": is_outdated,
                "website_not_mobile":  not_mobile,
            }
    except Exception:
        return {"website_is_outdated": "unknown", "website_not_mobile": "unknown"}


async def _check_social_activity(company_name: str, city: str) -> dict:
    """
    DDG search for their Instagram / Facebook page.
    Checks if the last post is older than ~3 months based on snippet dates.
    Returns: last_social_post_old
    """
    query = f'"{company_name}" {city} instagram OR facebook page'
    results = await asyncio.to_thread(_ddg_text, query, 5)

    if not results:
        return {"last_social_post_old": "unknown"}

    combined = " ".join(r.get("body", "") + " " + r.get("title", "") for r in results).lower()

    # Look for "X months ago", "X years ago" in snippets
    months_match = re.search(r'(\d+)\s*months?\s*ago', combined)
    years_match  = re.search(r'(\d+)\s*years?\s*ago', combined)

    if years_match:
        return {"last_social_post_old": True}

    if months_match:
        months = int(months_match.group(1))
        return {"last_social_post_old": months >= 3}

    # If no Instagram/Facebook found at all → could be inactive
    has_social = (
        "instagram.com" in combined or
        "facebook.com" in combined or
        "@" in combined
    )

    return {"last_social_post_old": not has_social}


async def _check_whatsapp_hint(company_name: str, city: str, existing_phone: str) -> dict:
    """
    A lead with an Indian mobile number on Maps is very likely WhatsApp-reachable.
    We don't verify the actual WA registration — just signal the possibility.
    """
    phone = existing_phone or ""
    if not phone:
        return {"whatsapp_hint": "unknown"}
    # Indian mobile numbers starting 6-9 are WhatsApp-compatible by default
    is_mobile = bool(re.match(r'^(\+91)?[6-9]\d{9}$', phone.replace(" ", "").replace("-", "")))
    return {"whatsapp_hint": is_mobile}


async def check_job_posting_signal(business_name: str, location: str) -> dict:
    """
    Search DDG or Yahoo for hiring signals related to manual data entry / support roles.
    """
    query = f'"{business_name}" {location} hiring data entry OR excel OR manual reporting OR customer support'
    results = await asyncio.to_thread(_ddg_text, query, 5)

    if not results:
        return {"hiring_manual_roles": "unknown"}

    combined = " ".join(r.get("body", "") + " " + r.get("title", "") for r in results).lower()

    # Check if dated within the last 60 days
    # DDG snippets typically use phrases like "2 days ago", "1 month ago"
    recent_patterns = [
        r'\b\d+\s*(day|hour|min|minute|week)s?\s*ago\b',
        r'\b1\s*month\s*ago\b',
        r'\b2\s*months?\s*ago\b',
        r'\byesterday\b',
        r'\bjust now\b'
    ]
    
    is_recent = any(re.search(pat, combined) for pat in recent_patterns)

    return {"hiring_manual_roles": True if is_recent else False}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def detect_pain_signals(lead: dict) -> dict:
    """
    Run all pain signal checks concurrently for a single lead.
    Adds signal fields directly to the lead dict.

    Fields added:
      has_maps_listing, no_google_maps_listing,
      negative_reviews_found, review_complaint, google_reviews_count,
      has_physical_location, website_is_outdated, website_not_mobile,
      last_social_post_old, whatsapp_hint
    """
    company = lead.get("company_name", "")
    city    = lead.get("location", lead.get("city", ""))
    website = lead.get("website", "")
    phone   = lead.get("phone", "")

    # If lead already has pain signals (e.g. from a Maps scraper), don't overwrite
    already_checked = lead.get("_pain_signals_checked", False)
    if already_checked:
        return lead

    tasks = [
        _check_google_reviews(company, city),
        _check_social_activity(company, city),
        _check_whatsapp_hint(company, city, phone),
        check_job_posting_signal(company, city),
    ]

    # Only check website freshness if there's a known website
    async def _no_website_fallback():
        return {"website_is_outdated": "unknown", "website_not_mobile": "unknown"}

    if website:
        tasks.append(_check_website_freshness(website))
    else:
        tasks.append(_no_website_fallback())

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        print(f"[pain_signals] Timeout for '{company}' — skipping")
        lead["_pain_signals_checked"] = True
        return lead

    for result in results:
        if isinstance(result, dict):
            lead.update(result)

    lead["_pain_signals_checked"] = True

    # Quick summary for logs
    signals_fired = [k for k in [
        "negative_reviews_found", "no_google_maps_listing",
        "website_is_outdated", "website_not_mobile", "last_social_post_old",
        "hiring_manual_roles"
    ] if lead.get(k) is True]

    if signals_fired:
        print(f"  [pain] {company[:30]:30} | signals: {', '.join(signals_fired)}")

    return lead


async def batch_detect_pain_signals(leads: list[dict], batch_size: int = 8) -> list[dict]:
    """
    Run pain signal detection on all leads in controlled batches.
    Returns the same list with pain signal fields added.
    """
    enriched = []
    for i in range(0, len(leads), batch_size):
        batch = leads[i: i + batch_size]
        results = await asyncio.gather(
            *[detect_pain_signals(lead) for lead in batch],
            return_exceptions=True,
        )
        for lead, result in zip(batch, results):
            if isinstance(result, dict):
                enriched.append(result)
            else:
                print(f"  [pain] ERROR for '{lead.get('company_name')}': {result}")
                enriched.append(lead)  # use lead without pain signals
    return enriched
