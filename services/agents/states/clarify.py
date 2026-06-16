"""CLARIFY state — politely re-ask when STT confidence is low."""

from __future__ import annotations

import time

from langgraph.types import interrupt

from services.agents.state_types import SlotBotState

_CLARIFY_MSGS = {
    "hinglish": "Sorry, main clearly samajh nahi paya. Kya aap thoda aur clearly bol sakte hain?",
    "hindi": "Kshama karein, main samajh nahi paya. Kripya thoda spashtata se bolein?",
    "english": "Sorry, I didn't catch that clearly. Could you please repeat a bit more clearly?",
}

_ESCALATE_MSGS = {
    "hinglish": "Main samajh nahi paya. Aapko hamare staff se connect karta hoon. Ek moment please.",
    "hindi": "Mujhe samajh nahi aa raha. Main aapko staff se jodta hoon. Ek pal...",
    "english": "I'm having trouble understanding. Let me connect you with our staff. One moment please.",
}

_MAX_CLARIFICATIONS = 2


async def clarify_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    attempts = state.get("clarification_attempts", 0)

    if attempts >= _MAX_CLARIFICATIONS:
        # Escalate to human — this node sets needs_human and ends
        msg = _ESCALATE_MSGS.get(language, _ESCALATE_MSGS["hinglish"])
        return {
            "agent_response": msg,
            "needs_human": True,
            "call_ended": True,
            "transcript": state.get("transcript", [])
            + [{"role": "agent", "text": msg, "ts": time.time()}],
        }

    msg = _CLARIFY_MSGS.get(language, _CLARIFY_MSGS["hinglish"])
    next_input: str = interrupt(msg)

    return {
        "last_user_input": next_input,
        "agent_response": msg,
        "turn_count": state.get("turn_count", 0) + 1,
        "clarification_attempts": attempts + 1,
        "transcript": state.get("transcript", [])
        + [
            {"role": "agent", "text": msg, "ts": time.time()},
            {"role": "user", "text": next_input, "ts": time.time()},
        ],
    }
