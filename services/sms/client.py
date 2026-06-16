"""Twilio SMS confirmation sender."""

from __future__ import annotations

import logging
from datetime import datetime

from twilio.rest import Client

from services.config import settings

logger = logging.getLogger(__name__)

_SMS_TEMPLATE = """\
Appointment confirmed ✓
{doctor_name}
{date_human}, {time_human}
{clinic_name}

Reply CANCEL to cancel.
Queries? {clinic_phone}
"""


def _format_slot(slot_datetime: str) -> tuple[str, str]:
    parts = slot_datetime.split()
    date_str = parts[0] if parts else ""
    time_str = parts[1] if len(parts) > 1 else ""
    try:
        if date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_human = dt.strftime("%a %d %b")   # "Mon 16 Jun"
        else:
            date_human = date_str
        if time_str:
            t = datetime.strptime(time_str, "%H:%M")
            time_human = t.strftime("%I:%M %p").lstrip("0")
        else:
            time_human = time_str
    except ValueError:
        date_human, time_human = date_str, time_str
    return date_human, time_human


async def send_confirmation_sms(
    *,
    to_phone: str,
    patient_name: str,
    doctor_name: str,
    clinic_name: str,
    clinic_phone: str,
    slot_datetime: str,
    booking_id: str | None = None,
) -> None:
    """
    Send SMS confirmation via Twilio.
    Called as asyncio.create_task() — not on the hot path.
    """
    date_human, time_human = _format_slot(slot_datetime)
    body = _SMS_TEMPLATE.format(
        doctor_name=doctor_name,
        date_human=date_human,
        time_human=time_human,
        clinic_name=clinic_name,
        clinic_phone=clinic_phone,
    ).strip()

    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=settings.twilio_phone_number,
            to=to_phone,
        )
        logger.info(
            "SMS sent to %s: sid=%s booking=%s",
            to_phone[-4:].rjust(len(to_phone), "*"),
            message.sid,
            booking_id,
        )
    except Exception as exc:
        logger.error("SMS send failed to %s: %s", to_phone[-4:].rjust(4, "*"), exc)
