from __future__ import annotations

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SpecialistRole(str, Enum):
    FLOW_TOPOLOGY = "Flow & Architectural Topology Specialist"
    DEVELOPER_INTENT = "Developer Intent & Archaeology Specialist"
    IDIOMS_PATTERNS = "Idioms & Architectural Patterns Specialist"
    INVARIANTS_HAZARDS = "Invariants, Resilience & Concurrency Sentinel"

class InvestigatorInsight(BaseModel):
    category: str
    observation: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)
    implication: str

class InvestigationFinding(BaseModel):
    investigator_role: SpecialistRole
    investigator_name: str
    specialization_lens: str
    core_hypothesis: str
    insights: List[InvestigatorInsight] = Field(default_factory=list)
    friction_points: List[str] = Field(default_factory=list)
    developer_thought_model: str
    recommended_action: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
