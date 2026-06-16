"""In-memory call session store. Sessions expire after 10 minutes."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 600  # 10 minutes


@dataclass
class ActiveSession:
    call_sid: str
    clinic_id: str
    caller_phone: str
    language: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: float = field(default_factory=time.monotonic)

    # LangGraph thread config (passed to every graph.ainvoke call)
    @property
    def graph_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.call_sid}}


class SessionStore:
    """Thread-safe in-memory store keyed by Twilio CallSid."""

    def __init__(self) -> None:
        self._sessions: dict[str, ActiveSession] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        call_sid: str,
        clinic_id: str,
        caller_phone: str,
        language: str,
    ) -> ActiveSession:
        session = ActiveSession(
            call_sid=call_sid,
            clinic_id=clinic_id,
            caller_phone=caller_phone,
            language=language,
        )
        async with self._lock:
            self._sessions[call_sid] = session
        logger.info("Session created: %s (clinic=%s)", call_sid, clinic_id)
        return session

    async def get(self, call_sid: str) -> ActiveSession | None:
        async with self._lock:
            session = self._sessions.get(call_sid)
            if session:
                # Check TTL
                if time.monotonic() - session.last_activity > _SESSION_TTL_SECONDS:
                    logger.warning("Session expired: %s", call_sid)
                    del self._sessions[call_sid]
                    return None
                session.last_activity = time.monotonic()
            return session

    async def remove(self, call_sid: str) -> ActiveSession | None:
        async with self._lock:
            return self._sessions.pop(call_sid, None)

    async def count(self) -> int:
        async with self._lock:
            return len(self._sessions)


# Module-level singleton
session_store = SessionStore()
