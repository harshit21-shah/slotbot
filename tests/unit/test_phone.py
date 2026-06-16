"""Unit tests for phone normalization."""

from services.telephony.phone import is_valid_e164, normalize_phone


def test_normalize_indian_10_digit():
    assert normalize_phone("8275566293") == "+918275566293"


def test_normalize_with_plus():
    assert normalize_phone("+14244963860") == "+14244963860"


def test_is_valid_e164():
    assert is_valid_e164("+918275566293") is True
    assert is_valid_e164("AC00000000000000000000000000000001") is False
    assert is_valid_e164("") is False
