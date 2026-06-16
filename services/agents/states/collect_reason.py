"""COLLECT_REASON state — understand why the patient is calling."""

from __future__ import annotations

import time

from langgraph.types import interrupt

from services.agents.llm_client import complete_json, load_prompt
from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id


async def collect_reason_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    clinic_name = clinic.name if clinic else "the clinic"
    doctor_name = clinic.doctor_name if clinic else "the doctor"
    patient_name = state.get("collected_name") or "aap"

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

    prompt_template = load_prompt("collect_reason_v1.txt")
    prompt = prompt_template.format(
        language=language,
        clinic_name=clinic_name,
        doctor_name=doctor_name,
        patient_name=patient_name,
        collected_info=collected_info or "name collected",
        transcript=state.get("last_user_input", ""),
    )

    result = await complete_json(prompt)
    response_text: str = result.get("response", "Kisi khaas reason se aa rahe hain ya general checkup?")
    extracted_reason: str | None = result.get("extracted_reason")
    confidence: float = float(result.get("confidence", 0))

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

    if extracted_reason and confidence >= 0.6:
        updates["collected_reason"] = extracted_reason
        updates["clarification_attempts"] = 0
    else:
        updates["clarification_attempts"] = state.get("clarification_attempts", 0) + 1

    return updates
