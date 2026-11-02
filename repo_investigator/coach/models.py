from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CodeExplanation(BaseModel):
    file_path: str
    symbol_name: Optional[str] = None
    title: str
    plain_english_summary: str
    key_responsibilities: List[str] = Field(default_factory=list)
    architectural_role: str
    potential_gotchas: List[str] = Field(default_factory=list)
    beginner_usage_example: str
    how_to_test: str

class DebugDiagnosis(BaseModel):
    error_type: str
    error_message: str
    implicated_file: Optional[str] = None
    implicated_line: Optional[int] = None
    plain_english_explanation: str
    root_cause_analysis: str
    step_by_step_fix: List[str] = Field(default_factory=list)
    code_diff_suggestion: Optional[str] = None
    how_to_prevent_next_time: str

class ImplementationGuide(BaseModel):
    goal: str
    recommended_approach: str
    files_to_modify: List[str] = Field(default_factory=list)
    files_to_create: List[str] = Field(default_factory=list)
    architectural_rules_to_respect: List[str] = Field(default_factory=list)
    step_by_step_checklist: List[str] = Field(default_factory=list)
    starter_code_snippet: Optional[str] = None

