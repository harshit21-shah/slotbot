"""LangGraph tool wrappers for calendar operations (used in tool-calling nodes)."""

from __future__ import annotations

from langchain_core.tools import tool

from services.calendar.client import check_slot_available, create_booking, get_available_slots


@tool
async def tool_get_available_slots(
    calcom_username: str,
    calcom_event_type_id: int,
    date: str,
    time_range_start: str = "",
    time_range_end: str = "",
    requested_time: str = "",
) -> list[str]:
    """Get available appointment slots for a given date from Cal.com."""
    return await get_available_slots(
        calcom_username=calcom_username,
        calcom_event_type_id=calcom_event_type_id,
        date=date,
        time_range_start=time_range_start or None,
        time_range_end=time_range_end or None,
        requested_time=requested_time or None,
    )


@tool
async def tool_check_slot_available(
    calcom_username: str,
    calcom_event_type_id: int,
    date: str,
    time: str,
) -> bool:
    """Check if a specific slot is still available (race-condition guard)."""
    return await check_slot_available(
        calcom_username=calcom_username,
        calcom_event_type_id=calcom_event_type_id,
        date=date,
        time=time,
    )


@tool
async def tool_create_booking(
    calcom_username: str,
    calcom_event_type_id: int,
    name: str,
    phone: str,
    date: str,
    time: str,
    reason: str,
) -> str:
    """Create a Cal.com booking. Returns the booking ID."""
    return await create_booking(
        calcom_username=calcom_username,
        calcom_event_type_id=calcom_event_type_id,
        name=name,
        phone=phone,
        date=date,
        time=time,
        reason=reason,
    )
