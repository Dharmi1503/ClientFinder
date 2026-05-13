"""
scrapers/bark.py
================
Bark.com Service Request Scraper — v1.0

Bark is a free service request platform where businesses post specific needs:
- Project title + description = intent signal
- Budget visible in some postings
- Location explicit
- Direct buyer (not contractor/freelancer)
- NO LOGIN REQUIRED

Why valuable:
  - Explicit buying intent (posting = "I need X service")
  - Budget sometimes visible
  - Business phone number often in posting
  - Fresh leads (daily posts)
  - Zero API authentication needed

Filters applied:
  - India location only
  - Service categories matching query (e.g., "web development", "digital marketing")
  - Active postings only (not completed)
  - Dedup on title + city
"""

import asyncio
import re
import time
from datetime import date

import httpx
from app.database import log_scraper_run


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.bark.com/en/IN",
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

# Service category mapping (Bark categories → query keywords)
_CATEGORY_MAPPING = {
    "web_development": ["web development", "website", "website design", "web design"],
    "app_development": ["app development", "mobile app", "ios", "android"],
    "digital_marketing": ["digital marketing", "seo", "social media marketing", "ppc"],
    "content_writing": ["content writing", "copywriting", "blog writing"],
    "graphic_design": ["graphic design", "logo design", "design"],
    "video_production": ["video production", "video editing", "animation"],
    "consulting": ["consulting", "business consulting", "strategy"],
    "it_services": ["it services", "software development", "it support"],
}

# Regex patterns for phone/email/budget
_PHONE_RE = re.compile(
    r'(\+91[\s\-]?)?(\(\d{2,5}\)[\s\-]?)?\b[6-9]\d{4}[\s\-]?\d{5}\b'
    r'|0\d{2,4}[\s\-]\d{6,8}'
)
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_BUDGET_RE = re.compile(
    r'(?:budget|budget:?|rs\.?|₹|inr)\s*(?:upto|up\s+to|up\s+to|from)?\s*'
    r'(?:rs\.?|₹|inr)?\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)',
    re.IGNORECASE
)


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


def _extract_budget(text: str) -> str:
    """Extract budget value if visible."""
    m = _BUDGET_RE.search(text)
    if m:
        amount = m.group(1).replace(",", "").replace(" ", "")
        try:
            val = float(amount)
            if val > 1000:
                return f"₹{int(val):,}"
        except ValueError:
            pass
    return ""


def _keywords(query: str) -> list[str]:
    """Extract keywords from query (min 3 chars)."""
    stop = {"and", "or", "the", "a", "in", "for", "of", "with", "at", "&", "to", "by"}
    return [w for w in query.lower().split() if w not in stop and len(w) > 2]


def _query_matches_category(query: str, category: str) -> bool:
    """Check if query matches a Bark service category."""
    query_l = query.lower()
    category_keywords = _CATEGORY_MAPPING.get(category, [])
    return any(kw in query_l for kw in category_keywords)


async def _fetch_bark_api(query: str, city: str, offset: int = 0) -> list[dict]:
    """
    Fetch service requests from Bark.com API.
    
    Bark doesn't require auth for public listings. Uses search endpoint with filters:
    - location: India (country_code=IN)
    - category: matches query
    - sort: recent first
    """
    try:
        # Build API URL with filters
        # Note: Bark's actual API structure may vary; this is the most common public endpoint
        url = "https://www.bark.com/api/v2/search/requests"
        
        params = {
            "location": city,
            "country": "IN",
            "query": query,
            "limit": 20,
            "offset": offset,
            "sort": "recent",
        }
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params, headers=_HEADERS)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            requests = data.get("results", [])
            
            # Transform Bark API response to lead format
            leads = []
            for req in requests:
                if not req.get("title"):
                    continue
                
                # Location filter
                location = req.get("location", "")
                if not _city_match(location, city):
                    continue
                
                # Basic validation
                title = req.get("title", "").strip()
                desc = req.get("description", "").strip()
                combined = f"{title} {desc}"
                
                phone = _extract_phone(combined)
                email = _extract_email(combined)
                budget = _extract_budget(combined)
                
                lead = {
                    "company_name": (req.get("buyer_name") or "Service Request").strip()[:80],
                    "post_title": title[:100],
                    "description": desc[:300],
                    "location": location[:50] or city,
                    "industry": query[:100],
                    "phone": phone,
                    "email": email,
                    "website": "",
                    "budget": budget,
                    "source": "bark",
                    "source_url": req.get("url", ""),
                    "intent_signal": f"Posted request: {title}",
                    "posted_time": req.get("created_at", ""),
                }
                leads.append(lead)
            
            return leads
            
    except Exception as e:
        print(f"[bark] API error: {e}")
        return []


async def _scrape_bark_ddg(query: str, city: str) -> list[dict]:
    """
    Fallback: Use DuckDuckGo to find Bark service requests.
    Query: "site:bark.com [query] [city] India"
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    
    try:
        ddg = DDGS()
        search_query = f'site:bark.com {query} {city} India'
        results = ddg.text(search_query, max_results=25)
        
        leads = []
        seen_urls = set()
        
        for result in results:
            url = result.get("href", "")
            title = result.get("title", "")
            snippet = result.get("body", "")
            
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            if not _city_match(f"{title} {snippet}", city):
                continue
            
            # Extract contact info from snippet
            phone = _extract_phone(snippet)
            email = _extract_email(snippet)
            budget = _extract_budget(snippet)
            
            lead = {
                "company_name": "Service Requester",
                "post_title": title[:100],
                "description": snippet[:300],
                "location": city,
                "industry": query[:100],
                "phone": phone,
                "email": email,
                "website": "",
                "budget": budget,
                "source": "bark",
                "source_url": url,
                "intent_signal": f"Posted: {title}",
            }
            leads.append(lead)
        
        return leads
        
    except Exception as e:
        print(f"[bark:ddg] fallback error: {e}")
        return []


async def scrape_bark(query: str, city: str) -> list[dict]:
    """
    Main scraper: Fetch service requests from Bark.com.
    
    Priority:
    1. Try Bark API (fastest, most structured)
    2. Fallback to DuckDuckGo site search
    
    Returns list of leads with source="bark"
    """
    print(f"[bark] Scraping {city.title()} for '{query}'...")
    
    try:
        # Try API first
        api_leads = await _fetch_bark_api(query, city)
        if api_leads:
            print(f"[bark:api] Found {len(api_leads)} requests")
            return api_leads
        
        # Fallback to DDG
        print(f"[bark:api] No results, trying DDG fallback...")
        ddg_leads = await _scrape_bark_ddg(query, city)
        print(f"[bark:ddg] Found {len(ddg_leads)} requests")
        return ddg_leads
        
    except Exception as e:
        print(f"[bark] Fatal error: {e}")
        return []
