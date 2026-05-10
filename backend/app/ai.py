"""
ai.py
======
AI Scoring Agent — Strategic B2B Analyst
------------------------------------------
Uses Groq API to analyse each lead like a senior
B2B sales strategist, not just a scorer.

What changed from v1:
  OLD: "Give fit/intent/contact scores"
  NEW: "Find BUYING SIGNALS, name the DECISION MAKER,
        articulate their SPECIFIC PAIN, predict OBJECTIONS
        with REBUTTALS, and write a READY-TO-SEND opener"

The LLM now outputs a rich analyst report.
The deterministic compute_priority_tag() still overrides the
label for consistency (LLMs hallucinate scores).
"""

import json
import os
import time
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

groq_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)



# ---------------------------------------------------------------------------
# Deterministic label — overrides LLM to ensure consistency
# ---------------------------------------------------------------------------

def compute_priority_tag(fit: int, intent: int, contactability: int) -> tuple[str, float]:
    """
    HOT/WARM/COLD label from weighted composite score.
    Weights: fit=40%, intent=40%, contactability=20%

    HOT  : composite >= 72
    WARM : composite >= 48
    COLD : below 48

    This always overrides whatever label the LLM suggests —
    prevents hallucinated scores producing wrong labels.
    """
    composite = (fit * 0.40) + (intent * 0.40) + (contactability * 0.20)
    if composite >= 72:
        tag = "HOT"
    elif composite >= 48:
        tag = "WARM"
    else:
        tag = "COLD"
    return tag, round(composite, 1)


def _tag_from_composite(composite: float) -> str:
    """Map a final composite score to HOT/WARM/COLD."""
    if composite >= 72:
        return "HOT"
    if composite >= 48:
        return "WARM"
    return "COLD"


# ---------------------------------------------------------------------------
# Client Readiness Score — deterministic, no LLM
# ---------------------------------------------------------------------------

def compute_client_readiness_score(lead: dict) -> int:
    """
    Measures HOW READY a business is to buy — distinct from lead quality.

    A business with money + pain + reachability = true client.
    A business with just a directory listing = not ready.

    Formula (max raw = 170, normalised to 100):
      Money signals  (they're established):  +20 physical, +15 reviews>10, +10 website
      Pain signals   (they need help):        +25 bad reviews, +20 outdated site,
                                              +20 no Maps listing, +15 inactive social
      Reachability   (we can reach them):     +15 phone, +20 WhatsApp, +10 email

    Returns: integer 0–100
    """
    raw = 0

    # ── Money signals (established = has money to spend) ──────────────────
    if lead.get("has_physical_location") is True:      raw += 20
    rev_count = lead.get("google_reviews_count")
    if isinstance(rev_count, int) and rev_count > 10:  raw += 15
    if lead.get("website") or lead.get("website_alive"): raw += 10

    # ── Pain signals (they have a detectable problem) ─────────────────────
    if lead.get("negative_reviews_found") is True:     raw += 25
    if lead.get("website_is_outdated") is True or lead.get("website_not_mobile") is True: raw += 20
    if lead.get("no_google_maps_listing") is True:     raw += 20
    if lead.get("last_social_post_old") is True:       raw += 15
    if lead.get("hiring_manual_roles") is True:        raw += 10

    # ── Reachability (we can actually contact them) ───────────────────────
    if lead.get("phone"):                              raw += 15
    if lead.get("whatsapp_hint") is True:              raw += 20
    if lead.get("email"):                              raw += 10

    # Normalise to 100
    MAX_RAW = 180
    return min(100, int(raw * 100 / MAX_RAW))


# ---------------------------------------------------------------------------
# Source-specific buying signal hints
# ---------------------------------------------------------------------------

