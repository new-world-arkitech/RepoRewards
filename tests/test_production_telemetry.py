import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import HealthScoreResult, SubstitutionEvent
from repo_investigator.bench_rotation.telemetry import TelemetryManager, get_telemetry_manager

def test_telemetry_manager_recording():
    tel = TelemetryManager(service_name="test-flowmind")

    health = HealthScoreResult(
        s_rep=1.0,
        s_stag=1.0,
        s_cycle=1.0,
        s_health=1.0,
        substitution_triggered=False,
        step_number=1,
        stint_steps=1,
    )

    # Must record without throwing any errors
    tel.record_turn_telemetry(
        workflow_id="wf-test-01",
        step_number=1,
        player_id="starter_agent",
        stint_number=1,
        health=health,
    )

    sub_event = SubstitutionEvent(
        stint_number=2,
        outgoing_player="starter_agent",
        incoming_player="bench_agent_2",
        step_number=5,
        reason="Test substitution",
        old_fencing_token=1,
        new_fencing_token=2,
    )
    tel.record_substitution_event("wf-test-01", sub_event)

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

