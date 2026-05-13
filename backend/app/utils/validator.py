"""
utils/validator.py
===================
Lead Quality Gate
------------------
Removes leads that are fundamentally unusable before we waste
LLM calls, enrichment time, or DB space on them.

A lead fails if:
  1. company_name is empty or too short (< 3 chars)
  2. No contact method at all: phone AND email AND website all empty
  3. Website returns 404 / is a parked domain
     (This check is async — skipped in fast mode)

These are hard failures. A lead that fails validation is
discarded — not saved to DB at all.
"""

import re
import asyncio
import httpx


# ---------------------------------------------------------------------------
# Synchronous checks (fast — no network)
# ---------------------------------------------------------------------------

_JUNK_NAME_PATTERNS = re.compile(
    r'^(list of|top \d+|best |all |find |get |the best|'
    r'rating|ratings|review|reviews|n/a|na|none|null|test|'
    r'justdial\.com|sulekha\.com|internshala\.com)',
    re.IGNORECASE
)

_NON_BUSINESS_NAME_PATTERNS = re.compile(
    r'(reviews?\s*\(\d+\)|pricing|verified ratings|services|near me|'
    r'google maps|street view|seo\b|digital marketing|archives|jobs?,|'
    r'characteristic of|how google|top interior designers|best interior designers|'
    r'interior designers in|ads sulekha\.com)',
    re.IGNORECASE
)

_LISTING_TERMS = (
    "apartment", "apartments", "flat", "flats", "property", "properties",
    "villa", "villas", "plot", "plots", "rent", "rental", "sale", "resale",
    "real estate", "realestate",
)

_IRRELEVANT_SERVICE_TERMS = (
    "for hire", "freelance", "freelancer", "developers", "developer",
    "software company", "software companies"
)

_INDUSTRY_KEYWORDS = {
    "restaurants": ("restaurant", "restaurants", "cafe", "cafes", "bar", "bars", "diner", "eatery", "kitchen", "food"),
    "dental clinics": ("dental", "dentist", "dentists", "clinic", "clinics", "orthodontic", "oral care"),
    "gyms": ("gym", "fitness", "workout", "crossfit", "health club", "training studio"),
    "law firms": ("law firm", "law firms", "advocate", "advocates", "attorney", "attorneys", "legal", "lawyer", "lawyers"),
    "salons": ("salon", "salons", "beauty", "spa", "hair", "makeup", "unisex salon"),
    "hospitals": ("hospital", "hospitals", "clinic", "clinics", "medical", "healthcare", "doctor", "doctors"),
    "interior design": ("interior", "interiors", "decorator", "design", "furnishing", "home decor"),
    "real estate": ("real estate", "property", "realtor", "broker", "builder", "developer"),
    "logistics": ("logistics", "transport", "freight", "shipping", "courier", "cargo", "packers"),
    "education": ("education", "school", "college", "university", "academy", "institute", "tuition", "tutor", "coaching"),
    "healthcare": ("healthcare", "health", "medical", "clinic", "hospital", "doctor", "nursing", "pharmacy"),
    "finance": ("finance", "financial", "accounting", "bank", "investment", "tax", "auditor", "cpa", "wealth"),
    "retail": ("retail", "store", "shop", "boutique", "mart", "supermarket"),
}

_PARKED_SIGNALS = [
    "domain is for sale",
    "buy this domain",
    "this domain is parked",
    "parked domain",
    "godaddy.com",
    "namecheap parking",
    "sedo.com",
    "under construction",
    "coming soon",
]


def _is_junk_name(name: str) -> bool:
    """True if name looks like a category page, not a real business."""
    name = name.strip()
    if len(name) < 3:
        return True
    if _JUNK_NAME_PATTERNS.match(name):
        return True
    # All numbers → not a company name
    if re.match(r'^\d+$', name):
        return True
    # Ends with a TLD → probably a URL leaked in
    if re.search(r'\.(com|in|org|net|co)$', name.lower()):
        return True
    return False


def _looks_like_non_business_name(name: str) -> bool:
    """Extra guardrail for generic SEO/article/directory titles."""
    return bool(_NON_BUSINESS_NAME_PATTERNS.search((name or "").strip()))


def _has_contact(lead: dict) -> bool:
    """Return True if at least one contact method exists."""
    return bool(
        lead.get("phone", "").strip()
        or lead.get("email", "").strip()
        or lead.get("website", "").strip()
        or lead.get("source_url", "").strip()  # source URL is always a fallback contact route
    )


def _looks_like_listing_or_property(lead: dict) -> bool:
    """
    True if the scraped lead looks like a property/listing page rather than a business.
    This is a conservative blocklist for obvious false positives.
    """
    haystack = " ".join([
        lead.get("company_name", ""),
        lead.get("industry", ""),
        lead.get("category", ""),
        lead.get("description", ""),
        lead.get("source_url", ""),
        lead.get("website", ""),
    ]).lower()
    return any(term in haystack for term in _LISTING_TERMS)


def _looks_like_directory_or_article_page(lead: dict) -> bool:
    """True if the lead resembles an article, SEO page, or directory page."""
    haystack = " ".join([
        lead.get("company_name", ""),
        lead.get("industry", ""),
        lead.get("category", ""),
        lead.get("description", ""),
        lead.get("source_url", ""),
        lead.get("website", ""),
    ]).lower()
    page_terms = (
        "verified ratings", "pricing", "google maps", "street view",
        "seo", "digital marketing", "archives", "jobs", "near me",
        "top interior designers", "best interior designers", "services in",
    )
    return any(term in haystack for term in page_terms)


