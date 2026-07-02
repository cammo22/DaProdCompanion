"""
Test della pipeline vocale con motore/brain finti e un orologio finto per la
finestra di conversazione: verifica che il wake-word apra la finestra e che,
mentre resta aperta, i messaggi successivi vengano inoltrati senza ripetere
il nome, finche' non passano 5 minuti di silenzio.

Usa asyncio.run() direttamente invece di pytest-asyncio: il progetto non ha
quella dipendenza e non serve introdurla solo per questi test.
"""

from __future__ import annotations

import asyncio

import numpy as np

from stt_service.conversation_window import ConversationWindow
from stt_service.pipeline import VoicePipeline

DUMMY_AUDIO = np.zeros(1, dtype=np.float32)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeEngine:
    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio: np.ndarray) -> str:
        return self.text


class FakeBrain:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, text: str) -> None:
        self.sent.append(text)


def test_wake_word_is_forwarded():
    brain = FakeBrain()
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone, ciao"),
        brain=brain,
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=FakeClock()),
    )
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))
    assert brain.sent == ["Babbasone, ciao"]


def test_without_wake_word_and_not_awake_is_discarded():
    brain = FakeBrain()
    pipeline = VoicePipeline(
        engine=FakeEngine("che tempo fa oggi"),
        brain=brain,
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=FakeClock()),
    )
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))
    assert brain.sent == []


def test_follow_up_without_wake_word_forwarded_while_awake():
    clock = FakeClock()
    brain = FakeBrain()
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone, ciao"),
        brain=brain,
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=clock),
    )
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))  # apre la finestra

    pipeline._engine = FakeEngine("e domani che tempo fa")  # follow-up, niente wake-word
    clock.advance(60.0)
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))

    assert brain.sent == ["Babbasone, ciao", "e domani che tempo fa"]


def test_follow_up_extends_window_past_original_five_minutes():
    clock = FakeClock()
    brain = FakeBrain()
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone, ciao"),
        brain=brain,
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=clock),
    )
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))  # t=0, finestra aperta fino a t=300

    clock.advance(250.0)  # t=250, ancora nella finestra originale
    pipeline._engine = FakeEngine("e un'altra cosa")
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))  # riazzera la finestra fino a t=550

    clock.advance(250.0)  # t=500: oltre i 300s originali, ma dentro i 550 riazzerati
    pipeline._engine = FakeEngine("ancora senza dire il nome")
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))

    assert brain.sent == ["Babbasone, ciao", "e un'altra cosa", "ancora senza dire il nome"]


def test_discarded_again_once_window_expires():
    clock = FakeClock()
    brain = FakeBrain()
    pipeline = VoicePipeline(
        engine=FakeEngine("Babbasone, ciao"),
        brain=brain,
        bot_name="Babbasone",
        extra_variants=[],
        conversation_window=ConversationWindow(clock=clock),
    )
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))

    clock.advance(301.0)  # 5 minuti di silenzio: la finestra si e' chiusa
    pipeline._engine = FakeEngine("qualcosa senza il nome")
    asyncio.run(pipeline.handle_segment(DUMMY_AUDIO))

    assert brain.sent == ["Babbasone, ciao"]  # il secondo messaggio e' stato scartato
