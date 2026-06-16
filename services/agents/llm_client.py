"""LLM client — Groq primary, Anthropic fallback. All LLM calls go through here."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from groq import AsyncGroq

from services.config import settings

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_groq_client: AsyncGroq | None = None
_anthropic_client: Any | None = None


def get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client


def get_anthropic_client() -> Any:
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        _anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def load_prompt(filename: str) -> str:
    """Load a versioned prompt file from services/agents/prompts/."""
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        logger.error("Failed to parse LLM JSON: %s", content[:200])
        raise ValueError(f"LLM returned non-JSON: {content[:200]}")


async def _groq_complete(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    client = get_groq_client()
    kwargs: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ("{}" if json_mode else "")


async def _anthropic_complete(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    client = get_anthropic_client()

    system_parts: list[str] = []
    user_parts: list[str] = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append(msg["content"])
        else:
            user_parts.append(msg["content"])

    if json_mode:
        system_parts.append("Respond with valid JSON only. No markdown fences.")

    system = "\n\n".join(system_parts) if system_parts else None
    user_content = "\n\n".join(user_parts)

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": user_content}],
    )
    block = response.content[0]
    return getattr(block, "text", str(block))


async def _try_provider(
    name: str,
    complete_fn: Any,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> tuple[str, str]:
    t0 = time.perf_counter()
    content = await complete_fn(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
    )
    logger.info("%s LLM succeeded in %.0fms", name.capitalize(), (time.perf_counter() - t0) * 1000)
    return content, name


async def _complete_raw(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> tuple[str, str]:
    """Try configured primary LLM, then the other provider. Returns (content, provider_name)."""
    errors: list[str] = []
    primary = (settings.llm_primary or "anthropic").strip().lower()
    if primary not in {"anthropic", "groq"}:
        primary = "anthropic"

    providers: list[tuple[str, Any]] = []
    if settings.anthropic_api_key:
        providers.append(("anthropic", _anthropic_complete))
    if settings.groq_api_key:
        providers.append(("groq", _groq_complete))

    ordered = sorted(providers, key=lambda p: 0 if p[0] == primary else 1)

    for name, complete_fn in ordered:
        try:
            return await _try_provider(
                name,
                complete_fn,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
        except Exception as exc:
            msg = f"{name.capitalize()}: {exc}"
            errors.append(msg)
            fallback = "Groq" if name == "anthropic" else "Anthropic"
            logger.warning("%s LLM failed — trying %s: %s", name.capitalize(), fallback, exc)

    detail = "; ".join(errors) if errors else "no LLM API keys configured"
    raise RuntimeError(f"All LLM providers failed ({detail})")


async def complete_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> dict[str, Any]:
    """
    Call LLM (Groq → Anthropic fallback) and parse the response as JSON.
    """
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return await complete_json_messages(
        messages, temperature=temperature, max_tokens=max_tokens
    )


async def complete_json_messages(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 768,
) -> dict[str, Any]:
    """Multi-turn chat → parsed JSON response."""
    content, provider = await _complete_raw(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )
    logger.debug("complete_json_messages via %s", provider)
    return _parse_json_content(content)


async def complete_text(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 256,
) -> str:
    """Call LLM (Groq → Anthropic fallback) and return raw text."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    content, _provider = await _complete_raw(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=False,
    )
    return content.strip()
