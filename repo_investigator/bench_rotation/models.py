from __future__ import annotations

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ExecutionTier(str, Enum):
    TIER_1_DIRECT = "TIER_1"
    TIER_2_MANAGED_SINGLE = "TIER_2"
    TIER_3_A2A_BENCH_ROTATION = "TIER_3"

    @property
    def display_name(self) -> str:
        if self == ExecutionTier.TIER_1_DIRECT:
            return "Tier 1: Direct Execution"
        elif self == ExecutionTier.TIER_2_MANAGED_SINGLE:
            return "Tier 2: Managed Single Agent"
        return "Tier 3: Full A2A Bench Rotation"

class VerifiedMilestone(BaseModel):
    step: int
    summary: str
    commit_or_snapshot_id: str

class DeadEndRecord(BaseModel):
    stint: int
    attempted_play: str
    failure_reason: str
    rule_out: str

class CanonicalStateBus(BaseModel):
    """
    Canonical State Bus Ledger storing shared truth across roster agents.
    Complies with memory.md Section 3 schema.
    """
    workflow_id: str
    fencing_token: int = 1
    active_player: str = "starter_agent"
    stint_number: int = 1
    goal: str
    verified_milestones: List[VerifiedMilestone] = Field(default_factory=list)
    active_blockers: List[str] = Field(default_factory=list)
    dead_ends_log: List[DeadEndRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Convenient alias for system parity
StateBusLedger = CanonicalStateBus

class JSONPatchOp(BaseModel):
    """
    RFC 6902 JSON Patch operation.
    """
    op: str  # "test", "replace", "add", "remove", "move", "copy"
    path: str
    value: Optional[Any] = None
    from_path: Optional[str] = Field(default=None, alias="from")

    model_config = {
        "populate_by_name": True
    }

class HealthScoreResult(BaseModel):
    """
    Result of Zero-LLM Coach Telemetry Reflex Loop.
    Shealth = 0.40(Srep) + 0.35(Sstag) + 0.25(Scycle)
    """
    s_rep: float
    s_stag: float
    s_cycle: float
    s_health: float
    substitution_triggered: bool
    trigger_reason: Optional[str] = None
    step_number: int = 0
    stint_steps: int = 0

class CoWSnapshot(BaseModel):
    """
    Firecracker-style Copy-on-Write workspace state snapshot.
    """
    snapshot_id: str
    step: int
    timestamp: float
    file_hashes: Dict[str, str] = Field(default_factory=dict)
    file_contents: Dict[str, str] = Field(default_factory=dict)

class SubstitutionEvent(BaseModel):
    """
    Telemetry event capturing an atomic bench player substitution.
    """
    stint_number: int
    outgoing_player: str
    incoming_player: str
    step_number: int
    reason: str
    old_fencing_token: int
    new_fencing_token: int
    restored_snapshot_id: Optional[str] = None
    patch_applied: Optional[List[Dict[str, Any]]] = None

class BenchRotationReport(BaseModel):
    """
    Complete telemetry and execution summary from the A2A Bench Rotation runtime.
    """
    initial_tier: ExecutionTier
    final_tier: ExecutionTier
    promoted_mid_game: bool = False
    promotion_reason: Optional[str] = None
    stints_count: int = 1
    substitutions: List[SubstitutionEvent] = Field(default_factory=list)
    final_state_bus: CanonicalStateBus
    telemetry_history: List[HealthScoreResult] = Field(default_factory=list)
    total_steps: int = 0

