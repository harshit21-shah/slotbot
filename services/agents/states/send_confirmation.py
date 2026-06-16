"""SEND_CONFIRMATION state — send SMS and verbally confirm booking."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from langgraph.types import interrupt

from services.agents.state_types import SlotBotState
from services.db.database import get_clinic_by_id
from services.sms.client import send_confirmation_sms

logger = logging.getLogger(__name__)

_CONFIRM_MSGS = {
    "hinglish": "Perfect! {name} ji, aapka appointment book ho gaya — {doctor} ke saath, {date} ko {time} baje. Aapko SMS aa jayega. Koi aur help chahiye?",
    "hindi": "Bahut acha! {name} ji, aapka appointment nishchit ho gaya — {doctor} ke saath, {date} ko {time} baje. SMS aa jayega. Kuch aur chahiye?",
    "english": "All set! {name}, your appointment with {doctor} is confirmed for {date} at {time}. You'll receive an SMS confirmation. Is there anything else I can help with?",
}


def _format_for_speech(slot_datetime: str) -> tuple[str, str]:
    """Return (date_human, time_human) suitable for TTS."""
    parts = slot_datetime.split()
    date_str = parts[0] if parts else ""
    time_str = parts[1] if len(parts) > 1 else ""
    try:
        if date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_human = dt.strftime("%A %d %B")
        else:
            date_human = "your chosen date"
        if time_str:
            t = datetime.strptime(time_str, "%H:%M")
            time_human = t.strftime("%I:%M %p").lstrip("0")
        else:
            time_human = "your chosen time"
    except ValueError:
        date_human, time_human = date_str, time_str
    return date_human, time_human


async def send_confirmation_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    doctor_name = clinic.doctor_name if clinic else "the doctor"
    clinic_name = clinic.name if clinic else "the clinic"
    clinic_phone = clinic.phone_number if clinic else ""

    patient_name = state.get("collected_name") or ("aap" if language != "english" else "you")
    slot_dt = state.get("confirmed_slot_datetime", "")
    date_human, time_human = _format_for_speech(slot_dt)

    # Verbal confirmation message
    template = _CONFIRM_MSGS.get(language, _CONFIRM_MSGS["hinglish"])
    spoken_confirmation = template.format(
        name=patient_name,
        doctor=doctor_name,
        date=date_human,
        time=time_human,
    )

    # Fire SMS async — does NOT block the hot path
    caller_phone = state.get("caller_phone", "")
    if caller_phone:
        asyncio.create_task(
            send_confirmation_sms(
                to_phone=caller_phone,
                patient_name=patient_name,
                doctor_name=doctor_name,
                clinic_name=clinic_name,
                clinic_phone=clinic_phone,
                slot_datetime=slot_dt,
                booking_id=state.get("booking_id"),
            )
        )

    next_input: str = interrupt(spoken_confirmation)

    return {
        "last_user_input": next_input,
        "agent_response": spoken_confirmation,
        "turn_count": state.get("turn_count", 0) + 1,
        "transcript": state.get("transcript", [])
        + [
            {"role": "agent", "text": spoken_confirmation, "ts": time.time()},
            {"role": "user", "text": next_input, "ts": time.time()},
        ],
    }
