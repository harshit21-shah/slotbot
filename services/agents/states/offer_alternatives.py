"""OFFER_ALTERNATIVES state — present alternative slots when requested one is taken."""

from __future__ import annotations

import time
from datetime import datetime

from langgraph.types import interrupt

from services.agents.llm_client import complete_json, load_prompt
from services.agents.state_types import SlotBotState


def _slot_to_human(slot_iso: str, language: str) -> str:
    """Convert 'YYYY-MM-DDTHH:MM:SS' or 'HH:MM' to human-readable."""
    try:
        if "T" in slot_iso:
            dt = datetime.fromisoformat(slot_iso.replace("Z", "+00:00"))
            return dt.strftime("%I:%M %p").lstrip("0")
        return slot_iso
    except ValueError:
        return slot_iso


async def offer_alternatives_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    patient_name = state.get("collected_name") or ("aap" if language != "english" else "you")
    available_slots = state.get("available_slots", [])

    slot_display = ", ".join(_slot_to_human(s, language) for s in available_slots[:3])
    requested = state.get("collected_time") or state.get("collected_date") or "your preferred time"

    prompt_template = load_prompt("offer_alternatives_v1.txt")
    prompt = prompt_template.format(
        language=language,
        patient_name=patient_name,
        requested_slot=requested,
        available_slots=slot_display,
        transcript=state.get("last_user_input", ""),
    )

    result = await complete_json(prompt)
    response_text: str = result.get("response", "Kaunsa slot prefer karenge?")
    chosen_slot: str | None = result.get("chosen_slot")
    wants_new_time: bool = bool(result.get("wants_new_time", False))

    next_input: str = interrupt(response_text)

    updates: dict = {  # type: ignore[type-arg]
        "last_user_input": next_input,
        "agent_response": response_text,
        "turn_count": state.get("turn_count", 0) + 1,
        "transcript": state.get("transcript", [])
        + [
            {"role": "agent", "text": response_text, "ts": time.time()},
            {"role": "user", "text": next_input, "ts": time.time()},
        ],
    }

    if wants_new_time:
        # Reset collected datetime so patient can provide a new one
        updates["collected_date"] = None
        updates["collected_time"] = None
        updates["time_is_flexible"] = False

    if chosen_slot and available_slots:
        # Find the full ISO slot string that matches the chosen time
        for s in available_slots:
            if chosen_slot in s:
                date_part = state.get("collected_date", "")
                updates["confirmed_slot_datetime"] = f"{date_part} {chosen_slot}".strip()
                break

    return updates
