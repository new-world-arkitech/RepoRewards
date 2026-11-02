import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import ExecutionTier
from repo_investigator.bench_rotation.tiers import (
    CompletionEffortNode,
    TierPromotionMonitor,
)
from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    ActionType,
)

def test_completion_effort_node_classification():
    # 1. Simple task -> Tier 1
    spec_tier1 = CodingAgentTaskSpec(
        task_id="TASK-T1",
        title="Quick interface fix",
        target_repo="sample_repo",
        consensus_verdict_ref="VERDICT-1",
        high_level_intent="Add single type annotation",
        developer_cognitive_context="Simple edit",
        execution_directives=[
            ExecutionDirective(
                step_number=1,
                action_type=ActionType.CREATE_FILE,
                target_file="utils.py",
                instruction="Create types helper",
            )
        ],
    )
    tier1, reason1 = CompletionEffortNode.classify_task(spec_tier1)
    assert tier1 == ExecutionTier.TIER_1_DIRECT
    assert "Tier 1" in reason1

    # 2. Medium task -> Tier 2
    spec_tier2 = CodingAgentTaskSpec(
        task_id="TASK-T2",
        title="Refactor service flow",
        target_repo="sample_repo",
        consensus_verdict_ref="VERDICT-2",
        high_level_intent="Refactor service and tests",
        developer_cognitive_context="Multi-step refactoring",
        execution_directives=[
            ExecutionDirective(
                step_number=i,
                action_type=ActionType.ENFORCE_INVARIANT,
                target_file=f"file_{i}.py",
                instruction=f"Step {i}",
            )
            for i in range(1, 5)
        ],
    )
    tier2, reason2 = CompletionEffortNode.classify_task(spec_tier2)
    assert tier2 == ExecutionTier.TIER_2_MANAGED_SINGLE

    # 3. High-complexity / high-churn task -> Tier 3
    spec_tier3 = CodingAgentTaskSpec(
        task_id="TASK-T3",
        title="Large distributed refactoring",
        target_repo="sample_repo",
        consensus_verdict_ref="VERDICT-3",
        high_level_intent="Massive architectural decouple",
        developer_cognitive_context="High state mutability",
        execution_directives=[
            ExecutionDirective(
                step_number=i,
                action_type=ActionType.ENFORCE_INVARIANT,
                target_file=f"module_{i}.py",
                instruction=f"Step {i}",
            )
            for i in range(1, 12)
        ],
        metadata={"has_cycles": True, "high_churn": True},
    )
    tier3, reason3 = CompletionEffortNode.classify_task(spec_tier3)
    assert tier3 == ExecutionTier.TIER_3_A2A_BENCH_ROTATION

    # 4. Explicit override
    tier_override, _ = CompletionEffortNode.classify_task(spec_tier1, override_tier=ExecutionTier.TIER_3_A2A_BENCH_ROTATION)
    assert tier_override == ExecutionTier.TIER_3_A2A_BENCH_ROTATION

def test_tier_promotion_monitor_threshold_1_step_count():
    monitor = TierPromotionMonitor()

    # Steps 1 to 7 without completion
    for s in range(1, 8):
        promoted, reason = monitor.record_turn(step_number=s, is_task_complete=False)
        assert promoted is False

    # Step 8 reached without completion -> Mid-game promotion!
    promoted, reason = monitor.record_turn(step_number=8, is_task_complete=False)
    assert promoted is True
    assert "Step count reached 8 >= 8" in (reason or "")

def test_tier_promotion_monitor_threshold_2_cumulative_tokens():
    monitor = TierPromotionMonitor()

    # 12,000 tokens at 4 chars/token is 48,000 characters
    massive_stdout = "x" * 50000
    promoted, reason = monitor.record_turn(step_number=2, stdout_output=massive_stdout)
    assert promoted is True
    assert "Cumulative stdout reached" in (reason or "")
    assert ">= 12,000 tokens" in (reason or "")

def test_tier_promotion_monitor_threshold_3_consecutive_failures():
    monitor = TierPromotionMonitor()

    # First failure
    promoted1, _ = monitor.record_turn(step_number=1, is_success=False)
    assert promoted1 is False

    # Second consecutive failure -> Mid-game promotion!
    promoted2, reason2 = monitor.record_turn(step_number=2, is_success=False)
    assert promoted2 is True
    assert "2 consecutive test/build failures" in (reason2 or "")

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

