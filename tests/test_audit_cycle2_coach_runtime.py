import sys
import time
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.coach_telemetry import ZeroLLMCoach
from repo_investigator.bench_rotation.models import ExecutionTier, CanonicalStateBus
from repo_investigator.bench_rotation.bench_runtime import A2ABenchRuntime
from repo_investigator.models.command_spec import CodingAgentTaskSpec, ExecutionDirective, ActionType

def test_attack_massive_thought_stagnation_dos():
    coach = ZeroLLMCoach()
    # 50,000 character strings simulating an LLM thought loop dump
    t1 = "Reasoning step " * 3500
    t2 = "Reasoning step " * 3500 + " ending"

    start_time = time.time()
    score = coach.compute_reasoning_stagnation_score([t1, t2])
    elapsed = time.time() - start_time

    # Reflex loop must complete deterministically under 100ms
    assert elapsed < 0.10, f"SequenceMatcher DOS vulnerability: took {elapsed:.3f}s"
    assert score == 0.0

def test_attack_circular_reference_args_in_repetition():
    coach = ZeroLLMCoach()
    # Circular dictionary
    circ = {}
    circ["self"] = circ

    # Must not raise RecursionError or crash
    score = coach.compute_tool_repetition_score([("bad_tool", circ, 200)])
    assert 0.0 <= score <= 1.0

def test_attack_mismatched_cycle_lengths():
    coach = ZeroLLMCoach()
    # Unequal history lengths
    actions = ["act_a", "act_b", "act_a", "act_b"]
    domain_progress = [1]  # shorter than actions

    # Must handle gracefully without IndexError
    score = coach.compute_call_graph_cycle_score(actions, domain_progress)
    assert 0.0 <= score <= 1.0

def test_attack_roster_substitution_bounds(tmp_path: Path):
    spec = CodingAgentTaskSpec(
        task_id="TASK-SUB-BOUNDS",
        title="Substitution Bounds Test",
        target_repo=str(tmp_path),
        consensus_verdict_ref="V1",
        high_level_intent="Test",
        developer_cognitive_context="Test",
    )
    runtime = A2ABenchRuntime(task_spec=spec, tier=ExecutionTier.TIER_3_A2A_BENCH_ROTATION)

    # Triggering multiple substitutions
    for i in range(12):
        runtime.execute_substitution(
            workspace_dir=tmp_path,
            reason=f"Degradation {i}",
            recent_traces=[],
            step_number=i,
            is_workspace_broken=False,
        )

    report = runtime.build_report(total_steps=12)
    assert report.stints_count == 13
    assert len(report.substitutions) == 12

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

