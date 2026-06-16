"""CHECK_AVAILABILITY state — query Cal.com for free slots."""

from __future__ import annotations

import logging
import time

from services.agents.state_types import SlotBotState
from services.calendar.client import get_available_slots
from services.db.database import get_clinic_by_id

logger = logging.getLogger(__name__)

_NO_SLOT_MSGS = {
    "hinglish": "Aapne jo time maanga tha wo available nahi hai. Main alternatives check karta hoon...",
    "hindi": "Jo samay aapne maanga wo uplabdh nahi hai. Dusre vikalp dekhte hain...",
    "english": "The slot you requested isn't available. Let me check alternatives...",
}


async def check_availability_node(state: SlotBotState) -> dict:  # type: ignore[type-arg]
    """
    Calls Cal.com to fetch available slots around the requested date/time.
    This node does NOT interrupt — it's a tool-call node.
    The result (available_slots) is used by the routing function.
    """
    language = state.get("language", "hinglish")
    clinic_id = state["clinic_id"]

    clinic = await get_clinic_by_id(clinic_id)
    if not clinic:
        logger.error("Clinic not found: %s", clinic_id)
        return {"available_slots": [], "needs_human": True}

    requested_date = state.get("collected_date")
    requested_time = state.get("collected_time")
    time_range_start = state.get("time_range_start")
    time_range_end = state.get("time_range_end")
    time_is_flexible = state.get("time_is_flexible", False)

    try:
        slots = await get_available_slots(
            calcom_username=clinic.calcom_username,
            calcom_event_type_id=clinic.calcom_event_type_id,
            date=requested_date or "",
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            requested_time=requested_time,
            duration_minutes=30,
        )
    except Exception as exc:
        logger.exception("Cal.com availability check failed: %s", exc)
        slots = []

    return {
        "available_slots": slots,
        "transcript": state.get("transcript", [])
        + (
            [{"role": "system", "text": f"Checked availability: {len(slots)} slots found", "ts": time.time()}]
            if not slots
            else []
        ),
    }
