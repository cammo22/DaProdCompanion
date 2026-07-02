"""Test del riconoscimento del wake-word nella trascrizione."""

from __future__ import annotations

from stt_service.wake_word import contains_wake_word


def test_exact_match():
    assert contains_wake_word("ehi Babbasone che ore sono", "Babbasone")


def test_case_insensitive():
    assert contains_wake_word("BABBASONE dimmi una cosa", "Babbasone")


def test_close_transcription_variant_matches():
    # Refuso tipico di trascrizione, come osservato realmente con Whisper.
    assert contains_wake_word("babbaxone come stai", "Babbasone")


def test_no_match_when_name_absent():
    assert not contains_wake_word("che tempo fa oggi", "Babbasone")


def test_extra_variants_from_calibration_match():
    assert contains_wake_word("bab a sone ciao", "Babbasone", extra_variants=["bab a sone"])


def test_unrelated_short_word_does_not_false_positive():
    assert not contains_wake_word("ciao a tutti", "Babbasone")
