"""Cal.com API v2 client — availability checks and booking creation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from services.config import settings

logger = logging.getLogger(__name__)

_V2_BASE = "https://api.cal.com/v2"
_SLOTS_VERSION = "2024-09-04"
_BOOKINGS_VERSION = "2024-08-13"


def _auth_headers(api_version: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.calcom_api_key}",
        "Content-Type": "application/json",
        "cal-api-version": api_version,
    }


async def get_available_slots(
    *,
    calcom_username: str,
    calcom_event_type_id: int,
    date: str,
    duration_minutes: int = 30,
    time_range_start: str | None = None,
    time_range_end: str | None = None,
    requested_time: str | None = None,
    timezone: str = "Asia/Kolkata",
) -> list[str]:
    """Return available local time strings (HH:MM) for the given date."""
    if not date or not settings.calcom_api_key:
        return []

    params: dict[str, Any] = {
        "eventTypeId": calcom_event_type_id,
        "start": date,
        "end": date,
        "timeZone": timezone,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{_V2_BASE}/slots",
                params=params,
                headers=_auth_headers(_SLOTS_VERSION),
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Cal.com slots HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
        return []
    except Exception as exc:
        logger.exception("Cal.com slots request failed: %s", exc)
        return []

    raw_slots: list[dict[str, Any]] = data.get("data", {}).get(date, [])
    all_times: list[str] = []
    tz = ZoneInfo(timezone)

    for slot in raw_slots:
        raw_start = slot.get("start", "")
        if not raw_start:
            continue
        try:
            dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            local = dt.astimezone(tz)
            all_times.append(local.strftime("%H:%M"))
        except ValueError:
            continue

    if time_range_start or time_range_end:
        def in_range(t: str) -> bool:
            if time_range_start and t < time_range_start:
                return False
            if time_range_end and t > time_range_end:
                return False
            return True

        all_times = [t for t in all_times if in_range(t)]

    if requested_time and requested_time in all_times:
        idx = all_times.index(requested_time)
        all_times = all_times[max(0, idx - 1) : idx + 3]

    return all_times[:5]


async def check_slot_available(
    *,
    calcom_username: str,
    calcom_event_type_id: int,
    date: str,
    time: str,
    timezone: str = "Asia/Kolkata",
) -> bool:
    """Re-check a specific slot immediately before booking."""
    slots = await get_available_slots(
        calcom_username=calcom_username,
        calcom_event_type_id=calcom_event_type_id,
        date=date,
        requested_time=time,
        timezone=timezone,
    )
    return time in slots


def local_slot_to_utc_iso(date: str, time: str, timezone: str = "Asia/Kolkata") -> str:
    """Convert local clinic date/time to UTC ISO string for Cal.com."""
    local_dt = datetime.strptime(f"{date}T{time}", "%Y-%m-%dT%H:%M")
    local_dt = local_dt.replace(tzinfo=ZoneInfo(timezone))
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_booking_id(data: dict[str, Any]) -> str:
    """Extract booking uid from Cal.com v1/v2 response shapes."""
    inner = data.get("data", data)
    if isinstance(inner, dict):
        booking = inner.get("booking", inner)
        if isinstance(booking, dict):
            return str(booking.get("uid") or booking.get("id") or "unknown")
    booking = data.get("booking")
    if isinstance(booking, dict):
        return str(booking.get("uid") or booking.get("id") or "unknown")
    return str(data.get("uid") or data.get("id") or "unknown")


async def create_booking(
    *,
    calcom_username: str,
    calcom_event_type_id: int,
    name: str,
    phone: str,
    date: str,
    time: str,
    reason: str,
    timezone: str = "Asia/Kolkata",
) -> str:
    """Create a Cal.com v2 booking. Returns the booking uid."""
    start_time_iso = local_slot_to_utc_iso(date, time, timezone)

    payload = {
        "start": start_time_iso,
        "eventTypeId": calcom_event_type_id,
        "attendee": {
            "name": name,
            "email": f"{phone.replace('+', '')}@slotbot.placeholder",
            "timeZone": timezone,
        },
        "bookingFieldsResponses": {
            "notes": reason or "Appointment via SlotBot",
        },
        "metadata": {"source": "slotbot", "phone": phone},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{_V2_BASE}/bookings",
            json=payload,
            headers=_auth_headers(_BOOKINGS_VERSION),
        )
        response.raise_for_status()
        data = response.json()

    booking_id = parse_booking_id(data)
    logger.info("Cal.com booking created: id=%s date=%s time=%s", booking_id, date, time)
    return booking_id
