#!/usr/bin/env python
"""Quick live integration check for SlotBot services."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from services.agents.llm_client import complete_json
from services.calendar.client import get_available_slots
from services.config import settings
from services.db.database import get_clinic_by_phone, init_db
from services.tts.sarvam_client import text_to_wav_file


async def main() -> int:
    failures = 0
    print("=== SlotBot Live Health Check ===\n")

    # Sarvam TTS
    try:
        wav = await text_to_wav_file("Namaste, test.")
        print(f"OK   Sarvam TTS ({len(wav)} bytes)")
    except Exception as exc:
        failures += 1
        print(f"FAIL Sarvam TTS: {exc}")

    # Groq LLM
    try:
        result = await asyncio.wait_for(
            complete_json('Reply with JSON only: {"response": "ok", "confidence": 1}'),
            timeout=15,
        )
        print(f"OK   Groq LLM (response={result.get('response')!r})")
    except Exception as exc:
        failures += 1
        print(f"FAIL Groq LLM: {exc}")

    # Cal.com
    await init_db()
    clinic = await get_clinic_by_phone(settings.twilio_phone_number)
    if not clinic:
        print("WARN Cal.com: no clinic seeded for TWILIO_PHONE_NUMBER")
    else:
        try:
            slots = await get_available_slots(
                calcom_username=clinic.calcom_username,
                calcom_event_type_id=clinic.calcom_event_type_id,
                date="2026-06-22",
            )
            if slots:
                print(f"OK   Cal.com slots ({len(slots)} on 2026-06-20, e.g. {slots[0]})")
            else:
                failures += 1
                print("FAIL Cal.com slots: empty (API error or no availability)")
        except Exception as exc:
            failures += 1
            print(f"FAIL Cal.com slots: {exc}")

    # Gather voice flow
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            base = {
                "From": "+918275566293",
                "To": settings.twilio_phone_number,
                "CallSid": "CA_health_check",
                "Direction": "outbound-api",
            }
            r = await client.post("http://127.0.0.1:8888/voice", data=base)
            if r.status_code != 200 or "<Play>" not in r.text:
                raise RuntimeError(f"/voice bad: {r.status_code}, Play missing")

            for speech in ("main Rahul hoon", "general checkup", "kal subah 10 baje"):
                tr = await client.post(
                    "http://127.0.0.1:8888/voice/turn",
                    data={**base, "SpeechResult": speech},
                )
                if tr.status_code != 200 or "<Play>" not in tr.text:
                    raise RuntimeError(f"turn failed for {speech!r}: {tr.status_code}")

            print("OK   Gather voice flow (greeting + 3 turns, Sarvam Play URLs)")
    except Exception as exc:
        failures += 1
        print(f"FAIL Gather flow: {exc}")

    print(f"\n=== Result: {failures} failure(s) ===")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
