import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import CanonicalStateBus
from repo_investigator.bench_rotation.state_bus import (
    InMemoryStateBusStorage,
    RedisStateBusStorage,
    NatsKVStateBusStorage,
    create_state_bus_storage,
    FencingTokenRejectedError,
)

def test_in_memory_state_bus_storage_fencing():
    bus = CanonicalStateBus(workflow_id="wf-1", fencing_token=10, goal="Test goal")
    storage = InMemoryStateBusStorage(initial_bus=bus)

    # Read state
    st = storage.read_state("wf-1")
    assert st is not None
    assert st.fencing_token == 10
    assert storage.get_max_accepted_token("wf-1") == 10

    # Write state with matching or higher token
    bus.goal = "Updated goal"
    storage.write_state(bus, fencing_token=11)
    assert storage.read_state("wf-1").goal == "Updated goal"
    assert storage.get_max_accepted_token("wf-1") == 11

    # Stale token write rejected
    with pytest.raises(FencingTokenRejectedError):
        storage.write_state(bus, fencing_token=9)

def test_redis_state_bus_storage_fallback():
    # If redis server is not running, falls back safely to in-memory
    storage = RedisStateBusStorage(redis_url="redis://localhost:9999/0")
    bus = CanonicalStateBus(workflow_id="wf-redis", fencing_token=1, goal="Redis test")
    storage.write_state(bus, 1)

    read_back = storage.read_state("wf-redis")
    assert read_back is not None
    assert read_back.goal == "Redis test"

def test_create_state_bus_storage_factory():
    storage = create_state_bus_storage("in_memory")
    assert isinstance(storage, InMemoryStateBusStorage)

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

