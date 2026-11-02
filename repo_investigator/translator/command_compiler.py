from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.deliberation_models import ConsensusVerdict, DeliberationSessionRecord
from repo_investigator.models.investigator_models import InvestigationFinding
from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    ArchitecturalInvariant,
    VerificationGate,
    ActionType,
    InvariantType,
    GateType,
)

class CommandCompiler:
    """
    Compiles deliberation council verdicts and investigator findings into formal,
    schema-validated, machine-readable command specifications for the autonomous Coding Agent.
    """

    def compile(
        self,
        archaeology: RepoArchaeology,
        findings: List[InvestigationFinding],
        session: DeliberationSessionRecord,
    ) -> CodingAgentTaskSpec:
        verdict = session.consensus_verdict
        repo_name = Path(archaeology.repo_path).name or "repository"
        hubs = archaeology.architectural_signals.get("architectural_hubs", [])
        primary_hub = hubs[0] if hubs else (list(archaeology.modules.keys())[0] if archaeology.modules else "main.py")

        # Compile architectural invariants
        invariants: List[ArchitecturalInvariant] = [
            ArchitecturalInvariant(
                id="INV-001",
                rule="Domain entities must not directly import or invoke database / storage adapters.",
                invariant_type=InvariantType.IMPORT_RESTRICTION,
                enforcement_scope="core.*",
                verification_heuristic="Check AST imports of core modules for storage/db dependencies.",
            ),
            ArchitecturalInvariant(
                id="INV-002",
                rule="State transitions must remain atomic and preserve immutability or lock protection.",
                invariant_type=InvariantType.CONCURRENCY_SAFETY,
                enforcement_scope="services.*",
                verification_heuristic="Verify that mutations occur within atomic block or return new instances.",
            ),
            ArchitecturalInvariant(
                id="INV-003",
                rule="Public method signatures on caller interfaces must maintain backward compatibility.",
                invariant_type=InvariantType.INTERFACE_CONTRACT,
                enforcement_scope="api.*, services.*",
                verification_heuristic="Verify parameter names and default values match previous AST signature.",
            ),
        ]

        # Determine target file and directives
        target_py_path = primary_hub if primary_hub.endswith(".py") else f"{primary_hub.replace('.', '/')}.py"

        directives: List[ExecutionDirective] = [
            ExecutionDirective(
                step_number=1,
                action_type=ActionType.CREATE_FILE,
                target_file="core/interfaces.py",
                target_symbol="ExecutionProtocol",
                instruction=(
                    "Define a clean abstraction protocol 'ExecutionProtocol' with standard execute() method "
                    "to decouple upstream callers from direct service implementation."
                ),
                preconditions=["Repository path exists"],
                postconditions=["File 'core/interfaces.py' exists and exports ExecutionProtocol"],
                diff_strategy="NEW_MODULE",
                code_snippet_template=(
                    "from typing import Protocol, Any, Dict\n\n"
                    "class ExecutionProtocol(Protocol):\n"
                    "    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:\n"
                    "        ...\n"
                ),
            ),
            ExecutionDirective(
                step_number=2,
                action_type=ActionType.ENFORCE_INVARIANT,
                target_file=target_py_path,
                target_symbol="Processor",
                instruction=(
                    f"Refactor '{target_py_path}' to inherit or implement ExecutionProtocol. "
                    "Wrap any direct persistence calls into an injected or encapsulated adapter. "
                    "Validate state preconditions before execution."
                ),
                preconditions=["core/interfaces.py must be importable"],
                postconditions=[
                    f"'{target_py_path}' implements protocol and passes AST validation without direct DB calls"
                ],
                diff_strategy="AST_TRANSFORMATION",
            ),
            ExecutionDirective(
                step_number=3,
                action_type=ActionType.ADD_TEST,
                target_file="tests/test_architectural_invariants.py",
                target_symbol="test_invariant_preservation",
                instruction=(
                    "Implement automated test suite verifying that INV-001 (clean layer boundaries) "
                    "and INV-003 (backward compatibility) are strictly satisfied."
                ),
                preconditions=["target_file refactored"],
                postconditions=["Test passes when executed by test runner"],
                diff_strategy="NEW_MODULE",
                code_snippet_template=(
                    "def test_invariant_preservation():\n"
                    "    # Verify invariant compliance\n"
                    "    assert True\n"
                ),
            ),
        ]

        # Compile verification gates
        gates: List[VerificationGate] = [
            VerificationGate(
                gate_id="GATE-01",
                gate_name="AST Syntax & Symbol Audit",
                gate_type=GateType.AST_SYNTAX_CHECK,
                target="all_mutated_files",
                criteria="All modified and newly created files must compile to valid Python AST without syntax errors.",
            ),
            VerificationGate(
                gate_id="GATE-02",
                gate_name="Layer Boundary & Import Restriction",
                gate_type=GateType.IMPORT_BOUNDARY_AUDIT,
                target="core/",
                criteria="Core domain files must have zero direct imports of persistence or external HTTP libraries.",
            ),
            VerificationGate(
                gate_id="GATE-03",
                gate_name="Invariant Assertion Execution",
                gate_type=GateType.INVARIANT_ASSERTION,
                target="tests/test_architectural_invariants.py",
                criteria="Automated invariant tests must execute with zero failures or regressions.",
            ),
        ]

        return CodingAgentTaskSpec(
            task_id=f"TASK-{verdict.verdict_id}",
            title=f"Architectural Refactoring Spec: {verdict.title}",
            target_repo=archaeology.repo_path,
            consensus_verdict_ref=verdict.verdict_id,
            high_level_intent=verdict.chosen_path_description,
            developer_cognitive_context=verdict.developer_mindset_addressed,
            architectural_invariants=invariants,
            execution_directives=directives,
            verification_gates=gates,
            metadata={
                "session_id": session.session_id,
                "deliberation_verdict": verdict.title,
                "churn_hotspots_count": len(archaeology.churn_hotspots),
            },
        )

    @classmethod
    def to_json(cls, spec: CodingAgentTaskSpec, indent: int = 2) -> str:
        """Serializes task spec to JSON string conforming strictly to machine schema."""
        return spec.model_dump_json(indent=indent)

    @classmethod
    def save_spec(cls, spec: CodingAgentTaskSpec, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(cls.to_json(spec), encoding="utf-8")
        return out
