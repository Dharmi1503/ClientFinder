"""
app/filters/business_qualifier.py
====================================
Pre-pipeline Quality Gate for active request leads.

Runs immediately after scraping, before any enrichment or AI scoring.
Rejects leads that are clearly low-quality (individuals, dead posts,
microbudgets) before wasting enrichment time and LLM tokens on them.

For all leads that PASS the filter, adds:
    source_intent_level = "active_request"   → for active sources
    source_intent_level = "directory_listing" → for all other sources

This field is passed to the Ollama scoring prompt in Stage 6 so
active_request leads get weighted higher in HOT classification.
"""

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# "Position filled" signals — post is dead
_CLOSED_SIGNALS = re.compile(
    r'already\s+hired|position\s+filled|closed|no\s+longer\s+available|'
    r'not\s+accepting',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public API — the single entry point
# ---------------------------------------------------------------------------

# Sources that produce active requests (not passive directory listings)
_ACTIVE_REQUEST_SOURCES = {"truelancer", "internshala"}

# Directory sources — lower baseline intent
_DIRECTORY_SOURCES = {
    "justdial", "google_maps", "clutch", "sulekha",
    "indiamart", "instagram", "facebook", "tradeindia",
}


def qualify_lead(lead: dict) -> dict | None:
    """
    Gate function. Call this immediately after scraping, before enrichment.

    Returns:
        The same lead dict (with source_intent_level added) if it passes.
        None if the lead should be rejected.
    """
    source = (lead.get("source") or "").lower().strip()

    # --- Source intent level ---
    if source in _ACTIVE_REQUEST_SOURCES:
        intent_level = "active_request"
    else:
        intent_level = "directory_listing"

    # --- Run source-specific filters ---
    passes = True
    rejection_reason = ""

    # Only apply the universal "closed" check
    combined_text = (
        (lead.get("company_name") or "") + " " +
        (lead.get("description") or "") + " " +
        (lead.get("intent_signal") or "")
    )
    if _CLOSED_SIGNALS.search(combined_text):
        passes = False
        rejection_reason = "post_closed"

    if not passes:
        print(f"  [qualifier] REJECTED {source}: {lead.get('company_name', '')[:40]} — {rejection_reason}")
        return None

    # Passed — add metadata fields
    lead["source_intent_level"] = intent_level

    return lead


def qualify_batch(leads: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Run qualify_lead() over a list of leads.

    Returns:
        (passed_leads, rejected_leads)
    """
    passed = []
    rejected = []
    for lead in leads:
        result = qualify_lead(lead)
        if result is not None:
            passed.append(result)
        else:
            rejected.append(lead)
    return passed, rejected


def tag_directory_leads(leads: list[dict]) -> list[dict]:
    """
    For non-Freelancer/Reddit sources, just add source_intent_level.
    Call this on directory leads that skip the qualifier gate.
    """
    for lead in leads:
        source = (lead.get("source") or "").lower()
        if "source_intent_level" not in lead:
            lead["source_intent_level"] = (
                "active_request" if source in _ACTIVE_REQUEST_SOURCES
                else "directory_listing"
            )
    return leads
