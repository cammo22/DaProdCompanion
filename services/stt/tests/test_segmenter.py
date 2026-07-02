"""Test del segmentatore RMS con blocchi audio sintetici (silenzio/rumore)."""

from __future__ import annotations

import numpy as np

from stt_service.audio.segmenter import SpeechSegmenter

BLOCK_SIZE = 8000  # 0.5s a 16kHz


def loud_block() -> np.ndarray:
    rng = np.random.default_rng(42)
    return (rng.random(BLOCK_SIZE, dtype=np.float32) - 0.5) * 0.8  # RMS ben sopra soglia


def silent_block() -> np.ndarray:
    return np.zeros(BLOCK_SIZE, dtype=np.float32)


def test_pure_silence_never_finalizes():
    segmenter = SpeechSegmenter()
    for _ in range(10):
        assert segmenter.push_block(silent_block()) is None


def test_speech_then_silence_finalizes_with_concatenated_audio():
    segmenter = SpeechSegmenter()
    for _ in range(3):
        assert segmenter.push_block(loud_block()) is None

    result = None
    for _ in range(8):
        result = segmenter.push_block(silent_block())
        if result is not None:
            break

    assert result is not None
    assert result.ended_by_silence is True
    # 3 blocchi di parlato + qualche blocco di silenzio incluso come coda
    assert len(result.audio) >= BLOCK_SIZE * 3


def test_too_short_blip_is_discarded():
    segmenter = SpeechSegmenter()
    segmenter.push_block(loud_block())  # un solo blocco: sotto MIN_SPEECH_BLOCKS
    result = None
    for _ in range(8):
        result = segmenter.push_block(silent_block())
        if result is not None:
            break
    assert result is None


def test_is_speaking_reflects_current_state():
    segmenter = SpeechSegmenter()
    assert segmenter.is_speaking is False

    segmenter.push_block(loud_block())
    assert segmenter.is_speaking is True

    for _ in range(8):
        segmenter.push_block(silent_block())
    assert segmenter.is_speaking is False


def test_is_speaking_stays_false_for_a_discarded_blip():
    segmenter = SpeechSegmenter()
    segmenter.push_block(loud_block())  # un solo blocco: sotto MIN_SPEECH_BLOCKS
    assert segmenter.is_speaking is True  # ancora "in ascolto" mentre il blip e' in corso

    for _ in range(8):
        segmenter.push_block(silent_block())
    # anche se il blip finisce scartato (return None), lo stato "in ascolto"
    # deve comunque chiudersi: e' quello che pilota l'avatar in capture.py.
    assert segmenter.is_speaking is False


def test_segmenter_resets_after_finalizing_and_can_detect_a_second_utterance():
    segmenter = SpeechSegmenter()
    for _ in range(3):
        segmenter.push_block(loud_block())
    first = None
    for _ in range(8):
        first = segmenter.push_block(silent_block())
        if first is not None:
            break
    assert first is not None

    for _ in range(3):
        segmenter.push_block(loud_block())
    second = None
    for _ in range(8):
        second = segmenter.push_block(silent_block())
        if second is not None:
            break
    assert second is not None


def test_long_continuous_speech_is_cut_by_the_max_length_cap_not_silence():
    # Un discorso continuo senza mai fermarsi tocca il tetto massimo di
    # sicurezza (240 blocchi): il segmento risultante deve segnalare che non
    # e' stata una pausa reale a chiuderlo, cosi' pipeline.py sa che
    # potrebbe arrivare un seguito invece di trattarlo come un enunciato
    # completo a se' stante.
    segmenter = SpeechSegmenter()
    result = None
    for _ in range(240):
        result = segmenter.push_block(loud_block())
        if result is not None:
            break

    assert result is not None
    assert result.ended_by_silence is False
    assert len(result.audio) == BLOCK_SIZE * 240
