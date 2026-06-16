"""Unit tests for offline LLM fallback replies."""

from __future__ import annotations

from services.agents.offline_fallback import offline_reply


def test_hear_me_devanagari():
    reply = offline_reply("क्या आप मुझे सुन पा रहे हो?")
    assert reply
    assert "sun rahi" in reply.lower()


def test_greeting_devanagari():
    reply = offline_reply("हेलो!")
    assert reply
    assert "namaste" in reply.lower() or "priya" in reply.lower()


def test_name_hinglish():
    reply = offline_reply("mera naam Harshit hai")
    assert reply
    assert "harshit" in reply.lower()
