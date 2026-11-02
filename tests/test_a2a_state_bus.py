import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import (
    CanonicalStateBus,
    VerifiedMilestone,
    DeadEndRecord,
)
from repo_investigator.bench_rotation.state_bus import (
    AsymmetricStateBus,
    FencingTokenRejectedError,
    JSONPatchError,
)

def test_state_bus_initialization_and_fencing():
    bus_data = CanonicalStateBus(
        workflow_id="task-9482",
        fencing_token=82,
        active_player="bench_agent_2",
        stint_number=2,
        goal="Refactor auth middleware to support rotating JWT keys without breaking session tests.",
        verified_milestones=[
            VerifiedMilestone(
                step=5,
                summary="Extracted key parser into src/auth/keys.py; unit tests passing.",
                commit_or_snapshot_id="cow-snap-001",
            )
        ],
        active_blockers=[
            "Integration test test_token_refresh fails with 401 when legacy token format is passed."
        ],
        dead_ends_log=[
            DeadEndRecord(
                stint=1,
                attempted_play="Modified jwt.decode() options to disable signature verification on fallback.",
                failure_reason="Triggered security linter failure and broke 4 downstream permission tests.",
                rule_out="Do not bypass signature verification in decode(); handle legacy key lookup in KeyProvider.",
            )
        ],
    )
    bus = AsymmetricStateBus(bus_data)

    # Initial token validation
    assert bus.validate_fencing_token(82) is True
    assert bus.validate_fencing_token(100) is True

    # Stale token rejection
    with pytest.raises(FencingTokenRejectedError):
        bus.validate_fencing_token(81)

    # Atomic increment on coach substitution
    new_token = bus.increment_fencing_token()
    assert new_token == 83
    assert bus.max_accepted_token == 83

    # Stale previous token 82 now rejected
    with pytest.raises(FencingTokenRejectedError):
        bus.validate_fencing_token(82)

def test_rfc_6902_json_patch_exact_spec_example():
    bus_data = CanonicalStateBus(
        workflow_id="task-9482",
        fencing_token=82,
        active_player="bench_agent_2",
        stint_number=2,
        goal="Refactor auth middleware",
        active_blockers=[
            "Integration test test_token_refresh fails with 401 when legacy token format is passed."
        ],
        dead_ends_log=[],
    )
    bus = AsymmetricStateBus(bus_data)

    # Exact RFC 6902 patch from memory.md lines 71-82
    patch = [
        {"op": "test", "path": "/fencing_token", "value": 82},
        {"op": "replace", "path": "/active_blockers/0", "value": "Resolved 401; now debugging race condition in Redis key cache."},
        {
            "op": "add",
            "path": "/dead_ends_log/-",
            "value": {
                "stint": 2,
                "attempted_play": "Added threading.Lock() around async Redis client call.",
                "failure_reason": "Blocked event loop and caused test timeout.",
                "rule_out": "Use asyncio.Lock() or Redis atomic Lua script instead of synchronous threading primitives.",
            },
        },
    ]

    updated = bus.apply_patch(patch, fencing_token=82)

    assert updated.active_blockers[0] == "Resolved 401; now debugging race condition in Redis key cache."
    assert len(updated.dead_ends_log) == 1
    assert updated.dead_ends_log[0].stint == 2
    assert "asyncio.Lock" in updated.dead_ends_log[0].rule_out

def test_rfc_6902_test_op_failure_aborts():
    bus_data = CanonicalStateBus(
        workflow_id="task-001",
        fencing_token=5,
        goal="Test goal",
    )
    bus = AsymmetricStateBus(bus_data)

    # Patch testing wrong fencing token
    bad_patch = [
        {"op": "test", "path": "/fencing_token", "value": 99},
        {"op": "replace", "path": "/goal", "value": "Changed"},
    ]

    with pytest.raises(JSONPatchError):
        bus.apply_patch(bad_patch, fencing_token=5)

    # State remained unchanged
    assert bus.state.goal == "Test goal"

def test_cow_snapshot_and_instantaneous_rollback(tmp_path: Path):
    test_file = tmp_path / "service.py"
    test_file.write_text("def valid(): return True\n", encoding="utf-8")

    bus_data = CanonicalStateBus(workflow_id="cow-test", fencing_token=1, goal="Snapshot test")
    bus = AsymmetricStateBus(bus_data)

    # Take verified snapshot
    snap = bus.take_cow_snapshot(step=1, workspace_dir=tmp_path)
    assert snap.snapshot_id.startswith("cow-snap-001")
    assert "service.py" in snap.file_contents

    # Corrupt workspace file
    test_file.write_text("def broken() Syntax Error !!!\n", encoding="utf-8")
    assert "Syntax Error" in test_file.read_text(encoding="utf-8")

    # Restore snapshot (~28ms simulation)
    restored = bus.restore_cow_snapshot(snap.snapshot_id, tmp_path)
    assert restored is True
    assert test_file.read_text(encoding="utf-8") == "def valid(): return True\n"

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

