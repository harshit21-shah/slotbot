#!/usr/bin/env python
"""
Simulate a complete call through the LangGraph state machine without Twilio.

Usage:
    python scripts/simulate_call.py                  # interactive mode
    python scripts/simulate_call.py --transcript tests/eval/transcripts/sample_booking.json
    python scripts/simulate_call.py --scenario booking_hinglish
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.types import Command

from services.agents.emergency import is_emergency
from services.agents.graph import conversation_graph
from services.agents.state_types import initial_state
from services.db.database import init_db, upsert_clinic
from scripts.seed_clinic import DEMO_CLINIC

# ── Built-in scenarios ────────────────────────────────────────────────────────

SCENARIOS: dict[str, list[str]] = {
    "booking_hinglish": [
        "Mujhe appointment chahiye",
        "Main Priya hoon",
        "General checkup",
        "Kal subah 10 baje",
        "Haan, sahi hai",
    ],
    "booking_english": [
        "I'd like to book an appointment",
        "My name is Ankit Singh",
        "I have a fever",
        "Tomorrow morning around 11",
        "Yes, that's correct",
    ],
    "emergency": [
        "Bahut chest pain ho raha hai emergency hai",
    ],
    "barge_in_recovery": [
        "Appointment book karna hai, mera naam Rahul hai, kal dopahar",
        "Haan theek hai",
    ],
}


async def run_simulated_call(
    utterances: list[str],
    clinic_id: str = "demo_clinic_01",
    language: str = "hinglish",
    verbose: bool = True,
) -> dict:  # type: ignore[type-arg]
    """
    Drive the graph with a list of pre-scripted utterances.
    Returns the final state dict.
    """
    call_sid = f"SIM_{int(time.time())}"
    config = {"configurable": {"thread_id": call_sid}}

    init = initial_state(
        call_sid=call_sid,
        caller_phone="+910000000000",
        clinic_id=clinic_id,
        language=language,
    )

    def _print(role: str, text: str) -> None:
        if verbose:
            prefix = "🤖 Agent" if role == "agent" else "👤 Caller"
            print(f"\n{prefix}: {text}")

    # Start graph (GREETING → first interrupt)
    t0 = time.perf_counter()
    result = await conversation_graph.ainvoke(init, config)
    elapsed = (time.perf_counter() - t0) * 1000

    agent_text = _get_interrupt_text(result)
    if agent_text:
        _print("agent", agent_text)

    latencies = [elapsed]
    utterance_idx = 0

    while utterance_idx < len(utterances):
        user_text = utterances[utterance_idx]
        utterance_idx += 1

        # Emergency short-circuit
        if is_emergency(user_text):
            _print("caller", user_text)
            print("\n🚨 EMERGENCY DETECTED — escalating immediately")
            break

        _print("caller", user_text)

        # Check if graph ended
        if result.get("call_ended") and not result.get("__interrupt__"):
            break

        # Resume graph
        t0 = time.perf_counter()
        result = await conversation_graph.ainvoke(Command(resume=user_text), config)
        elapsed = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed)

        agent_text = _get_interrupt_text(result)
        if agent_text:
            _print("agent", agent_text)

        if result.get("call_ended") and not result.get("__interrupt__"):
            break

    # Final stats
    if verbose:
        print("\n" + "─" * 60)
        print(f"✓ Call complete")
        print(f"  Booking ID : {result.get('booking_id', 'none')}")
        print(f"  Outcome    : {'booked' if result.get('booking_id') else 'not booked'}")
        print(f"  Emergency  : {result.get('is_emergency', False)}")
        print(f"  Turns      : {len(latencies)}")
        if latencies:
            avg = sum(latencies) / len(latencies)
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            print(f"  Latency avg: {avg:.0f}ms  p95: {p95:.0f}ms")

    return result


def _get_interrupt_text(result: dict) -> str | None:  # type: ignore[type-arg]
    interrupts = result.get("__interrupt__")
    if interrupts:
        val = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
        return str(val) if val else None
    return result.get("agent_response")


async def interactive_mode(clinic_id: str, language: str) -> None:
    call_sid = f"INTERACTIVE_{int(time.time())}"
    config = {"configurable": {"thread_id": call_sid}}
    init = initial_state(
        call_sid=call_sid,
        caller_phone="+910000000000",
        clinic_id=clinic_id,
        language=language,
    )

    print("=== SlotBot Interactive Simulation ===")
    print("Type your responses. Press Ctrl+C to end.\n")

    result = await conversation_graph.ainvoke(init, config)
    agent_text = _get_interrupt_text(result)
    if agent_text:
        print(f"\n🤖 Agent: {agent_text}")

    while True:
        if result.get("call_ended") and not result.get("__interrupt__"):
            print("\n[Call ended]")
            break

        try:
            user_input = input("\n👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Call terminated]")
            break

        if not user_input:
            continue

        result = await conversation_graph.ainvoke(Command(resume=user_input), config)
        agent_text = _get_interrupt_text(result)
        if agent_text:
            print(f"\n🤖 Agent: {agent_text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a SlotBot call")
    parser.add_argument("--transcript", help="Path to JSON transcript file")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), help="Built-in scenario name")
    parser.add_argument("--clinic-id", default="demo_clinic_01")
    parser.add_argument("--language", default="hinglish", choices=["hinglish", "hindi", "english"])
    args = parser.parse_args()

    async def run() -> None:
        await init_db()
        await upsert_clinic(DEMO_CLINIC)

        if args.transcript:
            transcript_path = Path(args.transcript)
            data = json.loads(transcript_path.read_text())
            utterances = [t["text"] for t in data if t.get("role") == "user"]
            await run_simulated_call(utterances, args.clinic_id, args.language)

        elif args.scenario:
            utterances = SCENARIOS[args.scenario]
            print(f"Running scenario: {args.scenario}")
            await run_simulated_call(utterances, args.clinic_id, args.language)

        else:
            await interactive_mode(args.clinic_id, args.language)

    asyncio.run(run())


if __name__ == "__main__":
    main()
