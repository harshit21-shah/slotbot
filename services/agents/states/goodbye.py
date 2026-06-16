"""GOODBYE state — warm close, end the call."""

from __future__ import annotations

import time

from services.agents.state_types import SlotBotState

_GOODBYES = {
    "hinglish": "Shukriya {name} ji! Get well soon. Agar koi changes chahiye toh hume call karein. Alvida!",
    "hindi": "Dhanyavad {name} ji! Jaldi swasth hon. Koi parivartan chahiye toh hume call karein. Alvida!",
    "english": "Thank you, {name}! Get well soon. Call us if you need to make any changes. Goodbye!",
}


async def goodbye_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    patient_name = state.get("collected_name") or ("aap" if language != "english" else "")

    template = _GOODBYES.get(language, _GOODBYES["hinglish"])
    farewell = template.format(name=patient_name).strip()

    return {
        "agent_response": farewell,
        "call_ended": True,
        "turn_count": state.get("turn_count", 0) + 1,
        "transcript": state.get("transcript", [])
        + [{"role": "agent", "text": farewell, "ts": time.time()}],
    }
