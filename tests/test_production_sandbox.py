import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.sandbox import (
    LocalSandbox,
    VsockFirecrackerDaemon,
    create_sandbox,
)
from repo_investigator.bench_rotation.state_bus import FencingTokenRejectedError

def test_local_sandbox_fencing_and_execution(tmp_path: Path):
    sandbox = LocalSandbox(workspace_dir=tmp_path, initial_fencing_token=5)

    # Valid fencing token allows writing and command execution
    written_path = sandbox.write_file("test.py", "print('hello from sandbox')", fencing_token=5)
    assert written_path.exists()
    assert sandbox.read_file("test.py") == "print('hello from sandbox')"

    # Executing command with current token succeeds
    code, stdout, stderr = sandbox.execute_command([sys.executable, "-c", "print(42)"], fencing_token=5)
    assert code == 0
    assert "42" in stdout

    # Incrementing fencing token (simulating coach substitution)
    sandbox.update_fencing_token(6)

    # Stale token 5 must be rejected
    with pytest.raises(FencingTokenRejectedError):
        sandbox.write_file("stale.py", "x = 1", fencing_token=5)

    with pytest.raises(FencingTokenRejectedError):
        sandbox.execute_command([sys.executable, "-c", "print('bad')"], fencing_token=5)

def test_vsock_firecracker_daemon_protocol():
    daemon = VsockFirecrackerDaemon(port=1024)
    assert daemon.active_fencing_token == 1
    assert daemon.active_player_session == "starter_agent"

    # Turn validation passes with current token
    assert daemon.validate_incoming_call(1, "starter_agent") is True

    # Coach triggers atomic substitution: n -> 2
    daemon.update_fencing_state(new_token=2, incoming_player="bench_agent_2")
    assert daemon.active_fencing_token == 2
    assert daemon.active_player_session == "bench_agent_2"

    # Stale Starter agent call with token 1 is dropped at vsock boundary
    assert daemon.validate_incoming_call(1, "starter_agent") is False
    assert daemon.validate_incoming_call(2, "bench_agent_2") is True

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

