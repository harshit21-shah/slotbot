"""Unit tests for LangGraph routing functions."""

from __future__ import annotations

import pytest

from services.agents.graph import (
    route_after_booking,
    route_after_check_availability,
    route_after_collect_datetime,
    route_after_collect_name,
    route_after_collect_reason,
    route_after_confirm_slot,
    route_after_greeting,
)
from services.agents.state_types import initial_state


def make_state(**kwargs):  # type: ignore[no-untyped-def]
    s = initial_state("SID", "+91999", "clinic1", "hinglish")
    s.update(kwargs)
    return s


class TestRoutingAfterGreeting:
    def test_goes_to_collect_name_normally(self) -> None:
        state = make_state()
        assert route_after_greeting(state) == "collect_name"

    def test_goes_to_emergency_on_flag(self) -> None:
        state = make_state(is_emergency=True)
        assert route_after_greeting(state) == "emergency_escalate"


class TestRoutingAfterCollectName:
    def test_goes_to_collect_reason_when_name_present(self) -> None:
        state = make_state(collected_name="Rahul")
        assert route_after_collect_name(state) == "collect_reason"

    def test_retries_when_no_name(self) -> None:
        state = make_state(clarification_attempts=1)
        assert route_after_collect_name(state) == "collect_name"

    def test_escalates_after_max_attempts(self) -> None:
        state = make_state(clarification_attempts=2)
        assert route_after_collect_name(state) == "human_escalate"

    def test_emergency_overrides(self) -> None:
        state = make_state(is_emergency=True, collected_name="Rahul")
        assert route_after_collect_name(state) == "emergency_escalate"


class TestRoutingAfterCheckAvailability:
    def test_exact_slot_match_goes_to_confirm(self) -> None:
        state = make_state(available_slots=["10:00", "11:00"], collected_time="10:00")
        assert route_after_check_availability(state) == "confirm_slot"

    def test_no_exact_match_goes_to_alternatives(self) -> None:
        state = make_state(available_slots=["11:00", "12:00"], collected_time="10:00")
        assert route_after_check_availability(state) == "offer_alternatives"

    def test_no_slots_retries_datetime(self) -> None:
        state = make_state(available_slots=[])
        assert route_after_check_availability(state) == "collect_datetime"

    def test_needs_human_escalates(self) -> None:
        state = make_state(needs_human=True)
        assert route_after_check_availability(state) == "human_escalate"


class TestRoutingAfterBooking:
    def test_booking_id_goes_to_confirmation(self) -> None:
        state = make_state(booking_id="bk_123")
        assert route_after_booking(state) == "send_confirmation"

    def test_needs_human_escalates(self) -> None:
        state = make_state(needs_human=True)
        assert route_after_booking(state) == "human_escalate"

    def test_slot_taken_goes_to_alternatives(self) -> None:
        state = make_state(available_slots=["11:00"], booking_id=None)
        assert route_after_booking(state) == "offer_alternatives"
