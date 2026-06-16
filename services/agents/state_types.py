"""LangGraph state type and supporting dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class SlotBotState(TypedDict, total=False):
    # ── Call metadata ──────────────────────────────────────────────────────────
    call_sid: str
    caller_phone: str
    clinic_id: str
    language: str                       # "hinglish" | "english" | "hindi"

    # ── Conversation turn ──────────────────────────────────────────────────────
    last_user_input: str
    agent_response: str
    turn_count: int

    # ── Collected patient info ─────────────────────────────────────────────────
    collected_name: str | None
    collected_reason: str | None
    collected_date: str | None          # YYYY-MM-DD
    collected_time: str | None          # HH:MM  (24-hour)
    time_is_flexible: bool
    time_range_start: str | None        # HH:MM
    time_range_end: str | None          # HH:MM
    doctor_preference: str | None

    # ── Booking ────────────────────────────────────────────────────────────────
    available_slots: list[str]          # ["10:00", "11:00", ...]
    confirmed_slot_datetime: str | None # "YYYY-MM-DD HH:MM"
    booking_id: str | None

    # ── Flow control ──────────────────────────────────────────────────────────
    clarification_attempts: int
    clarification_field: str | None     # which field we're clarifying
    is_emergency: bool
    needs_human: bool
    call_ended: bool

    # ── Full transcript for DB logging ─────────────────────────────────────────
    transcript: list[dict[str, Any]]

    # ── Per-turn latency tracking (ms) ────────────────────────────────────────
    turn_latencies_ms: list[float]


def initial_state(call_sid: str, caller_phone: str, clinic_id: str, language: str) -> SlotBotState:
    return SlotBotState(
        call_sid=call_sid,
        caller_phone=caller_phone,
        clinic_id=clinic_id,
        language=language,
        last_user_input="",
        agent_response="",
        turn_count=0,
        collected_name=None,
        collected_reason=None,
        collected_date=None,
        collected_time=None,
        time_is_flexible=False,
        time_range_start=None,
        time_range_end=None,
        doctor_preference=None,
        available_slots=[],
        confirmed_slot_datetime=None,
        booking_id=None,
        clarification_attempts=0,
        clarification_field=None,
        is_emergency=False,
        needs_human=False,
        call_ended=False,
        transcript=[],
        turn_latencies_ms=[],
    )


@dataclass
class ExtractionResult:
    """Structured output from the LLM extraction prompts."""
    response: str                       # text to speak back to caller
    confidence: float = 0.0
    extracted_name: str | None = None
    extracted_reason: str | None = None
    extracted_date: str | None = None   # YYYY-MM-DD
    extracted_time: str | None = None   # HH:MM
    time_is_flexible: bool = False
    time_range_start: str | None = None
    time_range_end: str | None = None
    doctor_preference: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)
