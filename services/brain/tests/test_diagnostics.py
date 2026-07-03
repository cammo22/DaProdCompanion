"""
Test della diagnostica prerequisiti. La parte di rete (fetch verso Ollama)
non e' testata qui (dipende da un'istanza reale, verificata dal vivo); si
testa la logica pura: il confronto tra tag configurato e modelli installati,
e i messaggi/azioni prodotti per ogni combinazione di problemi.
"""

from __future__ import annotations

from brain_service.diagnostics import DiagnosticsResult, _model_is_installed


def test_exact_match_is_installed():
    assert _model_is_installed("gemma4:e4b-it-qat", ["gemma4:e4b-it-qat", "nomic-embed-text:latest"])


def test_implicit_latest_tag_matches_installed_latest():
    # In .env il modello e' scritto senza ':latest', Ollama lo elenca con ':latest'.
    assert _model_is_installed("nomic-embed-text", ["nomic-embed-text:latest"])


def test_missing_model_is_not_installed():
    assert not _model_is_installed("gemma4:e4b-it-qat", ["qualcosaltro:latest"])


def test_blank_tag_is_never_installed():
    assert not _model_is_installed("", ["gemma4:e4b-it-qat"])


def test_tag_with_explicit_version_does_not_match_different_version():
    # 'gemma4:e2b' non deve combaciare con 'gemma4:e4b' installato.
    assert not _model_is_installed("gemma4:e2b-it-qat", ["gemma4:e4b-it-qat"])


def test_problems_empty_when_all_ok():
    result = DiagnosticsResult(
        ollama_reachable=True,
        brain_model_present=True,
        embedding_model_present=True,
        brain_model_tag="gemma4:e4b-it-qat",
        embedding_model_tag="nomic-embed-text",
        installed_models=["gemma4:e4b-it-qat", "nomic-embed-text:latest"],
    )
    assert result.all_ok
    assert result.problems() == []


def test_ollama_unreachable_short_circuits_other_problems():
    result = DiagnosticsResult(
        ollama_reachable=False,
        brain_model_present=False,
        embedding_model_present=False,
        brain_model_tag="gemma4:e4b-it-qat",
        embedding_model_tag="nomic-embed-text",
        installed_models=[],
    )
    problems = result.problems()
    assert len(problems) == 1
    assert "Ollama" in problems[0]


def test_missing_models_produce_pull_instructions():
    result = DiagnosticsResult(
        ollama_reachable=True,
        brain_model_present=False,
        embedding_model_present=False,
        brain_model_tag="gemma4:e4b-it-qat",
        embedding_model_tag="nomic-embed-text",
        installed_models=["qualcosaltro"],
    )
    problems = result.problems()
    assert len(problems) == 2
    assert any("ollama pull gemma4:e4b-it-qat" in p for p in problems)
    assert any("ollama pull nomic-embed-text" in p for p in problems)
