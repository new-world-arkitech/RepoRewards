from __future__ import annotations

from typing import List
from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.investigator_models import (
    InvestigationFinding,
    InvestigatorInsight,
    SpecialistRole,
)
from repo_investigator.investigators.base import BaseInvestigator

class IdiomsPatternInvestigator(BaseInvestigator):
    def __init__(self, engine=None):
        super().__init__(
            role=SpecialistRole.IDIOMS_PATTERNS,
            name="Kaelen Cross (Idioms & Architectural Patterns Specialist)",
            lens_description="Design patterns, abstraction boundaries, object-oriented/functional idioms, and anti-pattern detection.",
            engine=engine,
        )

    def investigate(self, archaeology: RepoArchaeology) -> InvestigationFinding:
        insights: List[InvestigatorInsight] = []
        friction_points: List[str] = []

        # 1. Detect God-Classes or Oversized Modules
        large_classes = []
        for mod in archaeology.modules.values():
            for cls in mod.classes:
                if len(cls.methods) > 6 or (cls.line_end - cls.line_start) > 100:
                    large_classes.append((cls.name, len(cls.methods), mod.file_path))

        if large_classes:
            names = ", ".join(f"{c[0]} in {c[2]} ({c[1]} methods)" for c in large_classes[:3])
            insights.append(
                InvestigatorInsight(
                    category="ANTIPATTERN_GOD_OBJECT",
                    observation=f"Identified oversized multi-responsibility classes: {names}",
                    evidence="Class method count and span exceed single responsibility threshold.",
                    confidence=0.91,
                    implication="Concentrates domain state and mutation logic into single points of failure."
                )
            )
            friction_points.append(f"Oversized multi-responsibility classes: {names}")

        # 2. Recognize Active Architectural Patterns
        class_names = [cls.name for m in archaeology.modules.values() for cls in m.classes]
        patterns_found = []
        if any("Factory" in n or "Builder" in n for n in class_names):
            patterns_found.append("Creational (Factory/Builder)")
        if any("Repository" in n or "Store" in n or "Dao" in n for n in class_names):
            patterns_found.append("Repository / Data Access")
        if any("Pipeline" in n or "Processor" in n or "Handler" in n for n in class_names):
            patterns_found.append("Pipeline / Chain of Responsibility")
        if any("Observer" in n or "Listener" in n or "Emitter" in n for n in class_names):
            patterns_found.append("Observer / Event-Driven")

        if patterns_found:
            insights.append(
                InvestigatorInsight(
                    category="ARCHITECTURAL_PATTERN_IN_USE",
                    observation=f"Codebase employs established design idioms: {', '.join(patterns_found)}",
                    evidence=f"Recognized pattern markers in class naming taxonomy.",
                    confidence=0.93,
                    implication="Future code changes should align with existing pattern conventions to maintain stylistic coherence."
                )
            )
        else:
            insights.append(
                InvestigatorInsight(
                    category="ARCHITECTURAL_PARADIGM_PROCEDURAL",
                    observation="Codebase relies on straightforward functional or procedural constructs.",
                    evidence="Minimal formal object-oriented design patterns detected.",
                    confidence=0.88,
                    implication="Simplicity is valued over speculative generality."
                )
            )

        core_hyp = (
            "The architectural idioms demonstrate a preference for direct object encapsulation, but boundaries "
            "between processing orchestration and domain entities have begun blurring."
        )

        dev_thought = (
            "Developers favored pragmatic encapsulation, initially placing related methods into the nearest existing "
            "class rather than introducing intermediate abstraction layers."
        )

        recommended = (
            "Introduce lightweight protocol or strategy interfaces to decouple business rules from execution harnesses "
            "without imposing heavy boilerplate."
        )

        return InvestigationFinding(
            investigator_role=self.role,
            investigator_name=self.name,
            specialization_lens=self.lens_description,
            core_hypothesis=core_hyp,
            insights=insights,
            friction_points=friction_points,
            developer_thought_model=dev_thought,
            recommended_action=recommended,
            metadata={"patterns": patterns_found, "god_classes_count": len(large_classes)},
        )
