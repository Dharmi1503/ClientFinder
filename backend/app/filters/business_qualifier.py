"""
app/filters/business_qualifier.py
=================================
Pre-pipeline quality gate for active request leads.

Runs immediately after scraping, before enrichment or AI scoring.
Rejects leads that are clearly low-quality before wasting enrichment
time and LLM tokens on them.
"""

import re


_CLOSED_SIGNALS = re.compile(
    r"already\s+hired|position\s+filled|closed|no\s+longer\s+available|not\s+accepting",
    re.IGNORECASE,
)

_ACTIVE_REQUEST_SOURCES = {
    "freelancer",
    "reddit",
    "truelancer",
    "internshala",
    "worknhire",
    "bark",
    "peopleperhour",
}

_DIRECTORY_SOURCES = {
    "justdial",
    "google_maps",
    "clutch",
    "sulekha",
    "indiamart",
    "instagram",
    "facebook",
    "tradeindia",
    "goodfirms",
}

_LOW_BUDGET_SIGNALS = re.compile(
    r"\b(?:rs\.?|inr|₹)?\s*(?:500|800|1000|1500|2000|2500|3000|4000|5000)\b|\blow\s+budget\b",
    re.IGNORECASE,
)

_NON_BUYER_SIGNALS = re.compile(
    r"\b(?:looking\s+for\s+job|seeking\s+job|hire\s+me|my\s+portfolio|available\s+for\s+work|"
    r"i\s+am\s+a\s+freelancer|i\s+am\s+a\s+developer)\b",
    re.IGNORECASE,
)

_STUDENT_SIGNALS = re.compile(
    r"\b(?:internship|intern|student\s+project|college\s+project|final\s+year)\b",
    re.IGNORECASE,
)

_BUYER_INTENT_SIGNALS = re.compile(
    r"\b(?:need|looking\s+for|want\s+to\s+hire|seeking|required|require|project|quote|proposal|"
    r"agency|company|business)\b",
    re.IGNORECASE,
)


def qualify_lead(lead: dict) -> dict | None:
    """Return the lead with intent metadata, or None if it should be rejected."""
    source = (lead.get("source") or "").lower().strip()
    intent_level = "active_request" if source in _ACTIVE_REQUEST_SOURCES else "directory_listing"

    combined_text = " ".join(
        filter(
            None,
            [
                lead.get("company_name"),
                lead.get("post_title"),
                lead.get("description"),
                lead.get("intent_signal"),
            ],
        )
    )

    rejection_reason = ""
    if _CLOSED_SIGNALS.search(combined_text):
        rejection_reason = "post_closed"
    elif source in _ACTIVE_REQUEST_SOURCES and _NON_BUYER_SIGNALS.search(combined_text):
        rejection_reason = "non_buyer_post"
    elif source in _ACTIVE_REQUEST_SOURCES and _STUDENT_SIGNALS.search(combined_text):
        rejection_reason = "student_or_internship_post"

    if rejection_reason:
        print(f"  [qualifier] REJECTED {source}: {lead.get('company_name', '')[:40]} - {rejection_reason}")
        return None

    if source in _ACTIVE_REQUEST_SOURCES and _LOW_BUDGET_SIGNALS.search(combined_text):
        lead["qualifier_flag"] = "LOW_BUDGET"
    elif source in _ACTIVE_REQUEST_SOURCES and not _BUYER_INTENT_SIGNALS.search(combined_text):
        lead["qualifier_flag"] = "WEAK_INTENT"

    lead["source_intent_level"] = intent_level
    lead["lead_type"] = "job_post" if intent_level == "active_request" else "directory"
    return lead


def qualify_batch(leads: list[dict]) -> tuple[list[dict], list[dict]]:
    """Run qualify_lead() over a list of leads."""
    passed: list[dict] = []
    rejected: list[dict] = []
    for lead in leads:
        result = qualify_lead(lead)
        if result is not None:
            passed.append(result)
        else:
            rejected.append(lead)
    return passed, rejected


def tag_directory_leads(leads: list[dict]) -> list[dict]:
    """Add source_intent_level metadata to directory leads."""
    for lead in leads:
        source = (lead.get("source") or "").lower().strip()
        if "source_intent_level" not in lead:
            lead["source_intent_level"] = (
                "active_request" if source in _ACTIVE_REQUEST_SOURCES else "directory_listing"
            )
        if "lead_type" not in lead:
            lead["lead_type"] = (
                "job_post" if lead["source_intent_level"] == "active_request" else "directory"
            )
    return leads
