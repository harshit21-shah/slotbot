"""GREETING state — first turn of every call. No LLM needed; uses template."""

from __future__ import annotations

import time

from langgraph.types import interrupt

from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id

_GREETINGS = {
    "hinglish": "Namaste! {clinic_name} mein aapka swagat hai. Main aapki virtual receptionist hoon. Aaj main aapki kaise help kar sakti hoon?",
    "hindi": "Namaste! {clinic_name} mein aapka swagat hai. Main aapki virtual receptionist hoon. Aaj main aapki kaise sahayata kar sakti hoon?",
    "english": "Hello! Thank you for calling {clinic_name}. I'm the virtual receptionist. How can I help you today?",
}


async def greeting_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    clinic_name = clinic.name if clinic else "the clinic"

    # Use custom greeting if set, otherwise use template
    if clinic and clinic.greeting_template:
        greeting_text = clinic.greeting_template
    else:
        template = _GREETINGS.get(language, _GREETINGS["hinglish"])
        greeting_text = template.format(clinic_name=clinic_name)

    # Send greeting, wait for first utterance
    first_utterance: str = interrupt(greeting_text)

    return {
        "last_user_input": first_utterance,
        "agent_response": greeting_text,
        "turn_count": 1,
        "transcript": [
            {"role": "agent", "text": greeting_text, "ts": time.time()},
            {"role": "user", "text": first_utterance, "ts": time.time()},
        ],
    }
