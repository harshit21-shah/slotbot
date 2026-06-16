"""HUMAN_ESCALATE — transfer to clinic staff after repeated failures."""

from __future__ import annotations

import time

from services.agents.state_types import SlotBotState

_ESCALATE_MSGS = {
    "hinglish": (
        "Main aapki puri madad nahi kar paya. Aapko abhi hamare staff se connect kar raha hoon. "
        "Ek moment please. Hum aapki help karenge."
    ),
    "hindi": (
        "Main aapki sahayata karne mein asmarth raha. Aapko hamari team se jod raha hoon. "
        "Ek pal ruk..."
    ),
    "english": (
        "I wasn't able to fully assist you. I'm connecting you with our staff now. "
        "One moment please."
    ),
}


async def human_escalate_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    msg = _ESCALATE_MSGS.get(language, _ESCALATE_MSGS["hinglish"])

    return {
        "agent_response": msg,
        "needs_human": True,
        "call_ended": True,
        "transcript": state.get("transcript", [])
        + [{"role": "agent", "text": msg, "ts": time.time()}],
    }
