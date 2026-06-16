"""In-memory WAV cache for Twilio <Play> URLs."""

from __future__ import annotations

import secrets
import time
from typing import Final

_TTL_SECONDS: Final[int] = 600
_store: dict[str, tuple[bytes, float]] = {}


def store_audio(wav_bytes: bytes) -> str:
    """Store WAV bytes and return a short public id."""
    _prune()
    audio_id = secrets.token_urlsafe(12)
    _store[audio_id] = (wav_bytes, time.time())
    return audio_id


def get_audio(audio_id: str) -> bytes | None:
    _prune()
    entry = _store.get(audio_id)
    if not entry:
        return None
    return entry[0]


def _prune() -> None:
    now = time.time()
    expired = [k for k, (_, ts) in _store.items() if now - ts > _TTL_SECONDS]
    for k in expired:
        _store.pop(k, None)
