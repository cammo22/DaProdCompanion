"""
Test del filtro anti-allucinazione con SegmentInfo sintetici — niente modello
Whisper vero caricato (stesso approccio del resto del progetto per il codice
che dipende da hardware/modelli pesanti: isola la logica pura e testa quella).
"""

from __future__ import annotations

from stt_service.engine.whisper_engine import SegmentInfo, filter_segments


def confident_segment(text: str) -> SegmentInfo:
    return SegmentInfo(text=text, no_speech_prob=0.05, avg_logprob=-0.2)


def uncertain_segment(text: str) -> SegmentInfo:
    return SegmentInfo(text=text, no_speech_prob=0.85, avg_logprob=-1.5)


def test_confident_real_speech_is_kept():
    result = filter_segments([confident_segment("Babbasone, come va?")])
    assert result == "Babbasone, come va?"


def test_low_confidence_segment_is_dropped():
    result = filter_segments([uncertain_segment("qualcosa di poco chiaro")])
    assert result == ""


def test_known_hallucination_dropped_even_with_high_confidence():
    # Il caso reale osservato: Whisper riproduce questa frase con confidenza
    # alta (l'ha vista tantissime volte in training), quindi il filtro di
    # confidenza da solo non basterebbe.
    segment = confident_segment("Sottotitoli a cura di QTSS")
    result = filter_segments([segment])
    assert result == ""


def test_known_hallucination_case_and_punctuation_insensitive():
    segment = confident_segment("sottotitoli a cura di qtss.")
    assert filter_segments([segment]) == ""


def test_empty_text_segment_is_skipped():
    result = filter_segments([confident_segment("")])
    assert result == ""


def test_multiple_segments_join_kept_text_only():
    segments = [
        confident_segment("Allora dicevo"),
        uncertain_segment("rumore di fondo"),
        confident_segment("che tutto bene"),
    ]
    result = filter_segments(segments)
    assert result == "Allora dicevo che tutto bene"


def test_mixed_no_speech_high_but_confident_tokens_is_kept():
    # no_speech_prob alto da solo non basta a scartare: serve anche
    # avg_logprob basso, altrimenti si perderebbe parlato reale ma sommesso.
    segment = SegmentInfo(text="ok va bene", no_speech_prob=0.7, avg_logprob=-0.3)
    assert filter_segments([segment]) == "ok va bene"