def _matches_target_city(lead: dict, target_city: str | None = None) -> bool:
    """
    Return True when the lead's location is compatible with the requested city.
    If the lead doesn't include a city, fail open to avoid dropping good data.
    """
    if not target_city:
        return True

    target = target_city.strip().lower()
    if not target:
        return True

    lead_city = (lead.get("location") or lead.get("city") or "").strip().lower()
    if not lead_city:
        return True

    # Special handling for Goa (State) to pass through typical Goan cities
    if target == "goa" and any(c in lead_city for c in ["panaji", "panjim", "margao", "vasco", "mapusa", "ponda", "goa"]):
        return True

    return target in lead_city or lead_city in target


def _matches_target_industry(lead: dict, target_industry: str | None = None) -> bool:
    """
    Return True if the lead text looks relevant to the requested industry.
    If we don't know the industry mapping yet, attempt a loose match against the raw data.
    """
    if not target_industry:
        return True

    normalized = target_industry.strip().lower()
    if not normalized:
        return True

    # Handle singular inputs implicitly by mapping them to their plural keys
    if not normalized.endswith('s') and f"{normalized}s" in _INDUSTRY_KEYWORDS:
        normalized = f"{normalized}s"

    keywords = _INDUSTRY_KEYWORDS.get(normalized)
    if not keywords:
        # Fallback: attempt loose match using the exact target industry string
        keywords = (normalized,)

    haystack = " ".join([
        lead.get("company_name", ""),
        lead.get("industry", ""),
        lead.get("category", ""),
        lead.get("description", ""),
        lead.get("source_url", ""),
        lead.get("website", ""),
    ]).lower()

    if any(term in haystack for term in _IRRELEVANT_SERVICE_TERMS):
        return False

    return any(keyword in haystack for keyword in keywords)


def validate_lead_sync(
    lead: dict,
    target_industry: str | None = None,
    target_city: str | None = None,
) -> tuple[bool, str]:
    """
    Fast synchronous validation (no network).
    Returns (is_valid, reason_if_invalid).

    Call this first — before any async enrichment.
    """
    name = (lead.get("company_name") or "").strip()

    # Rule 1: empty / junk name
    if not name:
        return False, "empty company_name"
    if _is_junk_name(name):
        return False, f"junk name: '{name}'"
    if _looks_like_non_business_name(name):
        return False, f"non-business name: '{name}'"

    # Rule 1b: obvious non-business/property listing pages
    if _looks_like_listing_or_property(lead):
        return False, "looks like a property/listing page"
    if _looks_like_directory_or_article_page(lead):
        return False, "looks like a directory/article page"

    # Rule 1c: explicit city mismatch with the user's requested city
    if not _matches_target_city(lead, target_city):
        return False, f"city mismatch: expected '{target_city}', got '{lead.get('location') or lead.get('city') or ''}'"

    # Rule 1d: clear mismatch with the user's requested industry
    if not _matches_target_industry(lead, target_industry):
        return False, f"industry mismatch: expected '{target_industry}'"

    # Rule 2: no contact method at all
    if not _has_contact(lead):
        return False, "no contact method (phone/email/website/source_url all empty)"

    return True, ""


# ---------------------------------------------------------------------------
# Async website check (optional — used in enrichment phase)
# ---------------------------------------------------------------------------

async def _check_website(url: str) -> tuple[bool, str]:
    """
    Check if a website is alive and not a parked domain.

    Returns:
        (is_alive, reason)
        is_alive = True  → real, working website
        is_alive = False → 404, timeout, parked, or error
    """
    if not url:
        return False, "no url"

    # Add scheme if missing
    if not url.startswith("http"):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"},
            )
            html = resp.text.lower()

            # Check for parked domain signals
            for signal in _PARKED_SIGNALS:
                if signal in html:
                    return False, f"parked domain ('{signal}')"

            # 404 or empty response
            if resp.status_code == 404:
                return False, "404 not found"
            if len(html.strip()) < 200:
                return False, "near-empty response"

            return True, ""

    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, f"error: {e}"


async def validate_lead(lead: dict, check_website: bool = False) -> tuple[bool, str]:
    """
    Full lead validation — sync checks + optional website check.

    Args:
        lead:          Lead dict in standard schema
        check_website: If True, also HTTP-checks the website URL
                       (slower — use only during enrichment phase)

    Returns:
        (is_valid, reason_if_invalid)
    """
    # Fast checks first
    ok, reason = validate_lead_sync(lead)
    if not ok:
        return False, reason

    # Optional website aliveness check
    if check_website and lead.get("website"):
        alive, reason = await _check_website(lead["website"])
        if not alive:
            # Don't discard the lead — just mark website as dead
            lead["website_alive"] = False
            lead["website"] = ""  # clear so enricher doesn't try again
        else:
            lead["website_alive"] = True

    return True, ""


def filter_valid_leads(
    leads: list[dict],
    target_industry: str | None = None,
    target_city: str | None = None,
) -> list[dict]:
    """
    Synchronous batch filter — removes clearly invalid leads fast.
    Use this immediately after scraping, before async enrichment.

    Returns the valid subset.
    """
    valid = []
    removed = 0
    for lead in leads:
        ok, reason = validate_lead_sync(
            lead,
            target_industry=target_industry,
            target_city=target_city,
        )
        if ok:
            valid.append(lead)
        else:
            removed += 1
            name = lead.get("company_name", "?")
            safe_name = str(name).encode("cp1252", errors="replace").decode("cp1252")
            safe_reason = str(reason).encode("cp1252", errors="replace").decode("cp1252")
            print(f"[validator] removed '{safe_name}': {safe_reason}")

    if removed:
        print(f"[validator] kept {len(valid)}, removed {removed} invalid leads")

    return valid
