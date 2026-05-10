"""
messages.py
============
Message Generation Agent — Hyper-Personalized Outreach
---------------------------------------------------------
Uses the rich AI analyst output (pain, buying signals, objections,
decision maker, opener) to write outreach that feels hand-crafted.

What changed from v1:
  OLD: Generic template with pain point + city
  NEW: Uses the personalized_opener the analyst already wrote,
       plus generates channel-specific variants that reference
       the SPECIFIC buying signals and pre-empt objections

Outputs per HOT lead:
  - WhatsApp: 3 variants (Hinglish, 2-3 lines, different angles)
  - LinkedIn:  Professional, 4-5 lines, objection handled
  - Email:     Subject + 80-100 word body
"""

import asyncio
from app.ai import run_llm


# ---------------------------------------------------------------------------
# Pain Template Selector — picks a specific opener based on detected signals
# ---------------------------------------------------------------------------

def _select_pain_template(lead: dict, company: str, city: str, industry: str) -> str:
    """
    Selects a pain-signal-anchored opener based on what was detected.
    Returns a specific observation string, or empty string to fall through
    to the LLM-generated opener.

    Priority order: negative reviews > no Maps listing > outdated website > inactive social
    These map directly to the pain signals set by pain_signals.py.
    """
    # 1. Customers are publicly complaining → most urgent, most specific
    if lead.get("negative_reviews_found") is True:
        complaint = lead.get("review_complaint") or "service quality issues"
        return (
            f"I noticed some of your customers mentioned {complaint} on Google. "
            f"Are you currently working on addressing that?"
        )

    # 2. Business is invisible on Google Maps → clear visibility pain
    if lead.get("no_google_maps_listing") is True:
        return (
            f"I searched for {industry} in {city} on Google and couldn't find "
            f"{company} on Maps. Are you getting walk-in customers from Google currently?"
        )

    # 3. Website is outdated or not mobile-friendly → obvious digital gap
    if lead.get("website_is_outdated") is True or lead.get("website_not_mobile") is True:
        return (
            f"I checked your website — it might not be displaying well on mobile phones. "
            f"Are most of your enquiries coming in through calls or WhatsApp instead?"
        )

    # 4. Social page exists but hasn't posted in 3+ months → struggling/pivoting
    if lead.get("last_social_post_old") is True:
        return (
            f"I came across your page online — it looks like you may have shifted away "
            f"from social posting. Are you still active or focusing on other channels for customers?"
        )

    # No signal detected → return empty, LLM uses its own opener
    return ""


