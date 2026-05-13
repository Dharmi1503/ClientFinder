import asyncio
import re
import time

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from app.database import log_scraper_run


JUNK_NAME_STARTS = {
    "top", "best", "list", "agency", "india", "companies",
    "2024", "2025", "leading", "find", "hire", "reviews",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _ddg_search(query: str, max_results: int = 10) -> list[dict]:
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            wait = 2 ** attempt
            print(f"[clutch] DDG attempt {attempt + 1} failed: {e}. Retry in {wait}s")
            time.sleep(wait)
    print("[clutch] DDG gave up after 3 attempts")
    return []


def _extract_review_count(text: str) -> int:
    match = re.search(r"(\d+)\s*review", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _extract_budget(text: str) -> str:
    match = re.search(
        r"(INR|₹|\$|USD|Rs\.?)\s?[\d,]+(\s?[-–]\s?[\d,]+)?"
        r"|(?:min(?:imum)?\.?\s*(?:project\s*)?size[:\s]+)([\d,]+)",
        text,
        re.IGNORECASE,
    )
    return match.group(0).strip() if match else ""


def _is_valid_name(name: str) -> bool:
    if not name or len(name) < 4:
        return False
    first_word = name.lower().split()[0]
    if first_word in JUNK_NAME_STARTS:
        return False
    if re.fullmatch(r"[\d\s]+", name):
        return False
    return True


async def _fetch_clutch_page(url: str) -> dict:
    result = {"email": "", "phone": "", "name": "", "budget": "", "reviews": 0}
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code != 200:
            return result

        soup = BeautifulSoup(response.text, "html.parser")

        h1 = soup.find("h1")
        if h1:
            result["name"] = h1.get_text(strip=True)

        email_tag = soup.find("a", href=lambda href: href and href.startswith("mailto:"))
        if email_tag:
            result["email"] = email_tag["href"].replace("mailto:", "").strip()

        phone_tag = soup.find("a", href=lambda href: href and href.startswith("tel:"))
        if phone_tag:
            result["phone"] = phone_tag["href"].replace("tel:", "").strip()

        full_text = soup.get_text(" ", strip=True)
        result["budget"] = _extract_budget(full_text)
        result["reviews"] = _extract_review_count(full_text)
    except Exception as e:
        print(f"[clutch] page fetch failed for {url}: {e}")

    return result


async def scrape_clutch(query: str, city: str) -> list[dict]:
    search_queries = [
        f'site:clutch.co "{query}" {city} reviews "min. project size"',
        f'site:clutch.co "{query}" India budget reviews',
        f'site:clutch.co "{query}" {city} top company',
        f'site:clutch.co "{query}" {city} OR India software',
    ]

    seen_urls: set[str] = set()
    raw: list[dict] = []
    for search_query in search_queries:
        for result in await asyncio.to_thread(_ddg_search, search_query, 10):
            url = result.get("href", "")
            if url and "clutch.co" in url.lower() and url not in seen_urls:
                seen_urls.add(url)
                raw.append(result)

    print(f"[clutch] {len(raw)} unique clutch URLs found across all queries")

    leads: list[dict] = []
    for result in raw:
        title = result.get("title", "")
        body = result.get("body", "")
        url = result.get("href", "")

        name = re.sub(
            r"\s*[-|–]\s*(Reviews|Clutch|Top|Best|Agency).*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        if not _is_valid_name(name):
            found = re.search(r"([A-Z][a-zA-Z0-9\s&]{3,40})", body)
            name = found.group(0).strip() if found else ""

        budget = _extract_budget(body + " " + title)
        reviews = _extract_review_count(body)
        page = await _fetch_clutch_page(url)

        if not _is_valid_name(name) and _is_valid_name(page["name"]):
            name = page["name"]

        if not _is_valid_name(name):
            print(f"[clutch] skip - bad name from: {url}")
            continue

        leads.append({
            "company_name": name[:80],
            "phone": page["phone"],
            "email": page["email"],
            "location": city,
            "category": query,
            "source": "clutch",
            "source_url": url,
            "contact_link": url,
            "snippet": body[:200],
            "budget_hint": page["budget"] or budget,
            "review_count": page["reviews"] or reviews,
        })

    print(f"[clutch] {len(leads)} valid leads after filtering")
    log_scraper_run(
        "clutch",
        attempted=len(raw),
        saved=len(leads),
        rejected=max(0, len(raw) - len(leads)),
    )
    return leads
