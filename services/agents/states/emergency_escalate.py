"""EMERGENCY_ESCALATE — pre-recorded response, no LLM, instant transfer."""

from __future__ import annotations

import time

from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id

_EMERGENCY_MSGS = {
    "hinglish": (
        "Yeh emergency lag rahi hai. Kripya abhi turant {emergency_number} pe call karein. "
        "Hum aapki madad karna chahte hain — please immediately call karein."
    ),
    "hindi": (
        "Yeh ek aapaat sthiti hai. Kripya abhi {emergency_number} par call karein. "
        "Hum aapki sahayata karna chahte hain."
    ),
    "english": (
        "This sounds like an emergency. Please call {emergency_number} immediately. "
        "We want to help — please call right away."
    ),
}


async def emergency_escalate_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    """
    No LLM call — uses a pre-composed message.
    Always ends the call (call_ended=True).
    """
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    emergency_number = clinic.emergency_number if clinic else "your local emergency number"

    template = _EMERGENCY_MSGS.get(language, _EMERGENCY_MSGS["hinglish"])
    msg = template.format(emergency_number=emergency_number)

    return {
        "agent_response": msg,
        "is_emergency": True,
        "call_ended": True,
        "transcript": state.get("transcript", [])
        + [{"role": "agent", "text": msg, "ts": time.time()}],
    }
