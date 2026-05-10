"""
scrapers/reddit.py — v2
========================
Fixes applied:
  - DDG results 10→25, retry 3× with backoff
  - Removed double-fetch bug (_search_and_count was re-fetching subreddit)
  - India filter: skip posts with no India signal
  - Recency weight: posts <7d scored higher (sorted to top)
  - Dedup by (normalized_title+city), not title alone
  - Email extraction from post body
  - City alias map for detection
  - t=week preferred over t=month for fresher posts
  - Multi-query: 3 query variants per scrape call
"""

import asyncio
import re
from datetime import date, datetime

import httpx
from app.database import log_scraper_run

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


_HEADERS = {
    "User-Agent": "ClientFinder/1.0 (B2B lead tool; contact@broaderai.com)",
    "Accept": "application/json",
}

_TODAY = date.today().isoformat()

_SUBREDDITS = [
    "indianbusiness",
    "startups_india",
    "india",
    "forhire",
]

_INTENT_KEYWORDS = re.compile(
    r'look\w* for|need\w*|hiring|want\w*|requir\w*|seek\w*|find\w*|'
    r'recommend\w*|suggest\w*|agency|freelancer|developer|designer|'
    r'vendor|outsourc\w*|budget|project|build\w*|creat\w*',
    re.IGNORECASE
)

# India signal — at least one must be present in post text
_INDIA_SIGNAL = re.compile(
    r'\bindia\b|\bindian\b|rupee|₹|\binr\b|lakh|crore|'
    r'mumbai|delhi|bangalore|bengaluru|hyderabad|chennai|'
    r'kolkata|pune|ahmedabad|jaipur|surat|noida|gurgaon|'
    r'startup\s*india|make\s*in\s*india',
    re.IGNORECASE
)

# City alias map for extraction
_CITY_ALIASES: dict[str, list[str]] = {
    "Mumbai":    ["mumbai", "bombay", "navi mumbai", "thane"],
    "Delhi":     ["delhi", "new delhi", "ncr", "gurgaon", "noida"],
    "Bangalore": ["bangalore", "bengaluru", "blr"],
    "Hyderabad": ["hyderabad", "secunderabad"],
    "Chennai":   ["chennai", "madras"],
    "Kolkata":   ["kolkata", "calcutta"],
    "Pune":      ["pune", "pimpri"],
    "Ahmedabad": ["ahmedabad", "amdavad"],
    "Jaipur":    ["jaipur"],
    "Surat":     ["surat"],
    "Lucknow":   ["lucknow"],
    "Kochi":     ["kochi", "cochin", "ernakulam"],
    "Chandigarh":["chandigarh"],
    "Coimbatore":["coimbatore"],
    "Indore":    ["indore"],
}


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
            print(f"[reddit] DDG attempt {attempt+1} error: {e}")
            if attempt < 2:
                import time; time.sleep(1.5 * (attempt + 1))
    return []


def _extract_email(text: str) -> str:
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', str(text))
    return match.group(0).lower() if match else ""


def _time_ago(utc_timestamp: float) -> str:
    try:
        dt = datetime.utcfromtimestamp(utc_timestamp)
        delta = datetime.utcnow() - dt
        days = delta.days
        if days == 0:
            hours = delta.seconds // 3600
            return f"{hours}h ago" if hours > 0 else "just now"
        return f"{days}d ago"
    except Exception:
        return ""


def _recency_score(utc_timestamp: float) -> int:
    """Higher = more recent. Used for sort."""
    try:
        dt = datetime.utcfromtimestamp(utc_timestamp)
        delta = datetime.utcnow() - dt
        days = delta.days
        if days <= 1:   return 100
        if days <= 7:   return 80
        if days <= 14:  return 60
        if days <= 30:  return 40
        return 20
    except Exception:
        return 0


def _extract_city(text: str, default_city: str) -> str:
    low = text.lower()
    for canonical, aliases in _CITY_ALIASES.items():
        if any(alias in low for alias in aliases):
            return canonical
    return default_city


def _make_lead(company_name, city, industry, description,
               source_url, intent_signal="", email="", recency=0) -> dict:
    return {
        "company_name": company_name[:80],
        "location": city,
        "industry": industry[:100],
        "description": description[:300],
        "phone": "",
        "email": email,
        "website": "",
        "linkedin_url": "",
        "source": "reddit",
        "source_url": source_url,
        "contact_link": source_url,
        "company_size": "SMB",
        "intent_signal": intent_signal[:300],
        "scrape_date": _TODAY,
        "_recency_score": recency,  # internal sort key, stripped before save
    }


# ---------------------------------------------------------------------------
# Strategy 1 — Reddit JSON API (primary, single fetch per subreddit)
# ---------------------------------------------------------------------------

