"""
utils/lead_input.py
===================
Sanitization and strict input validation for leads before DB save.
"""

import re


_PHONE_REGEX = re.compile(
    r"^(?:(?:\+91)?[6-9]\d{9}|0\d{10,11}|\d{2,4}\d{6,8})$"
)
_EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def sanitize_lead(lead: dict) -> dict:
    """
    Return a sanitized copy of the lead.
    - Strips whitespace from all string fields
    - Normalizes phone numbers by removing spaces/dashes/brackets
    - Lowercases email
    - Adds https:// to website if no scheme is present
    """
    clean: dict = {}
    for key, value in lead.items():
        if isinstance(value, str):
            value = value.strip()
            if key == "phone":
                value = re.sub(r"[\s\-\(\)]", "", value)
            elif key == "email":
                value = value.lower()
            elif key == "website" and value and not re.match(r"^https?://", value, re.IGNORECASE):
                value = f"https://{value}"
            clean[key] = value
        else:
            clean[key] = value
    return clean


def validate_lead(lead: dict) -> tuple[bool, list[str]]:
    """
    Validate sanitized input before save.
    Uses company_name as the canonical name field when present.
    """
    errors: list[str] = []

    name = (lead.get("name") or lead.get("company_name") or "").strip()
    phone = (lead.get("phone") or "").strip()
    email = (lead.get("email") or "").strip()
    website = (lead.get("website") or "").strip()
    contact_link = (lead.get("contact_link") or lead.get("source_url") or "").strip()

    if not name:
        errors.append("name is required")
    elif len(name) < 2:
        errors.append("name must be at least 2 characters")

    if phone and not _PHONE_REGEX.match(phone):
        lead["phone"] = ""  # clear invalid phone, do not reject lead

    if email and not _EMAIL_REGEX.match(email):
        errors.append("email must be valid")

    if website and not re.match(r"^https?://", website, re.IGNORECASE):
        errors.append("website must start with http:// or https://")

    if not any([phone, email, website, contact_link]):
        errors.append("at least one of phone, email, website, or source link is required")

    return len(errors) == 0, errors
