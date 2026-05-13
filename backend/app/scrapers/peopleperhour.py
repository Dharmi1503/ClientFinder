"""
scrapers/peopleperhour.py
==========================
PeoplePerHour Freelance Jobs Scraper — v1.0

PeoplePerHour is a UK/EU-focused freelance platform with global reach:
- Job postings by businesses looking to hire freelancers
- Budget visible in listings
- No login required for public pages
- Highly scrapable HTML structure

Why valuable:
  - Explicit client project postings
  - Budget posted openly
  - Location filterable
  - Fresh daily postings
  - UK/EU audience (premium clients)

Filters applied:
  - Title quality (>15 chars, no garbage patterns)
  - Budget validation
  - Garbage pattern filtering
  - Dedup on title + URL
"""

import asyncio
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.peopleperhour.com/",
}

# Regex patterns
_PHONE_RE = re.compile(
    r'(\+91[\s\-]?)?(\(\d{2,5}\)[\s\-]?)?\b[6-9]\d{4}[\s\-]?\d{5}\b'
    r'|0\d{2,4}[\s\-]\d{6,8}'
)
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_BUDGET_RE = re.compile(
    r'(?:budget|budget:?|price|from|upto|up\s+to)?'
    r'(?:£|\$|€|inr|₹|rs\.?)?'
    r'\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)',
    re.IGNORECASE
)

# Garbage title patterns
_GARBAGE_TITLE = re.compile(
    r"(?i)freelancer|sign\s+up|^\s*\|\s*|"
    r"post\s+a\s+job|how\s+it\s+works|find\s+freelancer"
)


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


def _parse_budget(text: str) -> str:
    """Extract budget value and return formatted string."""
    m = _BUDGET_RE.search(text)
    if m:
        amount_str = m.group(1).replace(",", "").replace(" ", "")
        try:
            amount = float(amount_str)
            if amount > 100:  # Minimum budget
                return f"£{int(amount):,}" if "£" in text else f"${int(amount):,}"
        except ValueError:
            pass
    return ""


def _is_title_quality(title: str) -> bool:
    """Check title has minimum quality."""
    if not title or len(title) < 15:
        return False
    return not _GARBAGE_TITLE.search(title)


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


