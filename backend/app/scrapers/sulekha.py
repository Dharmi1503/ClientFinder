"""
scrapers/sulekha.py — v2
=========================
Fixes applied:
  - DDG results 12→25, retry 3× with backoff
  - City alias map
  - Multi-query: 3 slug/query variants
  - Dedup by name+city
  - Email extraction from cards and snippets
  - JSON-LD fallback when HTML card selectors fail
  - HTTP fetch retry 3× before DDG fallback
  - Phone regex covers mobile + landline
"""

import asyncio
import json
import re
from datetime import date

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


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.sulekha.com/",
}

_TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# City alias map
# ---------------------------------------------------------------------------
_CITY_ALIASES: dict[str, list[str]] = {
    "mumbai":    ["mumbai", "bombay", "navi-mumbai", "thane"],
    "delhi":     ["delhi", "new-delhi", "ncr"],
    "bangalore": ["bangalore", "bengaluru", "blr"],
    "hyderabad": ["hyderabad", "secunderabad"],
    "chennai":   ["chennai", "madras"],
    "kolkata":   ["kolkata", "calcutta"],
    "pune":      ["pune", "pimpri-chinchwad"],
    "ahmedabad": ["ahmedabad", "amdavad"],
    "jaipur":    ["jaipur"],
    "surat":     ["surat"],
}

def _city_slugs(city: str) -> list[str]:
    key = city.lower().strip().replace(" ", "-")
    for canonical, aliases in _CITY_ALIASES.items():
        if key in aliases or key == canonical:
            return [canonical] + [a for a in aliases if a != canonical][:1]
    return [key]


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
            print(f"[sulekha] DDG attempt {attempt+1} error: {e}")
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


def _extract_rating(text: str) -> str:
    match = re.search(r'(\d\.\d)\s*(?:out of|/)?[\s]*5', text)
    return match.group(1) if match else ""


def _clean_name(raw: str) -> str:
    cleaned = re.sub(
        r'\s*[-|–]\s*(Sulekha|JustDial|IndiaMART|Yellow Pages|'
        r'Service Providers?|Near Me|in \w+).*$',
        '', raw, flags=re.IGNORECASE
    ).strip()
    return re.sub(r'[,.\-|]+$', '', cleaned).strip()


def _make_lead(company_name, city, industry, description,
               source_url, phone="", email="", website="", rating="") -> dict:
    return {
        "company_name": company_name[:80],
        "location": city,
        "industry": industry[:100],
        "description": description[:300],
        "phone": phone,
        "email": email,
        "website": website,
        "linkedin_url": "",
        "source": "sulekha",
        "source_url": source_url,
        "contact_link": source_url,
        "company_size": "",
        "intent_signal": f"Listed on Sulekha — active service provider in {city}",
        "scrape_date": _TODAY,
        "rating": rating,
    }


# ---------------------------------------------------------------------------
# JSON-LD fallback parser (when card selectors miss)
# ---------------------------------------------------------------------------

def _parse_jsonld(html: str, city: str, industry: str, page_url: str) -> list[dict]:
    """Extract leads from JSON-LD LocalBusiness blocks embedded in page."""
    leads = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                              html, re.DOTALL | re.IGNORECASE):
        try:
            blob = json.loads(match.group(1))
            items = blob if isinstance(blob, list) else [blob]
            for item in items:
                if item.get("@type") not in ("LocalBusiness", "Organization", "Store"):
                    continue
                name = item.get("name", "").strip()
                if not name or len(name) < 3:
                    continue
                phone = _extract_phone(str(item.get("telephone", "")))
                email = item.get("email", "")
                address = item.get("address", {})
                addr_str = ""
                if isinstance(address, dict):
                    addr_str = ", ".join(filter(None, [
                        address.get("streetAddress", ""),
                        address.get("addressLocality", ""),
                        address.get("addressRegion", ""),
                    ]))
                rating_obj = item.get("aggregateRating", {})
                rating = str(rating_obj.get("ratingValue", "")) if isinstance(rating_obj, dict) else ""
                url = item.get("url", page_url)

                leads.append(_make_lead(
                    company_name=name, city=city, industry=industry,
                    description=addr_str or f"Sulekha listing in {city}",
                    source_url=url, phone=phone, email=email, rating=rating,
                ))
        except Exception:
            continue
    return leads


# ---------------------------------------------------------------------------
# Strategy 1 — Direct HTTP + HTML parse + JSON-LD fallback
# ---------------------------------------------------------------------------

