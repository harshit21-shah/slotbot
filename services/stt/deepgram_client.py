"""Deepgram streaming STT client (SDK v7+).

Usage:
    async with DeepgramSTT() as stt:
        stt.on_transcript = my_callback        # async fn(text, is_final, confidence)
        stt.on_speech_started = my_vad_cb      # async fn()
        await stt.send_audio(audio_bytes)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.socket_client import AsyncV1SocketClient

from services.config import settings

logger = logging.getLogger(__name__)

TranscriptCallback = Callable[[str, bool, float], Awaitable[None]]
SpeechStartedCallback = Callable[[], Awaitable[None]]


class DeepgramSTT:
    """
    Async context manager wrapping Deepgram SDK v7 live transcription.

    - Streams mulaw 8kHz audio directly.
    - Fires on_transcript(text, is_final, confidence).
    - Fires on_speech_started() for barge-in detection.
    """

    def __init__(self) -> None:
        self.on_transcript: TranscriptCallback | None = None
        self.on_speech_started: SpeechStartedCallback | None = None
        self._socket: AsyncV1SocketClient | None = None
        self._ctx_manager: Any = None

    async def __aenter__(self) -> "DeepgramSTT":
        client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)

        self._ctx_manager = client.listen.v1.connect(
            model="nova-2",
            language="hi",
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            punctuate="true",
            interim_results="true",
            endpointing=300,
            vad_events="true",
            utterance_end_ms=1000,
        )
        self._socket = await self._ctx_manager.__aenter__()

        # Register event handlers
        self._socket.on("Results", self._handle_transcript)
        self._socket.on("SpeechStarted", self._handle_speech_started)

        # Start the background listener task
        asyncio.create_task(self._socket.start_listening())

        logger.debug("Deepgram STT session started")
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._ctx_manager:
            try:
                await self._ctx_manager.__aexit__(*args)
            except Exception as exc:
                logger.debug("Deepgram close error (non-fatal): %s", exc)
        self._socket = None
        self._ctx_manager = None
        logger.debug("Deepgram STT session closed")

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Forward raw audio bytes to Deepgram."""
        if self._socket:
            await self._socket.send_media(audio_bytes)

    async def _handle_transcript(self, result: Any) -> None:
        try:
            # v7 result structure
            channel = result.channel
            alternatives = channel.alternatives
            if not alternatives:
                return
            alt = alternatives[0]
            text: str = getattr(alt, "transcript", "").strip()
            confidence: float = float(getattr(alt, "confidence", 1.0))
            is_final: bool = bool(getattr(result, "is_final", False))

            if text and self.on_transcript:
                await self.on_transcript(text, is_final, confidence)
        except Exception as exc:
            logger.debug("Transcript parse error: %s", exc)

    async def _handle_speech_started(self, result: Any) -> None:
        if self.on_speech_started:
            try:
                await self.on_speech_started()
            except Exception as exc:
                logger.debug("SpeechStarted handler error: %s", exc)
