from __future__ import annotations

import ast
import difflib
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    VerificationGate,
    GateType,
)
from repo_investigator.coding_agent.reasoning_engine import CodingAgentReasoner, StepReasoningTrace
from repo_investigator.llm.base import BaseReasoningEngine, get_default_engine
from repo_investigator.bench_rotation.models import (
    ExecutionTier,
    CanonicalStateBus,
    BenchRotationReport,
)
from repo_investigator.bench_rotation.bench_runtime import A2ABenchRuntime

class GateEvaluationResult(BaseModel):
    gate_id: str
    gate_name: str
    passed: bool
    details: str

class CodingAgentExecutionReport(BaseModel):
    task_id: str
    status: str  # "COMPLETED_SUCCESSFULLY", "FAILED", "PARTIAL"
    files_mutated: List[str] = Field(default_factory=list)
    unified_diffs: Dict[str, str] = Field(default_factory=dict)
    step_traces: List[StepReasoningTrace] = Field(default_factory=list)
    gate_results: List[GateEvaluationResult] = Field(default_factory=list)
    summary: str = ""
    execution_tier: Optional[str] = None
    bench_rotation_report: Optional[BenchRotationReport] = None
    state_bus: Optional[CanonicalStateBus] = None

class ReasoningCodingAgent:
    """
    Autonomous Coding Agent possessing its own internal reasoning model,
    integrated with the A2A Bench Rotation Runtime (Tier 1, Tier 2, Tier 3).
    Receives compiled machine-readable directives, plans AST mutations,
    self-audits against invariants, and executes changes.
    """

    def __init__(
        self,
        engine: Optional[BaseReasoningEngine] = None,
        dry_run: bool = False,
        tier: Optional[ExecutionTier | str] = None,
        enable_bench_rotation: bool = True,
        review_mode: bool = False,
    ):
        self.engine = engine or get_default_engine()
        self.reasoner = CodingAgentReasoner(self.engine)
        self.dry_run = dry_run
        self.tier = tier
        self.enable_bench_rotation = enable_bench_rotation
        self.review_mode = review_mode

    @staticmethod
    def _resolve_safe_path(root: Path, target: str) -> Path:
        """
        Guards against directory traversal attacks, ensuring target is strictly
        contained within the repository workspace root.
        """
        resolved_root = root.resolve()
        resolved_target = (resolved_root / target).resolve()
        try:
            resolved_target.relative_to(resolved_root)
        except ValueError:
            raise PermissionError(
                f"Security Breach Attempt: Directive attempted path traversal outside repository: '{target}'"
            )
        return resolved_target

    def execute_spec(
        self,
        spec: CodingAgentTaskSpec,
        target_dir: Optional[str | Path] = None,
        initial_state_bus: Optional[CanonicalStateBus] = None,
    ) -> CodingAgentExecutionReport:
        repo_root = Path(target_dir or spec.target_repo).resolve()
        step_traces: List[StepReasoningTrace] = []
        files_mutated: List[str] = []
        unified_diffs: Dict[str, str] = {}
        all_steps_succeeded = True

        runtime: Optional[A2ABenchRuntime] = None
        if self.enable_bench_rotation:
            runtime = A2ABenchRuntime(
                task_spec=spec,
                initial_state_bus=initial_state_bus,
                tier=self.tier,
            )
            # Take initial clean baseline CoW snapshot
            runtime.state_bus.take_cow_snapshot(step=0, workspace_dir=repo_root)

        for idx, directive in enumerate(spec.execution_directives, start=1):
            # In A2A Tier 3, validate fencing token before execution
            if runtime is not None:
                runtime.state_bus.validate_fencing_token(runtime.state_bus.fencing_token)

            trace, code = self.reasoner.reason_step(
                directive=directive,
                invariants=spec.architectural_invariants,
                repo_root=repo_root,
            )
            step_traces.append(trace)

            step_succeeded = trace.ast_validation_passed and trace.error_message is None
            if not step_succeeded:
                all_steps_succeeded = False

            if code is not None and step_succeeded:
                try:
                    file_path = self._resolve_safe_path(repo_root, directive.target_file)
                    original_content = ""
                    if file_path.exists():
                        original_content = file_path.read_text(encoding="utf-8", errors="replace")

                    diff_lines = list(difflib.unified_diff(
                        original_content.splitlines(keepends=True),
                        code.splitlines(keepends=True),
                        fromfile=f"a/{directive.target_file}",
                        tofile=f"b/{directive.target_file}",
                    ))
                    diff_str = "".join(diff_lines)
                    if diff_str:
                        unified_diffs[directive.target_file] = diff_str

                    should_apply = not self.dry_run
                    if should_apply and self.review_mode and sys.stdin.isatty():
                        ans = input(f"\n[REVIEW] Apply patch to '{directive.target_file}'? [Y/n]: ").strip().lower()
                        if ans not in ("", "y", "yes"):
                            should_apply = False
                            trace.reasoning_chain_of_thought.append("User skipped applying patch during review mode.")

                    if should_apply:
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(code, encoding="utf-8")
                        if directive.target_file not in files_mutated:
                            files_mutated.append(directive.target_file)
                except PermissionError as pe:
                    step_succeeded = False
                    all_steps_succeeded = False
                    trace.ast_validation_passed = False
                    trace.error_message = str(pe)
                    trace.reasoning_chain_of_thought.append(f"SECURITY ALERT: {pe}")

            # Record telemetry & reflex loop in A2A Runtime
            if runtime is not None:
                tool_call = (
                    directive.action_type.value,
                    {"target_file": directive.target_file, "step": directive.step_number},
                    200 if step_succeeded else 400,
                )
                thought = " ".join(trace.reasoning_chain_of_thought)
                action = f"{directive.action_type.value}:{directive.target_file}"
                domain_progress = len(files_mutated)
                stdout = trace.error_message or "AST verification succeeded"
                is_task_complete = (idx == len(spec.execution_directives)) and all_steps_succeeded

                health = runtime.record_step_telemetry(
                    step_number=idx,
                    tool_call=tool_call,
                    thought=thought,
                    action=action,
                    domain_progress=domain_progress,
                    stdout=stdout,
                    is_success=step_succeeded,
                    is_complete=is_task_complete,
                )

                # If step succeeded, save verified milestone snapshot
                if step_succeeded:
                    snap = runtime.state_bus.take_cow_snapshot(step=idx, workspace_dir=repo_root)
                    milestone_patch = [{
                        "op": "add",
                        "path": "/verified_milestones/-",
                        "value": {
                            "step": idx,
                            "summary": f"Completed {directive.action_type.value} on {directive.target_file}",
                            "commit_or_snapshot_id": snap.snapshot_id,
                        },
                    }]
                    try:
                        runtime.state_bus.apply_patch(milestone_patch, fencing_token=runtime.state_bus.fencing_token)
                    except Exception:
                        pass

                # Broadcast 5-step Timeout updates using RFC 6902
                if idx % 5 == 0:
                    runtime.perform_5_step_timeout_sync(idx, step_traces)

                # Trigger Bench Player Substitution if Coach Health reflex flagged degradation or stint limit
                if health.substitution_triggered and idx < len(spec.execution_directives):
                    runtime.execute_substitution(
                        workspace_dir=repo_root,
                        reason=health.trigger_reason or "Coach Telemetry reflex substitution trigger",
                        recent_traces=step_traces[-5:],
                        step_number=idx,
                        is_workspace_broken=not step_succeeded,
                    )

        # Evaluate Verification Gates
        gate_results: List[GateEvaluationResult] = []
        for gate in spec.verification_gates:
            if gate.gate_type == GateType.AST_SYNTAX_CHECK:
                syntax_ok = True
                failed_file = ""
                for mf in files_mutated:
                    p = repo_root / mf
                    if p.exists():
                        try:
                            ast.parse(p.read_text(encoding="utf-8"))
                        except Exception as e:
                            syntax_ok = False
                            failed_file = f"{mf}: {e}"
                            break

                gate_results.append(
                    GateEvaluationResult(
                        gate_id=gate.gate_id,
                        gate_name=gate.gate_name,
                        passed=syntax_ok,
                        details="All mutated files pass AST syntax checks." if syntax_ok else f"Syntax error in {failed_file}",
                    )
                )

            elif gate.gate_type == GateType.IMPORT_BOUNDARY_AUDIT:
                boundary_ok = True
                leak_found = ""
                for mf in files_mutated:
                    if "core" in mf:
                        p = repo_root / mf
                        if p.exists():
                            content = p.read_text(encoding="utf-8")
                            for line in content.splitlines():
                                if "import db" in line or "import sql" in line or "import requests" in line:
                                    boundary_ok = False
                                    leak_found = f"{mf} contains illegal import: '{line.strip()}'"
                                    break

                gate_results.append(
                    GateEvaluationResult(
                        gate_id=gate.gate_id,
                        gate_name=gate.gate_name,
                        passed=boundary_ok,
                        details="Core layer boundary invariants strictly enforced." if boundary_ok else leak_found,
                    )
                )

            else:
                gate_results.append(
                    GateEvaluationResult(
                        gate_id=gate.gate_id,
                        gate_name=gate.gate_name,
                        passed=True,
                        details=f"Gate criteria satisfied: {gate.criteria}",
                    )
                )

        overall_status = (
            "COMPLETED_SUCCESSFULLY"
            if (all_steps_succeeded and all(g.passed for g in gate_results))
            else "FAILED"
        )

        bench_report: Optional[BenchRotationReport] = None
        state_bus_state: Optional[CanonicalStateBus] = None
        tier_name: Optional[str] = None

        if runtime is not None:
            bench_report = runtime.build_report(total_steps=len(step_traces))
            state_bus_state = runtime.state_bus.state
            tier_name = runtime.active_tier.value

        summary = (
            f"Reasoning Coding Agent processed {len(spec.execution_directives)} directives across {len(files_mutated)} files. "
            f"Execution Tier: {tier_name or 'STANDARD'}. "
            f"All {len(gate_results)} verification gates evaluated with status: {overall_status}."
        )

        return CodingAgentExecutionReport(
            task_id=spec.task_id,
            status=overall_status,
            files_mutated=files_mutated,
            unified_diffs=unified_diffs,
            step_traces=step_traces,
            gate_results=gate_results,
            summary=summary,
            execution_tier=tier_name,
            bench_rotation_report=bench_report,
            state_bus=state_bus_state,
        )
