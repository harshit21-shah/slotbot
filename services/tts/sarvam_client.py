"""Sarvam AI TTS client — converts text to Hinglish/Hindi audio.

Returns mulaw 8kHz bytes ready for Twilio Media Streams.
"""

from __future__ import annotations

import audioop
import base64
import io
import logging
import wave
from typing import AsyncIterator

import httpx

from services.config import settings

logger = logging.getLogger(__name__)

_SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
_ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Sarvam AI speaker choices per language (bulbul:v3 voices)
_SARVAM_SPEAKERS = {
    "hinglish": "priya",
    "hindi": "priya",
    "english": "shubh",
}
_SARVAM_MODEL = "bulbul:v3"


async def text_to_mulaw(text: str, language: str = "hinglish") -> bytes:
    """
    Convert text to mulaw 8kHz audio bytes suitable for Twilio.
    Tries Sarvam AI first (best Indian accent), falls back to a simple beep on error.
    """
    try:
        pcm_bytes = await _sarvam_tts(text, language)
        return _pcm_to_mulaw_8k(pcm_bytes)
    except Exception as exc:
        logger.error("Sarvam TTS failed (%s) — returning silence", exc)
        return _generate_silence(duration_ms=500)


async def _sarvam_tts(text: str, language: str) -> bytes:
    """Call Sarvam AI TTS API, return raw PCM bytes (22050Hz, 16-bit, mono)."""
    target_language = "hi-IN" if language in ("hinglish", "hindi") else "en-IN"
    speaker = _SARVAM_SPEAKERS.get(language, "meera")

    payload = {
        "text": text,
        "target_language_code": target_language,
        "speaker": speaker,
        "pace": 1.0,
        "speech_sample_rate": 8000,
        "model": _SARVAM_MODEL,
    }

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            _SARVAM_TTS_URL,
            json=payload,
            headers={
                "api-subscription-key": settings.sarvam_api_key,
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    # Sarvam returns base64-encoded WAV audio
    audio_b64: str = data["audios"][0]
    audio_bytes = base64.b64decode(audio_b64)

    # Extract raw PCM from WAV
    with io.BytesIO(audio_bytes) as wav_io:
        with wave.open(wav_io, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sample_width = wf.getsampwidth()   # bytes per sample
            n_channels = wf.getnchannels()
            framerate = wf.getframerate()

    # Mix to mono if stereo
    if n_channels == 2:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)

    # Resample from 22050 → 8000 Hz
    if framerate != 8000:
        frames, _ = audioop.ratecv(frames, sample_width, 1, framerate, 8000, None)

    return frames  # raw PCM 8kHz 16-bit mono


def _pcm_to_mulaw_8k(pcm_bytes: bytes) -> bytes:
    """Convert PCM 16-bit to mulaw 8-bit (Twilio's format)."""
    return audioop.lin2ulaw(pcm_bytes, 2)


def _generate_silence(duration_ms: int = 200) -> bytes:
    """Return silence as mulaw bytes (used as fallback)."""
    num_samples = int(8000 * duration_ms / 1000)
    pcm = b"\x00\x00" * num_samples
    return audioop.lin2ulaw(pcm, 2)


async def text_to_wav_file(text: str, language: str = "hinglish") -> bytes:
    """Return a WAV file suitable for Twilio <Play> (8kHz mono)."""
    try:
        pcm = await _sarvam_tts(text, language)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(pcm)
        return buf.getvalue()
    except Exception as exc:
        logger.error("Sarvam WAV generation failed (%s)", exc)
        raise


async def stream_text_to_mulaw(
    text: str,
    language: str = "hinglish",
    chunk_size_chars: int = 80,
) -> AsyncIterator[bytes]:
    """
    Yield mulaw audio chunks as they become available.
    Splits text into sentence-like chunks for lower perceived latency.
    This is an async generator — callers can start sending audio before all TTS is done.
    """
    # Split on sentence boundaries for natural chunking
    import re

    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    if not sentences:
        yield await text_to_mulaw(text, language)
        return

    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            chunk = await text_to_mulaw(sentence, language)
            if chunk:
                yield chunk
