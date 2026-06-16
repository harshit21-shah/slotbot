"""Barge-in controller — stops TTS playback when caller speaks mid-sentence."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class BargeinController:
    """
    Wraps the TTS streaming task. When Deepgram VAD detects caller speech
    while the agent is speaking, `on_speech_started()` cancels the synthesis
    task and sends silence to Twilio for a clean audio cut-off.
    """

    def __init__(self, send_silence_fn: Callable[[], Awaitable[None]]) -> None:
        self._send_silence = send_silence_fn
        self.is_agent_speaking: bool = False
        self._current_task: asyncio.Task[None] | None = None

    async def speak(
        self,
        text: str,
        tts_stream_fn: Callable[[str], Awaitable[None]],
    ) -> bool:
        """
        Stream TTS audio for `text`. Returns True if speech completed normally,
        False if it was interrupted by barge-in.
        """
        self.is_agent_speaking = True
        completed = True

        self._current_task = asyncio.create_task(tts_stream_fn(text))
        try:
            await self._current_task
        except asyncio.CancelledError:
            logger.debug("Barge-in: TTS cancelled mid-speech")
            completed = False
        finally:
            self.is_agent_speaking = False
            self._current_task = None

        return completed

    async def on_speech_started(self) -> None:
        """Called by the Deepgram VAD event handler when caller speech is detected."""
        if self.is_agent_speaking and self._current_task is not None:
            logger.debug("Barge-in detected — cancelling TTS task")
            self._current_task.cancel()
            await self._send_silence()
