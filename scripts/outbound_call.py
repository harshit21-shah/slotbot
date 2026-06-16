#!/usr/bin/env python
"""Place an outbound Twilio call — inline TwiML so the call never waits on /voice."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from twilio.rest import Client

from services.config import settings
from services.db.database import get_clinic_by_phone, init_db


def normalize_phone(raw: str) -> str:
    digits = "".join(c for c in raw if c.isdigit())
    if raw.strip().startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_STT_HINTS = (
    "appointment, naam, kal, aaj, parso, subah, dopahar, sham, baje, "
    "haan, nahi, doctor, checkup, fever, dard, book, slot"
)


async def _get_greeting() -> str:
    import asyncio

    await init_db()
    clinic = None
    if settings.twilio_phone_number:
        clinic = await get_clinic_by_phone(settings.twilio_phone_number)
    if clinic and clinic.greeting_template:
        return clinic.greeting_template
    return "Namaste! Main Priya hoon. Batayiye, main aapki kaise help kar sakti hoon?"


def build_inline_twiml(base_url: str, greeting: str) -> str:
    """Instant TwiML — Twilio plays greeting without fetching /voice first."""
    action = f"{base_url.rstrip('/')}/voice/turn"
    safe = _xml_escape(greeting[:400])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{action}" method="POST" speechTimeout="auto" timeout="15" language="hi-IN" hints="{_STT_HINTS}">
    <Say language="en-IN" voice="Polly.Aditi">{safe}</Say>
  </Gather>
  <Say language="en-IN" voice="Polly.Aditi">Sorry, sunai nahi diya. Phir call kijiye.</Say>
</Response>"""


def verify_tunnel(base_url: str) -> None:
    """Fail fast if Twilio would get 502 from a dead tunnel."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/health", timeout=12.0, follow_redirects=True)
        r.raise_for_status()
    except Exception as exc:
        print(f"ERROR: Tunnel not reachable at {base_url}")
        print(f"  {exc}")
        print()
        print("Fix:")
        print("  1. python scripts/start_dev.py")
        print("  2. Or run cloudflared + server, update APP_BASE_URL, pass --base-url")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Call a phone number via SlotBot + Twilio")
    parser.add_argument("phone", help="Patient phone, e.g. 918275566293")
    parser.add_argument(
        "--base-url",
        default=settings.app_base_url,
        help="Public HTTPS base URL (must match running tunnel)",
    )
    args = parser.parse_args()

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        print("ERROR: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN required in .env.local")
        sys.exit(1)

    if not settings.twilio_phone_number:
        print("ERROR: TWILIO_PHONE_NUMBER required in .env.local")
        sys.exit(1)

    base_url = args.base_url.rstrip("/")
    if not base_url.startswith("https://") or "your-app.onrender.com" in base_url:
        print("ERROR: Set a real public HTTPS URL via --base-url or APP_BASE_URL")
        sys.exit(1)

    verify_tunnel(base_url)

    import asyncio

    to_phone = normalize_phone(args.phone)
    greeting = asyncio.run(_get_greeting())
    twiml = build_inline_twiml(base_url, greeting)
    turn_url = f"{base_url}/voice/turn"

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    call = client.calls.create(
        to=to_phone,
        from_=settings.twilio_phone_number,
        twiml=twiml,
    )

    print(f"Calling {to_phone} from {settings.twilio_phone_number}")
    print(f"Turn webhook: {turn_url}")
    print(f"Tunnel: {base_url} (verified OK)")
    print(f"Call SID: {call.sid}")
    print(f"Status: {call.status}")
    print("Answer your phone. Speak after the greeting.")


if __name__ == "__main__":
    main()
