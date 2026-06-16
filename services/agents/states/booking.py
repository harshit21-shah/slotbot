"""BOOKING state — create Cal.com booking with double-booking guard."""

from __future__ import annotations

import logging
import time

from services.agents.state_types import SlotBotState
from services.calendar.client import check_slot_available, create_booking
from services.db.database import get_clinic_by_id

logger = logging.getLogger(__name__)

_SLOT_TAKEN_MSGS = {
    "hinglish": "Oh! Abhi abhi yeh slot book ho gaya. Ek second, main doosre options dekhta hoon...",
    "hindi": "Maafi kijiye, yeh slot abhi book hua. Ek pal ruk...",
    "english": "Oh! That slot was just taken. One moment, let me find alternatives...",
}

_BOOKING_ERROR_MSGS = {
    "hinglish": "Sorry, booking mein kuch technical problem aa gayi. Main aapko staff se connect karta hoon.",
    "hindi": "Khed hai, booking mein takneeki samasya aayi. Main aapko staff se jodta hoon.",
    "english": "Sorry, there was a technical issue with the booking. Let me connect you with our staff.",
}


async def booking_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    """
    Race-condition-safe booking:
    1. Re-check availability immediately before booking.
    2. Create booking only if slot is still free.
    3. On conflict: surface available_slots for OFFER_ALTERNATIVES.
    """
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    if not clinic:
        logger.error("Clinic not found for booking: %s", clinic_id)
        return {"needs_human": True}

    confirmed_slot = state.get("confirmed_slot_datetime", "")
    if not confirmed_slot:
        logger.error("Booking node reached without confirmed_slot_datetime")
        return {"needs_human": True}

    # Parse date and time from confirmed_slot ("YYYY-MM-DD HH:MM")
    parts = confirmed_slot.split()
    slot_date = parts[0] if parts else ""
    slot_time = parts[1] if len(parts) > 1 else ""

    # ── Guard: re-check availability ──────────────────────────────────────────
    still_available = await check_slot_available(
        calcom_username=clinic.calcom_username,
        calcom_event_type_id=clinic.calcom_event_type_id,
        date=slot_date,
        time=slot_time,
    )

    if not still_available:
        logger.warning("Slot taken between CONFIRM and BOOKING: %s", confirmed_slot)
        from services.calendar.client import get_available_slots  # avoid circular

        fresh_slots = await get_available_slots(
            calcom_username=clinic.calcom_username,
            calcom_event_type_id=clinic.calcom_event_type_id,
            date=slot_date,
            duration_minutes=30,
        )
        return {
            "available_slots": fresh_slots,
            "confirmed_slot_datetime": None,
            "agent_response": _SLOT_TAKEN_MSGS.get(language, _SLOT_TAKEN_MSGS["hinglish"]),
            "transcript": state.get("transcript", [])
            + [{"role": "system", "text": "Slot taken — offering alternatives", "ts": time.time()}],
        }

    # ── Create booking ────────────────────────────────────────────────────────
    try:
        booking_id = await create_booking(
            calcom_username=clinic.calcom_username,
            calcom_event_type_id=clinic.calcom_event_type_id,
            name=state.get("collected_name") or "Patient",
            phone=state.get("caller_phone", ""),
            date=slot_date,
            time=slot_time,
            reason=state.get("collected_reason") or "Appointment",
            timezone="Asia/Kolkata",
        )
        logger.info("Booking created: %s for %s", booking_id, confirmed_slot)
        return {
            "booking_id": booking_id,
            "transcript": state.get("transcript", [])
            + [{"role": "system", "text": f"Booking confirmed: {booking_id}", "ts": time.time()}],
        }
    except Exception as exc:
        logger.exception("Booking API failed: %s", exc)
        return {
            "needs_human": True,
            "agent_response": _BOOKING_ERROR_MSGS.get(language, _BOOKING_ERROR_MSGS["hinglish"]),
        }
