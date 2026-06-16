"""LangGraph tool wrapper for SMS confirmation."""

from __future__ import annotations

from langchain_core.tools import tool

from services.sms.client import send_confirmation_sms


@tool
async def tool_send_confirmation_sms(
    to_phone: str,
    patient_name: str,
    doctor_name: str,
    clinic_name: str,
    clinic_phone: str,
    slot_datetime: str,
    booking_id: str = "",
) -> str:
    """Send an SMS appointment confirmation to the patient."""
    await send_confirmation_sms(
        to_phone=to_phone,
        patient_name=patient_name,
        doctor_name=doctor_name,
        clinic_name=clinic_name,
        clinic_phone=clinic_phone,
        slot_datetime=slot_datetime,
        booking_id=booking_id or None,
    )
    return "SMS sent"
