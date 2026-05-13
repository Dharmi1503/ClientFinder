"""
scrapers/guru.py
================
Guru public jobs scraper with DDG fallback.
"""

import asyncio
import re
from datetime import date, timedelta
from urllib.parse import quote_plus

import httpx

from app.database import log_scraper_run

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


_TODAY = date.today()
_BUDGET_RE = re.compile(r"(?i)(?:\$|₹|rs\.?|inr)\s*([\d,]+)")
_DATE_RE = re.compile(r"(?i)(today|yesterday|\d+\s+(?:day|days|hour|hours)\s+ago)")
_DDG_GARBAGE = re.compile(
    r"(?i)find freelance jobs|search for projects|work your way|"
    r"\s\|\s|sign up|login|post a job|how it works"
)

# Title quality filter: reject garbage patterns
_GARBAGE_TITLE = re.compile(
    r"(?i)^guru|"  # starts with "Guru"
    r"\bfreelancer\b|"  # contains "freelancer" as standalone word
    r"hire a|"  # contains "hire a"
    r"find a developer|"  # contains "find a developer"
    r"top freelance"  # contains "top freelance"
)


def _extract_budget_value(text: str) -> tuple[str, float | None]:
    match = _BUDGET_RE.search(text or "")
    if not match:
        return "", None
    raw = match.group(0).strip()
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return raw, None
    return raw, value


def _budget_ok(text: str) -> tuple[str, bool]:
    raw, value = _extract_budget_value(text)
    if value is None:
        return raw, True
    lowered = (text or "").lower()
    if "$" in raw and value < 100:
        return raw, False
    if any(token in lowered for token in ("₹", "rs", "inr")) and value < 5000:
        return raw, False
    return raw, True


def _parse_relative_date(text: str) -> str:
    lowered = (text or "").lower()
    if "today" in lowered:
        return _TODAY.isoformat()
    if "yesterday" in lowered:
        return (_TODAY - timedelta(days=1)).isoformat()
    match = re.search(r"(\d+)\s+(day|days|hour|hours)\s+ago", lowered)
    if not match:
        return ""
    qty = int(match.group(1))
    unit = match.group(2)
    if "hour" in unit:
        return _TODAY.isoformat()
    return (_TODAY - timedelta(days=qty)).isoformat()


def _within_7_days(posted_date: str) -> bool:
    if not posted_date:
        return False
    try:
        parsed = date.fromisoformat(posted_date)
    except ValueError:
        return False
    return (_TODAY - parsed).days <= 7


def _is_title_quality(title: str) -> bool:
    """Check if title has minimum quality (length > 15 chars, no garbage patterns)."""
    if not title or len(title) < 15:
        return False
    return not _GARBAGE_TITLE.search(title)


async def _fetch_direct(service: str) -> str:
    slug = service.replace(" ", "-")
    keyword = quote_plus(service)
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        urls = [
            f"https://www.guru.com/d/jobs/q/{slug}/",
            f"https://www.guru.com/d/jobs/?keyword={keyword}",
        ]
        last_response = None
        for url in urls:
            resp = await client.get(url, headers={"User-Agent": "ClientFinder/1.0"})
            last_response = resp
            if resp.status_code == 200:
                return resp.text
        raise httpx.HTTPStatusError(
            f"Guru direct fetch failed for all URL patterns: {urls}",
            request=last_response.request if last_response else None,
            response=last_response,
        )


