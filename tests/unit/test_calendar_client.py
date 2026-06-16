"""Unit tests for Cal.com client helpers."""

from services.calendar.client import local_slot_to_utc_iso, parse_booking_id


def test_parse_booking_id_nested():
    data = {"data": {"uid": "abc-123", "id": 91}}
    assert parse_booking_id(data) == "abc-123"


def test_parse_booking_id_v1_nested():
    data = {"booking": {"id": 91, "uid": "abc-123"}}
    assert parse_booking_id(data) == "abc-123"


def test_parse_booking_id_top_level():
    data = {"uid": "top-uid", "id": 5}
    assert parse_booking_id(data) == "top-uid"


def test_local_slot_to_utc_iso_ist():
    # 10:00 IST on 2026-06-16 → 04:30 UTC
    iso = local_slot_to_utc_iso("2026-06-16", "10:00", "Asia/Kolkata")
    assert iso == "2026-06-16T04:30:00.000Z"


def test_local_slot_to_utc_iso_evening():
    iso = local_slot_to_utc_iso("2026-06-16", "17:00", "Asia/Kolkata")
    assert iso == "2026-06-16T11:30:00.000Z"
