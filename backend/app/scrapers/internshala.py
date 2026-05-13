"""
scrapers/internshala.py
========================
Internshala Job Scraper — FIXED (all 12 gaps patched)

Gap fixes:
  GAP 1  → 3 URL patterns tried (slug variations)
  GAP 2  → retry with backoff on HTTP failure
  GAP 3  → DDG results 12→25, retry with backoff
  GAP 4  → dedup on name+city not name only
  GAP 5  → city validation — city/alias must appear in result
  GAP 6  → city alias map (Bangalore→Bengaluru etc)
  GAP 7  → text-based extraction backup if CSS classes break
  GAP 8  → email + phone extraction from snippets
  GAP 9  → DDG query loosened, 2 query variants merged
  GAP 10 → date computed inside function not at import
  GAP 11 → pagination — fetches up to 3 pages
  GAP 12 → company_size captured from card text
"""

import asyncio
import re
import time
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
    "Referer": "https://internshala.com/",
}


# ── City aliases (GAP 6) ──────────────────────────────────────────────────────
CITY_ALIASES: dict[str, list[str]] = {
    "bengaluru":  ["bengaluru", "bangalore", "whitefield", "electronic city"],
    "mumbai":     ["mumbai", "bombay", "thane", "navi mumbai"],
    "delhi":      ["delhi", "new delhi", "noida", "gurugram", "gurgaon"],
    "hyderabad":  ["hyderabad", "secunderabad", "cyberabad"],
    "pune":       ["pune", "pimpri", "chinchwad"],
    "ahmedabad":  ["ahmedabad", "gandhinagar"],
    "chennai":    ["chennai", "madras"],
    "kolkata":    ["kolkata", "calcutta", "howrah"],
    "surat":      ["surat", "udhna", "adajan"],
    "jaipur":     ["jaipur", "pink city"],
}

_BLOCKED_JOB_TITLE = re.compile(
    r"(?i)\b(salary|hiring|job|internship|fresher|stipend)\b"
)
_REQUEST_STYLE_TITLE = re.compile(
    r"(?i)\b(looking for|need|require|wanted|project|freelance)\b"
)


def _city_match(text: str, city: str) -> bool:
    """GAP 5+6: city OR any alias must appear in text."""
    text_l = text.lower()
    variants = CITY_ALIASES.get(city.lower(), [city.lower()])
    return any(v in text_l for v in variants)


# ── Phone + email (GAP 8) ─────────────────────────────────────────────────────
_PHONE_RE = re.compile(
    r'(\+91[\s\-]?)?(\(\d{2,5}\)[\s\-]?)?\b[6-9]\d{4}[\s\-]?\d{5}\b'
    r'|0\d{2,4}[\s\-]\d{6,8}'
)
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')


def _extract_phone(text: str) -> str:
    m = _PHONE_RE.search(text)
    return re.sub(r'\s+', ' ', m.group(0)).strip() if m else ""


def _extract_email(text: str) -> str:
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else ""


# ── Company size (GAP 12) ─────────────────────────────────────────────────────
_SIZE_RE = re.compile(
    r'(\d+[\s\-–]+\d+\s*employees?|'
    r'\d+\+?\s*employees?|'
    r'(startup|small|mid[- ]size|large)\s*(company|team|organisation)?)',
    re.IGNORECASE
)


def _extract_company_size(text: str) -> str:
    m = _SIZE_RE.search(text)
    return m.group(0).strip() if m else ""


# ── DDG search with retry (GAP 3) ─────────────────────────────────────────────
def _ddg_search(query: str, max_results: int = 25) -> list[dict]:
    """GAP 3: 25 results, 3 retries with backoff."""
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
            print(f"[internshala] DDG attempt {attempt+1} error: {e}")
        time.sleep(1.5 * (2 ** attempt))
    return []


