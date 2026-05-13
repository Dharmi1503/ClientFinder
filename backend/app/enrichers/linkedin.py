"""
enricher_linkedin.py
=====================
LinkedIn Company Page Enricher
--------------------------------
LinkedIn blocks direct scraping, but DDG caches their pages.
We use DDG to find the company's LinkedIn page and extract:

  - Employee count (often in snippet: "51-200 employees")
  - Industry / specialties
  - Recent job postings (proxy for budget + growth)
  - About text (confirm what they actually do)

This converts vague "company size: Unknown" into
"SMB (51-200 employees)" and gives the AI real signals to work with.

No authentication, no Selenium — DDG + regex only.
"""

import asyncio
import re

import httpx

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

# Employee count ranges LinkedIn uses
_EMPLOYEE_RANGES = [
    (r'\b1[-–]10\b',       "1-10",     "Micro"),
    (r'\b11[-–]50\b',      "11-50",    "SMB"),
    (r'\b51[-–]200\b',     "51-200",   "SMB"),
    (r'\b201[-–]500\b',    "201-500",  "Mid-Market"),
    (r'\b501[-–]1[,.]?000\b', "501-1000", "Mid-Market"),
    (r'\b1[,.]?001[-–]5[,.]?000\b', "1001-5000", "Enterprise"),
    (r'\b5[,.]?001\b',     "5001+",    "Enterprise"),
    (r'\b10[,.]?001\b',    "10001+",   "Enterprise"),
]


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    if not DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
    except Exception as e:
        print(f"[linkedin_enricher] DDG error: {e}")
    return results


def _parse_employee_count(text: str) -> tuple[str, str]:
    """
    Extract employee range and size tag from text.
    Returns (range_str, size_tag) e.g. ("51-200", "SMB")
    """
    for pattern, range_str, size_tag in _EMPLOYEE_RANGES:
        if re.search(pattern, text, re.IGNORECASE):
            return range_str, size_tag
    # Try plain number: "200 employees"
    m = re.search(r'(\d[\d,]*)\s*\+?\s*employees?', text, re.IGNORECASE)
    if m:
        count = int(m.group(1).replace(",", ""))
        if count < 11:
            return f"~{count}", "Micro"
        elif count < 201:
            return f"~{count}", "SMB"
        elif count < 1001:
            return f"~{count}", "Mid-Market"
        else:
            return f"~{count}", "Enterprise"
    return "", "Unknown"


def _extract_job_count(text: str) -> int:
    """Extract number of open jobs from LinkedIn snippet."""
    m = re.search(r'(\d+)\s*(?:open\s+)?(?:job|position|opening|role)s?', text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


async def enrich_with_linkedin(company_name: str, city: str) -> dict:
    """
    Find and parse a company's LinkedIn page via DDG.

    Args:
        company_name: Company to look up
        city:         City for disambiguation

    Returns:
        {
          "linkedin_url":       str   — LinkedIn company page URL
          "employee_count":     str   — e.g. "51-200"
          "company_size_tag":   str   — SMB / Mid-Market / Enterprise
          "open_jobs":          int   — number of open positions
          "linkedin_about":     str   — About text from snippet
          "linkedin_signal":    str   — Formatted signal string for AI
          "hiring_signal":      bool  — True if actively hiring
        }
    """
    result = {
        "linkedin_url":     "",
        "employee_count":   "",
        "company_size_tag": "Unknown",
        "open_jobs":        0,
        "linkedin_about":   "",
        "linkedin_signal":  "",
        "hiring_signal":    False,
    }

    # Search for LinkedIn company page
    query = f'site:linkedin.com/company "{company_name}" {city}'
    raw = await asyncio.to_thread(_ddg_search, query, 5)

    if not raw:
        # Fallback: broader search
        query2 = f'"{company_name}" {city} linkedin employees'
        raw = await asyncio.to_thread(_ddg_search, query2, 5)

    for r in raw:
        href  = r.get("href", "")
        title = r.get("title", "")
        body  = r.get("body", "")
        combined = f"{title} {body}"

        # Prefer actual linkedin.com/company URLs
        if "linkedin.com/company" in href and not result["linkedin_url"]:
            result["linkedin_url"] = href

        # Extract employee count from any result
        if not result["employee_count"]:
            emp_range, size_tag = _parse_employee_count(combined)
            if emp_range:
                result["employee_count"]   = emp_range
                result["company_size_tag"] = size_tag

        # Job count
        jobs = _extract_job_count(combined)
        if jobs > result["open_jobs"]:
            result["open_jobs"] = jobs

        # About text
        if not result["linkedin_about"] and body and len(body) > 30:
            result["linkedin_about"] = body[:200]

    # Build signal string for AI context
    signals = []
    if result["employee_count"]:
        signals.append(f"{result['employee_count']} employees ({result['company_size_tag']})")
    if result["open_jobs"] > 0:
        signals.append(f"{result['open_jobs']} open job posting(s)")
        result["hiring_signal"] = True
    if result["linkedin_about"]:
        signals.append(f"About: {result['linkedin_about'][:120]}")

    result["linkedin_signal"] = " | ".join(signals)

    if result["linkedin_url"] or result["employee_count"]:
        print(
            f"[linkedin_enricher] '{company_name}': "
            f"size={result['company_size_tag']} | "
            f"jobs={result['open_jobs']} | "
            f"url={'found' if result['linkedin_url'] else 'not found'}"
        )

    return result
