"""Test della correzione del nome e della ripulitura del testo per il TTS."""

from __future__ import annotations

from brain_service.conversation.text_sanitize import (
    correct_bot_name,
    prepare_for_speech,
    strip_emoji,
    strip_markdown_emphasis,
)


def test_correct_bot_name_fixes_one_letter_typo():
    text = "Mi chiamo Babbaxone! Sono felice di conoscerti."
    assert correct_bot_name(text, "Babbasone") == "Mi chiamo Babbasone! Sono felice di conoscerti."


def test_correct_bot_name_leaves_correct_name_untouched():
    text = "Sono Babbasone, il tuo companion."
    assert correct_bot_name(text, "Babbasone") == text


def test_correct_bot_name_leaves_unrelated_words_untouched():
    text = "Oggi il tempo e' bellissimo fuori."
    assert correct_bot_name(text, "Babbasone") == text


def test_strip_emoji_removes_emoji_but_keeps_text():
    text = "Ciao! 😊 Come stai oggi? ✨"
    assert strip_emoji(text) == "Ciao! Come stai oggi?"


def test_strip_emoji_no_emoji_present():
    text = "Nessuna emoji qui."
    assert strip_emoji(text) == text


def test_strip_markdown_emphasis_removes_bold_and_italic_asterisks():
    text = "Ho segnato che il tuo numero e' **22** e mi piace *molto* ricordarlo."
    assert strip_markdown_emphasis(text) == "Ho segnato che il tuo numero e' 22 e mi piace molto ricordarlo."


def test_prepare_for_speech_strips_both_emoji_and_asterisks():
    text = "Perfetto! 😊 Ho segnato **Paolo** come tuo amico. ✨"
    assert prepare_for_speech(text) == "Perfetto! Ho segnato Paolo come tuo amico."
