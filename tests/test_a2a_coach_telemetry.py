import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.coach_telemetry import ZeroLLMCoach

def test_tool_repetition_scoring():
    coach = ZeroLLMCoach()

    # 1. Nominal calls (<3 repetitions)
    calls_nominal = [
        ("file_read", {"path": "a.py"}, 200),
        ("file_read", {"path": "b.py"}, 200),
        ("file_write", {"path": "a.py"}, 200),
    ]
    assert coach.compute_tool_repetition_score(calls_nominal) == 1.0

    # 2. 3 identical calls -> 0.5
    calls_3_reps = [
        ("file_read", {"path": "a.py"}, 200),
        ("file_read", {"path": "a.py"}, 200),
        ("file_read", {"path": "a.py"}, 200),
    ]
    assert coach.compute_tool_repetition_score(calls_3_reps) == 0.5

    # 3. >=6 identical calls -> 0.0
    calls_6_reps = [("file_read", {"path": "a.py"}, 200) for _ in range(6)]
    assert coach.compute_tool_repetition_score(calls_6_reps) == 0.0

    # 4. Immediate failure on consecutive identical error retries
    calls_error_retry = [
        ("file_write", {"path": "lock.py", "content": "bad"}, 400),
        ("file_write", {"path": "lock.py", "content": "bad"}, 400),
    ]
    assert coach.compute_tool_repetition_score(calls_error_retry) == 0.0

def test_reasoning_stagnation_scoring():
    coach = ZeroLLMCoach()

    # High divergence (nominal progression) -> S_stag = 1.0
    t1 = "Inspecting auth middleware to locate token decode handler"
    t2 = "Found decode handler in auth.py; planning decoupling into key parser protocol"
    assert coach.compute_reasoning_stagnation_score([t1, t2]) == 1.0

    # High stagnation (near-identical looped thoughts) -> S_stag = 0.0
    t3 = "Attempting to fix auth token decode by adjusting parameter defaults in method"
    t4 = "Attempting to fix auth token decode by adjusting parameter defaults in method."
    assert coach.compute_reasoning_stagnation_score([t3, t4]) == 0.0

def test_call_graph_cycle_scoring():
    coach = ZeroLLMCoach()

    # No cycle -> 1.0
    actions_linear = ["read:auth.py", "plan:keys.py", "write:keys.py"]
    progress_linear = [0, 0, 1]
    assert coach.compute_call_graph_cycle_score(actions_linear, progress_linear) == 1.0

    # Cycle with state progression (e.g. read -> edit -> read after file changed) -> 1.0
    actions_cycle_progress = ["read:auth.py", "write:keys.py", "read:auth.py"]
    progress_increased = [0, 1, 2]
    assert coach.compute_call_graph_cycle_score(actions_cycle_progress, progress_increased) == 1.0

    # Cycle with zero state progress -> 0.0
    actions_stuck = ["read:auth.py", "test:run", "read:auth.py"]
    progress_stuck = [1, 1, 1]
    assert coach.compute_call_graph_cycle_score(actions_stuck, progress_stuck) == 0.0

def test_composite_health_and_substitution_trigger():
    coach = ZeroLLMCoach()

    # Nominal turn
    result_healthy = coach.evaluate_health(
        stint_steps=3,
        step_number=3,
        call_history=[("tool_a", {}, 200), ("tool_b", {}, 200)],
        thought_history=["Thinking about step 1", "Proceeding to step 2"],
        action_history=["act_1", "act_2"],
        domain_progress_history=[1, 2],
    )
    assert result_healthy.s_health >= 0.80
    assert result_healthy.substitution_triggered is False

    # Stagnant loop turn (tool repetition + thought stagnation)
    result_unhealthy = coach.evaluate_health(
        stint_steps=5,
        step_number=5,
        call_history=[("file_write", {"p": "1"}, 400), ("file_write", {"p": "1"}, 400)],  # Srep = 0.0
        thought_history=["Stuck on bug error code 400", "Stuck on bug error code 400"],     # Sstag = 0.0
        action_history=["retry_write", "retry_write"],
        domain_progress_history=[1, 1],
    )
    # Shealth = 0.4(0.0) + 0.35(0.0) + 0.25(Scycle) <= 0.25 < 0.50
    assert result_unhealthy.s_health < 0.50
    assert result_unhealthy.substitution_triggered is True

    # Stint step limit reached (15 steps)
    result_stint_limit = coach.evaluate_health(
        stint_steps=15,
        step_number=15,
        call_history=[("t", {"i": i}, 200) for i in range(15)],
        thought_history=[f"Unique thought {i}" for i in range(15)],
        action_history=[f"action_{i}" for i in range(15)],
        domain_progress_history=list(range(15)),
    )
    assert result_stint_limit.substitution_triggered is True
    assert "15 steps Continue-As-New" in (result_stint_limit.trigger_reason or "")

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

