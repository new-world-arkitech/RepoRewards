from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class RepositoryAttribution(BaseModel):
    owner: str = Field(..., description="Entity, organization, or developer who owns the repository")
    repo_name: str
    remote_url: Optional[str] = None
    top_contributors: List[str] = Field(default_factory=list)
    license_type: Optional[str] = "Unknown"
    attribution_statement: str
    ingested_at: str

class LearnedSkill(BaseModel):
    skill_id: str
    skill_name: str
    description: str
    architectural_category: str
    code_pattern_template: str
    source_attribution: RepositoryAttribution

class LearnedRule(BaseModel):
    rule_id: str
    rule_statement: str
    enforcement_scope: str
    rationale: str
    source_attribution: RepositoryAttribution

class LearnedDeadEnd(BaseModel):
    attempted_approach: str
    failure_mode: str
    rule_out_reason: str
    source_attribution: RepositoryAttribution

class ModelEvolutionStage(BaseModel):
    stage_id: str = Field(..., description="Unique ID for this evolution stage (e.g., EVO-STAGE-001)")
    stage_number: int = Field(..., description="Sequential evolution stage number (1, 2, 3...)")
    model_version: str = Field("FlowMind-v1.0.0-cognitive", description="Model version tag after this evolution")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of evolution event")
    credited_owner: str = Field(..., description="Developer or entity credited for this model evolution stage")
    credited_repo: str = Field(..., description="Repository source whose code improved the model's capabilities")
    license_type: str = Field("Unknown", description="License of the source repository")
    capability_unlocked: str = Field(..., description="High-level description of capability improvement unlocked")
    stage_description: str = Field(..., description="Detailed explanation of how this repository improved the model's abilities")
    skills_gained: List[str] = Field(default_factory=list, description="Specific skills added in this stage")
    rules_codified: List[str] = Field(default_factory=list, description="Invariants/rules codified in this stage")
    heuristics_learned: List[str] = Field(default_factory=list, description="Heuristics added to model cognition")
    attribution_statement: str = Field(..., description="Official credit and attribution statement")

class CognitiveBrain(BaseModel):
    brain_id: str = "FLOWMIND_CENTRAL_BRAIN"
    total_repos_ingested: int = 0
    current_generation: int = 0
    attributions: Dict[str, RepositoryAttribution] = Field(default_factory=dict)
    evolution_stages: List[ModelEvolutionStage] = Field(default_factory=list)
    learned_skills: List[LearnedSkill] = Field(default_factory=list)
    learned_rules: List[LearnedRule] = Field(default_factory=list)
    learned_dead_ends: List[LearnedDeadEnd] = Field(default_factory=list)
    coding_heuristics: List[str] = Field(default_factory=list)
    last_updated: str = ""
