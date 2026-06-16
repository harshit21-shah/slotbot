"""Unit tests for emergency keyword detection."""

from __future__ import annotations

import pytest

from services.agents.emergency import is_emergency


class TestEmergencyDetection:
    """Exhaustive tests — emergency detection must have 100% recall."""

    # ── Should trigger ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("text", [
        "bahut chest pain ho raha hai",
        "Chest pain is very bad",
        "mujhe breathe karne mein problem hai",
        "breathing trouble aa raha hai",
        "emergency hai please help",
        "urgent help chahiye",
        "accident ho gaya",
        "bleeding nahi ruk raha",
        "wo unconscious ho gaya",
        "seizure aa raha hai",
        "fit aa raha hai",
        "bahut dard ho raha hai",
        "zyada pain ho raha hai",
        "extreme dard hai",
        "madad karo please",
        "help karo",
        "EMERGENCY",
        "CHEST PAIN",
    ])
    def test_should_detect_emergency(self, text: str) -> None:
        assert is_emergency(text), f"Expected emergency: {text!r}"

    # ── Should NOT trigger ────────────────────────────────────────────────────

    @pytest.mark.parametrize("text", [
        "Main Rahul hoon",
        "Mujhe appointment chahiye",
        "kal subah 10 baje",
        "general checkup",
        "follow-up appointment",
        "I have a mild headache",
        "cough aur cold hai",
        "fever hai thoda",
        "back pain hai thoda",
        "routine blood test",
        "Monday ko appointment chahiye",
        "Dr. Sharma se milna hai",
        "haan sahi hai",
        "nahi, doosra time chahiye",
    ])
    def test_should_not_detect_emergency(self, text: str) -> None:
        assert not is_emergency(text), f"False positive: {text!r}"