# ── Name cleaner ──────────────────────────────────────────────────────────────
def _clean_company_name(raw: str) -> str:
    cleaned = re.sub(
        r'\s*[-|–]\s*(Internshala|Jobs|Hiring|Recruitment|Careers?).*$',
        '', raw, flags=re.IGNORECASE
    ).strip()
    return re.sub(r'[,.\-|]+$', '', cleaned).strip()


def _is_request_style_title(title: str) -> bool:
    title = (title or "").strip()
    if not title:
        return False
    if _BLOCKED_JOB_TITLE.search(title):
        return False
    return bool(_REQUEST_STYLE_TITLE.search(title))


# ── Lead builder (GAP 10: date computed here) ─────────────────────────────────
def _make_lead(
    company_name: str,
    city: str,
    industry: str,
    description: str,
    source_url: str,
    website: str = "",
    phone: str = "",
    email: str = "",
    company_size: str = "",
    intent_signal: str = "",
) -> dict:
    return {
        "company_name":  company_name[:80],
        "location":      city,
        "industry":      industry[:100],
        "description":   description[:300],
        "phone":         phone,
        "email":         email,
        "website":       website,
        "source":        "internshala",
        "source_url":    source_url,
        "contact_link":  source_url,
        "company_size":  company_size,
        "intent_signal": intent_signal or f"Actively hiring for: {industry}",
        "scrape_date":   date.today().isoformat(),   # GAP 10: computed now
    }


# ── URL builder (GAP 1) ───────────────────────────────────────────────────────
def _build_urls(query: str, city: str, page: int = 1) -> list[str]:
    """
    GAP 1: 3 URL pattern variations.
    Internshala changes slug format — try all three.
    GAP 11: page param for pagination.
    """
    q = query.lower().strip().replace(" ", "-")
    c = city.lower().strip().replace(" ", "-")
    page_suffix = f"/{page}" if page > 1 else ""
    return [
        f"https://internshala.com/jobs/{q}-jobs-in-{c}{page_suffix}",
        f"https://internshala.com/jobs/{q}/{c}{page_suffix}",
        f"https://internshala.com/internships/{q}-internship-in-{c}{page_suffix}",
    ]