def _parse_direct(html: str, service: str, city: str, max_results: int) -> list[dict]:
    if not BS4_AVAILABLE:
        return []
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.jobRecord, div.job-card, div.record, li[data-job-id]")
    leads: list[dict] = []

    for card in cards[: max_results * 2]:
        title_tag = card.select_one("a.jobTitle, a.job-title, h2 a, h3 a, a[href*='/jobs/']")
        title = title_tag.get_text(" ", strip=True) if title_tag else ""
        job_url = title_tag.get("href", "") if title_tag else ""
        if job_url and job_url.startswith("/"):
            job_url = f"https://www.guru.com{job_url}"

        desc_tag = card.select_one("div.jobDescription, div.job-description, p, div.desc")
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""
        meta_text = card.get_text(" ", strip=True)
        employer_tag = card.select_one("div.emp-name, span.emp-name, a.employer-name")
        employer = employer_tag.get_text(" ", strip=True) if employer_tag else title
        location_tag = card.select_one("span.location, div.location")
        posted_city = location_tag.get_text(" ", strip=True) if location_tag else city

        posted_match = _DATE_RE.search(meta_text)
        posted_date = _parse_relative_date(posted_match.group(0)) if posted_match else ""
        if not _within_7_days(posted_date):
            continue

        budget, budget_allowed = _budget_ok(meta_text)
        if not budget_allowed:
            continue

        if not title or not job_url or not _is_title_quality(title):
            continue

        leads.append({
            "company_name": employer[:80] or title[:80],
            "title": title[:200],
            "post_title": title[:200],
            "description": description[:300] or title[:300],
            "budget": budget,
            "source": "guru",
            "source_url": job_url,
            "contact_link": job_url,
            "platform_url": job_url,
            "posted_date": posted_date,
            "location": posted_city[:100] or city,
            "industry": service[:100],
            "phone": "",
            "email": "",
            "website": "",
            "linkedin_url": "",
            "company_size": "SMB",
            "intent_signal": f"Guru job: {title}"[:500],
            "scrape_date": _TODAY.isoformat(),
        })
        if len(leads) >= max_results:
            break

    return leads


def _ddg_search(query: str, max_results: int = 20) -> list[dict]:
    if not DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        print(f"[guru] DDG error: {exc}")
        return []


async def _fetch_ddg(service: str, city: str, max_results: int) -> list[dict]:
    query = f"guru.com jobs {service} india client project"
    results = await asyncio.to_thread(_ddg_search, query, max_results)
    leads: list[dict] = []
    for item in results:
        title = (item.get("title") or "").strip()
        description = (item.get("body") or "").strip()
        url = (item.get("href") or "").strip()
        budget, budget_allowed = _budget_ok(description)
        combined = f"{title} {description}"
        if (
            not title
            or not url
            or not budget_allowed
            or _DDG_GARBAGE.search(title)
            or _DDG_GARBAGE.search(combined)
            or url.rstrip("/").lower() == "https://www.guru.com/d/jobs"
            or not _is_title_quality(title)
        ):
            continue
        leads.append({
            "company_name": title[:80],
            "title": title[:200],
            "post_title": title[:200],
            "description": description[:300],
            "budget": budget,
            "source": "guru",
            "source_url": url,
            "contact_link": url,
            "platform_url": url,
            "posted_date": _TODAY.isoformat(),
            "location": city,
            "industry": service[:100],
            "phone": "",
            "email": "",
            "website": "",
            "linkedin_url": "",
            "company_size": "SMB",
            "intent_signal": f"Guru DDG job: {title}"[:500],
            "scrape_date": _TODAY.isoformat(),
        })
        if len(leads) >= max_results:
            break
    return leads


async def scrape_guru(service: str, city: str, max_results: int = 20) -> list[dict]:
    try:
        html = await _fetch_direct(service)
        leads = _parse_direct(html, service, city, max_results)
    except Exception as exc:
        print(f"[guru] direct fetch failed: {exc}")
        leads = []

    if not leads:
        print("[guru] direct parse empty - trying DDG fallback")
        leads = await _fetch_ddg(service, city, max_results)

    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = (lead.get("platform_url") or "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[guru] {len(unique)} leads for '{service}' in {city}")
    log_scraper_run(
        "guru",
        attempted=len(leads),
        saved=len(unique),
        rejected=max(0, len(leads) - len(unique)),
    )
    return unique
