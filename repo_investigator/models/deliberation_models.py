from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DeliberationSpeaker(BaseModel):
    id: str
    name: str
    philosophical_stance: str
    primary_concern: str

class DebateArgument(BaseModel):
    speaker_id: str
    speaker_name: str
    target_perspective: Optional[str] = None
    point: str
    counter_evidence: str
    severity: str = "HIGH"  # CRITICAL, HIGH, MODERATE, LOW

class DeliberationRound(BaseModel):
    round_number: int
    round_name: str  # e.g., "Round 1: Divergent Theses", "Round 2: Dialectic Cross-Critique", "Round 3: Synthesis"
    arguments: List[DebateArgument] = Field(default_factory=list)
    round_summary: str = ""

class TradeoffScore(BaseModel):
    criterion: str
    score: float = Field(ge=0.0, le=10.0)
    justification: str

class PerspectiveScoring(BaseModel):
    perspective_id: str
    perspective_name: str
    scores: Dict[str, float] = Field(default_factory=dict)
    average_score: float = 0.0
    key_strengths: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)

class ConsensusVerdict(BaseModel):
    verdict_id: str
    title: str
    strategic_rationale: str
    developer_mindset_addressed: str
    chosen_path_description: str
    acknowledged_tradeoffs: List[str] = Field(default_factory=list)
    rejected_alternatives: List[str] = Field(default_factory=list)
    hard_invariants: List[str] = Field(default_factory=list)
    required_mutations: List[str] = Field(default_factory=list)

class DeliberationSessionRecord(BaseModel):
    session_id: str
    speakers: List[DeliberationSpeaker] = Field(default_factory=list)
    rounds: List[DeliberationRound] = Field(default_factory=list)
    perspectives_scoring: Dict[str, PerspectiveScoring] = Field(default_factory=dict)
    consensus_verdict: ConsensusVerdict
