"""
Twilio Media Streams WebSocket handler — the main real-time hot path.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from langgraph.types import Command

from services.agents.barge_in import BargeinController
from services.agents.emergency import emergency_response, is_emergency
from services.agents.graph import conversation_graph
from services.agents.session import session_store
from services.agents.state_types import initial_state
from services.config import settings
from services.db.database import get_clinic_by_phone, insert_call_log
from services.db.models import CallLog
from services.stt.deepgram_client import DeepgramSTT
from services.telephony.phone import is_valid_e164
from services.tts.sarvam_client import stream_text_to_mulaw

logger = logging.getLogger(__name__)


def _extract_interrupt_text(result: dict[str, Any]) -> str | None:
    interrupts = result.get("__interrupt__")
    if interrupts:
        val = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
        return str(val) if val else None
    return result.get("agent_response")


def _is_graph_ended(result: dict[str, Any]) -> bool:
    return bool(result.get("call_ended")) and not result.get("__interrupt__")


async def _lookup_clinic(clinic_phone: str):
    clinic = await get_clinic_by_phone(clinic_phone)
    if clinic:
        return clinic
    if settings.twilio_phone_number:
        return await get_clinic_by_phone(settings.twilio_phone_number)
    return None


async def _send_audio_to_twilio(ws: WebSocket, stream_sid: str, mulaw_bytes: bytes) -> None:
    payload = base64.b64encode(mulaw_bytes).decode("ascii")
    await ws.send_text(
        json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": payload}})
    )


async def _send_silence(ws: WebSocket, stream_sid: str) -> None:
    await _send_audio_to_twilio(ws, stream_sid, b"\x7f" * 160)


async def _send_clear_twilio(ws: WebSocket, stream_sid: str) -> None:
    await ws.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))


async def handle_media_stream(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("Twilio WebSocket connected")

    call_sid = ""
    stream_sid = ""
    caller_phone = ""
    clinic_phone = ""
    session = None
    graph_config: dict[str, Any] = {}
    graph_result: dict[str, Any] = {}
    language = "hinglish"
    clinic = None

    transcript_queue: asyncio.Queue[str] = asyncio.Queue()
    call_start_time = time.monotonic()
    turn_latencies: list[float] = []

    stt_holder: dict[str, DeepgramSTT | None] = {"stt": None}
    pending_audio: list[bytes] = []

    async def send_silence_fn() -> None:
        if stream_sid:
            await _send_clear_twilio(ws, stream_sid)
            await _send_silence(ws, stream_sid)

    barge_in = BargeinController(send_silence_fn=send_silence_fn)

    async def tts_stream_fn(text: str) -> None:
        if not stream_sid:
            return
        async for chunk in stream_text_to_mulaw(text, language):
            await _send_audio_to_twilio(ws, stream_sid, chunk)

    async def on_transcript(text: str, is_final: bool, confidence: float) -> None:
        if is_final and text.strip():
            logger.info("STT final [conf=%.2f]: %s", confidence, text[:80])
            await transcript_queue.put(text.strip())

    async def on_speech_started() -> None:
        await barge_in.on_speech_started()

    async def init_stt() -> None:
        try:
            stt = DeepgramSTT()
            stt.on_transcript = on_transcript
            stt.on_speech_started = on_speech_started
            await stt.__aenter__()
            stt_holder["stt"] = stt
            for chunk in pending_audio:
                await stt.send_audio(chunk)
            pending_audio.clear()
            logger.info("Deepgram STT ready for call %s", call_sid)
        except Exception as exc:
            logger.exception("Deepgram init failed: %s", exc)

    async def close_stt() -> None:
        stt = stt_holder.get("stt")
        if stt:
            await stt.__aexit__(None, None, None)
            stt_holder["stt"] = None

    async def audio_loop() -> None:
        nonlocal call_sid, stream_sid, caller_phone, clinic_phone, session, graph_config, language, clinic

        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                event = msg.get("event")

                if event == "connected":
                    logger.debug("Twilio stream connected event")

                elif event == "start":
                    meta = msg.get("start", {})
                    call_sid = meta.get("callSid", "")
                    stream_sid = meta.get("streamSid", "")
                    custom = meta.get("customParameters", {})
                    caller_phone = custom.get("patient") or custom.get("caller") or ""
                    if not is_valid_e164(caller_phone):
                        logger.warning("Invalid caller phone in stream params: %r", caller_phone)
                        caller_phone = "unknown"
                    clinic_phone = custom.get("clinic", custom.get("to", ""))

                    clinic = await _lookup_clinic(clinic_phone)
                    if not clinic:
                        logger.error("No clinic found for phone: %s", clinic_phone)
                        await transcript_queue.put("__CALL_ENDED__")
                        await ws.close()
                        return

                    language = clinic.language_preference
                    session = await session_store.create(
                        call_sid=call_sid,
                        clinic_id=clinic.clinic_id,
                        caller_phone=caller_phone,
                        language=language,
                    )
                    graph_config = session.graph_config
                    logger.info(
                        "Call started: sid=%s clinic=%s patient=***%s",
                        call_sid,
                        clinic.clinic_id,
                        caller_phone[-4:] if caller_phone else "????",
                    )

                    asyncio.create_task(init_stt())
                    await transcript_queue.put("__CALL_STARTED__")

                elif event == "media":
                    audio_bytes = base64.b64decode(msg["media"]["payload"])
                    stt = stt_holder.get("stt")
                    if stt:
                        await stt.send_audio(audio_bytes)
                    else:
                        pending_audio.append(audio_bytes)

                elif event == "stop":
                    logger.info("Twilio stream stopped: %s", call_sid)
                    await transcript_queue.put("__CALL_ENDED__")
                    break

        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected: %s", call_sid)
            await transcript_queue.put("__CALL_ENDED__")

    async def conversation_loop() -> None:
        nonlocal graph_result, clinic

        sentinel = await transcript_queue.get()
        if sentinel == "__CALL_ENDED__" or not clinic:
            return

        init = initial_state(
            call_sid=call_sid,
            caller_phone=caller_phone,
            clinic_id=clinic.clinic_id,
            language=language,
        )

        t0 = time.perf_counter()
        graph_result = await conversation_graph.ainvoke(init, graph_config)
        turn_latencies.append((time.perf_counter() - t0) * 1000)

        skip_first_tts = True  # greeting already played via TwiML <Say>

        while True:
            agent_text = _extract_interrupt_text(graph_result)
            if not agent_text:
                logger.warning("No agent text — ending call %s", call_sid)
                break

            if skip_first_tts:
                skip_first_tts = False
                logger.info("Skipping duplicate greeting TTS (played via TwiML)")
            else:
                await barge_in.speak(agent_text, tts_stream_fn)

            if _is_graph_ended(graph_result):
                break

            try:
                user_text = await asyncio.wait_for(transcript_queue.get(), timeout=45.0)
            except asyncio.TimeoutError:
                logger.warning("Turn timeout for %s", call_sid)
                break

            if user_text == "__CALL_ENDED__":
                break

            if is_emergency(user_text):
                emergency_msg = emergency_response(language, clinic.emergency_number)
                await barge_in.speak(emergency_msg, tts_stream_fn)
                graph_result = {"call_ended": True, "is_emergency": True}
                break

            t0 = time.perf_counter()
            graph_result = await conversation_graph.ainvoke(
                Command(resume=user_text), graph_config
            )
            turn_latencies.append((time.perf_counter() - t0) * 1000)

    try:
        await asyncio.gather(audio_loop(), conversation_loop())
    finally:
        await close_stt()
        asyncio.create_task(
            _persist_call_log(
                call_sid=call_sid,
                clinic_id=session.clinic_id if session else "",
                caller_phone=caller_phone,
                graph_result=graph_result,
                turn_latencies=turn_latencies,
                call_start_time=call_start_time,
            )
        )
        if session:
            await session_store.remove(call_sid)
        logger.info("Call complete: %s (turns=%d)", call_sid, len(turn_latencies))


async def _persist_call_log(
    *,
    call_sid: str,
    clinic_id: str,
    caller_phone: str,
    graph_result: dict[str, Any],
    turn_latencies: list[float],
    call_start_time: float,
) -> None:
    if not call_sid or not clinic_id:
        return

    from datetime import datetime

    ended_at_ts = time.time()
    duration = time.monotonic() - call_start_time
    booking_id: str | None = graph_result.get("booking_id")

    if graph_result.get("is_emergency"):
        outcome = "emergency"
    elif graph_result.get("needs_human"):
        outcome = "escalated"
    elif booking_id:
        outcome = "booked"
    else:
        outcome = "abandoned"

    sorted_latencies = sorted(turn_latencies)
    p50 = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else None
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else None

    log = CallLog(
        call_sid=call_sid,
        clinic_id=clinic_id,
        caller_phone=caller_phone,
        outcome=outcome,
        booking_id=booking_id,
        transcript=graph_result.get("transcript", []),
        duration_seconds=duration,
        turn_count=len(turn_latencies),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        started_at=datetime.utcfromtimestamp(ended_at_ts - duration),
        ended_at=datetime.utcfromtimestamp(ended_at_ts),
    )

    try:
        await insert_call_log(log)
    except Exception as exc:
        logger.error("Failed to persist call log %s: %s", call_sid, exc)
