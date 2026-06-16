"""Twilio webhook handler — returns TwiML to start a Media Stream."""

from __future__ import annotations

from fastapi import Request

from services.config import settings


def _xml_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_stream_twiml(
    ws_url: str,
    *,
    patient_phone: str,
    clinic_phone: str,
    greeting: str | None = None,
) -> str:
    """
    Build TwiML: optional immediate Say (Twilio voice), then Media Stream.
    Say plays before WebSocket connects so the caller never hears silence.
    """
    say_block = ""
    if greeting:
        safe = _xml_attr(greeting)
        say_block = f'  <Say voice="Polly.Aditi">{safe}</Say>\n'

    patient = _xml_attr(patient_phone)
    clinic = _xml_attr(clinic_phone)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{say_block}  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="patient" value="{patient}"/>
      <Parameter name="clinic" value="{clinic}"/>
    </Stream>
  </Connect>
</Response>"""


def get_ws_url(request: Request) -> str:
    """
    Build the WebSocket URL Twilio should connect to.

    Prefer the public host Twilio actually hit (via proxy headers), not a stale
    APP_BASE_URL — localtunnel URLs change every restart.
    """
    host = request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto", "https")

    if host and not host.startswith("127.0.0.1") and "localhost" not in host:
        base = f"{proto}://{host}".rstrip("/")
    else:
        base = (settings.app_base_url or str(request.base_url)).rstrip("/")

    if base.startswith("https://"):
        return base.replace("https://", "wss://") + "/ws/call"
    if base.startswith("http://"):
        return base.replace("http://", "ws://") + "/ws/call"
    return f"wss://{base}/ws/call"