# ── HTTP fetch with retry (GAP 2) ─────────────────────────────────────────────
async def _fetch_html(url: str) -> str | None:
    """GAP 2: 3 retries with backoff on HTTP failure."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True
            ) as client:
                resp = await client.get(url, headers=_HEADERS)
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code == 404:
                    return None   # URL pattern wrong, try next
                print(f"[internshala] HTTP {resp.status_code} attempt {attempt+1}: {url}")
        except Exception as e:
            print(f"[internshala] fetch error attempt {attempt+1}: {e}")
        await asyncio.sleep(1.5 * (2 ** attempt))
    return None


# ── Card parser (GAP 7: text fallback) ───────────────────────────────────────
def _parse_cards(soup: "BeautifulSoup", query: str, city: str) -> list[dict]:
    """
    GAP 7: tries CSS selectors first, falls back to
    text-pattern extraction if selectors fail.
    """
    cards = (
        soup.find_all("div", class_=re.compile(
            r"job.internship.card|individual_internship", re.I))
        or soup.find_all("div", attrs={"data-internship_id": True})
        or soup.find_all("div", class_=re.compile(
            r"container-fluid\s+individual", re.I))
    )

    leads = []

    if cards:
        for card in cards[:20]:
            text = card.get_text(" ", strip=True)

            # Company
            company_tag = (
                card.find("a", class_=re.compile(r"link_display|company", re.I))
                or card.find("p", class_=re.compile(r"company", re.I))
            )
            company = (
                _clean_company_name(company_tag.get_text(strip=True))
                if company_tag else ""
            )
            # GAP 7 fallback: regex on card text
            if not company or len(company) < 3:
                found = re.findall(
                    r'([A-Z][a-zA-Z0-9 &]{2,35}'
                    r'(?:Pvt\.?\s?Ltd\.?|LLP|Inc\.?|Technologies|Solutions|Services)?)',
                    text
                )
                company = found[0].strip() if found else ""

            if not company or len(company) < 3:
                continue

            # Role
            role_tag = (
                card.find("a", class_=re.compile(r"job.title|profile", re.I))
                or card.find("h3") or card.find("h4")
            )
            role = role_tag.get_text(strip=True) if role_tag else query
            if not _is_request_style_title(role):
                continue

            # Location
            loc_tag = card.find(class_=re.compile(r"location|city", re.I))
            location = (
                re.sub(r'[^a-zA-Z\s,]', '',
                       loc_tag.get_text(strip=True)).strip()
                if loc_tag else city
            ) or city

            # URL
            link_tag = card.find(
                "a", href=re.compile(r'/job-detail/|/jobs/', re.I))
            href = link_tag["href"] if link_tag and link_tag.get("href") else ""
            listing_url = (
                href if href.startswith("http")
                else f"https://internshala.com{href}"
            ) if href else ""

            # Website
            site_tag = card.find(
                "a", href=re.compile(r'^https?://(?!internshala)', re.I))
            website = site_tag["href"] if site_tag else ""

            # Description
            desc_tag = card.find(class_=re.compile(
                r"internship.other.details|job.desc|description", re.I))
            description = (
                desc_tag.get_text(" ", strip=True)[:250]
                if desc_tag
                else f"Hiring for {role} in {location}"
            )

            # GAP 8: extract contact info
            phone = _extract_phone(text)
            email = _extract_email(text)

            # GAP 12: company size
            size = _extract_company_size(text)

            leads.append(_make_lead(
                company_name=company,
                city=location,
                industry=role,
                description=description,
                source_url=listing_url,
                website=website,
                phone=phone,
                email=email,
                company_size=size,
                intent_signal=f"Actively hiring {role} — confirmed tech/digital budget",
            ))

    else:
        # GAP 7: full text fallback — extract from raw page text
        print("[internshala] CSS selectors failed — using text extraction fallback")
        page_text = soup.get_text(" ", strip=True)
        companies = re.findall(
            r'([A-Z][a-zA-Z0-9 &]{3,40}'
            r'(?:Pvt\.?\s?Ltd\.?|LLP|Technologies|Solutions|Services))',
            page_text
        )
        seen_fb: set[str] = set()
        for co in companies[:15]:
            co = co.strip()
            if co.lower() in seen_fb or len(co) < 4:
                continue
            seen_fb.add(co.lower())
            leads.append(_make_lead(
                company_name=co,
                city=city,
                industry=query,
                description=f"Hiring for {query} in {city}",
                source_url="https://internshala.com",
                intent_signal=f"Actively hiring {query} — confirmed digital budget",
            ))

    return leads


# ── Direct HTTP scraper (GAP 1, 2, 11) ───────────────────────────────────────
async def _scrape_direct(query: str, city: str) -> list[dict]:
    """
    GAP 1: tries 3 URL patterns.
    GAP 11: paginates up to 3 pages per working URL.
    GAP 2: each fetch retries 3× with backoff.
    """
    if not BS4_AVAILABLE:
        print("[internshala] BeautifulSoup not installed — skipping direct parse")
        return []

    all_leads: list[dict] = []
    working_url_base: str | None = None

    # Find which URL pattern works
    for url in _build_urls(query, city, page=1):
        html = await _fetch_html(url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            leads = _parse_cards(soup, query, city)
            if leads:
                working_url_base = url
                all_leads.extend(leads)
                break

    if not working_url_base:
        print("[internshala] no working URL pattern found")
        return []

    # GAP 11: paginate pages 2 and 3
    base = re.sub(r'/\d+$', '', working_url_base)   # strip existing page
    for page in range(2, 4):
        page_url = f"{base}/{page}"
        html = await _fetch_html(page_url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        page_leads = _parse_cards(soup, query, city)
        if not page_leads:
            break
        all_leads.extend(page_leads)
        await asyncio.sleep(1.0)   # polite gap between pages

    print(f"[internshala] direct parse: {len(all_leads)} leads")
    return all_leads


# ── DDG fallback (GAP 3, 9) ───────────────────────────────────────────────────
async def _scrape_ddg(query: str, city: str) -> list[dict]:
    """
    GAP 9: 2 query variants merged (strict + loose).
    GAP 3: 25 results + retry.
    """
    # GAP 9: two query angles
    queries = [
        f'site:internshala.com/job-detail "{query}" "{city}"',
        f'site:internshala.com {query} jobs {city} hiring',
    ]

    seen_urls: set[str] = set()
    raw_all:   list[dict] = []

    for q in queries:
        results = await asyncio.to_thread(_ddg_search, q, 25)
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
        href  = r.get("href", "")

        company = ""
        role    = query

        at_match      = re.search(r'\bat\s+([A-Z][a-zA-Z0-9 &]{2,40})', title)
        hiring_match  = re.search(
            r'([A-Z][a-zA-Z0-9 &]{2,40})\s+is hiring', title, re.IGNORECASE)
        bar_match     = re.search(r'^(.*?)\s*[|\-–]', title)

        if at_match:
            company = at_match.group(1).strip()
        elif hiring_match:
            company = hiring_match.group(1).strip()
        elif bar_match:
            company = _clean_company_name(bar_match.group(1).strip())

        role_m = re.search(r'^(.*?)\s+(?:at|job|internship)', title, re.IGNORECASE)
        if role_m:
            role = role_m.group(1).strip()[:80] or query
        if not _is_request_style_title(title) and not _is_request_style_title(role):
            continue

        if not company or len(company) < 3:
            found = re.findall(r'([A-Z][a-zA-Z0-9 &]{2,35})', body)
            company = found[0].strip() if found else ""

        if not company or len(company) < 3:
            continue

        # GAP 5+6: city must match
        combined = title + " " + body
        if not _city_match(combined, city):
            continue

        # GAP 8: extract contact info
        phone = _extract_phone(body)
        email = _extract_email(body)

        # GAP 12: company size
        size = _extract_company_size(body)

        description = f"Hiring for {role} in {city}. " + body[:180]

        leads.append(_make_lead(
            company_name=company,
            city=city,
            industry=role,
            description=description.strip(),
            source_url=href,
            phone=phone,
            email=email,
            company_size=size,
            intent_signal=f"Actively hiring {role} — confirmed digital budget",
        ))

    print(f"[internshala] DDG fallback: {len(leads)} leads")
    return leads


# ── Public API ────────────────────────────────────────────────────────────────

async def scrape_internshala(query: str, city: str) -> list[dict]:
    """
    Scrape Internshala for companies hiring `query` roles in `city`.
    Primary: direct HTTP + HTML parse (3 URL patterns, 3 pages).
    Fallback: DDG (2 query variants, 25 results each).
    """
    leads = await _scrape_direct(query, city)

    if not leads:
        print("[internshala] direct parse empty — trying DDG")
        leads = await _scrape_ddg(query, city)

    # GAP 4: dedup on name+city (strip city from name first)
    seen:   set[str]   = set()
    unique: list[dict] = []
    for lead in leads:
        name_stripped = re.sub(
            re.escape(lead["location"]), '',
            lead["company_name"], flags=re.IGNORECASE
        ).strip()
        key = re.sub(r'\s+', '', name_stripped.lower()) + lead["location"].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[internshala] {len(unique)} unique leads for '{query}' in {city}")
    log_scraper_run(
        "internshala",
        attempted=len(leads),
        saved=len(unique),
        rejected=max(0, len(leads) - len(unique)),
    )
    return unique
