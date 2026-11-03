from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CommitRecord(BaseModel):
    commit_hash: str
    author: str
    date: str
    message: str
    files_changed: List[str] = Field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    intent_tags: List[str] = Field(default_factory=list)
    cognitive_signals: List[str] = Field(default_factory=list)

class ChurnHotspot(BaseModel):
    file_path: str
    modification_count: int
    insertions: int = 0
    deletions: int = 0
    risk_score: float = 0.0
    author_entropy: float = 0.0
    author_count: int = 1
    has_firefighting_burst: bool = False

class InCodeCognitiveMarker(BaseModel):
    category: str  # "TODO", "FIXME", "HACK", "WORKAROUND", "CAUTION", "DEPRECATED"
    text: str
    line_number: int
    file_path: str

class MartinPackageMetrics(BaseModel):
    afferent_coupling: int = 0  # Ca: incoming dependencies (modules depending on this)
    efferent_coupling: int = 0  # Ce: outgoing dependencies (modules this depends on)
    instability: float = 0.0    # I = Ce / (Ca + Ce)
    abstractness: float = 0.0   # A = abstract_classes / total_classes
    distance_from_main_sequence: float = 0.0  # D = |A + I - 1|
    in_zone_of_pain: bool = False
    in_zone_of_uselessness: bool = False

class ASTFunction(BaseModel):
    name: str
    args: List[str] = Field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    line_start: int
    line_end: int
    calls: List[str] = Field(default_factory=list)
    is_async: bool = False

class ASTClass(BaseModel):
    name: str
    bases: List[str] = Field(default_factory=list)
    methods: List[ASTFunction] = Field(default_factory=list)
    docstring: Optional[str] = None
    line_start: int
    line_end: int

class ASTModule(BaseModel):
    file_path: str
    module_name: str
    imports: List[str] = Field(default_factory=list)
    internal_imports: List[str] = Field(default_factory=list)
    external_imports: List[str] = Field(default_factory=list)
    classes: List[ASTClass] = Field(default_factory=list)
    functions: List[ASTFunction] = Field(default_factory=list)
    total_lines: int = 0
    architectural_layer: str = "UNCLASSIFIED"  # "INGRESS", "APPLICATION", "DOMAIN", "INFRASTRUCTURE"
    cognitive_markers: List[InCodeCognitiveMarker] = Field(default_factory=list)
    cognitive_friction_density: float = 0.0
    package_metrics: Optional[MartinPackageMetrics] = None

class CallGraphEdge(BaseModel):
    source: str
    target: str
    context: str = "direct_call"

class RepoArchaeology(BaseModel):
    repo_path: str
    branch: str = "main"
    total_commits: int = 0
    commits: List[CommitRecord] = Field(default_factory=list)
    churn_hotspots: List[ChurnHotspot] = Field(default_factory=list)
    modules: Dict[str, ASTModule] = Field(default_factory=dict)
    call_graph_edges: List[CallGraphEdge] = Field(default_factory=list)
    detected_cycles: List[List[str]] = Field(default_factory=list)
    architectural_signals: Dict[str, Any] = Field(default_factory=dict)
