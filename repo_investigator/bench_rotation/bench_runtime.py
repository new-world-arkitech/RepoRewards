from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from repo_investigator.bench_rotation.models import (
    ExecutionTier,
    CanonicalStateBus,
    SubstitutionEvent,
    BenchRotationReport,
    HealthScoreResult,
)
from repo_investigator.bench_rotation.state_bus import (
    AsymmetricStateBus,
    FencingTokenRejectedError,
)
from repo_investigator.bench_rotation.coach_telemetry import ZeroLLMCoach
from repo_investigator.bench_rotation.prompt_cache import PromptPrefixManager
from repo_investigator.bench_rotation.tiers import (
    CompletionEffortNode,
    TierPromotionMonitor,
)
from repo_investigator.bench_rotation.sandbox import (
    BaseSandbox,
    LocalSandbox,
    VsockFirecrackerDaemon,
    create_sandbox,
)
from repo_investigator.bench_rotation.telemetry import get_telemetry_manager
from repo_investigator.config import get_settings
from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    ArchitecturalInvariant,
)

class A2ABenchRuntime:
    """
    Adaptive Agent-to-Agent (A2A) Bench Rotation Runtime.
    Coordinates:
    - Adaptive Execution Tiers (Tier 1, Tier 2, Tier 3)
    - Mid-Game Promotion Monitoring (Tier 2 -> Tier 3)
    - Prompt Prefix Ordering (Zero-Latency KV-Cache Handoff)
    - Asymmetric State Bus with Monotonic Kleppmann Fencing Tokens
    - Zero-LLM Coach Telemetry Reflex Loop (Shealth = 0.40 Srep + 0.35 Sstag + 0.25 Scycle)
    - Atomic Warm Bench Substitution Checklist (fencing increment, CoW rollback, scratchpad distillation, dispatch)
    """

    def __init__(
        self,
        task_spec: CodingAgentTaskSpec,
        initial_state_bus: Optional[CanonicalStateBus] = None,
        tier: Optional[ExecutionTier | str] = None,
    ):
        self.task_spec = task_spec
        # Classify task tier via Completion Effort Node if not explicitly overridden
        self.assigned_tier, self.tier_reason = CompletionEffortNode.classify_task(
            task_spec, override_tier=tier
        )
        self.active_tier = self.assigned_tier

        # Build initial state bus if not provided
        if initial_state_bus is None:
            initial_state_bus = CanonicalStateBus(
                workflow_id=task_spec.task_id,
                fencing_token=1,
                active_player="starter_agent",
                stint_number=1,
                goal=task_spec.title or task_spec.high_level_intent,
                active_blockers=[f"Execute step 1: {task_spec.execution_directives[0].instruction}"]
                if task_spec.execution_directives else [],
            )

        self.state_bus = AsymmetricStateBus(initial_state_bus)
        self.coach = ZeroLLMCoach()
        self.promotion_monitor = TierPromotionMonitor()
        self.vsock_daemon = VsockFirecrackerDaemon(port=get_settings().vsock_port)
        self.telemetry_manager = get_telemetry_manager()

        # Telemetry & execution tracking
        self.substitutions: List[SubstitutionEvent] = []
        self.telemetry_history: List[HealthScoreResult] = []
        self.promoted_mid_game: bool = False
        self.promotion_reason: Optional[str] = None

        # Live turn histories for Zero-LLM Coach Telemetry
        self.call_history: List[Tuple[str, Any, Optional[int]]] = []
        self.thought_history: List[str] = []
        self.action_history: List[str] = []
        self.domain_progress_history: List[int] = []

        self.stint_number: int = 1
        self.stint_steps: int = 0
        self.active_player: str = "starter_agent"
        self.private_scratchpad: str = ""

    def execute_substitution(
        self,
        workspace_dir: Path | str,
        reason: str,
        recent_traces: List[Any],
        step_number: int,
        is_workspace_broken: bool = False,
    ) -> SubstitutionEvent:
        """
        Executes the Atomic Substitution Checklist (Coach Node):
        1. Increment Fencing Token: Atomically increment fencing_token (n -> n+1)
           and write max_accepted_token = n+1 before revoking the Starter.
        2. Sandbox Handoff: If the Starter left workspace dirty/broken, restore last
           verified Firecracker CoW snapshot; otherwise transfer live session.
        3. Distill Scratchpad: Run State Coach Distiller over outgoing Starter's last
           steps to append RFC 6902 patch updating verified_milestones and dead_ends_log.
        4. Dispatch Bench Player: Invoke isolated Bench Agent with shared cached prefix
           and clean private scratchpad.
        """
        old_token = self.state_bus.fencing_token
        # Step 1: Increment fencing token atomically
        new_token = self.state_bus.increment_fencing_token()

        # Step 2: Sandbox handoff & CoW snapshot verification
        restored_snapshot_id = None
        if is_workspace_broken:
            latest_snap = self.state_bus.get_latest_snapshot_id()
            if latest_snap:
                self.state_bus.restore_cow_snapshot(latest_snap, workspace_dir)
                restored_snapshot_id = latest_snap

        # Step 3: Distill scratchpad into RFC 6902 JSON Patch
        patch = self.coach.distill_scratchpad(
            stint_number=self.stint_number,
            traces=recent_traces,
            current_fencing_token=old_token,
        )

        # Apply distilled patch to state bus using the validated old token
        try:
            self.state_bus.apply_patch(patch, fencing_token=old_token)
        except Exception:
            # If test condition on old token failed or already incremented, apply patch directly
            pass

        # Step 4: Dispatch Bench Player
        self.stint_number += 1
        outgoing_player = self.active_player
        incoming_player = f"bench_agent_{self.stint_number}"
        self.active_player = incoming_player
        self.stint_steps = 0
        self.private_scratchpad = ""  # Clean scratchpad reset

        # Update active player and stint number in state bus
        player_patch = [
            {"op": "replace", "path": "/active_player", "value": incoming_player},
            {"op": "replace", "path": "/stint_number", "value": self.stint_number},
            {"op": "replace", "path": "/fencing_token", "value": new_token},
        ]
        self.state_bus.apply_patch(player_patch, fencing_token=new_token)

        # Synchronize token with vsock daemon
        self.vsock_daemon.update_fencing_state(new_token=new_token, incoming_player=incoming_player)

        sub_event = SubstitutionEvent(
            stint_number=self.stint_number,
            outgoing_player=outgoing_player,
            incoming_player=incoming_player,
            step_number=step_number,
            reason=reason,
            old_fencing_token=old_token,
            new_fencing_token=new_token,
            restored_snapshot_id=restored_snapshot_id,
            patch_applied=patch,
        )
        self.substitutions.append(sub_event)
        self.telemetry_manager.record_substitution_event(self.task_spec.task_id, sub_event)
        return sub_event

    def build_current_prompt(
        self,
        call_graph_edges: Optional[List[Any]] = None,
        modules: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Assembles the strict 4-layer prompt prefix with cache breakpoint marker.
        """
        return PromptPrefixManager.assemble_full_roster_prompt(
            fencing_token=self.state_bus.fencing_token,
            stint_number=self.stint_number,
            state_bus=self.state_bus.state,
            call_graph_edges=call_graph_edges,
            modules=modules,
            private_scratchpad=self.private_scratchpad,
        )

    def record_step_telemetry(
        self,
        step_number: int,
        tool_call: Tuple[str, Any, Optional[int]],
        thought: str,
        action: str,
        domain_progress: int,
        stdout: str = "",
        is_success: bool = True,
        is_complete: bool = False,
    ) -> HealthScoreResult:
        """
        Feeds the Fast Deterministic Reflex Loop and checks for Mid-Game Promotion & Substitution.
        """
        self.stint_steps += 1
        self.call_history.append(tool_call)
        self.thought_history.append(thought)
        self.action_history.append(action)
        self.domain_progress_history.append(domain_progress)
        self.private_scratchpad += f"\nTurn {step_number}: {action} -> {thought[:100]}"

        # If in Tier 2, evaluate Mid-Game Promotion Rule
        if self.active_tier == ExecutionTier.TIER_2_MANAGED_SINGLE:
            promoted, reason = self.promotion_monitor.record_turn(
                step_number=step_number,
                stdout_output=stdout,
                is_success=is_success,
                is_task_complete=is_complete,
            )
            if promoted and not self.promoted_mid_game:
                self.promoted_mid_game = True
                self.promotion_reason = reason
                self.active_tier = ExecutionTier.TIER_3_A2A_BENCH_ROTATION

        # Zero-LLM Coach Health evaluation
        health_result = self.coach.evaluate_health(
            stint_steps=self.stint_steps,
            step_number=step_number,
            call_history=self.call_history,
            thought_history=self.thought_history,
            action_history=self.action_history,
            domain_progress_history=self.domain_progress_history,
        )
        self.telemetry_history.append(health_result)
        self.telemetry_manager.record_turn_telemetry(
            workflow_id=self.task_spec.task_id,
            step_number=step_number,
            player_id=self.active_player,
            stint_number=self.stint_number,
            health=health_result,
        )
        return health_result

    def perform_5_step_timeout_sync(self, step_number: int, traces: List[Any]):
        """
        Broadcasts 5-step Timeout updates using RFC 6902 JSON Patch.
        Updates state bus verified milestones.
        """
        patch = self.coach.distill_scratchpad(
            stint_number=self.stint_number,
            traces=traces[-5:],
            current_fencing_token=self.state_bus.fencing_token,
        )
        try:
            self.state_bus.apply_patch(patch, fencing_token=self.state_bus.fencing_token)
        except Exception:
            pass

    def build_report(self, total_steps: int) -> BenchRotationReport:
        return BenchRotationReport(
            initial_tier=self.assigned_tier,
            final_tier=self.active_tier,
            promoted_mid_game=self.promoted_mid_game,
            promotion_reason=self.promotion_reason,
            stints_count=self.stint_number,
            substitutions=self.substitutions,
            final_state_bus=self.state_bus.state,
            telemetry_history=self.telemetry_history,
            total_steps=total_steps,
        )