_SOURCE_SIGNALS = {
    # ── High-quality sources (real businesses, not job hunters) ──────────
    "justdial":    (
        "MEDIUM SIGNAL: SMB found on JustDial. Likely owner-operated. These "
        "businesses often run on manual processes and are prime for automation. "
        "Check if they have a website. Intent score 45–65."
    ),
    "sulekha":     (
        "MEDIUM SIGNAL: Local service business on Sulekha. Phone is usually the "
        "owner's direct line. Decision maker is reachable. Intent score 45–65."
    ),
    "google_maps": (
        "HIGH SIGNAL: Found on Google Maps — likely local business with customers "
        "but limited digital presence. A business with customers but no website = "
        "perfect prospect for digital services. Intent score 65–80."
    ),
    "clutch":      (
        "HIGH VALUE: Listed on Clutch.co — confirmed tech budget, usually "
        "mid-market or above. Decision maker is likely a CTO or VP. Intent score 70–85."
    ),
    "indiamart":   (
        "HIGH SIGNAL: Listed on IndiaMART as manufacturer/supplier — this is a "
        "verified B2B business with an ACTIVE listing (costs money to maintain). "
        "Owner-operated, decision maker directly reachable. Intent score 60–80."
    ),
    "tradeindia":  (
        "HIGH SIGNAL: Listed on TradeIndia — verified manufacturer/trader with "
        "physical operations. Similar to IndiaMART profile. Decision maker is "
        "owner/proprietor. Intent score 60–75."
    ),
    "instagram":   (
        "MEDIUM-HIGH SIGNAL: Active local business Instagram page found. "
        "If the page exists but posts are old → struggling business = easy conversation. "
        "DM response rates are 3x email for Indian SMBs. Intent score 50–70."
    ),
    "facebook":    (
        "MEDIUM SIGNAL: Local business Facebook page found. Very high penetration "
        "among Indian SMB owners 35+. Phone/WhatsApp often listed on page. "
        "Decision maker is usually the owner. Intent score 45–65."
    ),
    # ── Re-enabled sources (filtered by BusinessQualifier before reaching AI) ──
    "truelancer":  (
        "HIGH SIGNAL (ACTIVE REQUEST): Active project posted on Truelancer — "
        "confirmed buying intent. Price-driven but real project. Intent score 65–80."
    ),
    "internshala": (
        "MEDIUM SIGNAL (HIRING): Company is hiring on Internshala — may have budget "
        "but is looking for cheap labor, not a premium vendor. Intent score 30–50."
    ),
}



# ---------------------------------------------------------------------------
# Main scoring function — the strategic analyst prompt
# ---------------------------------------------------------------------------