async def _search_subreddit(
    subreddit: str,
    query: str,
    city: str,
    client: httpx.AsyncClient,
) -> tuple[list[dict], bool]:
    """Single subreddit search. Returns (leads, blocked)."""
    for tframe in ("week", "month"):
        url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            f"?q={query}+{city}&sort=new&restrict_sr=1&limit=20&t={tframe}"
        )
        try:
            resp = await client.get(url, headers=_HEADERS, timeout=12.0)
            if resp.status_code == 429:
                print(f"[reddit] rate limited on r/{subreddit}")
                return [], False
            if resp.status_code == 403:
                print(f"[reddit] HTTP 403 for r/{subreddit}")
                return [], True
            if resp.status_code != 200:
                print(f"[reddit] HTTP {resp.status_code} for r/{subreddit}")
                continue
            data = resp.json()
            break
        except Exception as e:
            print(f"[reddit] API error for r/{subreddit}: {e}")
            return [], False
    else:
        return [], False

    posts = data.get("data", {}).get("children", [])
    leads: list[dict] = []

    for post_wrapper in posts:
        post = post_wrapper.get("data", {})
        title = post.get("title", "").strip()
        selftext = post.get("selftext", "").strip()
        permalink = post.get("permalink", "")
        score = post.get("score", 0)
        created_utc = post.get("created_utc", 0)
        post_url = f"https://www.reddit.com{permalink}" if permalink else ""

        if selftext in ("[deleted]", "[removed]"):
            selftext = ""
        if not title and not selftext:
            continue
        if score < -5:
            continue

        combined = f"{title} {selftext}"

        # Must have buying intent
        if not _INTENT_KEYWORDS.search(combined):
            continue

        # Must have India signal
        if not _INDIA_SIGNAL.search(combined):
            continue

        company_placeholder = re.sub(r'\s+', ' ', title[:60]).strip()
        if not company_placeholder:
            continue

        detected_city = _extract_city(combined, city)
        email = _extract_email(combined)
        time_label = _time_ago(created_utc)
        recency = _recency_score(created_utc)
        body_snippet = selftext[:200].replace("\n", " ").strip()

        intent_signal = (
            f"Reddit r/{subreddit} ({time_label}): \"{title}\""
            + (f" — {body_snippet}" if body_snippet else "")
        )

        industry_map = {
            "web": "Web Development", "app": "App Development",
            "seo": "SEO / Digital Marketing", "marketing": "Digital Marketing",
            "design": "UI/UX Design", "logo": "Graphic Design",
            "social media": "Social Media Management",
            "content": "Content Writing", "ca ": "Accounting",
            "tax": "Accounting", "legal": "Legal Services",
        }
        industry = query
        for kw, label in industry_map.items():
            if kw in combined.lower():
                industry = label
                break

        leads.append(_make_lead(
            company_name=company_placeholder,
            city=detected_city,
            industry=industry,
            description=body_snippet or title,
            source_url=post_url,
            intent_signal=intent_signal,
            email=email,
            recency=recency,
        ))

    return leads, False


async def _scrape_reddit_api(query: str, city: str) -> tuple[list[dict], bool]:
    """Search all subreddits concurrently. Returns (leads, all_blocked)."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_search_subreddit(sub, query, city, client) for sub in _SUBREDDITS],
            return_exceptions=True,
        )

    all_leads: list[dict] = []
    blocked_count = 0
    for res in results:
        if isinstance(res, tuple):
            leads, blocked = res
            all_leads.extend(leads)
            if blocked:
                blocked_count += 1

    all_blocked = (blocked_count >= len(_SUBREDDITS))
    print(f"[reddit] API: {len(all_leads)} posts across {len(_SUBREDDITS)} subreddits")
    return all_leads, all_blocked


# ---------------------------------------------------------------------------
# Strategy 2 — DDG fallback (3 query variants)
# ---------------------------------------------------------------------------

async def _scrape_reddit_ddg(query: str, city: str) -> list[dict]:
    queries = [
        f'site:reddit.com/r/indianbusiness OR site:reddit.com/r/india '
        f'"{query}" "{city}" "looking for" OR "need" OR "hiring"',
        f'site:reddit.com "{query}" India freelancer OR agency OR vendor',
        f'reddit.com indianbusiness "{query}" recommend',
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
        combined = f"{title} {body}"

        if not _INTENT_KEYWORDS.search(combined):
            continue

        company = re.sub(r'\s+', ' ', title[:60]).strip()
        if len(company) < 5:
            continue

        detected_city = _extract_city(combined, city)
        email = _extract_email(combined)

        leads.append(_make_lead(
            company_name=company,
            city=detected_city,
            industry=query,
            description=body[:220],
            source_url=href,
            intent_signal=f"Reddit post: \"{title}\"",
            email=email,
            recency=20,
        ))

    print(f"[reddit] DDG fallback: {len(leads)} leads")
    return leads


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_reddit(query: str, city: str) -> list[dict]:
    """
    Reddit buying-intent scraper v2.
    - Single fetch per subreddit (no double-fetch bug)
    - India signal filter
    - Recency sort
    - Dedup by normalized_title+city
    """
    leads, all_blocked = await _scrape_reddit_api(query, city)

    if not leads:
        if all_blocked:
            print("[reddit] All subreddits blocked (403) — skipping DDG")
        else:
            print("[reddit] API empty — trying DDG")
            leads = await _scrape_reddit_ddg(query, city)

    # Dedup by normalized title + city
    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = f"{lead['company_name'].lower().strip()}|{lead['location'].lower().strip()}"
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)

    # Sort: recent posts first, then by intent signal length
    unique.sort(key=lambda x: (x.get("_recency_score", 0), len(x.get("intent_signal", ""))), reverse=True)

    # Strip internal sort key before returning
    for lead in unique:
        lead.pop("_recency_score", None)

    print(f"[reddit] {len(unique)} unique leads for '{query}' in {city}")
    log_scraper_run(
        "reddit",
        attempted=len(leads),
        saved=len(unique),
        rejected=max(0, len(leads) - len(unique)),
    )
    return unique
