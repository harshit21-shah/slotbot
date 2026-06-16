"""Unit tests for mulaw audio conversion utilities."""

from __future__ import annotations

import pytest

from services.tts.sarvam_client import _generate_silence, _pcm_to_mulaw_8k


class TestMulawConversion:
    def test_silence_has_correct_length(self) -> None:
        # 200ms at 8kHz = 1600 samples, mulaw = 1 byte per sample
        silence = _generate_silence(200)
        assert len(silence) == 1600

    def test_silence_500ms(self) -> None:
        silence = _generate_silence(500)
        assert len(silence) == 4000

    def test_pcm_to_mulaw_produces_bytes(self) -> None:
        pcm = b"\x00\x00" * 160  # 160 samples of silence
        mulaw = _pcm_to_mulaw_8k(pcm)
        assert isinstance(mulaw, bytes)
        assert len(mulaw) == 160  # 1 byte per sample in mulaw

    def test_pcm_to_mulaw_non_empty_audio(self) -> None:
        # Simple sine-like pattern
        import struct
        pcm = struct.pack("<160h", *[int(10000 * (i % 2 == 0) - 5000) for i in range(160)])
        mulaw = _pcm_to_mulaw_8k(pcm)
        assert len(mulaw) == 160
