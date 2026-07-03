"""
Test del wrapper di sandboxing filesystem: e' il modulo con zero tolleranza per
bug ("nessuna eccezione, nemmeno per comodita' di debug"), quindi ha una
copertura dedicata anche se il resto del progetto non ne ha ancora in Fase 1.
"""

from __future__ import annotations

import sqlite3

import pytest

from companion_shared.sandbox import FilesystemGuard, SandboxViolation, audit_log, policy


@pytest.fixture
def sandbox_root(tmp_path):
    return tmp_path / "sandbox"


@pytest.fixture
def guard(sandbox_root):
    return FilesystemGuard(sandbox_root, service="test")


def test_path_inside_sandbox_is_allowed(guard, sandbox_root):
    resolved = guard.resolve_and_check("notes.txt")
    assert resolved == (sandbox_root / "notes.txt").resolve()


def test_path_outside_sandbox_is_blocked(guard, tmp_path):
    outside = tmp_path / "outside" / "secret.txt"
    with pytest.raises(SandboxViolation):
        guard.resolve_and_check(outside)


def test_whitelisted_path_outside_sandbox_is_allowed(guard, sandbox_root, tmp_path):
    outside = tmp_path / "outside" / "shared.txt"
    policy.add_entry(sandbox_root, outside, reason="test esplicito")

    resolved = guard.resolve_and_check(outside)
    assert resolved == outside.resolve()


def test_open_sandboxed_writes_inside_sandbox(guard, sandbox_root):
    with guard.open_sandboxed("subdir/file.txt", "w") as f:
        f.write("ciao")
    assert (sandbox_root / "subdir" / "file.txt").read_text() == "ciao"


def test_open_sandboxed_outside_sandbox_is_blocked(guard, tmp_path):
    outside = tmp_path / "outside" / "file.txt"
    with pytest.raises(SandboxViolation):
        guard.open_sandboxed(outside, "r")


def test_delete_sandboxed_removes_file(guard, sandbox_root):
    with guard.open_sandboxed("to-delete.txt", "w") as f:
        f.write("ciao")
    guard.delete_sandboxed("to-delete.txt")
    assert not (sandbox_root / "to-delete.txt").exists()


def test_delete_sandboxed_removes_directory_recursively(guard, sandbox_root):
    with guard.open_sandboxed("dir/nested.txt", "w") as f:
        f.write("ciao")
    guard.delete_sandboxed("dir")
    assert not (sandbox_root / "dir").exists()


def test_delete_sandboxed_missing_path_is_a_no_op(guard):
    guard.delete_sandboxed("never-existed.txt")  # non deve sollevare eccezioni


def test_delete_sandboxed_outside_sandbox_is_blocked(guard, tmp_path):
    outside = tmp_path / "outside" / "file.txt"
    with pytest.raises(SandboxViolation):
        guard.delete_sandboxed(outside)


def test_audit_log_mirrors_allow_and_deny_to_db_when_sink_attached(guard, tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE sandbox_access_log (id INTEGER PRIMARY KEY, timestamp TEXT, "
        "service TEXT, requested_path TEXT, allowed INTEGER, reason TEXT)"
    )
    audit_log.attach_db_sink(conn)
    try:
        guard.resolve_and_check("allowed.txt")
        with pytest.raises(SandboxViolation):
            guard.resolve_and_check(tmp_path / "outside" / "denied.txt")

        rows = conn.execute(
            "SELECT allowed FROM sandbox_access_log ORDER BY id"
        ).fetchall()
        assert [row[0] for row in rows] == [1, 0]
    finally:
        audit_log.detach_db_sink()
