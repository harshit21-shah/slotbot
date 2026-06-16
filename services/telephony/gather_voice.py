"""HTTP-only Twilio voice via Gather+Speech — autonomous agentic receptionist."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.agents.agentic_receptionist import AgentContext, run_agent_turn
from services.agents.emergency import emergency_response, is_emergency
from services.agents.offline_fallback import offline_reply
from services.config import settings
from services.db.database import get_clinic_by_phone, insert_call_log
from services.db.models import CallLog
from services.telephony.audio_cache import store_audio
from services.telephony.phone import normalize_phone
from services.tts.sarvam_client import text_to_wav_file

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 600

_SAY_OPEN = '<Say language="en-IN" voice="Polly.Aditi">'
_SAY_CLOSE = "</Say>"
_STT_HINTS = (
    "appointment, naam, kal, aaj, parso, subah, dopahar, sham, baje, "
    "haan, nahi, doctor, checkup, fever, dard, book, slot, confirm"
)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _sanitize_speech(text: str) -> str:
    cleaned = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )
    return cleaned[:400]


def _say(text: str) -> str:
    return f"{_SAY_OPEN}{_xml_escape(_sanitize_speech(text))}{_SAY_CLOSE}"


async def _speech_block(base_url: str, text: str, language: str = "hinglish") -> str:
    clean = _sanitize_speech(text)
    if not clean.strip():
        return _say("Sorry, kuch problem hai.")

    if not settings.use_sarvam_play:
        return _say(clean)

    try:
        import asyncio

        wav = await asyncio.wait_for(text_to_wav_file(clean, language), timeout=4.0)
        audio_id = store_audio(wav)
        play_url = f"{base_url.rstrip('/')}/voice/audio/{audio_id}"
        return f'<Play>{play_url}</Play>'
    except Exception as exc:
        logger.warning("Sarvam TTS failed, using Polly fallback: %s", exc)
        return _say(clean)


def _gather_attrs(action_url: str) -> str:
    return (
        f'input="speech" action="{action_url}" method="POST" '
        f'speechTimeout="auto" timeout="15" language="hi-IN" '
        f'hints="{_STT_HINTS}"'
    )


async def _gather_block(base_url: str, action_url: str, say_text: str, language: str) -> str:
    prompt = await _speech_block(base_url, say_text, language)
    goodbye = _say("Sorry, sunai nahi diya. Phir call kijiye.")
    return f"""  <Gather {_gather_attrs(action_url)}>
    {prompt}
  </Gather>
  {goodbye}"""


async def _lookup_clinic(clinic_phone: str):
    clinic = await get_clinic_by_phone(clinic_phone)
    if clinic:
        return clinic
    if settings.twilio_phone_number:
        return await get_clinic_by_phone(settings.twilio_phone_number)
    return None


def _prune_sessions() -> None:
    now = time.monotonic()
    expired = [
        sid for sid, sess in _sessions.items()
        if now - sess.last_activity > _SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)


def _get_or_create_session(call_sid: str, clinic: Any, patient_phone: str) -> GatherSession:
    _prune_sessions()
    session = _sessions.get(call_sid)
    if session:
        session.last_activity = time.monotonic()
        return session
    session = GatherSession(
        call_sid=call_sid,
        clinic_id=clinic.clinic_id,
        language=clinic.language_preference,
        patient_phone=normalize_phone(patient_phone) if patient_phone else "",
        started_at=datetime.utcnow(),
    )
    _sessions[call_sid] = session
    return session


def _agent_context(session: GatherSession, clinic: Any) -> AgentContext:
    return AgentContext(
        call_sid=session.call_sid,
        clinic=clinic,
        patient_phone=session.patient_phone,
        language=session.language,
        messages=list(session.messages),
        booking_id=session.booking_id,
        call_ended=session.call_ended,
    )


def _sync_agent_to_session(session: GatherSession, ctx: AgentContext) -> None:
    session.messages = ctx.messages
    session.booking_id = ctx.booking_id
    session.call_ended = ctx.call_ended


async def build_start_twiml(
    *,
    base_url: str,
    patient_phone: str,
    clinic_phone: str,
) -> str:
    clinic = await _lookup_clinic(clinic_phone)
    greeting = (
        clinic.greeting_template
        if clinic
        else "Namaste! Main Priya hoon. Batayiye, main aapki kaise help kar sakti hoon?"
    )
    lang = clinic.language_preference if clinic else "hinglish"
    return await build_gather_twiml(base_url, greeting, lang)


async def build_gather_twiml(base_url: str, say_text: str, language: str = "hinglish") -> str:
    action = f"{base_url.rstrip('/')}/voice/turn"
    body = await _gather_block(base_url, action, say_text, language)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{body}
</Response>"""


