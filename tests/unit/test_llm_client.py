"""Unit tests for LLM client JSON parsing and provider fallback logic."""

from __future__ import annotations

import pytest

from services.agents import llm_client


def test_parse_json_content_plain():
    assert llm_client._parse_json_content('{"response": "hi"}') == {"response": "hi"}


def test_parse_json_content_with_surrounding_text():
    raw = 'Here is the result:\n{"response": "ok", "confidence": 0.9}\nDone.'
    parsed = llm_client._parse_json_content(raw)
    assert parsed["response"] == "ok"
    assert parsed["confidence"] == 0.9


def test_parse_json_content_invalid():
    with pytest.raises(ValueError, match="non-JSON"):
        llm_client._parse_json_content("not json at all")


@pytest.mark.asyncio
async def test_complete_json_falls_back_to_anthropic(monkeypatch):
    async def fail_groq(*_args, **_kwargs):
        raise RuntimeError("rate limit")

    async def ok_anthropic(*_args, **_kwargs):
        return '{"response": "fallback ok", "confidence": 1}'

    monkeypatch.setattr(llm_client.settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(llm_client, "_groq_complete", fail_groq)
    monkeypatch.setattr(llm_client, "_anthropic_complete", ok_anthropic)

    result = await llm_client.complete_json("test prompt")
    assert result["response"] == "fallback ok"


@pytest.mark.asyncio
async def test_complete_json_raises_when_all_providers_fail(monkeypatch):
    async def fail_groq(*_args, **_kwargs):
        raise RuntimeError("groq down")

    async def fail_anthropic(*_args, **_kwargs):
        raise RuntimeError("anthropic down")

    monkeypatch.setattr(llm_client.settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(llm_client, "_groq_complete", fail_groq)
    monkeypatch.setattr(llm_client, "_anthropic_complete", fail_anthropic)

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await llm_client.complete_json("test prompt")
