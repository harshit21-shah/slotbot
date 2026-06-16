"""COLLECT_NAME state — extract patient name, ask if not provided."""

from __future__ import annotations

import time

from langgraph.types import interrupt

from services.agents.llm_client import complete_json, load_prompt
from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id


async def collect_name_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    clinic_name = clinic.name if clinic else "the clinic"
    doctor_name = clinic.doctor_name if clinic else "the doctor"

    collected_info = {
        k: v
        for k, v in {
            "name": state.get("collected_name"),
            "reason": state.get("collected_reason"),
            "date": state.get("collected_date"),
            "time": state.get("collected_time"),
        }.items()
        if v is not None
    }

    prompt_template = load_prompt("collect_name_v1.txt")
    prompt = prompt_template.format(
        language=language,
        clinic_name=clinic_name,
        doctor_name=doctor_name,
        collected_info=collected_info or "nothing yet",
        transcript=state.get("last_user_input", ""),
    )

    result = await complete_json(prompt)
    response_text: str = result.get("response", "Aapka naam kya hai?")
    extracted_name: str | None = result.get("extracted_name")
    confidence: float = float(result.get("confidence", 0))

    # Send response, wait for next utterance
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

    if extracted_name and confidence >= 0.7:
        updates["collected_name"] = extracted_name
        updates["clarification_attempts"] = 0  # reset on success
    else:
        updates["clarification_attempts"] = state.get("clarification_attempts", 0) + 1

    return updates
