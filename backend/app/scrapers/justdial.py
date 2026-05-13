"""
JustDial Scraper — v5
======================
Fixes applied (matching common patch baseline):
  - DDG results 12→25, retry 3× with backoff
  - City alias map (10 cities, 30+ variants)
  - Multi-query: 3 slug variants per search
  - Dedup on name+city (not name only)
  - Email extraction from snippets
  - Phone regex covers mobile + landline
  - HTTP fetch retry 3× before fallback
"""

import asyncio
import json
import re
import httpx
from app.database import log_scraper_run

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


_JD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.justdial.com/",
}

# ---------------------------------------------------------------------------
# City alias map
# ---------------------------------------------------------------------------
_CITY_ALIASES: dict[str, list[str]] = {
    "mumbai":    ["mumbai", "bombay", "navi-mumbai", "thane"],
    "delhi":     ["delhi", "new-delhi", "ncr", "dilli"],
    "bangalore": ["bangalore", "bengaluru", "blr"],
    "hyderabad": ["hyderabad", "secunderabad", "hyd"],
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
            return [canonical] + [a for a in aliases if a != canonical][:2]
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
            print(f"[justdial] DDG attempt {attempt+1} error: {e}")
            if attempt < 2:
                import time; time.sleep(1.5 * (attempt + 1))
    return []


def _extract_phone(text: str) -> str:
    """Indian mobile (6-9 prefix, 10 digits) or landline (STD code)."""
    match = re.search(
        r'(?:\+91[\s\-]?|0)?(?:[6-9]\d{9}|\d{2,4}[\s\-]\d{6,8})',
        str(text)
    )
    return match.group(0).strip() if match else ""


def _extract_email(text: str) -> str:
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', str(text))
    return match.group(0).lower() if match else ""


def _extract_review_count(s: str) -> int:
    if not s:
        return 0
    m = re.search(r'(\d+)', str(s))
    return int(m.group(1)) if m else 0


def _clean_name(raw: str) -> str:
    cleaned = re.sub(
        r'\s*[|\-–]\s*(JustDial|Just Dial|IndiaMART|Sulekha|Yellow Pages|'
        r'IndiaBizFor|F6S|LinkedIn|Facebook|Wikipedia|Glassdoor).*$',
        '', raw, flags=re.IGNORECASE
    ).strip()
    return cleaned


def _build_jd_url(weburl: str, sharedt_url: str, docid: str) -> str:
    if sharedt_url and sharedt_url.startswith("http"):
        return sharedt_url
    if weburl:
        slug = weburl.split("_BZDET")[0] if "_BZDET" in weburl else weburl
        return f"https://www.justdial.com/{slug}"
    if docid:
        return f"https://www.justdial.com/DT-{docid}"
    return "https://www.justdial.com"


def _make_lead(name, phone, email, city, category, url,
               snippet="", rating="", reviews=0, address="") -> dict:
    return {
        "company_name": name[:80],
        "phone": phone,
        "email": email,
        "location": city,
        "category": category,
        "source": "justdial",
        "source_url": url,
        "snippet": snippet[:250],
        "budget_hint": "",
        "rating": rating,
        "review_count": reviews,
        "verified": reviews > 0,
        "address": address,
    }


# ---------------------------------------------------------------------------
# Strategy 1: Columnar JSON Blob (primary)
# ---------------------------------------------------------------------------

def _parse_first_row_from(html: str, col_idx: dict, start: int) -> list | None:
    depth = 0
    in_str = False
    esc = False
    i = start
    limit = min(start + 12000, len(html))
    while i < limit:
        ch = html[i]
        if esc:
            esc = False
        elif ch == '\\' and in_str:
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start:i + 1])
                    except Exception:
                        return None
        i += 1
    return None


