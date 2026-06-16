"""Phone number normalization for Twilio lookups."""

from __future__ import annotations

import re


def normalize_phone(raw: str) -> str:
    """Normalize to E.164 where possible."""
    raw = (raw or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return raw
    if raw.startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


def is_valid_e164(phone: str) -> bool:
    """Return True for plausible E.164 numbers (not Twilio AccountSid)."""
    return bool(re.fullmatch(r"\+\d{10,15}", phone or ""))
