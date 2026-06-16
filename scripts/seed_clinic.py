#!/usr/bin/env python
"""Seed a demo clinic profile into the database.

Usage:
    python scripts/seed_clinic.py
    python scripts/seed_clinic.py --clinic-id custom_id --phone +919876543210
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db.database import init_db, upsert_clinic
from services.db.models import ClinicProfile

DEMO_CLINIC = ClinicProfile(
    clinic_id="demo_clinic_01",
    name="Dr. Sharma's General Clinic",
    doctor_name="Dr. Rahul Sharma",
    specialty="General Physician",
    phone_number="+917000000000",        # Replace with your Twilio number
    language_preference="hinglish",
    business_hours={
        "mon": "09:00-18:00",
        "tue": "09:00-18:00",
        "wed": "09:00-18:00",
        "thu": "09:00-18:00",
        "fri": "09:00-18:00",
        "sat": "09:00-13:00",
        "sun": "closed",
    },
    calcom_username="harshit-shah-g40wxg",
    calcom_event_type_id=6012529,
    emergency_number="+911800000000",
    booking_lead_time_hours=2,
    greeting_template=(
        "Namaste! Main Priya hoon, Dr. Sharma ki clinic se. "
        "Batayiye, aaj main aapki kaise help kar sakti hoon?"
    ),
)


async def seed(clinic_id: str | None = None, phone: str | None = None) -> None:
    await init_db()

    clinic = DEMO_CLINIC
    if clinic_id:
        clinic.clinic_id = clinic_id
    if phone:
        clinic.phone_number = phone

    await upsert_clinic(clinic)
    print(f"✓ Seeded clinic: {clinic.clinic_id}")
    print(f"  Name: {clinic.name}")
    print(f"  Phone: {clinic.phone_number}")
    print(f"  Cal.com: {clinic.calcom_username} (event_type={clinic.calcom_event_type_id})")
    print()
    print("Next steps:")
    print(f"  1. Set your Twilio number to {clinic.phone_number} in .env.local")
    print(f"  2. Update calcom_username and calcom_event_type_id to match your Cal.com account")
    print(f"  3. Run: make tunnel  (then paste the ngrok URL into Twilio console)")
    print(f"  4. Run: make run")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a demo clinic profile")
    parser.add_argument("--clinic-id", default=None)
    parser.add_argument("--phone", default=None, help="Twilio phone number for the clinic")
    args = parser.parse_args()
    asyncio.run(seed(args.clinic_id, args.phone))


if __name__ == "__main__":
    main()
