"""
utils/contact_gate.py
======================
Contact Gate — Zero-Contact Lead Handler
-----------------------------------------
If a lead has absolutely no contact method after full enrichment
(no phone, no email, no live website), it cannot be acted on.

What we do:
  - Force contact_score = 0
  - Force label = COLD (regardless of fit/intent scores)
  - Still SAVE to DB (so we don't re-scrape it)
  - Never surface as HOT or WARM in results

Why save it at all?
  The deduplicator will skip it next time → saves API calls.
  The user can see it with filter=COLD if curious.

This gate runs AFTER enrichment (so website scraping had a chance)
and BEFORE AI scoring (so Ollama doesn't waste time on it).
"""


# Contact thresholds
_MIN_CONTACT_FOR_WARM = 1   # at least one contact method needed
_ZERO_CONTACT_SCORE = 0


def _count_contact_methods(lead: dict) -> int:
    """Count how many real contact methods exist on the lead."""
    count = 0
    if lead.get("phone", "").strip():
        count += 1
    if lead.get("email", "").strip():
        count += 1
    if lead.get("website", "").strip() and lead.get("website_alive"):
        count += 1
    if lead.get("linkedin_url", "").strip():
        count += 1
    return count


def apply_contact_gate(lead: dict) -> dict:
    """
    Apply the contact gate to a single lead.

    If no contact methods found after enrichment:
      - Sets contact_score = 0
      - Sets label = "COLD"
      - Adds a note explaining why

    Always returns the lead (modified if gated).

    Args:
        lead: Enriched lead dict

    Returns:
        Lead dict with contact gate applied
    """
    contact_count = _count_contact_methods(lead)

    if contact_count < _MIN_CONTACT_FOR_WARM:
        lead["contact_score"] = _ZERO_CONTACT_SCORE
        lead["label"] = "COLD"
        lead["_contact_gated"] = True  # internal flag for pipeline logging

        # Preserve existing note if any, append reason
        existing_note = lead.get("notes", "")
        gate_note = "Contact gate: no phone/email/live website found after enrichment."
        lead["notes"] = f"{existing_note} | {gate_note}".strip(" |")

        print(
            f"[contact_gate] GATED '{lead.get('company_name', '?')}' — "
            f"0 contact methods found"
        )
    else:
        lead["_contact_gated"] = False

    return lead


def batch_apply_contact_gate(leads: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Apply contact gate to a list of leads.

    Returns:
        (actionable_leads, gated_leads)
        actionable_leads: leads with at least one contact method
        gated_leads:      leads with zero contact methods (label forced to COLD)
    """
    actionable: list[dict] = []
    gated: list[dict] = []

    for lead in leads:
        apply_contact_gate(lead)
        if lead.get("_contact_gated"):
            gated.append(lead)
        else:
            actionable.append(lead)

    if gated:
        print(
            f"[contact_gate] {len(gated)} leads gated (COLD, no contact) | "
            f"{len(actionable)} actionable"
        )

    return actionable, gated
