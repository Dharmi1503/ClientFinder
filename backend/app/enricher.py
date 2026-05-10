import asyncio
import re
import httpx

try:
    import dns.resolver as _dns_resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from ddgs import DDGS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGGREGATOR_DOMAINS = {
    "justdial.com", "indiamart.com", "sulekha.com", "google.com",
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com",
    "bing.com", "duckduckgo.com", "freelancer.com", "truelancer.com",
    "clutch.co", "wikipedia.org", "glassdoor.com", "ambitionbox.com",
    "tripadvisor.in", "tripadvisor.com", "zomato.com", "swiggy.com",
    "magicpin.in", "eazydiner.com", "dineout.co.in", "foodpanda.com",
}

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"[enricher] DDG error: {e}")
        return []


def _extract_emails(text: str) -> list[str]:
    """Find all email addresses in a block of text."""
    return re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)


def _extract_phone(text: str) -> str:
    match = re.search(r'(\+91[\s\-]?|0)?[6-9]\d{9}', text)
    return match.group(0).strip() if match else ""


def _extract_domain(url: str) -> str | None:
    """Pull clean domain from a URL."""
    match = re.search(r'https?://(?:www\.)?([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', url)
    if match:
        domain = match.group(1)
        # Filter out known aggregators
        if domain not in _AGGREGATOR_DOMAINS:
            return domain
    return None


def _extract_email_domain(email: str) -> str:
    """Return the lowercase domain part of an email, or empty string."""
    if "@" not in email:
        return ""
    return email.split("@", 1)[1].strip().lower()


def _is_aggregator_domain(domain: str) -> bool:
    """True when the domain belongs to a directory/marketplace/aggregator site."""
    domain = domain.strip().lower()
    return domain in _AGGREGATOR_DOMAINS


def _filter_emails_for_domain(emails: list[str], domain: str) -> list[str]:
    """
    Keep only plausible business emails.
    Prefer emails on the business's own domain and reject aggregator domains.
    """
    if not emails:
        return []

    clean = []
    for email in emails:
        email_domain = _extract_email_domain(email)
        if not email_domain:
            continue
        if _is_aggregator_domain(email_domain):
            continue
        clean.append(email)

    if not domain:
        return clean

    preferred = [email for email in clean if _extract_email_domain(email) == domain.lower()]
    return preferred or clean


def _infer_company_size(text: str) -> str:
    """
    Try to infer company size tag from DDG snippets.
    Returns: 'SMB', 'Mid-Market', 'Enterprise', or 'Unknown'
    """
    text_lower = text.lower()

    # Look for explicit employee counts
    match = re.search(r'(\d[\d,]*)\s*(?:\+\s*)?employees?', text_lower)
    if match:
        count_str = match.group(1).replace(",", "")
        try:
            count = int(count_str)
            if count < 50:
                return "SMB"
            elif count < 500:
                return "Mid-Market"
            else:
                return "Enterprise"
        except ValueError:
            pass

    # Keyword fallbacks
    if any(k in text_lower for k in ["fortune 500", "multinational", "global corporation", "listed company"]):
        return "Enterprise"
    if any(k in text_lower for k in ["mid-size", "mid size", "growing company", "series b", "series c"]):
        return "Mid-Market"
    if any(k in text_lower for k in ["startup", "small business", "freelancer", "sole proprietor", "bootstrap"]):
        return "SMB"

    return "Unknown"


# ---------------------------------------------------------------------------
# Website Finder
# ---------------------------------------------------------------------------

async def find_website(company_name: str, city: str) -> str | None:
    """
    Search DDG for the company's official website.
    Returns the domain string (e.g. 'acmehospital.in') or None.
    """
    query = f'"{company_name}" {city} official site -justdial -indiamart -sulekha'
    results = await asyncio.to_thread(_ddg_search, query, 5)
    for r in results:
        url = r.get("href", "")
        domain = _extract_domain(url)
        if domain:
            return domain
    return None


# ---------------------------------------------------------------------------
# Contact Page Scraper (deep extraction)
# ---------------------------------------------------------------------------

_CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/team", "/our-team"]

_DM_TITLES = [
    "founder", "co-founder", "ceo", "chief executive", "director", "managing director",
    "md", "president", "owner", "proprietor", "head of", "vp ", "vice president",
]


