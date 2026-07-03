"""
Test di MicMuteState: il caso interessante e' che 'speaking' e' un contatore,
non un bool semplice, perche' avatar e finestra chat possono riprodurre audio
TTS in modo indipendente e sovrapposto (es. annuncio di un sogno sull'avatar
mentre l'utente manda un messaggio di testo) — con un bool, la prima
riproduzione a finire smuterebbe il microfono mentre l'altra sta ancora
suonando. Stesso pattern di bug gia' risolto in DreamingScheduler.
"""

from __future__ import annotations

from stt_service.api.http import MicMuteState


def test_manual_mute_is_independent_of_speaking():
    state = MicMuteState()
    state.manual_muted = True
    assert state.muted is True
    state.set_speaking(True)
    state.set_speaking(False)
    assert state.muted is True  # il mute manuale non e' toccato dal ciclo speaking


def test_speaking_mute_and_unmute():
    state = MicMuteState()
    assert state.muted is False
    state.set_speaking(True)
    assert state.muted is True
    state.set_speaking(False)
    assert state.muted is False


def test_overlapping_speaking_playbacks_both_must_end_before_unmute():
    # Scenario reale: l'avatar inizia a riprodurre (es. annuncio di un sogno),
    # poi la finestra chat inizia un'altra riproduzione, poi quella dell'avatar
    # finisce PRIMA. Il microfono deve restare mutato finche' anche l'altra
    # non e' finita.
    state = MicMuteState()
    state.set_speaking(True)  # avatar inizia
    state.set_speaking(True)  # chat inizia
    state.set_speaking(False)  # avatar finisce
    assert state.muted is True  # chat sta ancora suonando

    state.set_speaking(False)  # chat finisce
    assert state.muted is False


def test_quantum_and_manual_mute_remain_independent_flags():
    state = MicMuteState()
    state.quantum_muted = True
    assert state.muted is True
    state.manual_muted = True
    state.quantum_muted = False
    assert state.muted is True  # il manuale resta attivo
