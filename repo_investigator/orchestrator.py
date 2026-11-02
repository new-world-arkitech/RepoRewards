from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.investigator_models import InvestigationFinding
from repo_investigator.models.deliberation_models import DeliberationSessionRecord
from repo_investigator.models.command_spec import CodingAgentTaskSpec
from repo_investigator.extractor.flow_analyzer import FlowTopologyAnalyzer
from repo_investigator.extractor.repo_loader import (
    is_git_remote_url,
    clone_remote_repo,
    cleanup_repo_dir,
)
from repo_investigator.investigators import (
    FlowTopologyInvestigator,
    DeveloperIntentInvestigator,
    IdiomsPatternInvestigator,
    InvariantsHazardsInvestigator,
)
from repo_investigator.deliberation.council import DeliberationCouncil
from repo_investigator.translator.command_compiler import CommandCompiler
from repo_investigator.coding_agent import ReasoningCodingAgent, CodingAgentExecutionReport
from repo_investigator.llm.base import BaseReasoningEngine, get_default_engine
from repo_investigator.bench_rotation.models import (
    ExecutionTier,
    CanonicalStateBus,
    StateBusLedger,
)
from repo_investigator.bench_rotation.tiers import CompletionEffortNode
from repo_investigator.brain import CognitiveBrain, BrainManager

class PipelineResult(BaseModel):
    archaeology: RepoArchaeology
    findings: List[InvestigationFinding]
    deliberation: DeliberationSessionRecord
    task_spec: CodingAgentTaskSpec
    execution_report: Optional[CodingAgentExecutionReport] = None
    execution_tier: Optional[str] = None
    state_bus: Optional[CanonicalStateBus] = None
    brain: Optional[CognitiveBrain] = None

class FlowMindOrchestrator:
    """
    Main orchestration engine that runs the multi-agent cognitive pipeline:
    1. Archaeological Repo Ingestion & Flow Extraction
    2. Multi-disciplinary Specialist Investigation
    3. Group Reasoning Deliberation Council
    4. Machine-Readable Command Translation
    5. Adaptive A2A Bench Rotation & Reasoning Coding Agent Execution
    """

    def __init__(
        self,
        engine: Optional[BaseReasoningEngine] = None,
        default_tier: Optional[ExecutionTier | str] = None,
    ):
        self.engine = engine or get_default_engine()
        self.default_tier = default_tier
        self.flow_investigator = FlowTopologyInvestigator(self.engine)
        self.intent_investigator = DeveloperIntentInvestigator(self.engine)
        self.pattern_investigator = IdiomsPatternInvestigator(self.engine)
        self.invariant_investigator = InvariantsHazardsInvestigator(self.engine)
        self.council = DeliberationCouncil(self.engine)
        self.compiler = CommandCompiler()

    def run(
        self,
        repo_path: str | Path,
        execute_code: bool = True,
        dry_run: bool = False,
        tier: Optional[ExecutionTier | str] = None,
        enable_bench_rotation: bool = True,
        remote_depth: int = 50,
        remote_branch: Optional[str] = None,
        keep_cloned_repo: bool = False,
        review_mode: bool = False,
        repo_owner: Optional[str] = None,
        brain_path: Optional[Path] = None,
    ) -> PipelineResult:
        repo_str = str(repo_path)
        cloned_temp_dir: Optional[Path] = None

        if is_git_remote_url(repo_str):
            cloned_temp_dir = clone_remote_repo(
                url=repo_str,
                depth=remote_depth,
                branch=remote_branch,
            )
            repo_dir = cloned_temp_dir
        else:
            repo_dir = Path(repo_path).resolve()

        chosen_tier = tier or self.default_tier

        try:
            # Step 1: Scan and extract archaeology & flow topology
            extractor = FlowTopologyAnalyzer(repo_dir)
            archaeology = extractor.analyze()

            # Step 2: Dispatch Investigative Council
            findings: List[InvestigationFinding] = [
                self.flow_investigator.investigate(archaeology),
                self.intent_investigator.investigate(archaeology),
                self.pattern_investigator.investigate(archaeology),
                self.invariant_investigator.investigate(archaeology),
            ]

            # Step 3: Deliberation Council (Group Reasoning Session)
            repo_name = repo_dir.name or "repository"
            hubs = archaeology.architectural_signals.get("architectural_hubs", [])
            has_cycles = len(archaeology.detected_cycles) > 0
            has_churn = len(archaeology.churn_hotspots) > 0

            deliberation_record = self.council.deliberate(
                repo_name=repo_name,
                findings=findings,
                hubs=hubs,
                has_cycles=has_cycles,
                has_churn=has_churn,
                has_layer_leaks=any(
                    any(i.category == "INVARIANT_LAYER_BOUNDARY_BREACH" for i in f.insights)
                    for f in findings
                ),
            )

            # Step 4: Machine-Readable Command Compilation
            task_spec = self.compiler.compile(
                archaeology=archaeology,
                findings=findings,
                session=deliberation_record,
            )
            task_spec.metadata["has_cycles"] = has_cycles
            task_spec.metadata["high_churn"] = has_churn

            # Classify tier via Completion Effort Node
            classified_tier, _ = CompletionEffortNode.classify_task(
                task_spec=task_spec,
                override_tier=chosen_tier,
            )

            # Step 5: Autonomous Reasoning Coding Agent Execution with Bench Rotation
            execution_report = None
            state_bus_snapshot: Optional[CanonicalStateBus] = None
            final_tier_str = classified_tier.value

            if execute_code:
                coding_agent = ReasoningCodingAgent(
                    engine=self.engine,
                    dry_run=dry_run,
                    tier=chosen_tier,
                    enable_bench_rotation=enable_bench_rotation,
                    review_mode=review_mode,
                )
                execution_report = coding_agent.execute_spec(task_spec, target_dir=repo_dir)
                if execution_report.state_bus is not None:
                    state_bus_snapshot = execution_report.state_bus
                if execution_report.execution_tier:
                    final_tier_str = execution_report.execution_tier
            else:
                # If not executing code, initialize baseline state bus
                state_bus_snapshot = CanonicalStateBus(
                    workflow_id=task_spec.task_id,
                    fencing_token=1,
                    active_player="starter_agent",
                    stint_number=1,
                    goal=task_spec.title or task_spec.high_level_intent,
                    active_blockers=[f"Directives pending execution: {len(task_spec.execution_directives)}"],
                )

            result = PipelineResult(
                archaeology=archaeology,
                findings=findings,
                deliberation=deliberation_record,
                task_spec=task_spec,
                execution_report=execution_report,
                execution_tier=final_tier_str,
                state_bus=state_bus_snapshot,
            )

            # Ingest session knowledge into persistent, attributed Cognitive Brain
            try:
                brain_snapshot = BrainManager.ingest_session(
                    result=result,
                    repo_path=repo_dir,
                    owner_override=repo_owner,
                    brain_path=brain_path,
                )
                result.brain = brain_snapshot
            except Exception as e:
                pass

            return result
        finally:
            if cloned_temp_dir is not None and not keep_cloned_repo:
                cleanup_repo_dir(cloned_temp_dir)
