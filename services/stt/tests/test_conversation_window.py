"""Test della finestra di conversazione con un orologio finto (niente attese reali di 5 minuti)."""

from __future__ import annotations

from stt_service.conversation_window import ConversationWindow


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_not_awake_before_any_wake_word():
    window = ConversationWindow(clock=FakeClock())
    assert window.is_awake() is False


def test_awake_immediately_after_extend():
    window = ConversationWindow(clock=FakeClock())
    window.extend()
    assert window.is_awake() is True


def test_still_awake_just_before_five_minutes():
    clock = FakeClock()
    window = ConversationWindow(clock=clock)
    window.extend()
    clock.advance(299.0)
    assert window.is_awake() is True


def test_asleep_after_five_minutes_of_silence():
    clock = FakeClock()
    window = ConversationWindow(clock=clock)
    window.extend()
    clock.advance(300.0)
    assert window.is_awake() is False


def test_extend_resets_the_timer():
    clock = FakeClock()
    window = ConversationWindow(clock=clock)
    window.extend()
    clock.advance(250.0)
    window.extend()  # nuovo scambio: il timer riparte da qui
    clock.advance(250.0)
    assert window.is_awake() is True  # solo 250s dall'ultimo extend, non 500s dal primo
