"""Twilio webhook and WebSocket routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, WebSocket
from fastapi.responses import Response

from services.config import settings
from services.db.database import get_clinic_by_phone
from services.telephony.audio_cache import get_audio
from services.telephony.gather_voice import (
    build_start_twiml,
    build_turn_twiml,
    error_twiml,
    public_base_url,
)
from services.telephony.webhook import build_stream_twiml, get_ws_url
from services.telephony.websocket import handle_media_stream

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_call_parties(
    *,
    from_number: str,
    to_number: str,
    direction: str,
) -> tuple[str, str]:
    if direction.startswith("outbound"):
        return to_number, from_number or settings.twilio_phone_number
    return from_number, to_number or settings.twilio_phone_number


@router.post("/voice", response_class=Response)
async def voice_webhook(
    request: Request,
    From: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    CallSid: Annotated[str, Form()] = "",
    Direction: Annotated[str, Form()] = "inbound",
) -> Response:
    """
    HTTP-only voice (recommended for local dev).
    Uses Twilio Gather+Speech — works without WebSocket tunnels.
    """
    patient_phone, clinic_phone = _resolve_call_parties(
        from_number=From, to_number=To, direction=Direction
    )
    base = public_base_url(
        str(request.base_url),
        request.headers.get("x-forwarded-proto"),
        request.headers.get("host"),
    )
    logger.info("Voice/simple: sid=%s base=%s", CallSid, base)
    try:
        twiml = await build_start_twiml(
            base_url=base,
            patient_phone=patient_phone,
            clinic_phone=clinic_phone,
        )
    except Exception as exc:
        logger.exception("Voice webhook failed: %s", exc)
        twiml = error_twiml()
    return Response(content=twiml, media_type="application/xml")


@router.get("/voice/audio/{audio_id}", response_class=Response)
async def voice_audio(audio_id: str) -> Response:
    """Serve cached Sarvam WAV for Twilio <Play>."""
    wav = get_audio(audio_id)
    if not wav:
        raise HTTPException(status_code=404, detail="Audio not found or expired")
    return Response(content=wav, media_type="audio/wav")


@router.post("/voice/turn", response_class=Response)
async def voice_turn(
    request: Request,
    From: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    CallSid: Annotated[str, Form()] = "",
    Direction: Annotated[str, Form()] = "inbound",
    SpeechResult: Annotated[str, Form()] = "",
) -> Response:
    """Handle one speech turn from Twilio Gather."""
    patient_phone, clinic_phone = _resolve_call_parties(
        from_number=From, to_number=To, direction=Direction
    )
    base = public_base_url(
        str(request.base_url),
        request.headers.get("x-forwarded-proto"),
        request.headers.get("host"),
    )
    logger.info("Voice/turn: sid=%s speech=%s", CallSid, SpeechResult[:60] if SpeechResult else "")
    try:
        twiml = await build_turn_twiml(
            base_url=base,
            call_sid=CallSid,
            speech=SpeechResult,
            patient_phone=patient_phone,
            clinic_phone=clinic_phone,
            direction=Direction,
        )
    except Exception as exc:
        logger.exception("Voice turn failed: %s", exc)
        twiml = error_twiml("Sorry, technical problem. Please try again.")
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/stream", response_class=Response)
async def voice_stream_webhook(
    request: Request,
    From: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    CallSid: Annotated[str, Form()] = "",
    Direction: Annotated[str, Form()] = "inbound",
) -> Response:
    """Legacy Media Streams path (needs ngrok — Cloudflare breaks wss)."""
    patient_phone, clinic_phone = _resolve_call_parties(
        from_number=From, to_number=To, direction=Direction
    )
    clinic = await get_clinic_by_phone(clinic_phone)
    if not clinic and settings.twilio_phone_number:
        clinic = await get_clinic_by_phone(settings.twilio_phone_number)
    greeting = clinic.greeting_template if clinic else None
    ws_url = get_ws_url(request)
    twiml = build_stream_twiml(
        ws_url,
        patient_phone=patient_phone,
        clinic_phone=clinic_phone,
        greeting=greeting,
    )
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/ws/call")
async def websocket_call(ws: WebSocket) -> None:
    await handle_media_stream(ws)
