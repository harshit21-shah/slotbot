"""Async SQLite database operations via aiosqlite."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator

import aiosqlite

from services.config import settings
from services.db.models import CREATE_TABLES_SQL, CallLog, ClinicProfile
from services.telephony.phone import normalize_phone

logger = logging.getLogger(__name__)

_DB_PATH = settings.database_url


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        yield conn


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with get_db() as conn:
        await conn.executescript(CREATE_TABLES_SQL)
        await conn.commit()
    logger.info("Database initialised at %s", _DB_PATH)


# ── Clinic profiles ───────────────────────────────────────────────────────────

async def get_clinic_by_phone(phone_number: str) -> ClinicProfile | None:
    """Look up a clinic by its Twilio phone number (called on every inbound call)."""
    normalized = normalize_phone(phone_number)
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            SELECT * FROM clinic_profiles
            WHERE phone_number = ? OR phone_number = ?
            """,
            (phone_number, normalized),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ClinicProfile.from_row(dict(row))


async def get_clinic_by_id(clinic_id: str) -> ClinicProfile | None:
    async with get_db() as conn:
        cursor = await conn.execute(
            "SELECT * FROM clinic_profiles WHERE clinic_id = ?", (clinic_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ClinicProfile.from_row(dict(row))


async def upsert_clinic(clinic: ClinicProfile) -> None:
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO clinic_profiles
                (clinic_id, name, doctor_name, specialty, phone_number,
                 language_preference, business_hours, calcom_username,
                 calcom_event_type_id, emergency_number,
                 booking_lead_time_hours, greeting_template, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(clinic_id) DO UPDATE SET
                name                  = excluded.name,
                doctor_name           = excluded.doctor_name,
                specialty             = excluded.specialty,
                phone_number          = excluded.phone_number,
                language_preference   = excluded.language_preference,
                business_hours        = excluded.business_hours,
                calcom_username       = excluded.calcom_username,
                calcom_event_type_id  = excluded.calcom_event_type_id,
                emergency_number      = excluded.emergency_number,
                booking_lead_time_hours = excluded.booking_lead_time_hours,
                greeting_template     = excluded.greeting_template
            """,
            (
                clinic.clinic_id,
                clinic.name,
                clinic.doctor_name,
                clinic.specialty,
                clinic.phone_number,
                clinic.language_preference,
                json.dumps(clinic.business_hours),
                clinic.calcom_username,
                clinic.calcom_event_type_id,
                clinic.emergency_number,
                clinic.booking_lead_time_hours,
                clinic.greeting_template,
                clinic.created_at.isoformat(),
            ),
        )
        await conn.commit()


# ── Call logs ─────────────────────────────────────────────────────────────────

async def insert_call_log(log: CallLog) -> None:
    """Write a completed call log. Called async after call ends — not on hot path."""
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO call_logs
                (call_sid, clinic_id, caller_phone, outcome, booking_id,
                 transcript, duration_seconds, turn_count,
                 latency_p50_ms, latency_p95_ms, started_at, ended_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                log.call_sid,
                log.clinic_id,
                log.caller_phone,
                log.outcome,
                log.booking_id,
                json.dumps(log.transcript),
                log.duration_seconds,
                log.turn_count,
                log.latency_p50_ms,
                log.latency_p95_ms,
                log.started_at.isoformat(),
                log.ended_at.isoformat() if log.ended_at else None,
            ),
        )
        await conn.commit()


async def get_recent_call_logs(clinic_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            SELECT call_sid, caller_phone, outcome, booking_id,
                   turn_count, duration_seconds, started_at
            FROM call_logs
            WHERE clinic_id = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (clinic_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_call_stats(clinic_id: str) -> dict[str, Any]:
    """Aggregate stats for the health/dashboard endpoint."""
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            SELECT
                COUNT(*) AS total_calls,
                SUM(CASE WHEN outcome = 'booked' THEN 1 ELSE 0 END) AS booked,
                AVG(CASE WHEN latency_p50_ms IS NOT NULL THEN latency_p50_ms END) AS avg_latency_p50,
                AVG(duration_seconds) AS avg_duration
            FROM call_logs
            WHERE clinic_id = ?
            """,
            (clinic_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}
