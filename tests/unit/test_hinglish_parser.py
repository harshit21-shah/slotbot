"""Unit tests for Hinglish rule-based parser."""

from datetime import date

from services.agents.hinglish_parser import (
    extract_datetime,
    extract_name,
    extract_reason,
    is_confirm_yes,
    parse_confirm,
    wants_appointment,
)


def test_extract_name_patterns():
    assert extract_name("main Rahul hoon") == "Rahul"
    assert extract_name("mera naam Priya hai") == "Priya"
    assert extract_name("Rahul") == "Rahul"
    assert extract_name("appointment chahiye") is None


def test_extract_datetime_kal_subah():
    d, t = extract_datetime("kal subah 10 baje", today=date(2026, 6, 15))
    assert d == "2026-06-16"
    assert t == "10:00"


def test_extract_datetime_aaj_sham():
    d, t = extract_datetime("aaj sham 5 baje", today=date(2026, 6, 15))
    assert d == "2026-06-15"
    assert t == "17:00"


def test_extract_datetime_dopahar_hour():
    d, t = extract_datetime("kal dopahar 3 baje", today=date(2026, 6, 15))
    assert d == "2026-06-16"
    assert t == "15:00"


def test_wants_appointment():
    assert wants_appointment("mujhe appointment chahiye") is True
    assert wants_appointment("doctor se milna hai") is True


def test_extract_reason():
    assert extract_reason("bukhar hai") == "fever/cold"
    assert extract_reason("general checkup") == "general checkup"


def test_extract_name_rejects_yes():
    assert extract_name("Haan") is None
    assert extract_name("Yes") is None


def test_confirm_yes():
    assert is_confirm_yes("haan sahi hai") is True
    assert is_confirm_yes("theek hai") is True


def test_parse_confirm_denial_wins():
    assert parse_confirm("nahi theek nahi") == "no"
    assert parse_confirm("correct nahi hai") == "no"
    assert parse_confirm("haan bilkul") == "yes"