async def score_lead(lead: dict, context: dict) -> dict:
    """
    Agent 2: Strategic B2B Sales Analyst

    Takes a fully enriched lead and produces:
    - fit_score, buying_intent_score, contactability_score
    - decision_maker, pain_point, buying_signals
    - objection_1/2 + rebuttal_1/2
    - best_channel + channel_reason
    - personalized_opener (ready-to-send)
    - speed_to_close_estimate (clearly labelled as LLM estimate — not reliable
      until 10+ real closed deals are logged via the feedback loop)
    """
    # Load calibration floors if available (from real closed-deal feedback)
    calibration_note = ""
    intent_floor_adj = 0
    try:
        from app.utils.feedback import get_adjusted_score_floors
        floors = get_adjusted_score_floors()
        source = lead.get("source", "")
        if floors.get("has_data") and source in floors:
            adj = floors[source]
            intent_floor_adj = adj.get("intent_boost", 0)
            calibration_note = (
                f"CALIBRATION DATA (from real closed deals): "
                f"{source} has a {adj['close_rate']*100:.0f}% close rate. "
                f"Adjust buying_intent_score by {'+' if intent_floor_adj >= 0 else ''}{intent_floor_adj} points. "
                f"{adj['floor_note']}"
            )
        elif not floors.get("has_data"):
            calibration_note = (
                f"NOTE: No historical deal data yet ({floors.get('overall_close_rate', 0)*100:.0f}% outcomes logged). "
                f"Score based on signals only — not calibrated."
            )
    except Exception:
        calibration_note = "Calibration data unavailable — score based on signals."

    source         = lead.get("source", "")
    source_signal  = _SOURCE_SIGNALS.get(source, "")
    website_status = f"Yes — {lead.get('website')}" if lead.get("website") else "No website found"
    company_size   = lead.get("company_size", lead.get("company_size_tag", "Unknown"))
    intent_signal  = lead.get("intent_signal", "")   # from Truelancer/Internshala scraper
    intent_level   = lead.get("source_intent_level", "directory_listing")
    qualifier_flag = lead.get("qualifier_flag", "")

    # Contact availability
    has_phone = bool(lead.get("phone"))
    has_email = bool(lead.get("email"))
    has_site  = bool(lead.get("website_alive") or lead.get("website"))
    has_li    = bool(lead.get("linkedin_url"))

    contact_summary = ", ".join(filter(None, [
        "phone" if has_phone else "",
        "email" if has_email else "",
        "live website" if has_site else "",
        "LinkedIn" if has_li else "",
    ])) or "none"

    prompt = f"""You are a senior B2B sales strategist for Broader AI, an Indian AI services company.
Your job: analyse ONE business lead and produce a detailed sales intelligence report.

=== THE LEAD ===
Company:         {lead.get("company_name")}
Industry:        {lead.get("industry") or lead.get("category")}
City:            {lead.get("location")}
Source:          {source}
Intent Level:    {intent_level.upper().replace('_', ' ')} {"(⚠️ LOW BUDGET FLAG — score conservatively)" if qualifier_flag == 'LOW_BUDGET' else ""}
Website:         {website_status}
Website alive:   {"YES" if lead.get("website_alive") else "NO"}
Hiring manual:   {"YES — strong buying intent signal" if lead.get("hiring_manual_roles") is True else "NO / Unknown"}
Company size:    {company_size}
Known contacts:  {contact_summary}
Phone:           {lead.get("phone") or "not found"}
Email:           {lead.get("email") or "not found"}
LinkedIn:        {lead.get("linkedin_url") or "not found"}
Decision maker (if known): {lead.get("decision_maker") or "unknown — infer from industry + size"}

About / Services:
{(lead.get("services_text") or lead.get("description") or "Not available")[:300]}

Buying signal / Intent evidence:
{intent_signal or "No specific signal — infer from source and category"}

Budget hint: {lead.get("budget_hint") or "Unknown"}

=== BROADER AI CONTEXT ===
Our service:      {context.get("service")}
Budget range:     {context.get("budget_range")}

=== SOURCE INTELLIGENCE ===
{source_signal}

=== YOUR TASK ===
Analyse this lead like a top B2B sales consultant. Be SPECIFIC — use the company's
actual industry, city, size, and source signals. Never be generic.

Return ONLY valid JSON with these exact fields:

{{
  "fit_score": <integer 0-100>,
  "buying_intent_score": <integer 0-100>,
  "contactability_score": <integer 0-100>,

  "decision_maker": "<Name (Title)> — e.g. 'Rahul Sharma (Founder)'. If unknown, infer the most likely title for this company type and size.",

  "pain_point": "<SPECIFIC pain this exact company faces RIGHT NOW. Reference their industry, city, size. Example: 'Running 200+ daily patient appointments manually in Pune — staff spending 3+ hours on documentation that AI could do in minutes'>",

  "buying_signals": [
    "<concrete signal 1 — e.g. 'Posted web dev project on Freelancer 3 days ago'>",
    "<concrete signal 2 — e.g. 'No website found despite 4.5★ rating with 300+ reviews'>",
    "<concrete signal 3 if available>"
  ],

  "objection_1": "<Most likely reason they say NO — be specific, not generic>",
  "rebuttal_1": "<One sharp sentence that pre-empts objection_1>",

  "objection_2": "<Second most likely objection>",
  "rebuttal_2": "<Rebuttal for objection_2>",

  "best_channel": "<WhatsApp / LinkedIn / Cold Email / Direct Call>",
  "channel_reason": "<Why this channel? e.g. 'SMB owner — phone is direct line, WhatsApp reply rate 3x email in India'>",

  "personalized_opener": "<READY-TO-SEND first message. Must reference something REAL and SPECIFIC about them. NOT generic. Example: 'Saw you're hiring 2 ops managers in Pune — usually means you're scaling and manual tracking is breaking. We helped a similar clinic cut admin time by 40%. Quick 10-min chat?>",

  "estimated_deal": "<Rupee estimate based on company size and service>",

  "speed_to_close_estimate": "<Fast / Medium / Slow — NOTE: This is an LLM ESTIMATE based on industry norms, NOT real deal data. Label it as estimate in your UI until 10+ real closed deals are logged.>",

  "score_reason": "<ONE sentence: why HOT/WARM/COLD with SPECIFIC evidence. Example: 'HOT: Active project posted + no website + phone available — in active buying mode'>"
}}

{calibration_note}

=== SCORING RULES (follow strictly) ===
- fit_score: How precisely does our service solve their problem? (not just 'they're in the industry')
- buying_intent_score:
  - Intent Level is ACTIVE REQUEST (Truelancer/Internshala) = buyer is in market RIGHT NOW. Base score 75+.
  - Intent Level is DIRECTORY LISTING = passive business. Score based on pain signals.
  - Specific signals override base:
    - Active hiring or project request = 80–100
    - No website but active business = 65–80
    - Generic directory listing = 30–55
- contactability_score: phone+email+LinkedIn=100 | phone+email=90 | phone only=70 | email only=50 | website only=35 | nothing=5
- personalized_opener: Reference their CITY + INDUSTRY + a SPECIFIC signal (job posting, rating, no website, etc.)
- Return ONLY JSON — no explanation, no markdown, no extra text
{f'''
=== DIRECTORY LISTING SCORING OVERRIDE ===
(These rules apply because Intent Level = DIRECTORY LISTING)

CHANGE D — Source Context:
This lead is from a business directory. Purchase intent is UNKNOWN.
Score based primarily on contactability and pain signals — NOT on assumed intent.
Do not assign high intent scores just because they are in the right industry.

CHANGE A — Contact Completeness Rules (use these as your PRIMARY scoring guide):
  RULE 1: Lead has phone AND website AND email  → contactability base 75–100 → likely HOT
  RULE 2: Lead has phone AND website (no email) → contactability base 55–70  → likely WARM
  RULE 3: Lead has phone OR website (not both)  → contactability base 35–54  → likely WARM
  RULE 4: Lead has neither phone nor website    → contactability base 0–34   → likely COLD

Current contact info for this lead: {contact_summary}
Apply the matching rule above. Do NOT override it without specific evidence.

CHANGE B — Pain Signal Bonus:
  IF pain signals are present in the "Buying signal / Intent evidence" field → add +10 to your base contactability score.
  IF no pain signals detected → no adjustment. Do not invent signals.

CHANGE C — FORCE DECISION (read carefully):
IMPORTANT: You MUST output HOT, WARM, or COLD — no exceptions.
WARM is NOT a safe default. Only assign WARM if the lead genuinely scores between 35–70 using the contact completeness rules above.
If you are uncertain, use ONLY the contact completeness rule above to decide.
A lead with full contact info (phone + website + email) → HOT.
A lead with no contact info at all → COLD.
Defaulting everything to WARM because you are uncertain is WRONG.
''' if intent_level == 'directory_listing' else ''}
"""


    analysis = await run_llm(
        prompt,
        json_mode=True,
        lead_id=lead.get("_db_id") or lead.get("id"),
        lead=lead,
        task="scoring",
    )

    # Robust fallback if LLM fails or returns garbage
    if not analysis or not isinstance(analysis, dict):
        contactability = 90 if (has_phone and has_email) else 70 if has_phone else 50 if has_email else 20
        analysis = {
            "fit_score":            50,
            "buying_intent_score":  50,
            "contactability_score": contactability,
            "decision_maker":       "Owner / Founder",
            "pain_point":           f"Manual operations in {lead.get('industry', 'their industry')} that could be automated",
            "buying_signals":       [f"Found on {source}", "Active business"],
            "objection_1":          "Already have a solution",
            "rebuttal_1":           "Most of our clients said the same — until we showed them what they were leaving on the table.",
            "objection_2":          "Too expensive",
            "rebuttal_2":           "Our ROI calculator shows payback in under 90 days for most clients your size.",
            "best_channel":         "WhatsApp" if has_phone else "Email",
            "channel_reason":       "Fastest response channel for Indian SMB owners",
            "personalized_opener":  (
                f"Saw {lead.get('company_name')} on {source} — "
                f"businesses in {lead.get('location', 'your area')} are increasingly using AI to cut ops cost. "
                f"Quick 10-min chat to show you what's working?"
            ),
            "estimated_deal":       context.get("budget_range", "₹50k–₹2L"),
            "speed_to_close":       "Medium",
            "score_reason":         f"Default scoring — LLM unavailable. Source: {source}",
        }

    # Always recompute our deterministic label — never trust LLM's label
    tag, composite = compute_priority_tag(
        fit=int(analysis.get("fit_score", 0)),
        intent=int(analysis.get("buying_intent_score", 0)),
        contactability=int(analysis.get("contactability_score", 0)),
    )
    analysis["priority_tag"]    = tag
    analysis["label"]           = tag
    analysis["composite_score"] = composite

    # Rename speed_to_close → speed_to_close_estimate (never let UI show it as fact)
    if "speed_to_close" in analysis and "speed_to_close_estimate" not in analysis:
        analysis["speed_to_close_estimate"] = analysis.pop("speed_to_close")
    # Add a clear disclaimer flag
    analysis["speed_is_estimate"] = True
    analysis["speed_note"] = (
        "LLM estimate — not reliable until 10+ real deals logged via feedback loop"
    )

    # Apply calibration floor boost if we have real data + Manual Hiring signal (+10 intent)
    intent_adj_total = intent_floor_adj
    if lead.get("hiring_manual_roles") is True:
        intent_adj_total += 10

    if intent_adj_total != 0:
        raw_intent = int(analysis.get("buying_intent_score", 0))
        adjusted   = max(0, min(100, raw_intent + intent_adj_total))
        analysis["buying_intent_score"] = adjusted
        analysis["intent_score"]        = adjusted
        if intent_floor_adj != 0:
            analysis["intent_calibrated"] = True
        # Recompute label with adjusted scores
        tag2, composite2 = compute_priority_tag(
            fit=int(analysis.get("fit_score", 0)),
            intent=adjusted,
            contactability=int(analysis.get("contactability_score", 0)),
        )
        analysis["priority_tag"]    = tag2
        analysis["label"]           = tag2
        analysis["composite_score"] = composite2

    # Field aliases for pipeline/DB compatibility
    analysis["hot_reason"]           = analysis.get("score_reason", "")
    analysis["intent_score"]         = analysis.get("buying_intent_score", 0)
    analysis["contact_score"]        = analysis.get("contactability_score", 0)
    analysis["objection_prediction"] = analysis.get("objection_1", "")

    try:
        from app.database import get_source_weight
        source_weight = get_source_weight(source)
    except Exception:
        source_weight = 1.0

    base_score = float(analysis.get("composite_score", 0.0) or 0.0)
    final_score = int(round(base_score * source_weight))
    final_score = max(0, min(100, final_score))
    weighted_tag = _tag_from_composite(final_score)

    analysis["base_composite_score"] = base_score
    analysis["source_weight"] = source_weight
    analysis["composite_score"] = final_score
    analysis["priority_tag"] = weighted_tag
    analysis["label"] = weighted_tag

    return analysis


