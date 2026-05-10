"""
enricher_indiamart.py
======================
IndiaMART Buyer Enquiry Enricher — Active Purchase Intent
----------------------------------------------------------
IndiaMART is India's largest B2B marketplace.
When a buyer posts an enquiry on IndiaMART, that's the
strongest possible signal: they are ACTIVELY trying to buy something.

Two data points we extract:

1. Buyer enquiries for our target category in this city
   → "12 buyers enquired about 'digital marketing services' in Delhi"
   
2. Whether this specific company is listed as a BUYER on IndiaMART
   → means they have procurement activity and a budget

Strategy: DDG site:indiamart.com search (their pages are indexed).
No auth, no Selenium. IndiaMART's search pages are server-rendered.
"""

import asyncio
import re

import httpx

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer": "https://www.indiamart.com/",
}


def _ddg_search(query: str, max_results: int = 10) -> list[dict]:
    if not DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
    except Exception as e:
        print(f"[indiamart_enricher] DDG error: {e}")
    return results


def _extract_enquiry_count(text: str) -> int:
    """
    Extract buyer enquiry count from IndiaMART snippets.
    Patterns: '47 buyers', '120+ enquiries', '15 contacts'
    """
    for pattern in [
        r'(\d+)\s*\+?\s*buyers?',
        r'(\d+)\s*\+?\s*enquir(?:y|ies)',
        r'(\d+)\s*\+?\s*contacts?',
        r'(\d+)\s*\+?\s*(?:people\s+)?(?:are\s+)?(?:looking|requir)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


def _extract_budget_hint(text: str) -> str:
    """Extract price/budget mention from IndiaMART listing."""
    m = re.search(
        r'(?:Rs\.?|INR|₹)\s*[\d,]+(?:\s*[-–]\s*[\d,]+)?(?:\s*(?:per|/)\s*\w+)?',
        text, re.IGNORECASE
    )
    return m.group(0).strip() if m else ""


async def _search_category_enquiries(category: str, city: str) -> dict:
    """
    Search IndiaMART for buyer enquiries in a category + city.
    Returns a count + evidence string.
    """
    # IndiaMART buy lead pages: /buy-lead/{category}
    query = f'site:indiamart.com/buy-lead "{category}" "{city}"'
    raw = await asyncio.to_thread(_ddg_search, query, 8)

    total_enquiries = 0
    evidence_snippets = []

    for r in raw:
        body = r.get("body", "")
        title = r.get("title", "")
        combined = f"{title} {body}"

        count = _extract_enquiry_count(combined)
        total_enquiries += count

        if count > 0 or "buy" in title.lower() or "requir" in body.lower():
            snippet = body[:120].strip()
            if snippet:
                evidence_snippets.append(snippet)

    return {
        "enquiry_count": total_enquiries,
        "evidence":      evidence_snippets[:3],
    }


async def _check_company_on_indiamart(company_name: str) -> dict:
    """
    Check if a company appears on IndiaMART as a buyer or seller.
    Buyers = they have active procurement needs.
    Sellers = they're already digital (less likely to need our services).
    """
    query = f'site:indiamart.com "{company_name}"'
    raw = await asyncio.to_thread(_ddg_search, query, 5)

    is_buyer  = False
    is_seller = False
    budget_hint = ""
    listing_url = ""

    for r in raw:
        href  = r.get("href", "")
        title = r.get("title", "")
        body  = r.get("body", "")
        combined = f"{title} {body}".lower()

        if "buy-lead" in href or "buyer" in combined or "requir" in combined:
            is_buyer = True
        if "catalog" in href or "seller" in combined or "supplier" in combined:
            is_seller = True

        if not budget_hint:
            budget_hint = _extract_budget_hint(f"{title} {body}")

        if not listing_url and "indiamart.com" in href:
            listing_url = href

    return {
        "is_indiamart_buyer":  is_buyer,
        "is_indiamart_seller": is_seller,
        "indiamart_budget":    budget_hint,
        "indiamart_url":       listing_url,
    }


async def enrich_with_indiamart(
    company_name: str,
    city: str,
    category: str,
) -> dict:
    """
    IndiaMART enrichment — two parallel lookups:
    1. Category buyer enquiries in this city
    2. Company presence on IndiaMART

    Args:
        company_name: Company to check
        city:         Target city
        category:     Industry/service category to check for enquiries

    Returns:
        {
          "indiamart_signal":      str   — formatted signal for AI
          "category_buyers":       int   — buyers in this category + city
          "category_evidence":     list  — snippet evidence strings
          "is_indiamart_buyer":    bool  — company is a buyer on IndiaMART
          "is_indiamart_seller":   bool  — company is a seller (already digital)
          "indiamart_budget":      str   — budget hint if found
          "indiamart_url":         str
        }
    """
    # Run both lookups concurrently
    cat_result, company_result = await asyncio.gather(
        _search_category_enquiries(category, city),
        _check_company_on_indiamart(company_name),
        return_exceptions=True,
    )

    # Handle exceptions gracefully
    if isinstance(cat_result, Exception):
        cat_result = {"enquiry_count": 0, "evidence": []}
    if isinstance(company_result, Exception):
        company_result = {
            "is_indiamart_buyer": False, "is_indiamart_seller": False,
            "indiamart_budget": "", "indiamart_url": "",
        }

    # Build a signal string for the AI
    signal_parts = []

    if cat_result["enquiry_count"] > 0:
        signal_parts.append(
            f"{cat_result['enquiry_count']} active buyers on IndiaMART "
            f"looking for '{category}' in {city}"
        )

    if company_result["is_indiamart_buyer"]:
        signal_parts.append(
            f"{company_name} is an active BUYER on IndiaMART — confirmed procurement activity"
        )

    if company_result["indiamart_budget"]:
        signal_parts.append(f"IndiaMART budget hint: {company_result['indiamart_budget']}")

    if cat_result["evidence"]:
        signal_parts.append(f"Sample enquiry: '{cat_result['evidence'][0]}'")

    indiamart_signal = " | ".join(signal_parts)

    if indiamart_signal:
        print(f"[indiamart_enricher] '{company_name}': {indiamart_signal[:80]}")

    return {
        "indiamart_signal":    indiamart_signal,
        "category_buyers":     cat_result["enquiry_count"],
        "category_evidence":   cat_result["evidence"],
        "is_indiamart_buyer":  company_result["is_indiamart_buyer"],
        "is_indiamart_seller": company_result["is_indiamart_seller"],
        "indiamart_budget":    company_result["indiamart_budget"],
        "indiamart_url":       company_result["indiamart_url"],
    }