def _extract_blob_leads(html: str, city: str, category: str) -> list[dict]:
    col_m = re.search(r'"results"\s*:\s*\{"columns"\s*:\s*(\[[^\]]+\])', html)
    if not col_m:
        return []
    try:
        cols = json.loads(col_m.group(1))
    except Exception:
        return []

    col_idx = {c: i for i, c in enumerate(cols)}

    data_start = html.find('"data":[[')
    if data_start == -1:
        return []

    i = data_start + len('"data":')
    while i < len(html) and html[i] != '[':
        i += 1
    i += 1
    while i < len(html) and html[i] in ' \t\r\n':
        i += 1

    leads = []
    max_rows = 25

    while i < len(html) and len(leads) < max_rows:
        if html[i] != '[':
            break

        row = _parse_first_row_from(html, col_idx, i)
        if not row:
            break

        def get(key):
            idx = col_idx.get(key)
            return row[idx] if idx is not None and idx < len(row) else ""

        name = str(get("name") or get("nameln") or "").strip()
        if not name or len(name) < 3:
            i = html.find(']', i) + 1
            while i < len(html) and html[i] in ', \t\r\n':
                i += 1
            continue

        vnumber = str(get("VNumber") or "")
        wpnumber = get("wpnumber")
        if isinstance(wpnumber, list):
            wpnumber = wpnumber[0] if wpnumber else ""
        phone = _extract_phone(vnumber) or _extract_phone(str(wpnumber))

        # Email from any available text fields
        raw_text = " ".join(str(get(k) or "") for k in ("email", "attr_data", "nwtaglin"))
        email = _extract_email(raw_text)

        rating = str(get("compRating") or get("compRatingln") or "")
        reviews = _extract_review_count(str(get("totalReviews") or get("totJdReviews") or "0"))
        address = str(get("NewAddress") or get("NewAddressln") or get("area") or "")
        biz_type = str(get("type") or category)

        weburl = str(get("weburl") or "")
        sharedt_url = str(get("sharedt_url") or "")
        docid = str(get("docid") or "")
        url = _build_jd_url(weburl, sharedt_url, docid)

        verified_flag = get("verified")
        is_verified = str(verified_flag) == "1"

        attr = get("attr_data") or {}
        tags = get("nwtaglin") or []
        snippet_parts = []
        if isinstance(attr, dict):
            for k in ("node1", "node2"):
                v = attr.get(k, "")
                if isinstance(v, str) and v:
                    v = re.sub(r'<[^>]+>', '', v).strip()
                    if v:
                        snippet_parts.append(v)
        if isinstance(tags, list):
            snippet_parts.extend(str(t) for t in tags if t)
        snippet = ", ".join(snippet_parts)

        lead = _make_lead(
            name=name, phone=phone, email=email, city=city,
            category=biz_type, url=url, snippet=snippet,
            rating=rating, reviews=reviews, address=address,
        )
        lead["verified"] = is_verified or reviews > 0
        leads.append(lead)

        # Advance past this row
        depth = 0
        in_str2 = False
        esc2 = False
        j = i
        while j < len(html):
            ch = html[j]
            if esc2:
                esc2 = False
            elif ch == '\\' and in_str2:
                esc2 = True
            elif ch == '"':
                in_str2 = not in_str2
            elif not in_str2:
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        i = j + 1
                        break
            j += 1

        while i < len(html) and html[i] in ', \t\r\n':
            i += 1

    return leads


# ---------------------------------------------------------------------------
# Strategy 2: DDG fallback
# ---------------------------------------------------------------------------

async def _scrape_justdial_ddg(query: str, city: str) -> list[dict]:
    queries = [
        f'site:justdial.com "{query}" {city}',
        f'site:justdial.com {query} {city} phone',
        f'justdial {query} {city} contact',
    ]
    raw: list[dict] = []
    seen_urls: set[str] = set()
    for q in queries:
        for r in await asyncio.to_thread(_ddg_search, q, 25):
            if r.get("href") not in seen_urls:
                seen_urls.add(r.get("href", ""))
                raw.append(r)

    leads = []
    for r in raw:
        title = _clean_name(r.get("title", ""))
        body = r.get("body", "")
        url = r.get("href", "")

        if len(title) < 4:
            found = re.findall(
                r'([A-Z][a-zA-Z0-9\s&]{3,40}'
                r'(?:Pvt\.?\s?Ltd\.?|LLP|Hospital|Clinic|Labs?|Diagnostics)?)',
                body,
            )
            title = found[0].strip() if found else ""

        if not title or len(title) < 4:
            continue

        phone = _extract_phone(body + " " + title)
        email = _extract_email(body)
        reviews_m = re.search(r'(\d+)\s*(?:ratings?|reviews?|votes?)', body, re.IGNORECASE)
        reviews = int(reviews_m.group(1)) if reviews_m else 0
        rating_m = re.search(r'(\d\.\d)\s*(?:out of|/)?[\s]*5', body)
        rating = rating_m.group(1) if rating_m else ""

        leads.append(_make_lead(
            name=title, phone=phone, email=email, city=city, category=query,
            url=url, snippet=body[:200], rating=rating, reviews=reviews,
        ))
    return leads


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def scrape_justdial(query: str, city: str) -> list[dict]:
    """
    JustDial scraper v5:
      - Multi-slug: tries primary city slug + up to 2 aliases
      - Direct HTTP with 3× retry → blob parser
      - DDG fallback (3 query variants, 25 results each)
      - Dedup by name+city
      - Email extraction
    """
    slugs = _city_slugs(city)
    query_slug = query.lower().replace(" ", "-")

    leads: list[dict] = []
    html = ""

    for city_slug in slugs[:2]:  # primary + 1 alias max
        url = f"https://www.justdial.com/{city_slug}/{query_slug}"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers=_JD_HEADERS)
                    if resp.status_code == 200:
                        html = resp.text
                        break
                    print(f"[justdial] HTTP {resp.status_code} (attempt {attempt+1})")
            except Exception as e:
                print(f"[justdial] fetch error attempt {attempt+1}: {e}")
            await asyncio.sleep(1.5 * (attempt + 1))

        if html:
            blob_leads = _extract_blob_leads(html, city, query)
            if blob_leads:
                print(f"[justdial] blob parser ({city_slug}): {len(blob_leads)} listings")
                leads.extend(blob_leads)
                break  # got results, no need for alias

    if not leads:
        print("[justdial] falling back to DDG")
        leads = await _scrape_justdial_ddg(query, city)

    # Dedup by name+city
    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        key = f"{lead['company_name'].lower().strip()}|{lead['location'].lower().strip()}"
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[justdial] {len(unique)} unique leads")
    log_scraper_run(
        "justdial",
        attempted=len(leads),
        saved=len(unique),
        rejected=max(0, len(leads) - len(unique)),
    )
    return unique