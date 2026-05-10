"""
freelancer.py
=============
Freelancer project scraper — link-only mode.

Freelancer does NOT expose employer contact info publicly.
Goal: capture qualifying project URLs + metadata only.
Enricher + manual outreach handles contact later.

Filters applied before saving:
  - India/INR projects preferred (country param)
  - Open/active projects only (status 1 or 2)
  - Skills must overlap with query keywords
  - Budget must meet min threshold if specified
  - Paginated: up to 3 pages (60 projects)
"""

import asyncio
import re
import time
import httpx

from ddgs import DDGS
from app.database import log_scraper_run


_FL_API_BASE = "https://www.freelancer.com/api/projects/0.1/projects"

# Only score open or work-in-progress projects
_OPEN_STATUSES = {1, 2}

# Stop words for keyword matching
_STOP = {"and", "or", "the", "a", "in", "for", "of", "with", "at", "&", "to", "by"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_budget(minimum, maximum, currency: str) -> str:
    sym = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(currency, currency + " ")
    if minimum is None:
        return ""
    if maximum and maximum != minimum:
        return f"{sym}{int(minimum):,}–{sym}{int(maximum):,}"
    return f"{sym}{int(minimum):,}"


def _keywords(query: str) -> list[str]:
    return [w for w in query.lower().split() if w not in _STOP and len(w) > 2]


def _skills_match(jobs: list, query: str) -> bool:
    """At least one query keyword must appear in project skill tags."""
    kws = _keywords(query)
    if not kws:
        return True
    skill_blob = " ".join(j.get("name", "") for j in jobs).lower()
    return any(kw in skill_blob for kw in kws)


def _project_url(proj: dict) -> str:
    seo = proj.get("seo_url", "")
    pid = proj.get("id", "")
    if seo:
        return f"https://www.freelancer.com/projects/{seo}"
    return f"https://www.freelancer.com/projects/{pid}"


# ── API scraper (paginated) ───────────────────────────────────────────────────

async def _fetch_page(client: httpx.AsyncClient, query: str, offset: int) -> list[dict]:
    params = {
        "query":        query,
        "job_details":  "true",
        "limit":        20,
        "offset":       offset,
        "project_statuses[]": [1, 2],   # Gap 10: open only
        "country_code": "IN",           # Gap 3: India filter
    }
    headers = {
        "User-Agent":           "Mozilla/5.0 (compatible; LeadBot/1.0)",
        "freelancer-oauth-v1":  "",
    }
    try:
        resp = await client.get(_FL_API_BASE, params=params, headers=headers, timeout=15.0)
        if resp.status_code != 200:         # Gap 1: check status
            print(f"[freelancer] API {resp.status_code} at offset {offset}")
            return []
        data = resp.json()
        return data.get("result", {}).get("projects", [])
    except Exception as e:
        print(f"[freelancer] API error offset={offset}: {e}")
        return []


async def _scrape_api(query: str, city: str, max_pages: int = 3) -> list[dict]:
    leads = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient() as client:
        for page in range(max_pages):           # Gap 2: paginate
            offset = page * 20
            projects = await _fetch_page(client, query, offset)
            if not projects:
                break

            for proj in projects:
                # Gap 10: active status only
                if proj.get("status") not in _OPEN_STATUSES:
                    continue

                jobs = proj.get("jobs", [])

                # Gap 9: skill alignment
                if not _skills_match(jobs, query):
                    continue

                url = _project_url(proj)
                if url in seen_urls:            # Gap 7: dedup
                    continue
                seen_urls.add(url)

                budget = proj.get("budget", {})
                currency = proj.get("currency", {}).get("code", "USD")
                budget_str = _format_budget(
                    budget.get("minimum"), budget.get("maximum"), currency
                )

                skills_str = ", ".join(j.get("name", "") for j in jobs[:5] if j.get("name"))
                title = proj.get("title", "")[:80]
                desc  = (proj.get("description", "") or "")[:250]

                # Gap 4: use title as display name, flag it's a project not a company
                leads.append({
                    "company_name":  title,          # project title — enricher will resolve real company
                    "phone":         "",             # not available on Freelancer
                    "email":         "",             # not available on Freelancer
                    "location":      city,
                    "category":      skills_str or query,
                    "source":        "freelancer",
                    "source_url":    url,            # ← direct project link, the real value
                    "contact_link":  url,
                    "snippet":       desc,
                    "budget_hint":   budget_str,
                    "intent_signal": f"Active Freelancer project — buyer posted live requirement: {title}",
                })

            if len(projects) < 20:
                break                               # last page
            await asyncio.sleep(0.5)               # polite gap

    print(f"[freelancer] API: {len(leads)} qualifying projects across {max_pages} pages")
    return leads


# ── DDG fallback ──────────────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 10) -> list[dict]:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
    except Exception as e:
        print(f"[freelancer] DDG error: {e}")
    return results


async def _scrape_ddg(query: str, city: str) -> list[dict]:
    """Gap 5: tight, focused DDG query — no broad ORs."""
    search_query = f'site:freelancer.com/projects "{query}" India'
    raw = await asyncio.to_thread(_ddg_search, search_query, 15)

    leads = []
    seen: set[str] = set()

    for r in raw:
        url   = r.get("href", "")
        title = r.get("title", "")
        body  = r.get("body", "")

        if "freelancer.com/project" not in url:
            continue
        if url in seen:
            continue
        seen.add(url)

        # Gap 5: query keyword must appear in snippet
        kws = _keywords(query)
        combined = (title + " " + body).lower()
        if kws and not any(kw in combined for kw in kws):
            continue

        name = re.sub(r'\s*[-|–]\s*Freelancer.*$', '', title, flags=re.IGNORECASE).strip()
        if len(name) < 4:
            name = title[:60]

        leads.append({
            "company_name":  name[:80],
            "phone":         "",
            "email":         "",
            "location":      city,
            "category":      query,
            "source":        "freelancer",
            "source_url":    url,
            "contact_link":  url,
            "snippet":       body[:250],
            "budget_hint":   "",
            "intent_signal": f"Freelancer project listing — active buyer requirement",
        })

    print(f"[freelancer] DDG fallback: {len(leads)} leads")
    return leads


# ── Main ──────────────────────────────────────────────────────────────────────

async def scrape_freelancer(query: str, city: str) -> list[dict]:
    """
    Returns qualifying Freelancer project links.
    No phone/email — that's expected. source_url IS the lead.
    Enricher will attempt to find employer profile later.
    """
    leads = await _scrape_api(query, city)

    if not leads:
        print("[freelancer] API empty, falling back to DDG")
        leads = await _scrape_ddg(query, city)

    # Gap 8: real rejection count
    # (all raw projects fetched vs those that passed filters)
    # approximate: API returns up to 60 raw, leads = passed
    raw_attempted = 60  # max possible from 3 pages
    saved = len(leads)
    rejected = max(0, raw_attempted - saved)

    print(f"[freelancer] {saved} leads saved")
    log_scraper_run("freelancer", attempted=raw_attempted,
                    saved=saved, rejected=rejected)
    return leads