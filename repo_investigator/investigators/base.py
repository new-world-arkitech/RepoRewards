from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.investigator_models import InvestigationFinding, SpecialistRole
from repo_investigator.llm.base import BaseReasoningEngine, get_default_engine

class BaseInvestigator(ABC):
    def __init__(self, role: SpecialistRole, name: str, lens_description: str, engine: Optional[BaseReasoningEngine] = None):
        self.role = role
        self.name = name
        self.lens_description = lens_description
        self.engine = engine or get_default_engine()

    @abstractmethod
    def investigate(self, archaeology: RepoArchaeology) -> InvestigationFinding:
        """Conducts specialized investigation over the repo archaeology artifacts."""
        pass
