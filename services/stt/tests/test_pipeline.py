"""
Test della pipeline vocale con motore/brain finti e un orologio finto per la
finestra di conversazione: verifica che il wake-word apra la finestra, che i
messaggi successivi vengano inoltrati senza ripetere il nome finche' resta
aperta, e che un discorso lungo troncato dal tetto massimo di SpeechSegmenter
venga accodato e inviato come un unico messaggio invece di piu' messaggi
separati.

Usa asyncio.run() direttamente invece di pytest-asyncio: il progetto non ha
quella dipendenza e non serve introdurla solo per questi test. merge_window_seconds
e' tenuto piccolissimo nei test che devono davvero aspettare il timeout, cosi'
non si aspettano i 3 secondi reali di produzione.
"""

from __future__ import annotations

import asyncio

import numpy as np

from stt_service.audio.segmenter import SpeechSegment
from stt_service.conversation_window import ConversationWindow
from stt_service.pipeline import VoicePipeline

DUMMY_AUDIO = np.zeros(1, dtype=np.float32)


def silence_segment() -> SpeechSegment:
    return SpeechSegment(audio=DUMMY_AUDIO, ended_by_silence=True)


def forced_cut_segment() -> SpeechSegment:
    return SpeechSegment(audio=DUMMY_AUDIO, ended_by_silence=False)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeEngine:
    def __init__(self, *texts: str) -> None:
        self._texts = list(texts)

    def transcribe(self, audio: np.ndarray) -> str:
        return self._texts.pop(0)


class FakeBrain:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, text: str) -> None:
        self.sent.append(text)


def make_pipeline(*texts: str, clock: FakeClock | None = None, merge_window_seconds: float = 3.0) -> tuple[VoicePipeline, FakeBrain]:
    brain = FakeBrain()
    pipeline = VoicePipeline(
        engine=FakeEngine(*texts),
        brain=brain,
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=clock or FakeClock()),
        merge_window_seconds=merge_window_seconds,
    )
    return pipeline, brain


def test_wake_word_segment_ended_by_silence_is_sent_immediately():
    pipeline, brain = make_pipeline("Babbasone, ciao")
    asyncio.run(pipeline.handle_segment(silence_segment()))
    assert brain.sent == ["Babbasone, ciao"]


def test_without_wake_word_and_not_awake_is_discarded():
    pipeline, brain = make_pipeline("che tempo fa oggi")
    asyncio.run(pipeline.handle_segment(silence_segment()))
    assert brain.sent == []


def test_on_wake_word_callback_fires_when_wake_word_detected():
    calls: list[int] = []
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone, ciao"),
        brain=FakeBrain(),
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=FakeClock()),
        on_wake_word=lambda: calls.append(1),
    )
    asyncio.run(pipeline.handle_segment(silence_segment()))
    assert calls == [1]


def test_on_wake_word_callback_does_not_fire_without_wake_word():
    clock = FakeClock()
    calls: list[int] = []
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone, ciao", "e domani che tempo fa"),
        brain=FakeBrain(),
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=clock),
        on_wake_word=lambda: calls.append(1),
    )
    asyncio.run(pipeline.handle_segment(silence_segment()))  # apre la finestra: 1 chiamata
    clock.advance(10.0)
    asyncio.run(pipeline.handle_segment(silence_segment()))  # continuazione senza nome: nessuna nuova chiamata
    assert calls == [1]


def test_follow_up_without_wake_word_forwarded_while_awake():
    clock = FakeClock()
    pipeline, brain = make_pipeline("Babbasone, ciao", "e domani che tempo fa", clock=clock)

    asyncio.run(pipeline.handle_segment(silence_segment()))  # apre la finestra
    clock.advance(60.0)
    asyncio.run(pipeline.handle_segment(silence_segment()))

    assert brain.sent == ["Babbasone, ciao", "e domani che tempo fa"]


def test_discarded_again_once_conversation_window_expires():
    clock = FakeClock()
    pipeline, brain = make_pipeline("Babbasone, ciao", "qualcosa senza il nome", clock=clock)

    asyncio.run(pipeline.handle_segment(silence_segment()))
    clock.advance(301.0)  # 5 minuti di silenzio: la finestra si e' chiusa
    asyncio.run(pipeline.handle_segment(silence_segment()))

    assert brain.sent == ["Babbasone, ciao"]  # il secondo messaggio e' stato scartato


def test_forced_cut_then_silence_end_merges_into_one_message():
    # Discorso lungo: il primo pezzo tocca il tetto massimo (ended_by_silence=
    # False), il secondo e' la sua reale conclusione (ended_by_silence=True).
    # Devono arrivare a brain come UN SOLO messaggio, non due.
    pipeline, brain = make_pipeline("Babbasone volevo dirti che oggi", "ho fatto una passeggiata")

    async def run() -> None:
        await pipeline.handle_segment(forced_cut_segment())
        await pipeline.handle_segment(silence_segment())

    asyncio.run(run())

    assert brain.sent == ["Babbasone volevo dirti che oggi ho fatto una passeggiata"]


def test_forced_cut_flushes_alone_after_merge_window_if_no_continuation():
    # Se dopo il taglio forzato non arriva nessun seguito, va comunque
    # inviato quello che si ha (non deve restare bloccato per sempre).
    # merge_window_seconds e' ridotto apposta per non aspettare 3 secondi
    # veri; handle_segment e l'attesa devono girare nello stesso event loop,
    # altrimenti asyncio.run() cancella il task di flush schedulato in
    # background non appena la prima chiamata ritorna.
    pipeline, brain = make_pipeline("Babbasone dicevo che", merge_window_seconds=0.01)

    async def run() -> None:
        await pipeline.handle_segment(forced_cut_segment())
        await asyncio.sleep(0.05)

    asyncio.run(run())
    assert brain.sent == ["Babbasone dicevo che"]


def test_partial_transcript_callback_grows_with_each_pending_part():
    previews: list[str] = []
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone dicevo che", "ho fatto una passeggiata"),
        brain=FakeBrain(),
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=FakeClock()),
        on_partial_transcript=lambda text: previews.append(text),
    )

    async def run() -> None:
        await pipeline.handle_segment(forced_cut_segment())
        await pipeline.handle_segment(silence_segment())

    asyncio.run(run())

    assert previews[0] == "Babbasone dicevo che"
    assert previews[1] == "Babbasone dicevo che ho fatto una passeggiata"
    assert previews[-1] == ""  # cancellata subito prima dell'invio finale


def test_partial_transcript_callback_fires_and_clears_for_manual_recording():
    previews: list[str] = []
    pipeline = VoicePipeline(
        engine=FakeEngine("ciao babbasone"),
        brain=FakeBrain(),
        bot_name="Babbasone",
        extra_variants=[],
        on_partial_transcript=lambda text: previews.append(text),
    )
    asyncio.run(pipeline.handle_manual_recording(DUMMY_AUDIO))
    assert previews == ["ciao babbasone", ""]


def test_three_forced_cuts_in_a_row_still_merge_into_one_message():
    pipeline, brain = make_pipeline("Babbasone allora", "ti volevo dire", "che tutto bene")

    async def run() -> None:
        await pipeline.handle_segment(forced_cut_segment())
        await pipeline.handle_segment(forced_cut_segment())
        await pipeline.handle_segment(silence_segment())

    asyncio.run(run())

    assert brain.sent == ["Babbasone allora ti volevo dire che tutto bene"]
