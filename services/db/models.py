"""SQLite schema definitions as dataclasses."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ClinicProfile:
    clinic_id: str
    name: str                        # "Dr. Sharma's Clinic"
    doctor_name: str                 # "Dr. Rahul Sharma"
    specialty: str                   # "General Physician"
    phone_number: str                # Twilio number for this clinic
    language_preference: str         # "hinglish" | "english" | "hindi"
    business_hours: dict[str, str]   # {"mon": "09:00-18:00", ...}
    calcom_username: str             # Cal.com account username
    calcom_event_type_id: int        # Cal.com event type ID
    emergency_number: str            # human to transfer to
    booking_lead_time_hours: int     # minimum notice required (e.g. 2)
    greeting_template: str           # customizable opening line
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ClinicProfile":
        return cls(
            clinic_id=row["clinic_id"],
            name=row["name"],
            doctor_name=row["doctor_name"],
            specialty=row["specialty"],
            phone_number=row["phone_number"],
            language_preference=row["language_preference"],
            business_hours=json.loads(row["business_hours"]),
            calcom_username=row["calcom_username"],
            calcom_event_type_id=row["calcom_event_type_id"],
            emergency_number=row["emergency_number"],
            booking_lead_time_hours=row["booking_lead_time_hours"],
            greeting_template=row["greeting_template"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


@dataclass
class CallLog:
    call_sid: str
    clinic_id: str
    caller_phone: str
    outcome: str                 # "booked" | "escalated" | "emergency" | "abandoned"
    booking_id: str | None
    transcript: list[dict[str, Any]]
    duration_seconds: float
    turn_count: int
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    started_at: datetime
    ended_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CallLog":
        return cls(
            call_sid=row["call_sid"],
            clinic_id=row["clinic_id"],
            caller_phone=row["caller_phone"],
            outcome=row["outcome"],
            booking_id=row["booking_id"],
            transcript=json.loads(row["transcript"]),
            duration_seconds=row["duration_seconds"],
            turn_count=row["turn_count"],
            latency_p50_ms=row["latency_p50_ms"],
            latency_p95_ms=row["latency_p95_ms"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        )


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS clinic_profiles (
    clinic_id             TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    doctor_name           TEXT NOT NULL,
    specialty             TEXT NOT NULL DEFAULT 'General Physician',
    phone_number          TEXT NOT NULL UNIQUE,
    language_preference   TEXT NOT NULL DEFAULT 'hinglish',
    business_hours        TEXT NOT NULL,   -- JSON
    calcom_username       TEXT NOT NULL,
    calcom_event_type_id  INTEGER NOT NULL,
    emergency_number      TEXT NOT NULL,
    booking_lead_time_hours INTEGER NOT NULL DEFAULT 2,
    greeting_template     TEXT NOT NULL,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS call_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sid          TEXT NOT NULL UNIQUE,
    clinic_id         TEXT NOT NULL REFERENCES clinic_profiles(clinic_id),
    caller_phone      TEXT NOT NULL,
    outcome           TEXT NOT NULL,
    booking_id        TEXT,
    transcript        TEXT NOT NULL,  -- JSON array
    duration_seconds  REAL NOT NULL DEFAULT 0,
    turn_count        INTEGER NOT NULL DEFAULT 0,
    latency_p50_ms    REAL,
    latency_p95_ms    REAL,
    started_at        TEXT NOT NULL,
    ended_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_call_logs_clinic ON call_logs(clinic_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_started ON call_logs(started_at);
"""
