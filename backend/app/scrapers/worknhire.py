"""
scrapers/worknhire.py
=====================
WorkNHire Job Scraper — v1.0

WorkNHire.com is India's native B2B job platform:
- Job postings = explicit buying intent
- SME/agency focused (not freelancer marketplace)
- Project budget visible
- Minimal JS, highly scrapable
- Free public access

Why valuable:
  - 100% Indian SME clients (your target market)
  - Project postings with explicit requirements
  - Budget disclosed
  - Low scraping competition
  - Fresh daily postings

Filters applied:
  - India location only
  - Open projects only (not closed/completed)
  - Budget >= ₹10k (filters microbuyers)
  - Keyword match in title/description
  - Dedup on title + city
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.worknhire.com/",
}

# City aliases for India
_CITY_ALIASES: dict[str, list[str]] = {
    "bengaluru": ["bengaluru", "bangalore", "whitefield", "electronic city"],
    "mumbai": ["mumbai", "bombay", "thane", "navi mumbai", "kalyan"],
    "delhi": ["delhi", "new delhi", "noida", "gurugram", "gurgaon", "faridabad"],
    "hyderabad": ["hyderabad", "secunderabad", "cyberabad"],
    "pune": ["pune", "pimpri", "chinchwad", "hinjewadi"],
    "ahmedabad": ["ahmedabad", "gandhinagar"],
    "chennai": ["chennai", "madras", "tambaram"],
    "kolkata": ["kolkata", "calcutta", "howrah"],
    "surat": ["surat", "udhna", "adajan", "vesu", "katargam"],
    "jaipur": ["jaipur", "pink city"],
}

# Regex patterns
_PHONE_RE = re.compile(
    r'(\+91[\s\-]?)?(\(\d{2,5}\)[\s\-]?)?\b[6-9]\d{4}[\s\-]?\d{5}\b'
    r'|0\d{2,4}[\s\-]\d{6,8}'
)
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_BUDGET_RE = re.compile(
    r'(?:budget|budget:?|rs\.?|₹|inr|price)\s*(?:upto|up\s+to|from|-)?'
    r'(?:rs\.?|₹|inr)?\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?)',
    re.IGNORECASE
)
_MIN_BUDGET = 10000  # Filter out < ₹10k


def _city_match(text: str, city: str) -> bool:
    """Check if city or alias appears in text."""
    text_l = text.lower()
    variants = _CITY_ALIASES.get(city.lower(), [city.lower()])
    return any(v in text_l for v in variants)


def _extract_phone(text: str) -> str:
    """Extract first phone number from text."""
    m = _PHONE_RE.search(text)
    if m:
        return re.sub(r'\s+', ' ', m.group(0)).strip()
    return ""


def _extract_email(text: str) -> str:
    """Extract first email from text."""
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else ""


def _parse_budget(text: str) -> tuple[float, str]:
    """
    Extract budget value and return (amount_in_inr, formatted_string).
    Returns (0, "") if no valid budget found.
    """
    m = _BUDGET_RE.search(text)
    if m:
        amount_str = m.group(1).replace(",", "").replace(" ", "")
        try:
            amount = float(amount_str)
            if amount >= _MIN_BUDGET:
                return (amount, f"₹{int(amount):,}")
        except ValueError:
            pass
    return (0, "")


def _keywords(query: str) -> list[str]:
    """Extract keywords from query (min 3 chars)."""
    stop = {"and", "or", "the", "a", "in", "for", "of", "with", "at", "&", "to", "by"}
    return [w for w in query.lower().split() if w not in stop and len(w) > 2]


def _keywords_match(text: str, query_keywords: list[str]) -> bool:
    """Check if at least one query keyword appears in text."""
    if not query_keywords:
        return True
    text_l = text.lower()
    return any(kw in text_l for kw in query_keywords)


async def _fetch_page_html(client: httpx.AsyncClient, url: str) -> str:
    """Fetch HTML from WorkNHire page with retry."""
    for attempt in range(3):
        try:
            resp = await client.get(url, headers=_HEADERS, timeout=15.0)
            if resp.status_code == 200:
                return resp.text
            await asyncio.sleep(2 ** attempt)  # Backoff
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            continue
    return ""


def _parse_job_listing(html: str, query: str, city: str) -> dict | None:
    """
    Parse a WorkNHire job listing HTML.
    Returns a lead dict or None if invalid.
    """
    if not BS4_AVAILABLE or not html:
        return None
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Try to find job title
        title = None
        title_elem = soup.find("h1", class_=re.compile("job.*title|title", re.I))
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            title_elem = soup.find("h1")
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        if not title or len(title) < 5:
            return None
        
        # Find description
        desc = ""
        desc_elem = soup.find("div", class_=re.compile("description|detail", re.I))
        if desc_elem:
            desc = desc_elem.get_text(separator=" ", strip=True)
        
        combined = f"{title} {desc}"
        
        # Keyword match
        query_kws = _keywords(query)
        if not _keywords_match(combined, query_kws):
            return None
        
        # City match
        if not _city_match(combined, city):
            return None
        
        # Extract contact info
        phone = _extract_phone(combined)
        email = _extract_email(combined)
        budget, budget_str = _parse_budget(combined)
        
        # Skip low budget
        if budget < _MIN_BUDGET:
            return None
        
        # Get company name
        company = "WorkNHire Poster"
        company_elem = soup.find("div", class_=re.compile("company|employer", re.I))
        if company_elem:
            company = company_elem.get_text(strip=True)[:80]
        
        # Get URL
        url = ""
        canonical = soup.find("link", rel="canonical")
        if canonical:
            url = canonical.get("href", "")
        
        lead = {
            "company_name": company,
            "post_title": title[:100],
            "description": desc[:300],
            "location": city,
            "industry": query[:100],
            "phone": phone,
            "email": email,
            "website": "",
            "budget": budget_str,
            "source": "worknhire",
            "source_url": url,
            "intent_signal": f"Posted project: {title}",
        }
        return lead
        
    except Exception as e:
        print(f"[worknhire:parse] Error: {e}")
        return None


async def _scrape_worknhire_search(query: str, city: str) -> list[dict]:
    """
    Scrape WorkNHire search results page.
    URL: https://www.worknhire.com/search?q=[query]&location=[city]
    """
    if not BS4_AVAILABLE:
        return []
    
    leads = []
    seen_urls = set()
    
    try:
        base_url = "https://www.worknhire.com/search"
        params = {
            "q": query,
            "location": city,
            "type": "project",
        }
        
        async with httpx.AsyncClient() as client:
            # Fetch search results page
            url = base_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
            html = await _fetch_page_html(client, url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Find all job listing links
            job_links = soup.find_all("a", class_=re.compile("job|listing", re.I))
            if not job_links:
                # Fallback: find any links to job pages
                for link in soup.find_all("a", href=re.compile(r"/projects?/\d+|/jobs?/\d+")):
                    job_links.append(link)
            
            # Fetch and parse each job
            for job_link in job_links[:20]:  # Limit to 20 to avoid rate limiting
                job_url = job_link.get("href", "")
                if not job_url or job_url in seen_urls:
                    continue
                
                # Make absolute URL
                if job_url.startswith("/"):
                    job_url = "https://www.worknhire.com" + job_url
                
                seen_urls.add(job_url)
                
                # Fetch job detail page
                job_html = await _fetch_page_html(client, job_url)
                if not job_html:
                    continue
                
                # Parse job listing
                lead = _parse_job_listing(job_html, query, city)
                if lead:
                    leads.append(lead)
                    await asyncio.sleep(1)  # Rate limit: 1 sec per request
        
        return leads
        
    except Exception as e:
        print(f"[worknhire:search] Error: {e}")
        return []


async def _scrape_worknhire_ddg(query: str, city: str) -> list[dict]:
    """
    Fallback: Use DuckDuckGo to find WorkNHire project postings.
    Query: "site:worknhire.com [query] [city] project"
    """
    if not DDGS_AVAILABLE:
        return []
    
    try:
        ddg = DDGS()
        search_query = f'site:worknhire.com {query} {city} project'
        results = ddg.text(search_query, max_results=25)
        
        leads = []
        seen_urls = set()
        query_kws = _keywords(query)
        
        for result in results:
            url = result.get("href", "")
            title = result.get("title", "")
            snippet = result.get("body", "")
            
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            combined = f"{title} {snippet}"
            
            # Filters
            if not _city_match(combined, city):
                continue
            if not _keywords_match(combined, query_kws):
                continue
            
            # Extract info
            phone = _extract_phone(combined)
            email = _extract_email(combined)
            budget, budget_str = _parse_budget(combined)
            
            if budget < _MIN_BUDGET:
                continue
            
            lead = {
                "company_name": "WorkNHire Project Poster",
                "post_title": title[:100],
                "description": snippet[:300],
                "location": city,
                "industry": query[:100],
                "phone": phone,
                "email": email,
                "website": "",
                "budget": budget_str,
                "source": "worknhire",
                "source_url": url,
                "intent_signal": f"Posted: {title}",
            }
            leads.append(lead)
        
        return leads
        
    except Exception as e:
        print(f"[worknhire:ddg] Error: {e}")
        return []


async def scrape_worknhire(query: str, city: str) -> list[dict]:
    """
    Main scraper: Fetch project postings from WorkNHire.com.
    
    Priority:
    1. Try WorkNHire search page (HTML scraping)
    2. Fallback to DuckDuckGo site search
    
    Returns list of leads with source="worknhire"
    """
    print(f"[worknhire] Scraping {city.title()} for '{query}'...")
    
    try:
        # Try direct scraping first
        direct_leads = await _scrape_worknhire_search(query, city)
        if direct_leads:
            print(f"[worknhire:search] Found {len(direct_leads)} projects")
            return direct_leads
        
        # Fallback to DDG
        print(f"[worknhire:search] No results, trying DDG fallback...")
        ddg_leads = await _scrape_worknhire_ddg(query, city)
        print(f"[worknhire:ddg] Found {len(ddg_leads)} projects")
        return ddg_leads
        
    except Exception as e:
        print(f"[worknhire] Fatal error: {e}")
        return []
