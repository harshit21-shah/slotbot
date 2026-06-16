"""COLLECT_DATETIME state — parse preferred date/time from natural language."""

from __future__ import annotations

import time
from datetime import date

from langgraph.types import interrupt

from services.agents.llm_client import complete_json, load_prompt
from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id


async def collect_datetime_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    patient_name = state.get("collected_name") or ("aap" if language != "english" else "you")
    business_hours = clinic.business_hours if clinic else {"mon-sat": "09:00-18:00"}

    prompt_template = load_prompt("collect_datetime_v1.txt")
    prompt = prompt_template.format(
        today=date.today().isoformat(),
        timezone="Asia/Kolkata",
        business_hours=business_hours,
        patient_name=patient_name,
        transcript=state.get("last_user_input", ""),
    )

    result = await complete_json(prompt)
    response_text: str = result.get("response", "Aap kab aana chahte hain?")
    extracted_date: str | None = result.get("extracted_date")
    extracted_time: str | None = result.get("extracted_time")
    time_is_flexible: bool = bool(result.get("time_is_flexible", False))
    time_range_start: str | None = result.get("time_range_start")
    time_range_end: str | None = result.get("time_range_end")
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

    # Only store if we got a useful date/time extraction
    date_or_time_found = (extracted_date or extracted_time or time_is_flexible) and confidence >= 0.6
    if date_or_time_found:
        if extracted_date:
            updates["collected_date"] = extracted_date
        if extracted_time:
            updates["collected_time"] = extracted_time
        updates["time_is_flexible"] = time_is_flexible
        if time_range_start:
            updates["time_range_start"] = time_range_start
        if time_range_end:
            updates["time_range_end"] = time_range_end
        updates["clarification_attempts"] = 0
    else:
        updates["clarification_attempts"] = state.get("clarification_attempts", 0) + 1

    return updates