async def generate_messages(lead: dict, context: dict) -> dict:
    """
    Agent 3: Hyper-Personalized Message Generator.

    Uses the analyst output fields to write outreach that references
    real specifics: the decision maker's name, the exact buying signal,
    the predicted objection, and the company's own industry/city.

    Args:
        lead:    Fully enriched + AI-scored lead dict
        context: Pipeline context (service, budget_range, etc.)

    Returns:
        {
          whatsapp:          str       (primary variant),
          whatsapp_variants: list[str] (all 3),
          linkedin:          str,
          email_subject:     str,
          email_body:        str,
        }
    """

    # Pull all the rich analyst fields
    company         = lead.get("company_name", "this business")
    city            = lead.get("location", "")
    industry        = lead.get("industry") or lead.get("category") or ""
    dm              = lead.get("decision_maker") or "the founder"
    pain            = lead.get("pain_point") or "operational inefficiencies"
    objection_1     = lead.get("objection_1") or lead.get("objection_prediction") or "too expensive"
    rebuttal_1      = lead.get("rebuttal_1") or "We've helped similar businesses see ROI within 90 days."
    objection_2     = lead.get("objection_2") or "already have a solution"
    rebuttal_2      = lead.get("rebuttal_2") or ""
    best_channel    = lead.get("best_channel") or "WhatsApp"
    buying_signals  = lead.get("buying_signals") or []
    score_reason    = lead.get("score_reason") or lead.get("hot_reason") or ""
    size_tag        = lead.get("company_size") or lead.get("company_size_tag") or "SMB"
    source          = lead.get("source", "")

    # Pain-signal-specific opener takes priority over generic LLM opener
    pain_opener     = _select_pain_template(lead, company, city, industry)
    opener          = pain_opener or lead.get("personalized_opener") or ""

    # Store which template was selected (for API response / review UI)
    lead["pain_template"] = pain_opener if pain_opener else "llm_generated"

    # Format buying signals as a readable list
    signals_text = "\n".join(
        f"  - {s}" for s in (buying_signals if isinstance(buying_signals, list) else [str(buying_signals)])
    ) or f"  - Found on {source}"

    # ── WhatsApp: 3 variants ─────────────────────────────────────────────
    whatsapp_prompt = f"""You are an expert Indian B2B sales copywriter.
Write 3 WhatsApp messages for outreach to this specific company.

TARGET:
Company:        {company}
City:           {city}
Industry:       {industry}
Decision maker: {dm}
Their pain:     {pain}
Buying signals: 
{signals_text}
Why HOT:        {score_reason}
Pain observation (USE THIS as the base for Variant 1 — this is a REAL, specific observation about them):
{opener if opener else 'No specific pain signal detected — write a general but personalized opener'}

Our service: {context.get("service")}

RULES for all 3 variants:
- 2-3 lines max. WhatsApp is NOT email.
- Hinglish (natural mix — like a friend who works in tech writes)
- Start with THEIR situation or a specific observation — NOT "Hi" or "Hello"
- Use ONE specific buying signal or pain point per message
- Offer a quick insight or result — NOT "book a demo"
- Each variant must use a DIFFERENT angle / opener
- Variant 1: Reference their specific buying signal (job post / no website / rating)
- Variant 2: Lead with a result ("ek hospital in {city} ne...")
- Variant 3: Ask a sharp question that hits their pain

Return ONLY a JSON array of exactly 3 strings:
["variant1", "variant2", "variant3"]
"""

    # ── LinkedIn ─────────────────────────────────────────────────────────
    linkedin_prompt = f"""Write a LinkedIn connection request message for B2B outreach.

Sender: Broader AI (Indian AI services company)
Recipient: {dm} at {company} ({city})
Their pain: {pain}
Key buying signal: {buying_signals[0] if buying_signals else score_reason}
Our service: {context.get("service")}
Their likely objection: {objection_1}
Rebuttal: {rebuttal_1}

RULES:
- 4-5 lines max (LinkedIn has a 300 char limit for connection notes)
- Professional but warm — not corporate-stiff
- Open with something SPECIFIC about them (city + industry + signal)
- Address the pain → our solution → soft outcome claim
- Naturally handle the objection in one line
- End with a soft CTA: "Worth a 10-min chat?"
- Do NOT use emojis in LinkedIn

Return ONLY the message text, no JSON, no labels.
"""

    # ── Email ────────────────────────────────────────────────────────────
    email_prompt = f"""Write a cold outreach email for B2B sales.

To: {dm} at {company} ({city}, {industry})
From: Broader AI
Their specific pain: {pain}
Buying signal: {buying_signals[0] if buying_signals else score_reason}
Our service: {context.get("service")}
Budget context: {context.get("budget_range")}
Objection to handle: {objection_1}
Rebuttal: {rebuttal_1}
Second objection: {objection_2}

RULES:
- Subject: 6-8 words. SPECIFIC to their city + industry. Curiosity-driving.
- Body: exactly 80-100 words
- Structure: Pain they recognise → specific result we delivered → 
  handle objection naturally → one clear value statement → soft CTA
- Reference their company/city/industry specifically
- No "I hope this finds you well"
- No "synergy" or corporate jargon
- End with: "Worth 10 minutes?" or similar soft close

Return ONLY JSON:
{{
  "subject": "...",
  "body": "..."
}}
"""

    # Run all 3 prompts concurrently \u2014 hard 160s cap (3 \u00d7 50s LLM + buffer)
    # If messages time out, defaults below are used \u2014 pipeline never hangs here.
    try:
        whatsapp_result, linkedin_result, email_result = await asyncio.wait_for(
            asyncio.gather(
                run_llm(
                    whatsapp_prompt,
                    json_mode=True,
                    lead_id=lead.get("_db_id") or lead.get("id"),
                    lead=lead,
                    task="messages_whatsapp",
                ),
                run_llm(
                    linkedin_prompt,
                    json_mode=False,
                    lead_id=lead.get("_db_id") or lead.get("id"),
                    lead=lead,
                    task="messages_linkedin",
                ),
                run_llm(
                    email_prompt,
                    json_mode=True,
                    lead_id=lead.get("_db_id") or lead.get("id"),
                    lead=lead,
                    task="messages_email",
                ),
                return_exceptions=True,
            ),
            timeout=160.0,
        )
    except asyncio.TimeoutError:
        print(f"[messages] TIMEOUT generating messages for '{company}' \u2014 using defaults")
        whatsapp_result, linkedin_result, email_result = None, None, None

    # ── Parse WhatsApp variants ──────────────────────────────────────────
    default_variants = [
        (
            opener
            or f"{company} jaisi companies {city} mein abhi AI automation se apna 40% operations cost cut kar rahi hain. "
               f"Aapke liye bhi ek quick idea hai — 10 min milenge?"
        ),
        (
            f"Ek {industry} company in {city} ne hamaare saath {pain[:60]}... ka problem solve kiya — "
               f"3 hafte mein result aaya. Aap chahein toh same approach share kar sakta hun."
        ),
        (
            f"Seedha poochhna chahta hun — {company} mein {pain[:50]}... ka issue hai? "
               f"10 min mein batata hun exactly kaise fix karte hain."
        ),
    ]

    if isinstance(whatsapp_result, Exception) or not whatsapp_result:
        variants = default_variants
    elif isinstance(whatsapp_result, list):
        variants = [str(v) for v in whatsapp_result[:3]]
    elif isinstance(whatsapp_result, dict):
        for key in ("variants", "messages", "whatsapp", "0", "1"):
            if isinstance(whatsapp_result.get(key), list):
                variants = [str(v) for v in whatsapp_result[key][:3]]
                break
        else:
            variants = default_variants
    else:
        variants = default_variants

    while len(variants) < 3:
        variants.append(default_variants[len(variants) % len(default_variants)])
    variants = variants[:3]

    # ── Parse LinkedIn ───────────────────────────────────────────────────
    if isinstance(linkedin_result, Exception) or not linkedin_result:
        linkedin_msg = (
            f"Hi {dm}, I came across {company} in {city} — "
            f"looks like {pain[:80]}. "
            f"We've helped similar {industry} businesses solve this efficiently. "
            f"Worth a 10-min chat?"
        )
    else:
        linkedin_msg = str(linkedin_result).strip()

    # ── Parse Email ──────────────────────────────────────────────────────
    if isinstance(email_result, Exception) or not email_result or not isinstance(email_result, dict):
        email_subject = f"Quick idea for {company} [{city}]"
        email_body = (
            f"Hi {dm},\n\n"
            f"I came across {company} and noticed {pain[:100]}.\n\n"
            f"We've helped similar {industry} businesses solve this in {city}. "
            f"{rebuttal_1}\n\n"
            f"Worth 10 minutes?"
        )
    else:
        email_subject = email_result.get("subject") or email_result.get("email_subject") or f"Quick idea for {company}"
        email_body    = email_result.get("body")    or email_result.get("email_body")    or ""

    return {
        "whatsapp":          variants[0],
        "whatsapp_variants": variants,
        "linkedin":          linkedin_msg,
        "email_subject":     email_subject,
        "email_body":        email_body,
    }
