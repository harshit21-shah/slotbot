"""Rule-based replies when LLM is unavailable — keeps calls human, not robotic."""

from __future__ import annotations

import re


_HEAR_ME = re.compile(
    r"(sun\s*pa\s*rahe|sun\s*rahi|sun\s*raha|can you hear|hear me|"
    r"सुन\s*पा\s*रहे|सुन\s*रहे|सुन\s*रही|सुन\s*रह)",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^(hello|hi|hey|namaste|namaskar|haan|ji|"
    r"हेलो|हैलो|नमस्ते|नमस्कार|हाँ|जी)[\s!.?]*$",
    re.IGNORECASE,
)
_NAME = re.compile(
    r"(?:mera|my)\s*(?:naam|name)\s*(?:hai\s*)?(.+?)(?:\s+hai)?$|"
    r"मेरा\s*नाम\s*(.+?)\s*है",
    re.IGNORECASE,
)
_APPOINTMENT = re.compile(
    r"(appointment|slot|book|booking|doctor|checkup|"
    r"अपॉइंटमेंट|डॉक्टर|बुक)",
    re.IGNORECASE,
)


def offline_reply(user_message: str, *, clinic_name: str = "clinic") -> str | None:
    """Return a friendly Hinglish reply without LLM, or None if no match."""
    text = (user_message or "").strip()
    if not text:
        return "Ji, main sun rahi hoon. Aaram se boliye — kaise help kar sakti hoon?"

    if _HEAR_ME.search(text):
        return (
            "Haan ji, bilkul sun rahi hoon! Aapki awaaz clear aa rahi hai. "
            "Batayiye, appointment book karni hai ya kuch aur?"
        )

    if _GREETING.match(text):
        return (
            f"Namaste ji! Main Priya hoon, {clinic_name} se. "
            "Batayiye, main aapki kaise help kar sakti hoon?"
        )

    name_match = _NAME.search(text)
    if name_match:
        name = (name_match.group(1) or "").strip(" .!?")
        if name:
            return (
                f"Achha ji, {name}. Aapko kya problem hai — "
                "fever, dard, ya general checkup?"
            )

    if _APPOINTMENT.search(text):
        return (
            "Ji bilkul, appointment book kar deti hoon. "
            "Pehle apna naam aur problem batayiye, phir date aur time?"
        )

    return (
        "Ji, main samajh gayi. Thoda detail mein batayiye — "
        "naam, problem, aur kab aana chahenge?"
    )
