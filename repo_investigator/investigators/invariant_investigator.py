from __future__ import annotations

from typing import List
from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.investigator_models import (
    InvestigationFinding,
    InvestigatorInsight,
    SpecialistRole,
)
from repo_investigator.investigators.base import BaseInvestigator

class InvariantsHazardsInvestigator(BaseInvestigator):
    def __init__(self, engine=None):
        super().__init__(
            role=SpecialistRole.INVARIANTS_HAZARDS,
            name="Seraphina Locke (Invariants & Resilience Sentinel)",
            lens_description="Domain invariants, state integrity, concurrency hazards, boundary leaks, and defensive resilience.",
            engine=engine,
        )

    def investigate(self, archaeology: RepoArchaeology) -> InvestigationFinding:
        insights: List[InvestigatorInsight] = []
        friction_points: List[str] = []

        # 1. Scrutinize Layer Boundaries and Direct State Mutations
        layer_leaks = []
        for file_path, mod in archaeology.modules.items():
            if "core" in file_path or "domain" in file_path:
                for imp in mod.imports:
                    if any(bad in imp for bad in ("db", "database", "sql", "api", "http", "view")):
                        layer_leaks.append((file_path, imp))

        if layer_leaks:
            leaks_desc = ", ".join(f"{l[0]} -> {l[1]}" for l in layer_leaks[:3])
            insights.append(
                InvestigatorInsight(
                    category="INVARIANT_LAYER_BOUNDARY_BREACH",
                    observation=f"Core domain layer leaks into infrastructure/storage: {leaks_desc}",
                    evidence="Direct external driver/adapter import in core domain module.",
                    confidence=0.97,
                    implication="Violates clean architectural separation of concerns; changes in persistence cascade directly into core rules."
                )
            )
            friction_points.append(f"Boundary breach: {leaks_desc}")

        # 2. Concurrency and Mutable Shared State Audit
        has_locks = False
        mutable_globals = False
        for mod in archaeology.modules.values():
            for fn in mod.functions:
                for call in fn.calls:
                    if "acquire" in call or "Lock" in call or "mutex" in call:
                        has_locks = True
            for cls in mod.classes:
                for m in cls.methods:
                    for call in m.calls:
                        if "acquire" in call or "Lock" in call or "mutex" in call:
                            has_locks = True

        if not has_locks and archaeology.architectural_signals.get("has_concurrency_markers", False):
            insights.append(
                InvestigatorInsight(
                    category="HAZARD_UNPROTECTED_ASYNC_STATE",
                    observation="Asynchronous execution detected without explicit locking or synchronization primitives.",
                    evidence="Async functions present without corresponding Lock or synchronization constructs.",
                    confidence=0.92,
                    implication="High risk of race conditions, torn reads, and state corruption under concurrent load."
                )
            )
            friction_points.append("Unprotected state across asynchronous execution pathways")
        else:
            insights.append(
                InvestigatorInsight(
                    category="INVARIANT_SYNCHRONOUS_SAFETY",
                    observation="Execution is contained within deterministic single-thread bounds or synchronous calls.",
                    evidence="No unsafe concurrent access patterns detected.",
                    confidence=0.90,
                    implication="State transitions are predictable; invariant enforcement is straightforward."
                )
            )

        core_hyp = (
            "The repository's core domain requires strict invariant preservation: state modifications must be "
            "atomic, and persistence details must never leak into the calculation engine."
        )

        dev_thought = (
            "Developers treated database and network layers as utilitarian tools to be imported wherever needed, "
            "prioritizing fast delivery over defensive isolation."
        )

        recommended = (
            "Establish hard invariant enforcement: mandate dependency inversion for persistence and ensure all state "
            "mutations pass through validated, immutable or guarded transactions."
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
            metadata={"layer_leaks_count": len(layer_leaks), "has_locks": has_locks},
        )
