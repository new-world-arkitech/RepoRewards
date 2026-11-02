import tempfile
from pathlib import Path
from repo_investigator.coding_agent import ReasoningCodingAgent
from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    ArchitecturalInvariant,
    VerificationGate,
    ActionType,
    InvariantType,
    GateType,
)

def test_coding_agent_reasoning_and_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        spec = CodingAgentTaskSpec(
            task_id="TASK-TEST-001",
            title="Refactor Invariant Decoupling",
            target_repo=str(tmp_path),
            consensus_verdict_ref="VERDICT-TEST-001",
            high_level_intent="Decouple domain processor from persistence",
            developer_cognitive_context="Address cognitive debt from historical churn",
            architectural_invariants=[
                ArchitecturalInvariant(
                    id="INV-001",
                    rule="No direct persistence imports in domain",
                    invariant_type=InvariantType.IMPORT_RESTRICTION,
                    enforcement_scope="core.*",
                    verification_heuristic="Check AST imports"
                )
            ],
            execution_directives=[
                ExecutionDirective(
                    step_number=1,
                    action_type=ActionType.CREATE_FILE,
                    target_file="core/interfaces.py",
                    target_symbol="ProcessorProtocol",
                    instruction="Define ProcessorProtocol",
                ),
                ExecutionDirective(
                    step_number=2,
                    action_type=ActionType.ENFORCE_INVARIANT,
                    target_file="services/processor.py",
                    target_symbol="Processor",
                    instruction="Refactor Processor to use adapter injection",
                ),
            ],
            verification_gates=[
                VerificationGate(
                    gate_id="GATE-01",
                    gate_name="AST Check",
                    gate_type=GateType.AST_SYNTAX_CHECK,
                    target="all",
                    criteria="Pass AST parse",
                )
            ],
        )

        agent = ReasoningCodingAgent(dry_run=False)
        report = agent.execute_spec(spec, target_dir=tmp_path)

        assert report.status == "COMPLETED_SUCCESSFULLY"
        assert len(report.files_mutated) == 2
        assert (tmp_path / "core" / "interfaces.py").exists()
        assert (tmp_path / "services" / "processor.py").exists()

        # Check step traces and internal reasoning
        for trace in report.step_traces:
            assert trace.ast_validation_passed is True
            assert len(trace.reasoning_chain_of_thought) > 0
            assert len(trace.pre_flight_invariant_checks) > 0
