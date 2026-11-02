import sys
import threading
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import CanonicalStateBus
from repo_investigator.bench_rotation.state_bus import (
    AsymmetricStateBus,
    FencingTokenRejectedError,
    JSONPatchError,
)

def test_attack_negative_array_index_in_patch():
    bus = CanonicalStateBus(workflow_id="wf-neg", fencing_token=1, goal="test", active_blockers=["b1", "b2"])
    asb = AsymmetricStateBus(bus)

    # RFC 6902 forbids negative array index (except '-' for append)
    bad_patch = [{"op": "replace", "path": "/active_blockers/-1", "value": "bad"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_patch)

def test_attack_out_of_bounds_array_index():
    bus = CanonicalStateBus(workflow_id="wf-oob", fencing_token=1, goal="test", active_blockers=["b1"])
    asb = AsymmetricStateBus(bus)

    bad_patch = [{"op": "replace", "path": "/active_blockers/999", "value": "bad"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_patch)

    bad_remove = [{"op": "remove", "path": "/active_blockers/999"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_remove)

def test_attack_non_container_traversal():
    bus = CanonicalStateBus(workflow_id="wf-leaf", fencing_token=1, goal="simple string")
    asb = AsymmetricStateBus(bus)

    # Trying to traverse into a string as if it's a dict/list
    bad_patch = [{"op": "add", "path": "/goal/invalid_subfield", "value": "bad"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_patch)

def test_attack_move_copy_nonexistent_from():
    bus = CanonicalStateBus(workflow_id="wf-move", fencing_token=1, goal="test")
    asb = AsymmetricStateBus(bus)

    bad_move = [{"op": "move", "from": "/nonexistent_field", "path": "/goal"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_move)

    bad_copy = [{"op": "copy", "from": "/nonexistent_field", "path": "/goal"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_copy)

def test_attack_concurrent_fencing_race_condition():
    bus = CanonicalStateBus(workflow_id="wf-race", fencing_token=1, goal="race test")
    asb = AsymmetricStateBus(bus)

    errors = []
    successes = []

    def worker(worker_id: int):
        for _ in range(20):
            try:
                # Concurrent increments
                new_tok = asb.increment_fencing_token()
                asb.apply_patch([{"op": "replace", "path": "/goal", "value": f"Worker {worker_id} tok {new_tok}"}], fencing_token=new_tok)
                successes.append(new_tok)
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no unhandled data corruptions or deadlock
    assert len(successes) > 0
    assert asb.state.fencing_token > 1

def test_attack_invalid_schema_mutation_wrapping():
    bus = CanonicalStateBus(workflow_id="wf-schema", fencing_token=1, goal="test")
    asb = AsymmetricStateBus(bus)

    # Corrupting state bus with invalid data type (active_blockers must be list of strings)
    bad_patch = [{"op": "replace", "path": "/active_blockers", "value": "NOT_A_LIST"}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_patch)

def test_attack_root_replacement_with_primitive():
    bus = CanonicalStateBus(workflow_id="wf-prim", fencing_token=1, goal="test")
    asb = AsymmetricStateBus(bus)

    bad_patch = [{"op": "replace", "path": "", "value": 12345}]
    with pytest.raises(JSONPatchError):
        asb.apply_patch(bad_patch)

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))
