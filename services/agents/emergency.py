"""Fast regex-based emergency detection — runs before any LLM call."""

from __future__ import annotations

import re

_EMERGENCY_PATTERNS = [
    re.compile(r"\b(emergency|urgent)\b", re.IGNORECASE),
    re.compile(r"\b(chest pain|breath\w*\s+trouble|breathe\s+nahi|saans\s+nahi|unconscious|fainted)\b", re.IGNORECASE),
    re.compile(r"\bbreathe\s+karne\s+mein\s+problem\b", re.IGNORECASE),
    re.compile(r"\b(accident|bleeding|seizure|fit|stroke)\b", re.IGNORECASE),
    re.compile(r"\bbahut\s+(dard|pain|problem|takleef)\b", re.IGNORECASE),
    re.compile(r"\b(zyada|extreme|severe)\s+.{0,20}(dard|pain)\b", re.IGNORECASE),
    re.compile(r"\b(help|madad)\s+karo\b", re.IGNORECASE),
]

_EMERGENCY_RESPONSES = {
    "hinglish": (
        "Yeh emergency lag rahi hai. Kripya abhi turant emergency number pe call karein. "
        "Aapki madad karna chahte hain — please immediately call karein."
    ),
    "hindi": (
        "Yeh ek emergency hai. Kripya abhi emergency number par call karein. "
        "Hum aapki sahayata karna chahte hain."
    ),
    "english": (
        "This sounds like an emergency. Please call the emergency number immediately. "
        "We want to help you — please call right away."
    ),
}


def is_emergency(transcript: str) -> bool:
    """Return True if any emergency pattern matches. Runs in < 1ms."""
    return any(p.search(transcript) for p in _EMERGENCY_PATTERNS)


def emergency_response(language: str, emergency_number: str) -> str:
    base = _EMERGENCY_RESPONSES.get(language, _EMERGENCY_RESPONSES["hinglish"])
    return f"{base} Emergency number: {emergency_number}"
