#!/usr/bin/env python
"""Simulate the autonomous agent without Twilio."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agents.agentic_receptionist import AgentContext, run_agent_turn
from services.agents.emergency import is_emergency
from services.db.database import get_clinic_by_id, init_db, upsert_clinic
from scripts.seed_clinic import DEMO_CLINIC

SCENARIOS: dict[str, list[str]] = {
    "natural_hinglish": [
        "Hi, mujhe Dr. Sharma se milna hai",
        "Main Rahul hoon, kal subah 10 baje chalega? Bukhar hai thoda",
        "Haan bilkul, book kar do",
    ],
    "all_at_once": [
        "Namaste, main Priya Sharma hoon, general checkup ke liye parso dopahar 3 baje appointment chahiye",
        "Haan confirm karo",
    ],
}


async def run_scenario(name: str, utterances: list[str]) -> None:
    await init_db()
    await upsert_clinic(DEMO_CLINIC)
    clinic = await get_clinic_by_id("demo_clinic_01")
    assert clinic

    ctx = AgentContext(
        call_sid="SIM",
        clinic=clinic,
        patient_phone="+918275566293",
        language="hinglish",
    )

    print(f"\n=== Agent simulation: {name} ===\n")
    print(f"🤖 Priya: Namaste! Batayiye, kaise help kar sakti hoon?\n")

    for text in utterances:
        print(f"👤 Caller: {text}")
        if is_emergency(text):
            print("🚨 Emergency detected — would escalate\n")
            break
        result = await run_agent_turn(ctx, text)
        print(f"🤖 Priya: {result.response}\n")
        if result.call_ended:
            print(f"✓ Call ended. Booking: {result.booking_id or 'none'}\n")
            break


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="natural_hinglish", choices=list(SCENARIOS))
    args = parser.parse_args()
    asyncio.run(run_scenario(args.scenario, SCENARIOS[args.scenario]))


if __name__ == "__main__":
    main()
