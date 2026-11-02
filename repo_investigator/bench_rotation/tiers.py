from __future__ import annotations

from typing import Dict, List, Any, Optional, Tuple
from repo_investigator.bench_rotation.models import ExecutionTier
from repo_investigator.models.command_spec import CodingAgentTaskSpec

class CompletionEffortNode:
    """
    Lightweight Task Effort & Execution Tier Classifier.
    Evaluates incoming task complexity, estimated steps, state mutability,
    and log risk to assign the initial runtime configuration:
    - Tier 1: Direct Execution (Est. steps <= 5)
    - Tier 2: Managed Single Agent (Est. steps 6--15)
    - Tier 3: Full A2A Bench Rotation (Est. steps > 15)
    """

    @classmethod
    def classify_task(
        cls,
        task_spec: CodingAgentTaskSpec,
        override_tier: Optional[ExecutionTier | str] = None,
    ) -> Tuple[ExecutionTier, str]:
        if override_tier:
            if isinstance(override_tier, str):
                for t in ExecutionTier:
                    if t.value == override_tier or t.name == override_tier:
                        return t, f"Manual tier override: {t.display_name}"
            elif isinstance(override_tier, ExecutionTier):
                return override_tier, f"Manual tier override: {override_tier.display_name}"

        directives_count = len(task_spec.execution_directives)
        invariants_count = len(task_spec.architectural_invariants)

        # Unique files targeted
        target_files = {d.target_file for d in task_spec.execution_directives}
        file_count = len(target_files)

        # Estimated steps calculation (each directive typically requires planning + AST edit + gate verify)
        est_steps = directives_count * 2

        metadata = task_spec.metadata or {}
        has_cycles = metadata.get("has_cycles", False)
        high_churn = metadata.get("high_churn", False)

        if est_steps <= 5 and file_count <= 2 and not has_cycles:
            reason = (
                f"Classified as Tier 1: Est. steps {est_steps} <= 5, static state, "
                f"{file_count} bounded target file(s)."
            )
            return ExecutionTier.TIER_1_DIRECT, reason

        elif est_steps <= 15 and not has_cycles and not high_churn:
            reason = (
                f"Classified as Tier 2: Est. steps {est_steps} (6-15), moderate state "
                f"mutability across {file_count} file(s)."
            )
            return ExecutionTier.TIER_2_MANAGED_SINGLE, reason

        else:
            reason = (
                f"Classified as Tier 3: Est. steps {est_steps} > 15, high state "
                f"mutability ({file_count} files, churn/cycles={has_cycles or high_churn}). "
                f"Routing to Full A2A Bench Rotation."
            )
            return ExecutionTier.TIER_3_A2A_BENCH_ROTATION, reason

class TierPromotionMonitor:
    """
    Monitors live execution of Tier 2 agents.
    Automatically promotes to Tier 3 if:
    1. Step count reaches step >= 8 without task completion.
    2. Cumulative raw tool stdout exceeds 12,000 tokens.
    3. The agent logs 2 consecutive test/build failures or tool errors.
    """

    def __init__(self, token_char_ratio: float = 4.0):
        self.current_step: int = 0
        self.cumulative_stdout_tokens: int = 0
        self.consecutive_failures: int = 0
        self.token_char_ratio: float = token_char_ratio
        self.promoted: bool = False
        self.promotion_reason: Optional[str] = None

    def record_turn(
        self,
        step_number: int,
        stdout_output: str = "",
        is_success: bool = True,
        is_task_complete: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Records a turn and checks if Mid-Game Promotion Rule triggers (Tier 2 -> Tier 3).
        """
        if self.promoted:
            return True, self.promotion_reason

        self.current_step = step_number

        # Add estimated tokens from stdout
        if stdout_output:
            tokens = int(len(stdout_output) / self.token_char_ratio)
            self.cumulative_stdout_tokens += tokens

        if not is_success:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        # Check Threshold 1: Step count reaches step >= 8 without task completion
        if self.current_step >= 8 and not is_task_complete:
            self.promoted = True
            self.promotion_reason = (
                f"Mid-Game Promotion Triggered: Step count reached {self.current_step} >= 8 "
                f"without task completion."
            )
            return True, self.promotion_reason

        # Check Threshold 2: Cumulative raw tool stdout exceeds 12,000 tokens
        if self.cumulative_stdout_tokens >= 12000:
            self.promoted = True
            self.promotion_reason = (
                f"Mid-Game Promotion Triggered: Cumulative stdout reached "
                f"{self.cumulative_stdout_tokens:,} tokens >= 12,000 tokens."
            )
            return True, self.promotion_reason

        # Check Threshold 3: 2 consecutive test/build failures or tool errors
        if self.consecutive_failures >= 2:
            self.promoted = True
            self.promotion_reason = (
                f"Mid-Game Promotion Triggered: Agent logged {self.consecutive_failures} "
                f"consecutive test/build failures or tool errors."
            )
            return True, self.promotion_reason

        return False, None

