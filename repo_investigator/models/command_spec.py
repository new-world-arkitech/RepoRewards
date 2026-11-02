from __future__ import annotations

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    CREATE_FILE = "CREATE_FILE"
    REFACTOR_FUNCTION = "REFACTOR_FUNCTION"
    MUTATE_INTERFACE = "MUTATE_INTERFACE"
    ENFORCE_INVARIANT = "ENFORCE_INVARIANT"
    ADD_TEST = "ADD_TEST"
    REMOVE_DEPRECATED = "REMOVE_DEPRECATED"

class InvariantType(str, Enum):
    IMPORT_RESTRICTION = "IMPORT_RESTRICTION"
    CONCURRENCY_SAFETY = "CONCURRENCY_SAFETY"
    STATE_IMMUTABILITY = "STATE_IMMUTABILITY"
    INTERFACE_CONTRACT = "INTERFACE_CONTRACT"
    ERROR_HANDLING = "ERROR_HANDLING"

class ArchitecturalInvariant(BaseModel):
    id: str
    rule: str
    invariant_type: InvariantType
    enforcement_scope: str  # e.g., "core.*", "services.processor"
    verification_heuristic: str

class ExecutionDirective(BaseModel):
    step_number: int
    action_type: ActionType
    target_file: str
    target_symbol: Optional[str] = None
    instruction: str
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    diff_strategy: str = "AST_TRANSFORMATION"
    code_snippet_template: Optional[str] = None

class GateType(str, Enum):
    AST_SYNTAX_CHECK = "AST_SYNTAX_CHECK"
    IMPORT_BOUNDARY_AUDIT = "IMPORT_BOUNDARY_AUDIT"
    INVARIANT_ASSERTION = "INVARIANT_ASSERTION"
    TEST_EXECUTION = "TEST_EXECUTION"

class VerificationGate(BaseModel):
    gate_id: str
    gate_name: str
    gate_type: GateType
    target: str
    criteria: str

class CodingAgentTaskSpec(BaseModel):
    task_id: str
    title: str
    target_repo: str
    consensus_verdict_ref: str
    high_level_intent: str
    developer_cognitive_context: str
    architectural_invariants: List[ArchitecturalInvariant] = Field(default_factory=list)
    execution_directives: List[ExecutionDirective] = Field(default_factory=list)
    verification_gates: List[VerificationGate] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
