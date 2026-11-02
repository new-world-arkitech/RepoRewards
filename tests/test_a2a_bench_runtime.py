import sys
from pathlib import Path

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import ExecutionTier
from repo_investigator.bench_rotation.bench_runtime import A2ABenchRuntime
from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    ActionType,
)

def test_a2a_bench_runtime_substitution_lifecycle(tmp_path: Path):
    target_file = tmp_path / "processor.py"
    target_file.write_text("class Processor: pass\n", encoding="utf-8")

    spec = CodingAgentTaskSpec(
        task_id="TASK-A2A-001",
        title="Decouple processor and auth",
        target_repo=str(tmp_path),
        consensus_verdict_ref="VERDICT-A2A",
        high_level_intent="Refactor processor with bench rotation",
        developer_cognitive_context="Complex decouple",
        execution_directives=[
            ExecutionDirective(
                step_number=1,
                action_type=ActionType.CREATE_FILE,
                target_file="interfaces.py",
                instruction="Create interface",
            ),
            ExecutionDirective(
                step_number=2,
                action_type=ActionType.ENFORCE_INVARIANT,
                target_file="processor.py",
                instruction="Refactor processor",
            ),
        ],
    )

    runtime = A2ABenchRuntime(task_spec=spec, tier=ExecutionTier.TIER_3_A2A_BENCH_ROTATION)
    assert runtime.state_bus.fencing_token == 1
    assert runtime.active_player == "starter_agent"
    assert runtime.stint_number == 1

    # Take baseline snapshot
    runtime.state_bus.take_cow_snapshot(step=0, workspace_dir=tmp_path)

    # Step 1: Nominal execution
    h1 = runtime.record_step_telemetry(
        step_number=1,
        tool_call=("CREATE_FILE", {"file": "interfaces.py"}, 200),
        thought="Step 1 completed successfully",
        action="CREATE_FILE:interfaces.py",
        domain_progress=1,
    )
    assert h1.substitution_triggered is False
    assert runtime.stint_steps == 1

    # Step 2: First failing turn
    h2 = runtime.record_step_telemetry(
        step_number=2,
        tool_call=("ENFORCE_INVARIANT", {"file": "processor.py"}, 400),
        thought="Attempting to enforce invariant on processor",
        action="ENFORCE_INVARIANT:processor.py",
        domain_progress=1,
    )

    # Step 3: Repeated identical failing turn (immediate error retry failure + thought stagnation)
    h3 = runtime.record_step_telemetry(
        step_number=3,
        tool_call=("ENFORCE_INVARIANT", {"file": "processor.py"}, 400),
        thought="Attempting to enforce invariant on processor",  # Stagnant thought
        action="ENFORCE_INVARIANT:processor.py",
        domain_progress=1,
    )
    # Consecutive identical error retry triggers Srep = 0.0 & Sstag = 0.0 -> Shealth < 0.50
    assert h3.substitution_triggered is True

    # Execute Warm Bench Substitution Checklist
    sub_event = runtime.execute_substitution(
        workspace_dir=tmp_path,
        reason=h3.trigger_reason or "Health degraded",
        recent_traces=[],
        step_number=3,
        is_workspace_broken=False,
    )

    # Validate substitution outcomes
    assert sub_event.outgoing_player == "starter_agent"
    assert sub_event.incoming_player == "bench_agent_2"
    assert sub_event.old_fencing_token == 1
    assert sub_event.new_fencing_token == 2
    assert runtime.active_player == "bench_agent_2"
    assert runtime.stint_number == 2
    assert runtime.stint_steps == 0
    assert runtime.private_scratchpad == ""  # Zeroed out!

    # Verify state bus updated with new fencing token
    assert runtime.state_bus.fencing_token == 2
    assert runtime.state_bus.max_accepted_token == 2

    # Verify report output
    report = runtime.build_report(total_steps=2)
    assert report.stints_count == 2
    assert len(report.substitutions) == 1
    assert report.substitutions[0].incoming_player == "bench_agent_2"

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))