def _rule_based_scoring_fallback(lead: dict | None = None) -> dict:
    """Tier 3 deterministic fallback for scoring."""
    lead = lead or {}
    has_email = bool((lead.get("email") or "").strip())
    has_phone = bool((lead.get("phone") or "").strip())
    has_website = bool((lead.get("website") or "").strip())
    name = (lead.get("company_name") or lead.get("name") or "").strip()

    score = 0
    if has_email:
        score += 20
    if has_phone:
        score += 20
    if has_website:
        score += 15
    if len(name) > 3:
        score += 10
    if lead.get("hiring_manual_roles") is True:
        score += 10

    try:
        from app.database import get_source_weight
        source_weight = get_source_weight(lead.get("source", ""))
    except Exception:
        source_weight = 1.0

    score = int(round(score * source_weight))
    score = max(0, min(100, score))

    return {
        "fit_score": score,
        "buying_intent_score": score,
        "contactability_score": score,
        "decision_maker": "Owner / Founder",
        "pain_point": "Business may need help with online visibility and lead generation.",
        "buying_signals": [f"Found on {lead.get('source', 'unknown')}"],
        "objection_1": "Not sure if this is needed right now",
        "rebuttal_1": "A small improvement in lead flow can make the next quarter much stronger.",
        "objection_2": "We already do some marketing",
        "rebuttal_2": "We often complement existing efforts rather than replacing them.",
        "best_channel": "WhatsApp" if has_phone else "Email",
        "channel_reason": "Generic fallback based on available contact information",
        "personalized_opener": "Hi, I help businesses like yours grow their client base. Would you be open to a quick call?",
        "estimated_deal": lead.get("budget_hint") or "",
        "speed_to_close_estimate": "Medium",
        "score_reason": "Rule-based fallback used because AI tiers were unavailable.",
    }