def _extract_decision_maker(text: str) -> str:
    """
    Look for patterns like 'Rajesh Kumar, Founder' or 'CEO: Anita Sharma'.
    Returns 'Name (Title)' or empty string.
    """
    # Pattern 1: Name followed by title (e.g. "Rajesh Kumar, Founder & CEO")
    for title in _DM_TITLES:
        pattern = rf'([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)[,\s]+(?:is\s+)?(?:the\s+)?{re.escape(title)}'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return f"{name} ({title.title()})"

    # Pattern 2: Title followed by name (e.g. "CEO: Rajesh Kumar" or "Founder - Anita")
    for title in _DM_TITLES:
        pattern = rf'{re.escape(title)}[:\-–\s]+([A-Z][a-z]+ [A-Z][a-z]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return f"{name} ({title.title()})"

    return ""


async def _scrape_contact_pages(domain: str, client: httpx.AsyncClient) -> dict:
    """
    Try /contact, /about, /team pages for additional phone/email/decision-maker.
    Returns dict with keys: email, phone, decision_maker.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"}
    found = {"email": "", "phone": "", "decision_maker": ""}

    for path in _CONTACT_PATHS:
        url = f"https://{domain}{path}"
        try:
            resp = await client.get(url, headers=headers, timeout=8.0)
            if resp.status_code != 200:
                continue
            html = resp.text
        except Exception:
            continue

        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
        else:
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()

        if not found["email"]:
            mailto = re.findall(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html)
            body_emails = _extract_emails(text)
            all_emails = mailto + [e for e in body_emails if e not in mailto]
            clean = [e for e in all_emails if not any(
                bad in e for bad in ["noreply", "donotreply", "unsubscribe", "@sentry", "@example"]
            )]
            clean = _filter_emails_for_domain(clean, domain)
            if clean:
                found["email"] = clean[0]

        if not found["phone"]:
            found["phone"] = _extract_phone(text)

        if not found["decision_maker"]:
            found["decision_maker"] = _extract_decision_maker(text)

        # Stop early if we found everything
        if found["email"] and found["phone"] and found["decision_maker"]:
            break

    return found


# ---------------------------------------------------------------------------
# Website Scraper
# ---------------------------------------------------------------------------

async def scrape_website(domain: str) -> dict:
    """
    Fetch the company's homepage + contact/about subpages.
    Extracts: email, phone, services_text, alive (bool), decision_maker.
    """
    if not domain:
        return {"email": "", "phone": "", "services_text": "", "alive": False, "decision_maker": ""}

    url = f"https://{domain}"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"}
            resp = await client.get(url, headers=headers)
            html = resp.text
            alive = len(html.strip()) > 500

            # --- Parse homepage ---
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html, "html.parser")
                plain_text = soup.get_text(separator=" ", strip=True)
                meta = soup.find("meta", attrs={"name": "description"})
                services_text = meta["content"][:300] if (meta and meta.get("content")) else plain_text[:400]
            else:
                plain_text = re.sub(r'<[^>]+>', ' ', html)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                services_text = plain_text[:400]

            # Parked domain check
            parked_signals = ["domain is for sale", "this domain", "parked domain",
                              "buy this domain", "godaddy", "namecheap parking"]
            if any(s in plain_text.lower() for s in parked_signals):
                return {"email": "", "phone": "", "services_text": "", "alive": False, "decision_maker": ""}

            # Extract from homepage
            mailto_emails = re.findall(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html)
            body_emails = _extract_emails(plain_text)
            all_emails = mailto_emails + [e for e in body_emails if e not in mailto_emails]
            clean_emails = [e for e in all_emails if not any(
                bad in e for bad in ["noreply", "donotreply", "unsubscribe", "@sentry", "@example"]
            )]
            clean_emails = _filter_emails_for_domain(clean_emails, domain)
            email = clean_emails[0] if clean_emails else ""
            phone = _extract_phone(plain_text)
            decision_maker = _extract_decision_maker(plain_text)

            # Deep scrape contact/about/team pages if still missing info
            if not email or not phone or not decision_maker:
                deep = await _scrape_contact_pages(domain, client)
                email = email or deep["email"]
                phone = phone or deep["phone"]
                decision_maker = decision_maker or deep["decision_maker"]

    except Exception as e:
        print(f"[enricher] scrape_website failed for {domain}: {e}")
        return {"email": "", "phone": "", "services_text": "", "alive": False, "decision_maker": ""}

    return {
        "email": email,
        "phone": phone,
        "services_text": services_text,
        "alive": alive,
        "decision_maker": decision_maker,
    }



# ---------------------------------------------------------------------------
# Email Guesser
# ---------------------------------------------------------------------------

# Step 2 — Domains that must NEVER appear in a guessed email
BLACKLISTED_DOMAINS = {
    "youtube.com", "facebook.com", "instagram.com", "twitter.com",
    "linkedin.com", "justdial.com", "sulekha.com", "indiamart.com",
    "tradeindia.com", "google.com", "gmail.com", "yahoo.com",
    "hotmail.com", "outlook.com", "surfindia.com", "wikipedia.org",
    "maps.google.com", "whatsapp.com", "telegram.org",
}

# Step 3 — DNS and Cache
_mx_cache = {}


def has_mx_record(domain: str) -> bool:
    """Return True only if the domain has at least one valid MX DNS record."""
    if not DNS_AVAILABLE:
        # dnspython not installed — skip check and allow the guess through
        return True
    try:
        _dns_resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False


async def guess_email(company_name: str, domain: str | None) -> str:
    """
    Generate the most likely email address for a contact at this company.

    Validates the domain against a blacklist (step 2) and checks that
    it has a real MX record (step 3) before returning any guess.
    Uses a thread pool to avoid blocking the event loop.
    Returns empty string if domain fails either check.
    """
    if not domain:
        return ""

    # ── Step 2: Reject blacklisted / third-party domains ─────────────────
    domain_lower = domain.strip().lower()
    if domain_lower in BLACKLISTED_DOMAINS:
        print(f"[guess_email] Rejected blacklisted domain: {domain_lower}")
        return ""

    # ── Step 3: Reject domains with no MX record (with Cache + Executor) ──
    if domain_lower in _mx_cache:
        is_valid = _mx_cache[domain_lower]
    else:
        # Wrap the blocking DNS call in a thread pool
        is_valid = await asyncio.get_event_loop().run_in_executor(None, has_mx_record, domain_lower)
        _mx_cache[domain_lower] = is_valid

    if not is_valid:
        print(f"[guess_email] Rejected domain with no MX record: {domain_lower}")
        return ""

    # ── Build candidates (info@ is the safest generic guess) ─────────────
    clean = re.sub(r'[^a-zA-Z\s]', '', company_name).strip().lower()
    words = clean.split()

    candidates = [
        f"info@{domain_lower}",
        f"contact@{domain_lower}",
        f"hello@{domain_lower}",
    ]

    # Add first-word-of-company-name guess
    if words:
        candidates.append(f"{words[0]}@{domain_lower}")

    # Add combined first+second word (common for Indian business names)
    if len(words) >= 2:
        candidates.append(f"{words[0]}{words[1]}@{domain_lower}")

    # Return the "safest" generic one — info@ is the most likely to exist
    return candidates[0]


# ---------------------------------------------------------------------------
# Company Size Inference
# ---------------------------------------------------------------------------

async def infer_company_size(company_name: str, city: str) -> str:
    """
    Search DDG for employee count / size mentions.
    Returns: 'SMB', 'Mid-Market', 'Enterprise', or 'Unknown'
    """
    query = f'"{company_name}" {city} employees team size glassdoor linkedin'
    results = await asyncio.to_thread(_ddg_search, query, 5)
    combined_text = " ".join(r.get("body", "") + " " + r.get("title", "") for r in results)
    return _infer_company_size(combined_text)


# ---------------------------------------------------------------------------
# Unified Enrichment Entry Point
# ---------------------------------------------------------------------------

async def enrich_lead(lead: dict, fast_mode: bool = True) -> dict:
    """
    Full enrichment pipeline for a single lead.

    fast_mode=True  (default): Website + company size only. ~3-5s per lead.
    fast_mode=False (deep):    + LinkedIn, Google News, IndiaMART. ~15-30s per lead.

    Runs these concurrently:
      1. Website finder        → domain via DDG
      2. Company size          → employee count via DDG
      3. Website scraper       → email/phone/DM from /contact /about /team
      [if fast_mode=False:]
      4. LinkedIn enricher     → employee count, open jobs, about text
      5. News enricher         → funding/expansion/pain signals
      6. IndiaMART enricher    → active buyer enquiries in this category+city
    """
    EXTENDED_ENRICHMENT = False
    if not fast_mode:
        try:
            from app.enrichers.linkedin import enrich_with_linkedin
            from app.enrichers.news import enrich_with_news
            from app.enrichers.indiamart import enrich_with_indiamart
            EXTENDED_ENRICHMENT = True
        except ImportError as e:
            print(f"[enricher] Extended enrichers not available: {e}")

    company_name = lead.get("company_name", "")
    city         = lead.get("location", "")
    category     = lead.get("industry") or lead.get("category") or ""

    # ── Stage A: Find website + company size in parallel ─────────────────
    domain, company_size_tag = await asyncio.gather(
        find_website(company_name, city),
        infer_company_size(company_name, city),
    )

    lead["website"]          = f"https://{domain}" if domain else ""
    lead["company_size_tag"] = company_size_tag
    lead["company_size"]     = company_size_tag   # canonical field name

    # ── Stage B: Website scrape + extended enrichment (all concurrent) ───
    enrichment_tasks = []
    task_names = []

    if domain:
        enrichment_tasks.append(scrape_website(domain))
        task_names.append("website")

    if EXTENDED_ENRICHMENT:
        enrichment_tasks.append(enrich_with_linkedin(company_name, city))
        task_names.append("linkedin")
        enrichment_tasks.append(enrich_with_news(company_name, city))
        task_names.append("news")
        enrichment_tasks.append(enrich_with_indiamart(company_name, city, category))
        task_names.append("indiamart")

    results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)
    result_map = {name: res for name, res in zip(task_names, results)}

    # ── Merge website data ────────────────────────────────────────────────
    site_data = result_map.get("website")
    if isinstance(site_data, dict):
        if not lead.get("phone")          and site_data.get("phone"):
            lead["phone"]          = site_data["phone"]
        if not lead.get("email")          and site_data.get("email"):
            lead["email"]          = site_data["email"]
        if not lead.get("decision_maker") and site_data.get("decision_maker"):
            lead["decision_maker"] = site_data["decision_maker"]
        lead["services_text"] = site_data.get("services_text", "")
        lead["website_alive"] = site_data.get("alive", False)
    else:
        lead["services_text"] = ""
        lead["website_alive"] = False

    # ── Merge LinkedIn data ───────────────────────────────────────────────
    li_data = result_map.get("linkedin")
    if isinstance(li_data, dict):
        # Prefer LinkedIn employee count over DDG-inferred size
        if li_data.get("employee_count"):
            lead["employee_count"]   = li_data["employee_count"]
            lead["company_size_tag"] = li_data["company_size_tag"]
            lead["company_size"]     = li_data["company_size_tag"]
        if li_data.get("linkedin_url") and not lead.get("linkedin_url"):
            lead["linkedin_url"] = li_data["linkedin_url"]
        if li_data.get("linkedin_signal"):
            lead["linkedin_signal"]  = li_data["linkedin_signal"]
        lead["open_jobs"]       = li_data.get("open_jobs", 0)
        lead["hiring_signal"]   = li_data.get("hiring_signal", False)

    # ── Merge News data ───────────────────────────────────────────────────
    news_data = result_map.get("news")
    if isinstance(news_data, dict):
        lead["news_signals"]    = news_data.get("news_signals", [])
        lead["has_funding"]     = news_data.get("has_funding", False)
        lead["has_expansion"]   = news_data.get("has_expansion", False)
        lead["news_summary"]    = news_data.get("news_summary", "")

    # ── Merge IndiaMART data ──────────────────────────────────────────────
    im_data = result_map.get("indiamart")
    if isinstance(im_data, dict):
        lead["indiamart_signal"]   = im_data.get("indiamart_signal", "")
        lead["category_buyers"]    = im_data.get("category_buyers", 0)
        lead["is_indiamart_buyer"] = im_data.get("is_indiamart_buyer", False)
        if im_data.get("indiamart_budget") and not lead.get("budget_hint"):
            lead["budget_hint"]    = im_data["indiamart_budget"]

    # ── Build consolidated buying_signals list ────────────────────────────
    # This is what the AI analyst sees — needs to be CONCRETE FACTS
    existing_signals = lead.get("buying_signals") or []
    if isinstance(existing_signals, str):
        existing_signals = [existing_signals] if existing_signals else []

    new_signals = list(existing_signals)   # start from scraper's intent_signal

    # News signals
    for sig in lead.get("news_signals", [])[:3]:
        new_signals.append(sig)

    # LinkedIn signals
    if lead.get("linkedin_signal"):
        new_signals.append(f"[LINKEDIN] {lead['linkedin_signal']}")

    # IndiaMART signal
    if lead.get("indiamart_signal"):
        new_signals.append(f"[INDIAMART] {lead['indiamart_signal']}")

    # Website-absence signal
    if not domain:
        new_signals.append("No website found — business likely running entirely offline")

    # Funding bump
    if lead.get("has_funding"):
        new_signals.append("Recent funding announcement found — budget confirmed")

    # Hiring = growth + budget
    if lead.get("hiring_signal") and lead.get("open_jobs", 0) > 0:
        new_signals.append(
            f"Actively hiring {lead['open_jobs']} role(s) — growth phase, budget available"
        )

    lead["buying_signals"] = new_signals[:8]   # Cap at 8 — AI handles up to 8 well

    # ── Stage C: Guess email if still missing ─────────────────────────────
    if not lead.get("email"):
        lead["email"] = await guess_email(company_name, domain)

    return lead