async def build_turn_twiml(
    *,
    base_url: str,
    call_sid: str,
    speech: str,
    patient_phone: str,
    clinic_phone: str,
    direction: str,
) -> str:
    action = f"{base_url.rstrip('/')}/voice/turn"
    clinic = await _lookup_clinic(clinic_phone)
    if not clinic:
        return await _play_only(base_url, "Sorry, clinic setup error. Alvida.", "hinglish")

    session = _get_or_create_session(call_sid, clinic, patient_phone)
    utterance = (speech or "").strip()
    logger.info("Agent turn speech=%r turns=%d", utterance, len(session.messages) // 2)

    if not utterance:
        body = await _gather_block(
            base_url,
            action,
            "Ji, main sun rahi hoon. Aaram se boliye — kaise help kar sakti hoon?",
            session.language,
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{body}
</Response>"""

    if is_emergency(utterance):
        _sessions.pop(call_sid, None)
        msg = emergency_response(session.language, clinic.emergency_number)
        return await _play_only(base_url, msg, session.language)

    ctx = _agent_context(session, clinic)
    try:
        result = await run_agent_turn(ctx, utterance)
    except Exception as exc:
        logger.exception("Agent turn failed: %s", exc)
        result_response = offline_reply(utterance, clinic_name=clinic.name) or (
            "Haan ji, main sun rahi hoon. Aaram se dobara boliye?"
        )
        session.messages.append({"role": "user", "content": utterance})
        session.messages.append({"role": "assistant", "content": result_response})
        body = await _gather_block(base_url, action, result_response, session.language)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{body}
</Response>"""

    _sync_agent_to_session(session, ctx)

    if result.call_ended or session.call_ended:
        outcome = "booked" if session.booking_id else "abandoned"
        await _persist_call_log(session, outcome)
        _sessions.pop(call_sid, None)
        return await _play_only(base_url, result.response, session.language)

    body = await _gather_block(base_url, action, result.response, session.language)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{body}
</Response>"""


async def _play_only(base_url: str, text: str, language: str = "hinglish") -> str:
    block = await _speech_block(base_url, text, language)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {block}
</Response>"""


def error_twiml(message: str = "Sorry, technical problem. Please call again.") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {_say(message)}
</Response>"""


@dataclass
class GatherSession:
    call_sid: str
    clinic_id: str
    language: str
    patient_phone: str = ""
    booking_id: str | None = None
    call_ended: bool = False
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: float = field(default_factory=time.monotonic)
    messages: list[dict[str, str]] = field(default_factory=list)


_sessions: dict[str, GatherSession] = {}


async def _persist_call_log(session: GatherSession, outcome: str) -> None:
    try:
        ended = datetime.utcnow()
        duration = max(0.0, (ended - session.started_at).total_seconds())
        transcript = [
            {"role": "user" if m["role"] == "user" else "agent", "text": m["content"]}
            for m in session.messages
        ]
        await insert_call_log(
            CallLog(
                call_sid=session.call_sid,
                clinic_id=session.clinic_id,
                caller_phone=session.patient_phone or "unknown",
                outcome=outcome,
                booking_id=session.booking_id,
                transcript=transcript,
                duration_seconds=duration,
                turn_count=len(session.messages) // 2,
                latency_p50_ms=None,
                latency_p95_ms=None,
                started_at=session.started_at,
                ended_at=ended,
            )
        )
    except Exception as exc:
        logger.exception("Failed to persist gather call log: %s", exc)


def public_base_url(request_base: str, forwarded_proto: str | None, host: str | None) -> str:
    if host and "127.0.0.1" not in host and "localhost" not in host:
        proto = forwarded_proto or "https"
        return f"{proto}://{host}".rstrip("/")
    return settings.app_base_url.rstrip("/")
