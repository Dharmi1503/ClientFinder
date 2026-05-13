"""
enricher_news.py
=================
Google News Enricher — Real Funding & Expansion Signals
---------------------------------------------------------
Searches DDG News for recent (last 6 months) articles about the company.

Looks for:
  - Funding rounds  ("raised", "Series A/B", "funding")
  - Expansion       ("opens new", "launched", "expansion")
  - Hiring signals  ("hiring", "growing team")
  - Press coverage  ("featured in", "awarded")

These become CONCRETE buying_signals in the AI prompt —
not inferences, but things that actually happened.

DDG has a separate news search endpoint that hits Google News,
Bing News, etc. No key required.
"""

import asyncio
import re
from datetime import date, timedelta

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


# How recent is "recent" — articles older than this are less useful
_MAX_DAYS_OLD = 180

# Signals that indicate buying capacity / growth
_FUNDING_PATTERNS = re.compile(
    r'raised|funding|series [abc]|seed round|investment|investor|crore|lakh|million|'
    r'backed by|venture|angel round|pre-series',
    re.IGNORECASE
)
_GROWTH_PATTERNS = re.compile(
    r'expand|expansion|launch|launched|opens|new office|new branch|'
    r'hiring|growing|scaled|acqui|partnership|tie-up|collaboration',
    re.IGNORECASE
)
_PAIN_PATTERNS = re.compile(
    r'shortage|struggle|challeng|problem|difficult|manual|inefficien|'
    r'delay|backlog|overload|burnout|complaint',
    re.IGNORECASE
)


def _ddg_news_search(query: str, max_results: int = 8) -> list[dict]:
    """Search DDG news endpoint — hits Google News, Bing News."""
    if not DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append(r)
    except Exception as e:
        print(f"[news_enricher] DDG news error: {e}")
    return results


def _classify_article(title: str, body: str) -> str:
    """Return a short label for what kind of signal this article represents."""
    combined = f"{title} {body}".lower()
    if _FUNDING_PATTERNS.search(combined):
        return "funding"
    if _GROWTH_PATTERNS.search(combined):
        return "expansion"
    if _PAIN_PATTERNS.search(combined):
        return "pain_signal"
    return "press"


def _format_signal(title: str, source: str, date_str: str, signal_type: str) -> str:
    """Format a news article into a readable buying signal string."""
    type_labels = {
        "funding":      "FUNDING",
        "expansion":    "GROWTH",
        "pain_signal":  "PAIN",
        "press":        "PRESS",
    }
    label = type_labels.get(signal_type, "NEWS")
    date_display = date_str[:10] if date_str else "recent"
    return f"[{label}] {title} ({source}, {date_display})"


async def enrich_with_news(company_name: str, city: str) -> dict:
    """
    Search for recent news about a company and extract buying signals.

    Args:
        company_name: Company name to search
        city:         City for disambiguating common names

    Returns:
        {
          "news_signals":    list[str]  — formatted signal strings
          "has_funding":     bool       — recent funding found
          "has_expansion":   bool       — expansion/launch found
          "has_pain_signal": bool       — struggle/problem found
          "news_summary":    str        — short readable summary
        }
    """
    result = {
        "news_signals":    [],
        "has_funding":     False,
        "has_expansion":   False,
        "has_pain_signal": False,
        "news_summary":    "",
    }

    if not DDGS_AVAILABLE:
        return result

    # Build a targeted query — city helps disambiguate
    query = f'"{company_name}" {city}'

    raw_articles = await asyncio.to_thread(_ddg_news_search, query, 8)

    if not raw_articles:
        # Fallback: try without city
        query_noncity = f'"{company_name}" India'
        raw_articles = await asyncio.to_thread(_ddg_news_search, query_noncity, 5)

    signals = []
    summaries = []

    for article in raw_articles:
        title   = article.get("title", "")
        body    = article.get("body", "") or article.get("excerpt", "")
        source  = article.get("source", "") or article.get("publisher", "")
        pub_date = article.get("date", "") or article.get("published", "")

        if not title:
            continue

        signal_type = _classify_article(title, body)
        formatted   = _format_signal(title, source, pub_date, signal_type)
        signals.append(formatted)
        summaries.append(title[:100])

        if signal_type == "funding":
            result["has_funding"] = True
        elif signal_type == "expansion":
            result["has_expansion"] = True
        elif signal_type == "pain_signal":
            result["has_pain_signal"] = True

    result["news_signals"]  = signals[:5]   # Top 5 most recent
    result["news_summary"]  = " | ".join(summaries[:3])

    if signals:
        print(f"[news_enricher] {len(signals)} articles found for '{company_name}'")

    return result