def _rule_based_message_fallback() -> dict:
    """Tier 3 deterministic fallback for outreach generation."""
    generic = "Hi, I help businesses like yours grow their client base. Would you be open to a quick call?"
    return {
        "whatsapp": generic,
        "whatsapp_variants": [generic, generic, generic],
        "linkedin": generic,
        "email_subject": "Quick growth idea",
        "email_body": generic,
    }


def _coerce_rule_based_response(json_mode: bool, task: str | None, lead: dict | None) -> dict | str:
    """Shape Tier 3 fallback to match the expected caller contract."""
    task = (task or "").lower()
    if task == "scoring":
        return _rule_based_scoring_fallback(lead)
    if task.startswith("messages"):
        payload = _rule_based_message_fallback()
        if json_mode:
            if task == "messages_whatsapp":
                return payload["whatsapp_variants"]
            if task == "messages_email":
                return {"subject": payload["email_subject"], "body": payload["email_body"]}
            return payload
        if task == "messages_linkedin":
            return payload["linkedin"]
        return payload["whatsapp"]
    return {} if json_mode else ""


async def llm_call(
    prompt: str,
    json_mode: bool = True,
    lead_id: int | None = None,
    lead: dict | None = None,
    task: str | None = None,
) -> dict | str:
    """
    LLM call via Groq (llama-3.3-70b-versatile).
    Raises RuntimeError on failure so callers get a clear signal.
    """
    try:
        from app.database import log_llm_health
    except Exception:
        log_llm_health = None

    start = time.perf_counter()
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            **({"response_format": {"type": "json_object"}} if json_mode else {})
        )
        result_text = response.choices[0].message.content
        result = json.loads(result_text) if json_mode else result_text.strip()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if log_llm_health:
            log_llm_health(1, lead_id, elapsed_ms, True)
        print(f"LLM tier used: Groq for lead_id {lead_id}")
        return result
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if log_llm_health:
            log_llm_health(1, lead_id, elapsed_ms, False)
        raise RuntimeError(
            f"Groq LLM call failed for lead_id {lead_id} "
            f"(task={task}, elapsed={elapsed_ms}ms): {e}"
        ) from e


async def run_llm(
    prompt: str,
    json_mode: bool = True,
    lead_id: int | None = None,
    lead: dict | None = None,
    task: str | None = None,
) -> dict | str:
    """Compatibility wrapper around llm_call() (Groq only)."""
    return await llm_call(prompt, json_mode=json_mode, lead_id=lead_id, lead=lead, task=task)
