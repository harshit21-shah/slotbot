"""Health check and basic stats endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.agents.session import session_store
from services.db.database import get_call_stats

router = APIRouter()

_START_TIME = time.time()


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({
        "status": "ok",
        "uptime_seconds": round(time.time() - _START_TIME),
        "active_calls": await session_store.count(),
    })


@router.get("/stats/{clinic_id}")
async def clinic_stats(clinic_id: str) -> JSONResponse:
    stats = await get_call_stats(clinic_id)
    return JSONResponse(stats)
