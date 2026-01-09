"""Tests for Memory v0 isolation and propose/commit pattern."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory import MemoryManager, MemoryType, SessionMemory


def test_session_memory_does_not_persist_to_backend():
    mm = MemoryManager(backend=None)
    proposal = mm.propose_write(MemoryType.SESSION, "test_key", "test_value")
    mm.commit_write(proposal)

    results = mm.query(MemoryType.SESSION, key="test_key")
    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    assert results[0]["value"] == "test_value"
    print("PASS: test_session_memory_does_not_persist_to_backend")


def test_boot_context_is_readonly():
    mm = MemoryManager(backend=None)
    proposal = mm.propose_write(MemoryType.BOOT_CONTEXT, "system_role", "test")
    success = mm.commit_write(proposal)
    assert success is False, "BOOT_CONTEXT should be readonly"
    print("PASS: test_boot_context_is_readonly")


def test_boot_context_not_queryable():
    mm = MemoryManager(backend=None)
    results = mm.query(MemoryType.BOOT_CONTEXT)
    assert results == [], "BOOT_CONTEXT should not be queryable"
    print("PASS: test_boot_context_not_queryable")


def test_user_profile_requires_backend():
    mm = MemoryManager(backend=None)
    proposal = mm.propose_write(MemoryType.USER_PROFILE, "pref", "dark_mode")
    success = mm.commit_write(proposal)
    assert success is False, "USER_PROFILE requires backend"
    print("PASS: test_user_profile_requires_backend")


def test_uncommitted_proposals_not_visible():
    mm = MemoryManager(backend=None)
    mm.propose_write(MemoryType.SESSION, "pending_key", "pending_value")

    results = mm.query(MemoryType.SESSION, key="pending_key")
    assert len(results) == 0, "Uncommitted proposals should not be visible"
    print("PASS: test_uncommitted_proposals_not_visible")


def test_commit_removes_from_pending():
    mm = MemoryManager(backend=None)
    proposal = mm.propose_write(MemoryType.SESSION, "key", "value")
    assert mm.pending_count == 1

    mm.commit_write(proposal)
    assert mm.pending_count == 0
    print("PASS: test_commit_removes_from_pending")


def test_reject_removes_from_pending():
    mm = MemoryManager(backend=None)
    proposal = mm.propose_write(MemoryType.SESSION, "key", "value")
    assert mm.pending_count == 1

    mm.reject_proposal(proposal, "test rejection")
    assert mm.pending_count == 0
    print("PASS: test_reject_removes_from_pending")


def test_cannot_commit_non_pending_proposal():
    mm = MemoryManager(backend=None)
    proposal = mm.propose_write(MemoryType.SESSION, "key", "value")
    mm.commit_write(proposal)

    success = mm.commit_write(proposal)
    assert success is False, "Should not commit same proposal twice"
    print("PASS: test_cannot_commit_non_pending_proposal")


def test_capability_tracking():
    sm = SessionMemory(session_id="test-1")
    assert not sm.has_capability("READ_UPLOADS")

    sm.grant_capability("READ_UPLOADS")
    assert sm.has_capability("READ_UPLOADS")
    print("PASS: test_capability_tracking")


def test_running_summary_limits_to_10():
    sm = SessionMemory(session_id="test-2")
    for i in range(15):
        sm.add_summary_point(f"Point {i}")

    assert len(sm.running_summary) == 10, f"Expected 10, got {len(sm.running_summary)}"
    assert sm.running_summary[0] == "Point 5"
    print("PASS: test_running_summary_limits_to_10")


def test_clear_resets_all():
    sm = SessionMemory(session_id="test-3")
    sm.batch_id = "batch-123"
    sm.grant_capability("READ_UPLOADS")
    sm.set("custom", "data")

    sm.clear()

    assert sm.batch_id is None
    assert not sm.has_capability("READ_UPLOADS")
    assert sm.get("custom") is None
    print("PASS: test_clear_resets_all")


if __name__ == "__main__":
    tests = [
        test_session_memory_does_not_persist_to_backend,
        test_boot_context_is_readonly,
        test_boot_context_not_queryable,
        test_user_profile_requires_backend,
        test_uncommitted_proposals_not_visible,
        test_commit_removes_from_pending,
        test_reject_removes_from_pending,
        test_cannot_commit_non_pending_proposal,
        test_capability_tracking,
        test_running_summary_limits_to_10,
        test_clear_resets_all,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    if failed > 0:
        exit(1)
