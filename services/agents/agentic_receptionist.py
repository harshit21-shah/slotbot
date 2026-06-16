"""Autonomous agentic receptionist — one brain for natural human-like calls."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from services.agents.llm_client import complete_json, complete_json_messages, load_prompt
from services.agents.offline_fallback import offline_reply
from services.calendar.client import check_slot_available, create_booking, get_available_slots
from services.sms.client import send_confirmation_sms
from services.telephony.phone import is_valid_e164

logger = logging.getLogger(__name__)

_MAX_HISTORY = 14
_MAX_TOOL_ROUNDS = 2


@dataclass
class AgentContext:
    call_sid: str
    clinic: Any
    patient_phone: str
    language: str = "hinglish"
    messages: list[dict[str, str]] = field(default_factory=list)
    booking_id: str | None = None
    call_ended: bool = False


@dataclass
class AgentTurnResult:
    response: str
    call_ended: bool = False
    booking_id: str | None = None


def _system_prompt(ctx: AgentContext) -> str:
    clinic = ctx.clinic
    return load_prompt("agentic_receptionist_v1.txt").format(
        clinic_name=clinic.name,
        doctor_name=clinic.doctor_name,
        language=ctx.language,
        today=date.today().isoformat(),
        emergency_number=clinic.emergency_number,
        patient_phone=ctx.patient_phone or "unknown",
    )


def _chat_messages(ctx: AgentContext) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": _system_prompt(ctx)}]
    msgs.extend(ctx.messages[-_MAX_HISTORY:])
    return msgs


async def _execute_tools(ctx: AgentContext, tool_calls: list[dict[str, Any]]) -> list[str]:
    """Run agent-requested tools; return human-readable results for the LLM."""
    clinic = ctx.clinic
    results: list[str] = []

    for call in tool_calls[:3]:
        tool = str(call.get("tool", "")).lower()
        try:
            if tool == "get_slots":
                d = str(call.get("date", ""))
                slots = await get_available_slots(
                    calcom_username=clinic.calcom_username,
                    calcom_event_type_id=clinic.calcom_event_type_id,
                    date=d,
                )
                if slots:
                    results.append(f"get_slots({d}): available times — {', '.join(slots[:8])}")
                else:
                    results.append(f"get_slots({d}): no slots available, try another date")

            elif tool == "book":
                name = str(call.get("name", "Patient"))
                d = str(call.get("date", ""))
                t = str(call.get("time", ""))
                reason = str(call.get("reason", "Appointment"))
                phone = ctx.patient_phone if is_valid_e164(ctx.patient_phone) else "+910000000000"

                if not d or not t:
                    results.append("book: failed — need date and time")
                    continue

                available = await check_slot_available(
                    calcom_username=clinic.calcom_username,
                    calcom_event_type_id=clinic.calcom_event_type_id,
                    date=d,
                    time=t,
                )
                if not available:
                    alt = await get_available_slots(
                        calcom_username=clinic.calcom_username,
                        calcom_event_type_id=clinic.calcom_event_type_id,
                        date=d,
                    )
                    alt_str = ", ".join(alt[:5]) if alt else "none"
                    results.append(f"book: slot {d} {t} taken. Alternatives: {alt_str}")
                    continue

                booking_id = await create_booking(
                    calcom_username=clinic.calcom_username,
                    calcom_event_type_id=clinic.calcom_event_type_id,
                    name=name,
                    phone=phone,
                    date=d,
                    time=t,
                    reason=reason,
                )
                ctx.booking_id = booking_id
                results.append(f"book: SUCCESS id={booking_id} for {name} on {d} at {t}")
                ctx.call_ended = True

                if is_valid_e164(ctx.patient_phone):
                    asyncio.create_task(
                        send_confirmation_sms(
                            to_phone=ctx.patient_phone,
                            patient_name=name,
                            doctor_name=clinic.doctor_name,
                            clinic_name=clinic.name,
                            clinic_phone=clinic.phone_number,
                            slot_datetime=f"{d} {t}",
                            booking_id=booking_id,
                        )
                    )

            elif tool == "end_call":
                ctx.call_ended = True
                results.append(f"end_call: {call.get('reason', 'goodbye')}")

        except Exception as exc:
            logger.exception("Tool %s failed: %s", tool, exc)
            results.append(f"{tool}: error — {exc}")

    return results


async def run_agent_turn(ctx: AgentContext, user_message: str) -> AgentTurnResult:
    """
    One autonomous agent turn: understand, optionally use tools, respond naturally.
    Maintains conversation memory in ctx.messages.
    """
    ctx.messages.append({"role": "user", "content": user_message})

    tool_results: list[str] = []
    final_response = ""
    end_call = False

    for round_num in range(_MAX_TOOL_ROUNDS):
        if round_num == 0:
            messages = _chat_messages(ctx)
        else:
            tool_block = load_prompt("agentic_tool_result_v1.txt").format(
                tool_results="\n".join(tool_results)
            )
            messages = _chat_messages(ctx) + [{"role": "user", "content": tool_block}]

        try:
            result = await asyncio.wait_for(
                complete_json_messages(messages, temperature=0.55, max_tokens=700),
                timeout=14.0,
            )
        except Exception as exc:
            logger.exception("Agent LLM failed: %s", exc)
            final_response = offline_reply(
                user_message,
                clinic_name=ctx.clinic.name,
            ) or "Haan ji, main sun rahi hoon. Aaram se dobara boliye?"
            break

        spoken = str(result.get("response", "")).strip()
        if spoken:
            final_response = spoken

        if result.get("end_call"):
            ctx.call_ended = True
            end_call = True

        tool_calls = result.get("tool_calls") or []
        if not tool_calls:
            if ctx.booking_id and not end_call:
                ctx.call_ended = True
                end_call = True
            break

        tool_results = await _execute_tools(ctx, tool_calls)
        if ctx.call_ended:
            end_call = True
            break

    if not final_response:
        final_response = "Ji, main sun rahi hoon. Batayiye kaise help kar sakti hoon?"

    ctx.messages.append({"role": "assistant", "content": final_response})

    return AgentTurnResult(
        response=final_response,
        call_ended=end_call or ctx.call_ended,
        booking_id=ctx.booking_id,
    )


async def run_agent_greeting(ctx: AgentContext) -> str:
    """Optional LLM greeting when not using inline TwiML."""
    try:
        result = await complete_json(
            f"Generate a warm opening greeting (1-2 sentences) as Priya at {ctx.clinic.name}. "
            f"Ask how you can help. Return JSON: {{\"response\": \"...\"}}",
            system=_system_prompt(ctx),
            temperature=0.6,
            max_tokens=200,
        )
        text = str(result.get("response", "")).strip()
        if text:
            ctx.messages.append({"role": "assistant", "content": text})
            return text
    except Exception:
        pass
    clinic = ctx.clinic
    return (
        clinic.greeting_template
        if clinic.greeting_template
        else f"Namaste! Main Priya hoon, {clinic.name} se. Batayiye, kaise help kar sakti hoon?"
    )
