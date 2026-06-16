"""CONFIRM_SLOT state — verbal confirmation before booking."""

from __future__ import annotations

import time
from datetime import datetime

from langgraph.types import interrupt

from services.agents.llm_client import complete_json, load_prompt
from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id


def _format_slot_human(date_str: str | None, time_str: str | None) -> tuple[str, str]:
    date_human = date_str or "your chosen date"
    time_human = time_str or "your chosen time"
    try:
        if date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_human = dt.strftime("%A, %d %B")  # "Monday, 16 June"
        if time_str:
            t = datetime.strptime(time_str, "%H:%M")
            time_human = t.strftime("%I:%M %p").lstrip("0")  # "10:00 AM"
    except ValueError:
        pass
    return date_human, time_human


async def confirm_slot_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    doctor_name = clinic.doctor_name if clinic else "the doctor"
    patient_name = state.get("collected_name") or ("aap" if language != "english" else "you")

    date_human, time_human = _format_slot_human(
        state.get("collected_date"),
        state.get("collected_time"),
    )

    prompt_template = load_prompt("confirm_slot_v1.txt")
    prompt = prompt_template.format(
        language=language,
        doctor_name=doctor_name,
        slot_date_human=date_human,
        slot_time_human=time_human,
        patient_name=patient_name,
        transcript=state.get("last_user_input", ""),
    )

    result = await complete_json(prompt)
    response_text: str = result.get("response", "Kya main book kar doon?")
    confirmed: bool | None = result.get("confirmed")  # True / False / None

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

    if confirmed is True:
        # Build confirmed_slot_datetime
        date_part = state.get("collected_date", "")
        time_part = state.get("collected_time", "")
        updates["confirmed_slot_datetime"] = f"{date_part} {time_part}".strip()
    elif confirmed is False:
        # Patient wants to change — reset date/time
        updates["collected_date"] = None
        updates["collected_time"] = None
        updates["time_is_flexible"] = False
        updates["confirmed_slot_datetime"] = None
    # confirmed is None → stay in confirm_slot (re-ask)

    return updates