def _extract_company_name(title: str, snippet: str) -> str:
    """
    Extract company name from DDG result.
    Try: "by", "from", "posted by" in snippet.
    Fallback: first 4 words of title.
    Last resort: title truncated to 40 chars.
    """
    # Try to find company name in snippet after "by", "from", "posted by"
    for pattern in [r"by\s+([A-Za-z0-9\s&,.-]{2,50}?)(?:\s+on|$|\||\d)", 
                     r"from\s+([A-Za-z0-9\s&,.-]{2,50}?)(?:\s+on|$|\||\d)",
                     r"posted\s+by\s+([A-Za-z0-9\s&,.-]{2,50}?)(?:\s+on|$|\||\d)"]:
        m = re.search(pattern, snippet, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if name and len(name) > 2:
                return name[:80]
    
    # Fallback: first 4 words of title
    words = title.split()[:4]
    if words:
        return " ".join(words)[:80]
    
    # Last resort: truncated title
    return title[:40] if title else "Project Poster"


async def _fetch_page_html(client: httpx.AsyncClient, url: str) -> str:
    """Fetch HTML from PeoplePerHour page with retry."""
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


def _parse_job_cards(html: str, query: str) -> list[dict]:
    """Parse job listing cards from PeoplePerHour HTML."""
    if not BS4_AVAILABLE or not html:
        return []
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Find job cards (various possible selectors)
        cards = soup.select(
            "div.freelance-item, div.job-card, div[class*='job'], "
            "li[class*='freelance'], article[class*='job']"
        )
        
        leads = []
        query_kws = _keywords(query)
        
        for card in cards:
            # Extract title
            title = ""
            for selector in ["h2 a", "h3 a", "a.job-title", ".job-title"]:
                title_elem = card.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not _is_title_quality(title):
                continue
            
            # Extract job URL
            url = ""
            for link in card.find_all("a"):
                href = link.get("href", "")
                if "/freelance/" in href or "/jobs/" in href:
                    url = href
                    if not url.startswith("http"):
                        url = "https://www.peopleperhour.com" + url
                    break
            
            if not url:
                continue
            
            # Extract description
            desc = ""
            for selector in [".job-description", ".description", "p"]:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    desc = desc_elem.get_text(separator=" ", strip=True)
                    break
            
            combined = f"{title} {desc}"
            
            # Keyword match
            if not _keywords_match(combined, query_kws):
                continue
            
            # Extract contact info
            phone = _extract_phone(combined)
            email = _extract_email(combined)
            budget = _parse_budget(combined)
            
            # Get posted time
            posted = ""
            for selector in [".time-ago", ".posted-time", "time"]:
                time_elem = card.select_one(selector)
                if time_elem:
                    posted = time_elem.get_text(strip=True)
                    break
            
            lead = {
                "company_name": "PPH Project Poster",
                "post_title": title[:100],
                "description": desc[:300],
                "location": "Global",
                "industry": query[:100],
                "phone": phone,
                "email": email,
                "website": "",
                "budget": budget,
                "source": "peopleperhour",
                "source_url": url,
                "contact_link": url,
                "platform_url": url,
                "posted_date": posted,
                "intent_signal": f"Posted project: {title}",
            }
            leads.append(lead)
        
        return leads
        
    except Exception as e:
        print(f"[peopleperhour:parse] Error: {e}")
        return []


async def _scrape_peopleperhour_direct(query: str, max_results: int = 20) -> list[dict]:
    """
    Scrape PeoplePerHour search results directly.
    URL: https://www.peopleperhour.com/freelance-{service}-jobs
    """
    if not BS4_AVAILABLE:
        return []
    
    try:
        # Convert service name to URL slug (e.g., "web development" -> "web-development")
        slug = query.lower().replace(" ", "-")
        url = f"https://www.peopleperhour.com/freelance-{slug}-jobs"
        
        async with httpx.AsyncClient() as client:
            html = await _fetch_page_html(client, url)
            if not html:
                return []
            
            # Parse job cards
            leads = _parse_job_cards(html, query)
            return leads[:max_results]
        
    except Exception as e:
        print(f"[peopleperhour:direct] Error: {e}")
        return []


async def _scrape_peopleperhour_ddg(query: str, max_results: int = 20) -> list[dict]:
    """
    Fallback: Use DuckDuckGo to find PeoplePerHour project postings.
    Query: 'peopleperhour.com "{service}" project india budget'
    """
    if not DDGS_AVAILABLE:
        return []
    
    try:
        ddg = DDGS()
        search_query = f'peopleperhour.com "{query}" project india budget'
        results = ddg.text(search_query, max_results=max_results)
        
        leads = []
        seen_urls = set()
        
        for result in results:
            url = result.get("href", "").strip()
            title = result.get("title", "").strip()
            snippet = result.get("body", "").strip()
            
            if url in seen_urls or not _is_title_quality(title):
                continue
            
            seen_urls.add(url)
            
            combined = f"{title} {snippet}"
            
            # Extract company name intelligently
            company_name = _extract_company_name(title, snippet)
            
            # Extract contact info
            phone = _extract_phone(combined)
            email = _extract_email(combined)
            budget = _parse_budget(combined)
            
            lead = {
                "company_name": company_name,
                "post_title": title[:100],
                "description": snippet[:300],
                "location": "Global",
                "industry": query[:100],
                "phone": phone,
                "email": email,
                "website": "",
                "budget": budget,
                "source": "peopleperhour",
                "source_url": url,
                "contact_link": url,
                "platform_url": url,
                "posted_date": "",
                "intent_signal": f"Posted: {title}",
            }
            leads.append(lead)
        
        return leads
        
    except Exception as e:
        print(f"[peopleperhour:ddg] Error: {e}")
        return []


async def scrape_peopleperhour(query: str, city: str, max_results: int = 20) -> list[dict]:
    """
    Main scraper: Fetch project postings from PeoplePerHour.com.
    
    Priority:
    1. Try direct scraping (HTML from /freelance-{service}-jobs)
    2. Fallback to DuckDuckGo search
    
    Returns list of leads with source="peopleperhour"
    """
    print(f"[peopleperhour] Scraping for '{query}' (location: {city})...")
    
    try:
        # Try direct scraping first
        direct_leads = await _scrape_peopleperhour_direct(query, max_results)
        if direct_leads:
            print(f"[peopleperhour:direct] Found {len(direct_leads)} projects")
            return direct_leads
        
        # Fallback to DDG
        print(f"[peopleperhour:direct] No results, trying DDG fallback...")
        ddg_leads = await _scrape_peopleperhour_ddg(query, max_results)
        print(f"[peopleperhour:ddg] Found {len(ddg_leads)} projects")
        return ddg_leads
        
    except Exception as e:
        print(f"[peopleperhour] Fatal error: {e}")
        return []