async def _scrape_direct(query: str, city: str) -> list[dict]:
    slugs = _city_slugs(city)
    query_slug = query.lower().strip().replace(" ", "-")

    html = ""
    final_url = ""
    for city_slug in slugs[:2]:
        url = f"https://www.sulekha.com/{city_slug}/{query_slug}"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers=_HEADERS)
                    if resp.status_code == 200:
                        html = resp.text
                        final_url = url
                        break
                    print(f"[sulekha] HTTP {resp.status_code} (attempt {attempt+1})")
            except Exception as e:
                print(f"[sulekha] fetch error attempt {attempt+1}: {e}")
            await asyncio.sleep(1.5 * (attempt + 1))
        if html:
            break

    if not html:
        return []

    if not BS4_AVAILABLE:
        # JSON-LD only
        return _parse_jsonld(html, city, query, final_url)

    soup = BeautifulSoup(html, "html.parser")
    leads: list[dict] = []

    cards = (
        soup.find_all("div", class_=re.compile(r"sp-list|sp-card|splist|biz-card|listing-card", re.I))
        or soup.find_all("li", class_=re.compile(r"sp-list|listing|business", re.I))
        or soup.find_all("div", class_=re.compile(r"business.listing|provider.card", re.I))
    )

    if not cards:
        all_divs = soup.find_all("div")
        cards = [d for d in all_divs if re.search(r'[6-9]\d{9}', d.get_text())][:20]

    for card in cards[:25]:
        text = card.get_text(" ", strip=True)

        name_tag = (
            card.find(class_=re.compile(r"business.name|sp.name|company.name|biz.name", re.I))
            or card.find("h2")
            or card.find("h3")
            or card.find("a", class_=re.compile(r"name|title", re.I))
        )
        name = _clean_name(name_tag.get_text(strip=True)) if name_tag else ""

        if not name or len(name) < 3:
            found = re.findall(
                r'([A-Z][a-zA-Z0-9 &]{2,40}'
                r'(?:Pvt\.?\s?Ltd\.?|LLP|Associates?|Enterprises?|Technologies|Solutions)?)',
                text
            )
            name = found[0].strip() if found else ""

        if not name or len(name) < 3:
            continue

        phone = _extract_phone(text)
        email = _extract_email(text)

        site_tag = card.find("a", href=re.compile(r'^https?://(?!sulekha)', re.I))
        website = site_tag["href"] if site_tag else ""

        link_tag = card.find("a", href=re.compile(r'/profile/|/business/', re.I))
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            listing_url = href if href.startswith("http") else f"https://www.sulekha.com{href}"
        else:
            listing_url = final_url

        rating = _extract_rating(text)
        desc_tag = card.find(class_=re.compile(r"description|about|snippet|tagline", re.I))
        description = desc_tag.get_text(" ", strip=True)[:250] if desc_tag else text[:200]

        leads.append(_make_lead(
            company_name=name, city=city, industry=query,
            description=description, source_url=listing_url,
            phone=phone, email=email, website=website, rating=rating,
        ))

    # If HTML parse got nothing, try JSON-LD
    if not leads:
        leads = _parse_jsonld(html, city, query, final_url)

    print(f"[sulekha] direct parse: {len(leads)} leads")
    return leads


# ---------------------------------------------------------------------------
# Strategy 2 — DDG fallback (3 query variants)
# ---------------------------------------------------------------------------

async def _scrape_ddg(query: str, city: str) -> list[dict]:
    queries = [
        f'site:sulekha.com "{query}" "{city}"',
        f'site:sulekha.com {query} {city} phone contact',
        f'sulekha {query} {city} service provider',
    ]
    raw: list[dict] = []
    seen_urls: set[str] = set()
    for q in queries:
        for r in await asyncio.to_thread(_ddg_search, q, 25):
            if r.get("href") not in seen_urls:
                seen_urls.add(r.get("href", ""))
                raw.append(r)

    leads: list[dict] = []
    for r in raw:
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href", "")

        name = _clean_name(title)
        if len(name) < 3:
            found = re.findall(
                r'([A-Z][a-zA-Z0-9 &]{2,40}'
                r'(?:Pvt\.?\s?Ltd\.?|LLP|Associates?|Enterprises?)?)',
                body
            )
            name = found[0].strip() if found else ""

        if not name or len(name) < 3:
            continue

        phone = _extract_phone(body + " " + title)
        email = _extract_email(body + " " + title)

        leads.append(_make_lead(
            company_name=name, city=city, industry=query,
            description=body[:220], source_url=href,
            phone=phone, email=email,
        ))

    print(f"[sulekha] DDG fallback: {len(leads)} leads")
    return leads


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_sulekha(query: str, city: str) -> list[dict]:
    """
    Sulekha scraper v2.
    - City aliases + multi-slug
    - JSON-LD fallback when HTML cards missing
    - Email extraction
    - Dedup by name+city
    - DDG 3-query variant fallback
    """
    leads = await _scrape_direct(query, city)

    if not leads:
        print("[sulekha] direct empty — trying DDG")
        leads = await _scrape_ddg(query, city)

    # Dedup by name+city
    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = f"{lead['company_name'].lower().strip()}|{lead['location'].lower().strip()}"
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[sulekha] {len(unique)} unique leads for '{query}' in {city}")
    log_scraper_run(
        "sulekha",
        attempted=len(leads),
        saved=len(unique),
        rejected=max(0, len(leads) - len(unique)),
    )
    return unique