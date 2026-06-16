"""Fast rule-based extraction for common Hinglish appointment phrases."""

from __future__ import annotations

import re
from datetime import date, timedelta

HINDI_NUMBERS: dict[str, int] = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12,
}

_NAME_PATTERNS = [
    re.compile(r"\bmain\s+([a-zA-Z]{2,20})\s+hoon\b", re.I),
    re.compile(r"\bmera\s+naam\s+([a-zA-Z]{2,20})\b", re.I),
    re.compile(r"\bnaam\s+([a-zA-Z]{2,20})\s+hai\b", re.I),
    re.compile(r"\bnaam\s+hai\s+([a-zA-Z]{2,20})\b", re.I),
    re.compile(r"\bi\s+am\s+([a-zA-Z]{2,20})\b", re.I),
    re.compile(r"\bthis\s+is\s+([a-zA-Z]{2,20})\b", re.I),
    re.compile(r"\bmy\s+name\s+is\s+([a-zA-Z]{2,20})\b", re.I),
    re.compile(r"\b([a-zA-Z]{2,20})\s+bol\s+raha\b", re.I),
    re.compile(r"\b([a-zA-Z]{2,20})\s+bol\s+rahi\b", re.I),
]

_REJECT_NAMES = frozenset({
    "hi", "hello", "haan", "han", "yes", "no", "nahi", "ok", "theek", "thik",
    "main", "appointment", "doctor", "kal", "aaj", "subah", "sham",
})

_APPOINTMENT_WORDS = (
    "appointment", "slot", "booking", "book", "milna", "aana", "checkup", "doctor",
)

_CONFIRM_YES = ("haan", "han", "yes", "sahi", "theek", "thik", "bilkul", "confirm", "correct")
_CONFIRM_NO = ("nahi", "no", "galat", "change", "alag")


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", lower) for word in words)


def extract_name(text: str) -> str | None:
    t = text.strip()
    for pat in _NAME_PATTERNS:
        m = pat.search(t)
        if m:
            name = m.group(1).strip().title()
            if name.lower() not in _REJECT_NAMES:
                return name
    words = t.split()
    if len(words) == 1 and words[0].isalpha() and len(words[0]) >= 2:
        if words[0].lower() not in _REJECT_NAMES:
            return words[0].title()
    return None


def wants_appointment(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _APPOINTMENT_WORDS)


def extract_reason(text: str) -> str | None:
    lower = text.lower()
    if any(w in lower for w in ("checkup", "general", "routine", "follow")):
        return "general checkup"
    if any(w in lower for w in ("fever", "bukhar", "cold", "sardi", "cough", "khansi")):
        return "fever/cold"
    if any(w in lower for w in ("pain", "dard")):
        return "pain"
    if wants_appointment(text) and not extract_name(text):
        return "general checkup"
    return None


def _apply_period(hour: int, lower: str) -> int:
    if any(x in lower for x in ("sham", "shaam", "evening", "raat")) and hour < 12:
        return hour + 12
    if any(x in lower for x in ("dopahar", "afternoon")) and 1 <= hour <= 8:
        return hour + 12
    return hour


def extract_datetime(text: str, today: date | None = None) -> tuple[str | None, str | None]:
    """Return (YYYY-MM-DD, HH:MM) if found."""
    today = today or date.today()
    lower = text.lower()

    d: date | None = None
    if "aaj" in lower or "today" in lower:
        d = today
    elif "kal" in lower or "tomorrow" in lower:
        d = today + timedelta(days=1)
    elif "parso" in lower:
        d = today + timedelta(days=2)

    time_str: str | None = None
    m = re.search(r"\b(\d{1,2})\s*baje\b", lower)
    if m:
        hour = int(m.group(1))
        if 1 <= hour <= 12:
            hour = _apply_period(hour, lower)
            time_str = f"{hour:02d}:00"

    if not time_str:
        for word, num in HINDI_NUMBERS.items():
            if re.search(rf"\b{word}\s+baje\b", lower):
                hour = _apply_period(num, lower)
                time_str = f"{hour:02d}:00"
                break

    if not time_str:
        if "subah" in lower or "morning" in lower:
            time_str = "10:00"
        elif "dopahar" in lower or "afternoon" in lower:
            time_str = "13:00"
        elif any(x in lower for x in ("sham", "shaam", "evening")):
            time_str = "17:00"

    return (d.isoformat() if d else None, time_str)


def is_confirm_yes(text: str) -> bool:
    return _has_word(text, _CONFIRM_YES)


def is_confirm_no(text: str) -> bool:
    return _has_word(text, _CONFIRM_NO)


def parse_confirm(text: str) -> str | None:
    """Return 'yes', 'no', or None. Denials checked before affirmations."""
    if is_confirm_no(text):
        return "no"
    if is_confirm_yes(text):
        return "yes"
    return None
