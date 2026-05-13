"""
scrapers/reddit.py
==================
PRAW-based Reddit intent scraper.
Searches business/freelance subreddits for active service requests.
"""

import asyncio
import os
import re
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from app.database import log_scraper_run

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

load_dotenv()

_TODAY = date.today().isoformat()
_SUBREDDITS = ["forhire", "indianbusiness", "FreelanceIndia"]
_SERVICE_KEYWORDS = re.compile(
    r"(?i)\b(looking for|need|require|wanted|project|freelance|developer|designer|agency|seo|marketing|website|app)\b"
)
_GARBAGE_PATTERNS = re.compile(
    r"(?i)\s\|\s|write for us|guest post|agency partners|job search|latest news|"
    r"(reddit|indeed|glassdoor|nytimes|new york times|upwork)\s*$"
)


def _build_reddit_client():
    client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret or not PRAW_AVAILABLE:
        return None
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="ClientFinder/1.0 by BroaderAI",
        check_for_async=False,
    )


def _extract_budget(text: str) -> str:
    match = re.search(r"(?i)(?:rs\.?|inr|₹|\$)\s*[\d,]+(?:\s*[-–]\s*(?:rs\.?|inr|₹|\$)?\s*[\d,]+)?", text or "")
    return match.group(0).strip() if match else ""


def _posted_label(created_utc: float) -> str:
    try:
        created = datetime.fromtimestamp(created_utc, tz=timezone.utc)
        delta = datetime.now(timezone.utc) - created
        if delta.days <= 0:
            return "today"
        if delta.days == 1:
            return "yesterday"
        return f"{delta.days}d ago"
    except Exception:
        return ""


def _submission_to_lead(submission, query: str, city: str) -> dict | None:
    title = (submission.title or "").strip()
    body = (submission.selftext or "").strip()
    combined = f"{title} {body}"

    if not _SERVICE_KEYWORDS.search(combined):
        return None
    if _GARBAGE_PATTERNS.search(title) or _GARBAGE_PATTERNS.search(combined):
        return None

    posted = _posted_label(float(getattr(submission, "created_utc", 0) or 0))
    description = body[:300] if body else title
    return {
        "company_name": title[:80],
        "location": city,
        "industry": query[:100],
        "description": description,
        "phone": "",
        "email": "",
        "website": "",
        "linkedin_url": "",
        "source": "reddit",
        "source_url": f"https://www.reddit.com{submission.permalink}",
        "contact_link": f"https://www.reddit.com{submission.permalink}",
        "company_size": "SMB",
        "intent_signal": f"Reddit {submission.subreddit.display_name} {posted}: {title}"[:500],
        "scrape_date": _TODAY,
        "post_title": title[:200],
        "title": title[:200],
        "budget": _extract_budget(combined),
        "posted_date": posted,
        "platform_url": f"https://www.reddit.com{submission.permalink}",
    }


def _search_reddit_sync(query: str, city: str) -> list[dict]:
    client = _build_reddit_client()
    if client is None:
        print("[reddit] PRAW unavailable or Reddit credentials missing")
        return []

    results: list[dict] = []
    for subreddit_name in _SUBREDDITS:
        try:
            subreddit = client.subreddit(subreddit_name)
            for submission in subreddit.search(query, sort="new", time_filter="month", limit=25):
                lead = _submission_to_lead(submission, query, city)
                if lead is not None:
                    results.append(lead)
        except Exception as exc:
            print(f"[reddit] PRAW error for r/{subreddit_name}: {exc}")
    return results


async def scrape_reddit(query: str, city: str) -> list[dict]:
    leads = await asyncio.to_thread(_search_reddit_sync, query, city)

    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = f"{lead['company_name'].lower().strip()}|{lead['source_url'].lower().strip()}"
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[reddit] {len(unique)} unique PRAW leads for '{query}' in {city}")
    log_scraper_run(
        "reddit",
        attempted=len(leads),
        saved=len(unique),
        rejected=max(0, len(leads) - len(unique)),
    )
    return unique
